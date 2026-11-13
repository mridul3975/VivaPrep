import { useCallback, useEffect, useState } from 'react'

export type Page = 'study' | 'setup' | 'history' | 'profile' | 'debug' | 'incidents'
export interface Route { page: Page; sourceId?: string; runId?: string }

function readRoute(): Route {
  const parts = window.location.hash.replace(/^#\/?/, '').split('/')
  if (parts[0] === 'history') return { page: 'history', sourceId: parts[1] === 'file' ? parts[2] : undefined }
  if (parts[0] === 'debug') return { page: 'debug', runId: parts[1] === 'run' ? parts[2] : undefined }
  if (parts[0] === 'incidents') return { page: 'incidents', runId: parts[1] === 'run' ? parts[2] : undefined }
  if (parts[0] === 'profile' || parts[0] === 'setup') return { page: parts[0] }
  if (parts[0] === 'study') return { page: 'study' }
  return { page: 'setup' }
}

export function useNavigation() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [depth, setDepth] = useState(() => Number(window.history.state?.repovivaDepth) || 0)
  useEffect(() => {
    const changed = () => { setRoute(readRoute()); setDepth(Number(window.history.state?.repovivaDepth) || 0) }
    window.addEventListener('popstate', changed)
    window.addEventListener('hashchange', changed)
    return () => { window.removeEventListener('popstate', changed); window.removeEventListener('hashchange', changed) }
  }, [])
  const navigate = useCallback((next: Route) => {
    const hash = `#/${next.page}${next.sourceId ? `/file/${encodeURIComponent(next.sourceId)}` : next.runId ? `/run/${encodeURIComponent(next.runId)}` : ''}`
    if (hash !== window.location.hash) {
      const nextDepth = (Number(window.history.state?.repovivaDepth) || 0) + 1
      window.history.pushState({ repovivaDepth: nextDepth }, '', hash)
      setDepth(nextDepth)
    }
    setRoute(next)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [])
  const back = useCallback(() => {
    if (depth > 0) window.history.back()
    else navigate(route.sourceId ? { page: 'history' } : route.runId ? { page: route.page === 'incidents' ? 'incidents' : 'debug' } : { page: 'study' })
  }, [depth, navigate, route.page, route.sourceId, route.runId])
  return { route, navigate, back, depth }
}
