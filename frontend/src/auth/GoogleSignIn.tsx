import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon'
import UiloraEffect from '../components/UiloraEffect'
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
  onGuest,
  enteringGuest = false,
  onCancel,
}: {
  session: AuthSession | null
  loading: boolean
  signingIn: boolean
  error: string
  onCredential: (credential: string) => Promise<void>
  onRetry: () => void
  onGuest?: () => Promise<void>
  enteringGuest?: boolean
  onCancel?: () => void
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
          <span className="brand-mark"><UiloraEffect variant="aurora" />
            <Icon name="book" size={22} />
          </span>
          <span>
            RepoViva<span className="brand-period">.</span>
          </span>
        </a>
      </header>
      <div className="auth-back-bar"><button type="button" className="text-button back-button" disabled={window.history.length <= 1} onClick={() => window.history.back()}><Icon name="arrow" size={17} className="rotate-180" />Back</button></div>
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
            {onCancel ? 'Sign in with Google to keep your guest work and get your account allowance.' : 'Try the Python example or upload your own material. No Google account needed for guest access.'}
          </p>
          {onGuest && <><button className="button button-primary guest-start" disabled={loading || signingIn || enteringGuest} onClick={() => { void onGuest() }}>{enteringGuest ? 'Opening guest session…' : 'Try as guest'}<Icon name="arrow" size={16} /></button><p className="guest-entry-note">Free prepared example · Your own files welcome · Limited AI allowance</p></>}
          <div
            className="google-sign-in"
            ref={target}
            inert={signingIn || enteringGuest}
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
              Google sign-in isn’t available yet. You can still try as a guest.
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
            {onCancel ? 'Your guest files and progress will move into your account.' : session?.storage_mode === 'postgresql'
              ? 'Guest work is temporary for up to 24 hours. Sign in with Google to keep it.'
              : 'Practice sessions are temporary. Your material and progress clear after an hour or a server restart.'}
          </p>
          {onCancel && <button className="text-button" disabled={signingIn} onClick={onCancel}>Continue as guest</button>}
        </section>
      </main>
    </div>
  )
}
