import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon'
import ActivityOrb from '../components/ActivityOrb'
import { loadGoogleIdentity } from './google'
import type { AuthSession } from './context'

export default function GoogleSignIn({
  session,
  loading,
  signingIn,
  error,
  onCredential,
  onRetry,
}: {
  session: AuthSession | null
  loading: boolean
  signingIn: boolean
  error: string
  onCredential: (credential: string) => Promise<void>
  onRetry: () => void
}) {
  const target = useRef<HTMLDivElement>(null)
  const [scriptError, setScriptError] = useState('')
  const [buttonReady, setButtonReady] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const clientId = session?.google_client_id
  const nonce = session?.nonce
  useEffect(() => {
    if (!clientId || !nonce || !target.current) return
    const container = target.current
    let active = true
    let observer: ResizeObserver | undefined
    setButtonReady(false)
    setScriptError('')
    void loadGoogleIdentity()
      .then((google) => {
        if (!active) return
        google.initialize({
          client_id: clientId,
          nonce,
          auto_select: false,
          callback: ({ credential }) => {
            if (active) void onCredential(credential)
          },
        })
        let renderedWidth = 0
        const render = () => {
          const width = Math.max(
            200,
            Math.min(360, Math.floor(container.clientWidth)),
          )
          if (width === renderedWidth) return
          renderedWidth = width
          container.replaceChildren()
          google.renderButton(container, {
            theme: 'outline',
            size: 'large',
            shape: 'rectangular',
            width,
          })
        }
        render()
        observer = new ResizeObserver(render)
        observer.observe(container)
        setButtonReady(true)
      })
      .catch((failure: unknown) => {
        if (active)
          setScriptError(
            failure instanceof Error
              ? failure.message
              : 'Google sign-in could not load. Please retry.',
          )
      })
    return () => {
      active = false
      observer?.disconnect()
      container.replaceChildren()
    }
  }, [clientId, nonce, onCredential, attempt])

  const message = error || scriptError
  return (
    <div className="auth-shell">
      <header className="auth-header">
        <a className="brand" href="/" aria-label="RepoViva home">
          <span className="brand-mark">
            <Icon name="book" size={22} />
          </span>
          <span>
            RepoViva<span className="brand-period">.</span>
          </span>
        </a>
      </header>
      <main className="auth-layout">
        <div className="auth-introduction">
          <h1>
            <span>Know it.</span>
            <span>Explain it.</span>
          </h1>
          <p>
            Practice with questions built from your material. Answer in your own
            words, then check the evidence.
          </p>
        </div>
        <section className="auth-panel" aria-labelledby="sign-in-title">
          <Icon name="book" size={28} />
          <h2 id="sign-in-title">Your study desk awaits.</h2>
          <p>
            Sign in with Google to upload your material and start practicing.
          </p>
          <div
            className="google-sign-in"
            ref={target}
            inert={signingIn}
            aria-busy={signingIn}
          />
          {(loading ||
            signingIn ||
            (!!clientId && !buttonReady && !scriptError)) && (
            <p className="auth-status" role="status">
              <ActivityOrb state="connecting" />
              {signingIn
                ? 'Verifying your sign-in…'
                : loading
                  ? 'Checking your session…'
                  : 'Loading Google sign-in…'}
            </p>
          )}
          {message && (
            <p className="auth-error" role="alert">
              {message}
            </p>
          )}
          {!loading && !clientId && !error && (
            <p className="auth-error" role="status">
              Google sign-in isn’t available yet. Please try again later.
            </p>
          )}
          {(message || (!loading && !clientId)) && (
            <button
              type="button"
              className="button button-secondary"
              disabled={loading || signingIn}
              onClick={() => {
                setAttempt((value) => value + 1)
                onRetry()
              }}
            >
              Try again
            </button>
          )}
          <p className="auth-session-note">
            {session?.storage_mode === 'postgresql'
              ? 'Your uploaded material and submitted answers are saved to your Google account.'
              : 'Practice sessions are temporary. Your material and progress clear after an hour or a server restart.'}
          </p>
        </section>
      </main>
    </div>
  )
}
