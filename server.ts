import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';

async function startServer() {
  const app = express();
  const PORT = Number(process.env.PORT) || 3000;
  const FASTAPI_TARGET = process.env.FASTAPI_INTERNAL_URL || 'http://127.0.0.1:8000';

  // Reverse proxy: forward everything under /api/* to the real FastAPI
  // backend. There is no mock fallback here — if FastAPI is unreachable,
  // the client gets a real 502 instead of silently-served fake data.
  app.use('/api', async (req, res) => {
    const targetPath = req.originalUrl.replace(/^\/api/, '') || '/';
    try {
      const headers: Record<string, string> = {};
      for (const [key, value] of Object.entries(req.headers)) {
        if (typeof value === 'string' && key.toLowerCase() !== 'host') {
          headers[key] = value;
        }
      }

      const chunks: Buffer[] = [];
      for await (const chunk of req) chunks.push(chunk as Buffer);
      const body = chunks.length ? Buffer.concat(chunks) : undefined;

      const upstream = await fetch(`${FASTAPI_TARGET}${targetPath}`, {
        method: req.method,
        headers,
        body: req.method !== 'GET' && req.method !== 'HEAD' ? body : undefined,
      });

      res.status(upstream.status);
      upstream.headers.forEach((value, key) => {
        if (key.toLowerCase() !== 'content-encoding') res.setHeader(key, value);
      });

      if (upstream.body) {
        const reader = upstream.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          res.write(value);
        }
      }
      res.end();
    } catch (err) {
      console.error(`[Proxy] FastAPI unreachable at ${FASTAPI_TARGET}${targetPath}:`, err);
      res.status(502).json({
        success: false,
        message: 'AquaMind API backend is unreachable. Confirm FastAPI is running.',
      });
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
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🚀 AquaMind AI Server is live!`);
    console.log(`   - Local Address:  http://localhost:${PORT}`);
    console.log(`   - Network Access: http://0.0.0.0:${PORT}`);
    console.log(`   - Proxying /api/* -> ${FASTAPI_TARGET}\n`);
  });
}

startServer();
