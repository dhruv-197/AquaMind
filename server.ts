import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { randomUUID } from 'crypto';

const PROXY_BODY_LIMIT_BYTES = 25 * 1024 * 1024; // 25 MB — covers vision uploads
const PROXY_UPSTREAM_TIMEOUT_MS = 60_000;
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'host',
]);

async function readBodyWithLimit(
  req: express.Request,
  limitBytes: number
): Promise<{ body?: Buffer; tooLarge?: boolean }> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = chunk as Buffer;
    total += buf.length;
    if (total > limitBytes) {
      // Drain remaining so the socket does not hang, then reject.
      for await (const _ of req) {
        /* discard */
      }
      return { tooLarge: true };
    }
    chunks.push(buf);
  }
  return { body: chunks.length ? Buffer.concat(chunks) : undefined };
}

function applySecurityHeaders(res: express.Response, req: express.Request) {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  const forwardedProto = String(req.headers['x-forwarded-proto'] || '')
    .split(',')[0]
    .trim();
  if (req.secure || forwardedProto === 'https') {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
}

async function startServer() {
  const app = express();
  const PORT = Number(process.env.PORT) || 3000;
  const FASTAPI_TARGET = process.env.FASTAPI_INTERNAL_URL || 'http://127.0.0.1:8000';

  app.disable('x-powered-by');

  app.use((req, res, next) => {
    applySecurityHeaders(res, req);
    next();
  });

  // Reverse proxy: forward everything under /api/* to the real FastAPI
  // backend. There is no mock fallback here — if FastAPI is unreachable,
  // the client gets a real 502 instead of silently-served fake data.
  // Host is never forwarded upstream (hop-by-hop), preventing Host spoofing
  // from influencing FastAPI absolute URL generation.
  app.use('/api', async (req, res) => {
    const requestId =
      (typeof req.headers['x-request-id'] === 'string' && req.headers['x-request-id']) ||
      randomUUID();
    const targetPath = req.originalUrl.replace(/^\/api/, '') || '/';
    const logCtx = `[Proxy ${requestId}] ${req.method} ${targetPath}`;

    const controller = new AbortController();
    const onClientClose = () => controller.abort();
    req.on('close', onClientClose);
    const timeout = setTimeout(() => controller.abort(), PROXY_UPSTREAM_TIMEOUT_MS);

    try {
      const headers: Record<string, string> = { 'x-request-id': requestId };
      for (const [key, value] of Object.entries(req.headers)) {
        const lower = key.toLowerCase();
        if (HOP_BY_HOP.has(lower)) continue;
        if (typeof value === 'string') headers[key] = value;
        else if (Array.isArray(value) && value[0]) headers[key] = value.join(', ');
      }

      let body: Buffer | undefined;
      if (req.method !== 'GET' && req.method !== 'HEAD') {
        const read = await readBodyWithLimit(req, PROXY_BODY_LIMIT_BYTES);
        if (read.tooLarge) {
          console.warn(`${logCtx} rejected: body exceeds ${PROXY_BODY_LIMIT_BYTES} bytes`);
          res.status(413).json({
            success: false,
            message: 'Request body too large.',
            request_id: requestId,
          });
          return;
        }
        body = read.body;
      }

      const upstream = await fetch(`${FASTAPI_TARGET}${targetPath}`, {
        method: req.method,
        headers,
        body,
        signal: controller.signal,
      });

      res.status(upstream.status);
      res.setHeader('x-request-id', requestId);
      upstream.headers.forEach((value, key) => {
        const lower = key.toLowerCase();
        if (lower === 'content-encoding' || lower === 'transfer-encoding') return;
        if (HOP_BY_HOP.has(lower)) return;
        res.setHeader(key, value);
      });

      if (upstream.body) {
        const reader = upstream.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (res.writableEnded) break;
          res.write(value);
        }
      }
      if (!res.writableEnded) res.end();
    } catch (err) {
      const aborted = controller.signal.aborted;
      console.error(
        `${logCtx} ${aborted ? 'timed out or aborted' : 'unreachable'} at ${FASTAPI_TARGET}${targetPath}:`,
        err instanceof Error ? err.message : err
      );
      if (res.headersSent) {
        res.end();
        return;
      }
      res.status(aborted ? 504 : 502).json({
        success: false,
        message: aborted
          ? 'AquaMind AI API timed out. Retry shortly.'
          : 'AquaMind AI API is unreachable. Confirm FastAPI is running on port 8000.',
        request_id: requestId,
      });
    } finally {
      clearTimeout(timeout);
      req.off('close', onClientClose);
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    // SPA CSP is looser than the API (needs scripts/styles from self).
    app.use((req, res, next) => {
      res.setHeader(
        'Content-Security-Policy',
        "default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
      );
      next();
    });
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`\nAquaMind AI Server is live!`);
    console.log(`   - Local Address:  http://localhost:${PORT}`);
    console.log(`   - Network Access: http://0.0.0.0:${PORT}`);
    console.log(`   - Proxying /api/* -> ${FASTAPI_TARGET}\n`);
  });
}

startServer();
