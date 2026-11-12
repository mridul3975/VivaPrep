import { useCallback, useEffect, useState } from 'react'
import { bootstrapGet } from './connection'

type Connection = { ready: boolean; error: string; incompatible: boolean }
export default function useBackendConnection() {
  const [connection, setConnection] = useState<Connection>({ ready: false, error: '', incompatible: false })
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => setAttempt(value => value + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    let timer: number | undefined
    let checking = false
    let healthy = false
    let incompatible = false
    async function check() {
      if (checking || healthy || incompatible || controller.signal.aborted) return
      if (document.hidden) {
        timer = window.setTimeout(check, 30_000)
        return
      }
      checking = true
      window.clearTimeout(timer)
      try {
        const response = await bootstrapGet('/health', controller.signal)
        const data = await response.json().catch(() => null)
        if (controller.signal.aborted) return
        if (response.ok && data?.api_version && data.api_version !== 'study-v2') {
          incompatible = true
          setConnection({ ready: false, incompatible: true, error: 'This page and the service are different versions. Save your work, then reload this page.' })
        } else if (response.ok && data?.api_version === 'study-v2' && data.status === 'ok') {
          healthy = true
          setConnection({ ready: true, error: '', incompatible: false })
        } else {
          setConnection({ ready: false, incompatible: false, error: data?.error_code === 'database_unavailable'
            ? 'Saved practice is temporarily unavailable. We’ll reconnect automatically. Keep this page open.'
            : 'The service is taking longer to respond. We’ll reconnect automatically. Keep this page open.' })
        }
      } catch {
        if (!controller.signal.aborted) setConnection({ ready: false, incompatible: false, error: 'Connection interrupted. Check your internet connection; we’ll retry automatically.' })
      } finally {
        checking = false
        if (!healthy && !incompatible && !controller.signal.aborted) timer = window.setTimeout(check, 30_000)
      }
    }
    const reconnect = () => { if (!document.hidden) void check() }
    const lost = () => { healthy = false; void check() }
    void check()
    window.addEventListener('online', reconnect)
    window.addEventListener('focus', reconnect)
    document.addEventListener('visibilitychange', reconnect)
    window.addEventListener('repoviva-connection-lost', lost)
    return () => {
      controller.abort(); window.clearTimeout(timer)
      window.removeEventListener('online', reconnect); window.removeEventListener('focus', reconnect)
      document.removeEventListener('visibilitychange', reconnect); window.removeEventListener('repoviva-connection-lost', lost)
    }
  }, [attempt])
  return { backendReady: connection.ready, backendError: connection.error, incompatible: connection.incompatible, retryBackend: retry }
}
