import { useEffect, useState } from 'react'
import { useAuth } from '../auth/context'
import { apiJson } from '../api'
import ActivityOrb from '../components/ActivityOrb'
import Icon from '../components/Icon'

type Action = 'questions' | 'answers' | 'transcriptions'
interface Details { display_name: string; institution: string; course: string; study_year: string }
interface Profile {
  name: string; email: string; details: Partial<Details>; joined_at: string | null; storage_mode: string
  usage: { reset_at: string; allowances: Record<Action, { limit: number; used: number; remaining: number }> }
}
const empty: Details = { display_name: '', institution: '', course: '', study_year: '' }
const fields: { key: keyof Details; label: string; limit: number; placeholder: string }[] = [
  { key: 'display_name', label: 'Display name', limit: 80, placeholder: 'Your name' },
  { key: 'institution', label: 'Institution', limit: 120, placeholder: 'College or university' },
  { key: 'course', label: 'Course', limit: 120, placeholder: 'What are you studying?' },
  { key: 'study_year', label: 'Year of study', limit: 40, placeholder: 'For example, second year' },
]
const actions: { key: Action; label: string }[] = [
  { key: 'questions', label: 'Question sets' }, { key: 'answers', label: 'Answer reviews' }, { key: 'transcriptions', label: 'Voice transcriptions' },
]

export default function ProfilePage() {
  const { apiFetch, user, beginSignIn } = useAuth()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [details, setDetails] = useState<Details>(empty)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void apiFetch('/profile', { signal: controller.signal }).then(apiJson<Profile>).then(data => {
      if (!data.usage?.allowances || (!data.email && !user.is_guest)) throw new Error('Profile details could not be read.')
      if (!controller.signal.aborted) { setProfile(data); setDetails({ ...empty, ...data.details, display_name: data.details.display_name || data.name }) }
    }).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load your profile.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [apiFetch, attempt, user.is_guest])
  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError(''); setNotice('')
    try {
      const result = await apiFetch('/profile', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(details) }).then(apiJson<Profile>)
      setProfile(result); setNotice('Profile saved.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save your profile.') }
    finally { setSaving(false) }
  }
  return (
    <main className="workspace account-page" id="profile-page" tabIndex={-1}>
      <div className="page-heading"><div><h1>Profile</h1><p>Your details and daily allowance.</p></div></div>
      {loading && <p className="page-loading" role="status"><ActivityOrb state="connecting" /> Loading profile…</p>}
      {error && <div className="error-banner" role="alert"><Icon name="info" /><div><p>{error}</p>{!profile && <button className="text-button" onClick={() => { setLoading(true); setError(''); setAttempt(value => value + 1) }}>Try again</button>}</div></div>}
      {profile && !loading && <div className="profile-grid">
        <section className="profile-panel" aria-labelledby="profile-details-heading">
          <div className="profile-identity"><span className="profile-avatar" aria-hidden="true">{(details.display_name || profile.name).trim().slice(0, 1).toUpperCase()}</span><div><h2 id="profile-details-heading">Your details</h2><p>{profile.email}</p></div></div>
          {user.is_guest ? <div className="guest-profile"><p>You are trying RepoViva without an email account. Your work belongs to this browser session and is temporary.</p><button className="button button-primary" onClick={beginSignIn}>Sign in with Google to keep it</button></div> : <form className="profile-form" onSubmit={save}>
            {fields.map(field => <label key={field.key}><span>{field.label}{field.key !== 'display_name' && <small>Optional</small>}</span><input name={field.key} value={details[field.key]} maxLength={field.limit} placeholder={field.placeholder} disabled={saving} onChange={event => { setDetails(previous => ({ ...previous, [field.key]: event.target.value })); setNotice('') }} /></label>)}
            <p className="field-note">Your sign-in email is managed by Google.</p>
            <div className="profile-save"><p role="status">{notice}</p><button className="button button-primary" disabled={saving}>{saving ? 'Saving…' : 'Save details'}</button></div>
          </form>}
        </section>
        <section className="profile-panel usage-panel" aria-labelledby="usage-heading">
          <h2 id="usage-heading">Daily allowance</h2>
          <p className="panel-description">{user.is_guest ? 'Guest AI uses for today. The prepared Python questions and source comparisons are free. Shared guest provider limits may also apply.' : 'Available uses for today.'}</p>
          <div className="usage-list">{actions.map(action => { const quota = profile.usage.allowances[action.key]; return <div className="usage-row" key={action.key}><div className="usage-topline"><h3>{action.label}</h3><p><strong>{quota.remaining}</strong><span> / {quota.limit} left</span></p></div><progress aria-label={`${action.label} used`} value={Math.min(quota.used, quota.limit)} max={quota.limit || 1} /><p className="usage-caption">{quota.used} used today{quota.remaining === 0 ? ' · Daily limit reached' : ''}</p></div> })}</div>
          <div className="usage-notes"><p>Resets {new Date(profile.usage.reset_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}.</p><p>Creating a debugging exercise uses one question-set allowance. Opening History, resuming exercises and running tests do not use this allowance. AI reviews of alternative debugging repairs use one answer-review allowance. Source comparisons and browser tests are free. Provider limits may apply separately.</p></div>
          {profile.storage_mode === 'memory' && <p className="inline-error">Temporary development storage: usage resets if the server restarts.</p>}
        </section>
      </div>}
    </main>
  )
}
