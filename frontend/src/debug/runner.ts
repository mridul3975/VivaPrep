/** Pure-JavaScript practice only. Learner code never executes in the app window. */
export interface DebugTest { id: string; name: string; args: unknown[]; expected: boolean }
export interface TestObservation { id: string; passed: boolean; actual: boolean | null; error: string }

const workerSource = `
self.onmessage = event => {
  self.onmessage = null;
  const port = event.ports[0];
  const send = port.postMessage.bind(port);
  const same = Object.is;
  const { code, tests } = event.data;
  let candidate, compileError = '';
  try {
    candidate = new Function('"use strict";\\n' + code + '\\n;return validateRecording;')();
    if (typeof candidate !== 'function') throw new Error('Define validateRecording as a function.');
  } catch (error) { compileError = String(error.message || error).slice(0, 160); }
  const results = [];
  for (const test of tests) {
    let actual = null, error = compileError;
    if (!error) {
      try {
        const value = candidate(...test.args);
        if (typeof value !== 'boolean') error = 'Return a boolean (true or false).';
        else actual = value;
      } catch (failure) { error = String(failure.message || failure).slice(0, 160); }
    }
    results.push({ id: test.id, actual, error, passed: !error && same(actual, test.expected) });
  }
  send(results);
};`

export function runInSandbox(code: string, tests: DebugTest[], signal?: AbortSignal): Promise<TestObservation[]> {
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
          worker.postMessage({code:event.data.code,tests:event.data.tests}, [channel.port2]);
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
      if (event.data.ready) { frame.contentWindow?.postMessage({ token, code, tests }, '*'); return }
      if (event.data.error) { finish(undefined, new Error(event.data.error)); return }
      const rows = event.data.results
      if (!Array.isArray(rows) || rows.length !== tests.length || !rows.every((row, index) => row.id === tests[index].id && typeof row.passed === 'boolean' && (row.actual === null || typeof row.actual === 'boolean') && typeof row.error === 'string')) {
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
