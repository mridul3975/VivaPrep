// Exercise Vite's real proxy routing without touching the app database or port 5000.
import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer, loadConfigFromFile } from 'vite'

const root = fileURLToPath(new URL('../', import.meta.url))
const cacheDir = await mkdtemp(join(tmpdir(), 'repoviva-proxy-cache-'))
const backend = createHttpServer((request, response) => {
  response.writeHead(418, { 'Content-Type': 'application/json', 'X-Proxy-Regression': 'backend' })
  response.end(JSON.stringify({ path: request.url, method: request.method }))
})
await new Promise(resolve => backend.listen(0, '127.0.0.1', resolve))
let vite
try {
  const loaded = await loadConfigFromFile({ command: 'serve', mode: 'development' }, `${root}/vite.config.ts`)
  assert(loaded, 'Vite configuration must load')
  const target = `http://127.0.0.1:${backend.address().port}`
  // Keep the configured route keys; substitute only a disposable backend target.
  const proxy = Object.fromEntries(Object.entries(loaded.config.server?.proxy ?? {}).map(([key, value]) => [key, typeof value === 'string' ? target : { ...value, target }]))
  vite = await createServer({ ...loaded.config, configFile: false, root, cacheDir, logLevel: 'error', server: { ...loaded.config.server, host: '127.0.0.1', port: 0, open: false, hmr: false, proxy } })
  await vite.listen()
  const origin = `http://127.0.0.1:${vite.httpServer.address().port}`
  for (const [method, path] of [
    ['GET', '/auth/session'], ['GET', '/health'], ['POST', '/sources'],
    ['POST', '/questions'], ['POST', '/answers'], ['POST', '/transcriptions'],
    ['POST', '/retrieve'], ['GET', '/profile'], ['PATCH', '/profile'],
    ['GET', '/history/documents'], ['PUT', '/history/turns/example/draft'],
    ['GET', '/debug/challenges'], ['POST', '/debug/runs'],
  ]) {
    const response = await fetch(origin + path, { method })
    assert.equal(response.headers.get('X-Proxy-Regression'), 'backend', `${method} ${path} must reach Flask instead of Vite's HTML fallback`)
    assert.equal(response.status, 418, `${method} ${path} must preserve the backend status`)
    assert.deepEqual(await response.json(), { path, method })
    console.log(`PASS ${method} ${path}`)
  }
  console.log('All 13 development proxy requests reached the backend.')
} finally {
  await vite?.close()
  await new Promise(resolve => backend.close(resolve))
  assert.equal(dirname(resolve(cacheDir)), resolve(tmpdir()))
  assert(basename(cacheDir).startsWith('repoviva-proxy-cache-'))
  await rm(cacheDir, { recursive: true, force: true })
}
