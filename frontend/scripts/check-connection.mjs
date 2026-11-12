import assert from 'node:assert/strict'
import { bootstrapGet } from '../src/connection.ts'
const originalFetch = globalThis.fetch, originalTimer = globalThis.setTimeout
globalThis.setTimeout = (fn, _ms, ...args) => originalTimer(fn, 0, ...args)
const json = (status, body = {}) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
try {
  let calls = 0
  globalThis.fetch = async (_path, init) => { assert(!init.method || init.method === 'GET'); return ++calls < 3 ? json(503) : json(200) }
  assert.equal((await bootstrapGet('/health', new AbortController().signal)).status, 200); assert.equal(calls, 3)
  calls = 0
  globalThis.fetch = async () => ++calls === 1 ? new Response('<html>Starting</html>', { headers: { 'content-type': 'text/html' } }) : json(200)
  assert.equal((await bootstrapGet('/auth/session', new AbortController().signal)).status, 200); assert.equal(calls, 2)
  calls = 0
  globalThis.fetch = async () => { if (++calls === 1) throw new DOMException('Slow start', 'TimeoutError'); return json(200) }
  assert.equal((await bootstrapGet('/health', new AbortController().signal)).status, 200); assert.equal(calls, 2)
  calls = 0
  globalThis.fetch = async () => { calls++; return json(503) }
  assert.equal((await bootstrapGet('/health', new AbortController().signal)).status, 503); assert.equal(calls, 3)
  calls = 0
  globalThis.fetch = async () => { calls++; return json(401) }
  assert.equal((await bootstrapGet('/auth/session', new AbortController().signal)).status, 401); assert.equal(calls, 1)
  const controller = new AbortController(); controller.abort(); calls = 0
  await assert.rejects(bootstrapGet('/health', controller.signal)); assert.equal(calls, 0)
  console.log('Bootstrap GET recovery passed: transient 503, wake-up HTML, timeout, bounded attempts, terminal 401 and cancellation. No mutation replay.')
} finally { globalThis.fetch = originalFetch; globalThis.setTimeout = originalTimer }
