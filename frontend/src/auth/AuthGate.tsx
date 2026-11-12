import { useCallback, useEffect, useRef, useState } from 'react'
import App from '../App'
import GoogleSignIn from './GoogleSignIn'
import { AuthContext, type AuthSession } from './context'

// A suspended cloud database can take longer to connect than a local database.
const AUTH_REQUEST_TIMEOUT_MS = 30_000

async function readSession(response: Response): Promise<AuthSession> {
  const data = await response.json()
  if (!response.ok)
    throw new Error(
      typeof data?.error === 'string'
        ? data.error
        : 'Could not check your session. Please retry.',
    )
  if (
    typeof data?.csrf_token !== 'string' ||
    typeof data?.nonce !== 'string' ||
    !(
      data.google_client_id === null ||
      typeof data.google_client_id === 'string'
    ) ||
    !(
      data.user === null ||
      (typeof data.user?.id === 'string' &&
        typeof data.user?.email === 'string' &&
        typeof data.user?.name === 'string' &&
        Number.isFinite(data.expires_at))
    )
  ) {
    throw new Error('The server returned an unreadable session. Please reload.')
  }
  return data as AuthSession
}

function requestSession(signal = AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS)) {
  return fetch('/auth/session', {
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  }).then(readSession)
}

export default function AuthGate() {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [signingIn, setSigningIn] = useState(false)
  const [error, setError] = useState('')
  const [enteringGuest, setEnteringGuest] = useState(false)
  const [upgrading, setUpgrading] = useState(false)
  const authGeneration = useRef(0)
  const currentUserId = useRef<string | null>(null)
  const signInPending = useRef(false)

  const applySession = useCallback((result: AuthSession) => {
    currentUserId.current = result.user?.id ?? null
    setSession(result)
  }, [])

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const generation = authGeneration.current
      const result = await requestSession(signal)
      if (!signal?.aborted && generation === authGeneration.current) {
        if (currentUserId.current && !result.user) {
          setError('Your sign-in session ended. Sign in with Google again.')
        }
        applySession(result)
      }
      return result
    },
    [applySession],
  )

  const reload = useCallback(() => {
    setLoading(true)
    setError('')
    void refresh()
      .catch(() => setError('Could not connect to sign-in. Please retry.'))
      .finally(() => setLoading(false))
  }, [refresh])

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const generation = authGeneration.current
    const timeout = window.setTimeout(() => controller.abort(), AUTH_REQUEST_TIMEOUT_MS)
    void requestSession(controller.signal)
      .then((result) => {
        if (active && generation === authGeneration.current)
          applySession(result)
      })
      .catch(() => {
        if (active) setError('Could not connect to sign-in. Please retry.')
      })
      .finally(() => {
        if (active) {
          setLoading(false)
          window.clearTimeout(timeout)
        }
      })
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [applySession])

  const userId = session?.user?.id
  const expiresAt = session?.expires_at
  const expiresIn = session?.expires_in_seconds
  useEffect(() => {
    if (!userId || !expiresAt) return
    const expire = () => {
      currentUserId.current = null
      setSession(null)
      void refresh()
        .catch(() => {})
        .finally(() =>
          setError('Your session expired. Continue as guest or sign in again.'),
        )
    }
    const timer = window.setTimeout(
      expire,
      typeof expiresIn === 'number' && Number.isFinite(expiresIn)
        ? Math.max(0, expiresIn * 1000)
        : Math.max(0, expiresAt * 1000 - Date.now()),
    )
    const onFocus = () => {
      void refresh().catch(() => {
        /* Existing session remains usable during a brief network failure. */
      })
    }
    window.addEventListener('focus', onFocus)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [userId, expiresAt, expiresIn, refresh])

  const csrfToken = session?.csrf_token
  const signIn = useCallback(
    async (credential: string) => {
      if (!csrfToken || signInPending.current) return
      signInPending.current = true
      const generation = ++authGeneration.current
      setSigningIn(true)
      setError('')
      try {
        const response = await fetch('/auth/google', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify({ credential }),
          signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS),
        })
        const accepted = await readSession(response)
        if (!accepted.user) {
          throw new Error(
            'Google sign-in did not open an app session. Please try again.',
          )
        }
        // A 200 alone does not prove the browser retained the session cookie.
        const confirmed = await requestSession()
        if (confirmed.user?.id !== accepted.user.id) {
          throw new Error(
            'Google verified your account, but your app session ended. Reload the page and sign in again.',
          )
        }
        if (generation === authGeneration.current) {
          ++authGeneration.current
          applySession(confirmed)
          setUpgrading(false)
        }
      } catch (failure) {
        setError(
          failure instanceof Error &&
            failure.name !== 'TimeoutError' &&
            !(failure instanceof TypeError)
            ? failure.message
            : 'Could not finish signing in. Please retry.',
        )
        // Renew the nonce and CSRF data if another tab signed in or out.
        await refresh().catch(() => {})
      } finally {
        signInPending.current = false
        setSigningIn(false)
      }
    },
    [csrfToken, refresh, applySession],
  )

  const apiFetch = useCallback(
    async (path: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers)
      if (
        !['GET', 'HEAD', 'OPTIONS'].includes(
          (init.method ?? 'GET').toUpperCase(),
        ) &&
        csrfToken
      )
        headers.set('X-CSRF-Token', csrfToken)
      const response = await fetch(path, {
        ...init,
        headers,
        credentials: 'same-origin',
      })
      if ((init.method ?? 'GET').toUpperCase() !== 'GET' && /^\/(questions|answers|transcriptions|debug\/runs|viva\/turns)/.test(path)) window.dispatchEvent(new Event('repoviva-usage-changed'))
      if (
        response.status === 401 ||
        (response.status === 403 && response.headers.get('X-RepoViva-API'))
      )
        await refresh().catch(() => {})
      return response
    },
    [csrfToken, refresh],
  )

  const signOut = useCallback(async () => {
    ++authGeneration.current
    const response = await fetch('/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': csrfToken ?? '' },
      signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS),
    })
    const result = await readSession(response)
    window.google?.accounts.id.disableAutoSelect()
    ++authGeneration.current
    applySession(result)
    setUpgrading(false)
    setError('')
  }, [csrfToken, applySession])

  async function startGuest() {
    if (!csrfToken || signInPending.current) return
    signInPending.current = true; setEnteringGuest(true); setError('')
    const generation = ++authGeneration.current
    try {
      const response = await fetch('/auth/guest', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrfToken }, signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS) })
      const accepted = await readSession(response)
      const confirmed = await requestSession()
      if (!accepted.user || confirmed.user?.id !== accepted.user.id) throw new Error('Your guest session could not be kept. Enable cookies and retry.')
      if (generation === authGeneration.current) { ++authGeneration.current; applySession(confirmed) }
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open guest access. Retry.'); await refresh().catch(() => {}) }
    finally { signInPending.current = false; setEnteringGuest(false) }
  }

  if (!session?.user)
    return (
      <GoogleSignIn
        session={session}
        loading={loading}
        signingIn={signingIn}
        error={error}
        onCredential={signIn}
        onRetry={reload}
        onGuest={startGuest}
        enteringGuest={enteringGuest}
      />
    )
  return (
    <AuthContext.Provider
      value={{
        user: session.user,
        storageMode: session.storage_mode ?? 'memory',
        apiFetch,
        signOut,
        beginSignIn: () => { setError(''); setUpgrading(true) },
      }}
    >
      <div hidden={upgrading}><App key={session.user.id} /></div>
      {upgrading && <GoogleSignIn session={session} loading={false} signingIn={signingIn} error={error} onCredential={signIn} onRetry={reload} onCancel={() => setUpgrading(false)} />}
    </AuthContext.Provider>
  )
}
