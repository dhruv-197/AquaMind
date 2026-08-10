/**
 * Tests for request cancellation and deadlines in the shared API client.
 *
 * Run with: npm run test:dashboard  (node's test runner via tsx)
 */
import assert from 'node:assert/strict';
import test, { beforeEach, describe } from 'node:test';

import { ApiError, apiGet, isAbortError, isTimeoutError } from './apiClient';

type FetchCall = { url: string; init: RequestInit };

const calls: FetchCall[] = [];

/** A fetch that never resolves until its signal aborts, like the real one. */
function hangingFetch(): typeof fetch {
  return ((url: string, init: RequestInit) => {
    calls.push({ url, init });
    const abortError = () => new DOMException('The operation was aborted.', 'AbortError');
    if (init.signal?.aborted) return Promise.reject(abortError());
    return new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(abortError()));
    });
  }) as unknown as typeof fetch;
}

function jsonFetch(body: unknown): typeof fetch {
  return ((url: string, init: RequestInit) => {
    calls.push({ url, init });
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    } as Response);
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  calls.length = 0;
  (globalThis as any).localStorage = {
    getItem: () => null,
    removeItem: () => {},
    setItem: () => {},
  };
});

describe('apiClient deadlines and cancellation', () => {
  test('a request without timeoutMs keeps its existing unbounded behaviour', async () => {
    (globalThis as any).fetch = jsonFetch({ ok: true });

    await apiGet('/weather');

    assert.equal(calls.length, 1);
    assert.equal(calls[0].init.signal, undefined, 'no deadline should mean no injected signal');
  });

  test('timeoutMs aborts the request and surfaces a typed timeout error', async () => {
    (globalThis as any).fetch = hangingFetch();

    const error = await apiGet('/analytics/water-stress', { timeoutMs: 20 }).catch((e) => e);

    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, 'timeout');
    assert.equal(isTimeoutError(error), true);
    // A deadline is not a user cancellation: the panel should show the failure.
    assert.equal(isAbortError(error), false);
  });

  test('a caller abort produces an error the dashboard silently drops', async () => {
    (globalThis as any).fetch = hangingFetch();
    const controller = new AbortController();

    const pending = apiGet('/analytics/leakages', {
      signal: controller.signal,
      timeoutMs: 10_000,
    }).catch((e) => e);
    controller.abort(new ApiError('Superseded by a newer dashboard refresh', 'aborted'));

    const error = await pending;
    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, 'aborted');
    assert.equal(isAbortError(error), true);
  });

  test('the caller signal is forwarded even when a deadline is layered on top', async () => {
    (globalThis as any).fetch = jsonFetch({ ok: true });
    const controller = new AbortController();

    await apiGet('/telemetry/sensors', { signal: controller.signal, timeoutMs: 10_000 });

    assert.ok(calls[0].init.signal, 'fetch must receive a signal');
    assert.notEqual(calls[0].init.signal, controller.signal, 'deadline wraps the caller signal');
  });

  test('an already-aborted caller signal never reaches the network as a live request', async () => {
    (globalThis as any).fetch = hangingFetch();
    const controller = new AbortController();
    controller.abort(new ApiError('Dashboard unmounted', 'aborted'));

    const error = await apiGet('/weather', {
      signal: controller.signal,
      timeoutMs: 10_000,
    }).catch((e) => e);

    assert.equal(isAbortError(error), true);
  });

  test('timeoutMs is not leaked into the fetch options', async () => {
    (globalThis as any).fetch = jsonFetch({ ok: true });

    await apiGet('/weather', { timeoutMs: 10_000 });

    assert.equal((calls[0].init as any).timeoutMs, undefined);
  });

  test('non-JSON HTTP errors still surface a usable message', async () => {
    (globalThis as any).fetch = ((url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error('not json')),
      } as Response);
    }) as unknown as typeof fetch;

    const error = await apiGet('/telemetry/sensors').catch((e) => e);
    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, 'http');
    assert.equal(error.status, 502);
    assert.match(error.message, /502/);
  });

  test('401 on /login does not redirect-loop', async () => {
    const assigns: string[] = [];
    (globalThis as any).window = {
      location: {
        pathname: '/login',
        assign: (url: string) => assigns.push(url),
      },
    };
    (globalThis as any).fetch = ((url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'expired' }),
      } as Response);
    }) as unknown as typeof fetch;

    const error = await apiGet('/telemetry/sensors').catch((e) => e);
    assert.ok(error instanceof ApiError);
    assert.equal(error.kind, 'unauthorized');
    assert.deepEqual(assigns, []);
  });
});

/**
 * The executive report modal clears its spinner on every outcome except an
 * abort, where a newer request has taken ownership of the loading flag. So the
 * modal can only get stuck if some *other* failure were classified as an abort.
 */
describe('executive report request outcomes', () => {
  const REPORT_PATH = '/ai/recommendation-engine/live?force_refresh=false';

  test('a backend fallback payload resolves the request normally', async () => {
    (globalThis as any).fetch = jsonFetch({
      data: {
        recommendations: ['Trim municipal supply by 10%.'],
        expected_saving: '0.4 Million Liters',
        text_summary: 'Rules synthesis.',
        source: 'rules_fallback',
        provider: 'local-rules',
      },
    });

    const body = await apiGet<any>(REPORT_PATH, { timeoutMs: 30_000 });

    assert.equal(body.data.source, 'rules_fallback');
    assert.ok(body.data.recommendations.length > 0, 'the modal had no actions to render');
  });

  test('every non-cancellation failure is reported rather than silently dropped', async () => {
    const failures: typeof fetch[] = [
      // Backend down.
      (() => Promise.reject(new TypeError('Failed to fetch'))) as unknown as typeof fetch,
      // Backend up, synthesis blew up.
      (() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Live recommendation synthesis failed' }),
        } as Response)) as unknown as typeof fetch,
    ];

    for (const failure of failures) {
      (globalThis as any).fetch = failure;
      const error = await apiGet(REPORT_PATH, { timeoutMs: 30_000 }).catch((e) => e);
      assert.ok(error instanceof ApiError);
      assert.equal(isAbortError(error), false, `${error.kind} must not read as a cancellation`);
    }

    // A hung backend must also surface, so the deadline ends the spinner.
    (globalThis as any).fetch = hangingFetch();
    const timedOut = await apiGet(REPORT_PATH, { timeoutMs: 20 }).catch((e) => e);
    assert.equal(isTimeoutError(timedOut), true);
    assert.equal(isAbortError(timedOut), false);
  });
});
