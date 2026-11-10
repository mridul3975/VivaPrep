/** Pure-JavaScript practice only. Learner code never executes in the app window. */
export interface DebugTest { id: string; name: string; args: unknown[]; expected: unknown }
export interface TestObservation { id: string; passed: boolean; actual: unknown; error: string }

const workerSource = `
self.onmessage = event => {
  self.onmessage = null;
  const port = event.ports[0];
  const send = port.postMessage.bind(port);
  const stringify = JSON.stringify;
  const parse = JSON.parse;
  const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  const { code, tests, functionName } = event.data;
  let candidate, compileError = '';
  try {
    if (!/^[A-Za-z_$][A-Za-z0-9_$]{0,79}$/.test(functionName)) throw new Error('Invalid test function name.');
    const source = code.replace(/\\bexport\\s+default\\s+(?=(?:async\\s+)?function\\b)/g, '').replace(/\\bexport\\s+(?=(?:async\\s+)?function\\b|const\\b|let\\b|var\\b)/g, '');
    candidate = new Function('"use strict";\\n' + source + '\\n;return ' + functionName + ';')();
    if (typeof candidate !== 'function') throw new Error('Define ' + functionName + ' as a function.');
  } catch (error) { compileError = String(error.message || error).slice(0, 160); }
  const results = [];
  for (const test of tests) {
    let actual = null, error = compileError;
    if (!error) {
      try {
        const value = candidate(...test.args);
        if (value === undefined || (value && typeof value.then === 'function')) throw new Error('Return a synchronous JSON value.');
        const encoded = stringify(value, (_key, entry) => {
          if (typeof entry === 'undefined' || typeof entry === 'function' || typeof entry === 'symbol' || (typeof entry === 'number' && !Number.isFinite(entry))) throw new Error('Return finite JSON values.');
          return entry;
        });
        if (!encoded || encoded.length > 4000) throw new Error('Return a JSON value under 4,000 characters.');
        actual = parse(encoded);
      } catch (failure) { error = String(failure.message || failure).slice(0, 160); }
    }
    results.push({ id: test.id, actual, error, passed: !error && stringify(canonical(actual)) === stringify(canonical(test.expected)) });
  }
  send(results);
};`

export function runInSandbox(code: string, tests: DebugTest[], signal?: AbortSignal, functionName = 'validateRecording'): Promise<TestObservation[]> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('Cancelled', 'AbortError')); return }
    const frame = document.createElement('iframe')
    const token = crypto.randomUUID()
    frame.hidden = true
    frame.title = 'Isolated debugging test runner'
    frame.setAttribute('sandbox', 'allow-scripts')
    frame.setAttribute('allow', "camera 'none'; microphone 'none'; geolocation 'none'")
    // No learner text is interpolated into HTML. It arrives by structured clone.
    frame.srcdoc = `<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; worker-src blob:; connect-src 'none'; form-action 'none'; base-uri 'none'"><script>
      (() => {
        const token = ${JSON.stringify(token)};
        let worker;
        addEventListener('message', event => {
          if (event.source !== parent || event.data?.token !== token) return;
          if (event.data.cancel) { worker?.terminate(); return; }
          if (worker) return;
          const url = URL.createObjectURL(new Blob([${JSON.stringify(workerSource)}], {type:'text/javascript'}));
          worker = new Worker(url);
          URL.revokeObjectURL(url);
          const channel = new MessageChannel();
          channel.port1.onmessage = result => {
            parent.postMessage({token, results:result.data}, '*');
            channel.port1.close(); worker.terminate();
          };
          worker.onerror = () => { parent.postMessage({token,error:'The test runner failed. Check your syntax and retry.'}, '*'); worker.terminate(); };
          worker.postMessage({code:event.data.code,tests:event.data.tests,functionName:event.data.functionName}, [channel.port2]);
        });
        parent.postMessage({token,ready:true}, '*');
      })();
    </script>`
    let settled = false
    const finish = (results?: TestObservation[], error?: Error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      window.removeEventListener('message', receive)
      signal?.removeEventListener('abort', cancel)
      frame.contentWindow?.postMessage({ token, cancel: true }, '*')
      frame.remove()
      if (error) reject(error)
      else resolve(results!)
    }
    const cancel = () => finish(undefined, new DOMException('Cancelled', 'AbortError'))
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.contentWindow || event.data?.token !== token) return
      if (event.data.ready) { frame.contentWindow?.postMessage({ token, code, tests, functionName }, '*'); return }
      if (event.data.error) { finish(undefined, new Error(event.data.error)); return }
      const rows = event.data.results
      if (!Array.isArray(rows) || rows.length !== tests.length || !rows.every((row, index) => row.id === tests[index].id && typeof row.passed === 'boolean' && 'actual' in row && typeof row.error === 'string')) {
        finish(undefined, new Error('The runner returned invalid results. Retry the tests.')); return
      }
      finish(rows)
    }
    const timer = window.setTimeout(() => finish(tests.map(test => ({ id: test.id, passed: false, actual: null, error: 'Execution stopped after 3 seconds. Check for an infinite loop.' }))), 3000)
    window.addEventListener('message', receive)
    signal?.addEventListener('abort', cancel, { once: true })
    document.body.append(frame)
  })
}
