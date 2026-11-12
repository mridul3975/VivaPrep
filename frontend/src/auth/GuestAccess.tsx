import { useEffect, useState } from 'react'
import { useAuth } from './context'
import { apiJson } from '../api'

interface Usage { usage: { allowances: Record<'questions' | 'answers' | 'transcriptions', { remaining: number }> } }
export default function GuestAccess({ beforeSignIn, disabled }: { beforeSignIn: () => Promise<void>; disabled: boolean }) {
  const { user, apiFetch, beginSignIn } = useAuth()
  const [usage, setUsage] = useState<Usage | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!user.is_guest) return
    let active = true
    const load = () => { void apiFetch('/profile').then(apiJson<Usage>).then(data => { if (active) setUsage(data) }).catch(() => {}) }
    load(); window.addEventListener('repoviva-usage-changed', load)
    return () => { active = false; window.removeEventListener('repoviva-usage-changed', load) }
  }, [apiFetch, user.is_guest])
  if (!user.is_guest) return null
  return <aside className="guest-access" aria-label="Guest access"><div><strong>Guest session</strong><span>{usage ? `${usage.usage.allowances.questions.remaining} AI set · ${usage.usage.allowances.answers.remaining} reviews · ${usage.usage.allowances.transcriptions.remaining} transcription left` : 'Small AI allowance · Free Python example'}</span><p>Try the Python example or upload your own file. Prepared questions are free; AI feedback uses your review allowance. Guest work is temporary.</p>{error && <p role="alert">{error}</p>}</div><button className="text-button" disabled={disabled} onClick={() => { void beforeSignIn().then(beginSignIn).catch(() => setError('Save your current work before signing in.')) }}>Sign in to keep your work<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 12h16m-6-6 6 6-6 6" /></svg></button></aside>
}
