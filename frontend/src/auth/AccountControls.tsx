import { useState } from 'react'
import { useAuth } from './context'

export default function AccountControls() {
  const { user, signOut } = useAuth()
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
          {user.email}
        </span>
        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={() => {
            void logout()
          }}
        >
          {busy ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
      {error && (
        <span className="account-error" role="alert">
          {error}
        </span>
      )}
    </div>
  )
}
