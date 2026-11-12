// Only safe bootstrap GETs are retried. Never replay uploads, answers or AI calls.
export async function bootstrapGet(path: string, signal: AbortSignal) {
  for (let attempt = 0; ; attempt++) {
    signal.throwIfAborted()
    try {
      const response = await fetch(path, {
        credentials: 'same-origin', cache: 'no-store',
        signal: AbortSignal.any([signal, AbortSignal.timeout(25_000)]),
      })
      const temporary = [408, 502, 503, 504].includes(response.status) || (response.ok && !response.headers.get('content-type')?.includes('application/json'))
      if (!temporary || attempt === 2) return response
      await response.body?.cancel()
    } catch (failure) {
      if (signal.aborted || attempt === 2) throw failure
    }
    await new Promise<void>((resolve, reject) => {
      const abort = () => { clearTimeout(timer); reject(signal.reason) }
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, (attempt + 1) * 1500)
      signal.addEventListener('abort', abort, { once: true })
      if (signal.aborted) abort()
    })
  }
}
