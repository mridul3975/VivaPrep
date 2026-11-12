import { useState } from 'react'
import { useAuth } from './context'

export default function AccountControls({ beforeSignIn, disabled = false }: { beforeSignIn?: () => Promise<void>; disabled?: boolean }) {
  const { user, signOut, beginSignIn } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function logout() {
    setBusy(true)
    setError('')
    try {
      await signOut()
    } catch {
      setError('Sign-out failed. Please retry.')
      setBusy(false)
    }
  }
  return (
    <div className="account-controls">
      <div className="account-actions">
        <span className="account-email" title={user.email}>
          {user.is_guest ? 'Guest' : user.email}
        </span>
        <button
          type="button"
          className="text-button"
          disabled={busy || disabled}
          onClick={() => {
            void logout()
          }}
        >
          {busy ? 'Signing out…' : user.is_guest ? 'End session' : 'Sign out'}
        </button>
        {user.is_guest && <button className="text-button" disabled={busy || disabled} onClick={() => { void (beforeSignIn?.() ?? Promise.resolve()).then(beginSignIn).catch(() => setError('Save your current work before signing in.')) }}>Sign in with Google</button>}
      </div>
      {error && (
        <span className="account-error" role="alert">
          {error}
        </span>
      )}
    </div>
  )
}
