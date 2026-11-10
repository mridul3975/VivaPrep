import { useEffect, useState } from 'react'
import { useAuth } from '../auth/context'
import { apiJson } from '../api'
import type { SourceDocument } from '../components/SourceUpload'
import ActivityOrb from '../components/ActivityOrb'
import Icon from '../components/Icon'

interface DocumentItem { id: string; filename: string; kind: string; last_opened_at: string; active: boolean; practice_count: number }
interface PracticeItem { id: string; source_id: string; created_at: string; questions: number; answered: number; score: number | null }
interface LibraryData { documents: DocumentItem[]; next_offset: number | null }
interface FileData { source_id: string; filename: string; kind: string; practice_sets: PracticeItem[]; next_offset: number | null }
interface DebugSummary { id: string; updated_at: string; complete: boolean; tests_passed: boolean }
const date = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export default function HistoryPage({ sourceId, onSelect, onOpen, onDeleted, beforeAction, onDebug }: {
  sourceId?: string; onSelect: (id: string) => void; onOpen: (source: SourceDocument) => void
  onDeleted: (ids: string[]) => void; beforeAction: () => Promise<void>
  onDebug: (id: string) => void
}) {
  const { apiFetch } = useAuth()
  const [data, setData] = useState<LibraryData | FileData | null>(null)
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [debugRuns, setDebugRuns] = useState<DebugSummary[]>([])
  const [debugError, setDebugError] = useState('')
  useEffect(() => {
    if (sourceId) return
    const controller = new AbortController()
    void apiFetch('/debug/runs', { signal: controller.signal }).then(apiJson<{ runs: DebugSummary[] }>).then(result => {
      if (!controller.signal.aborted) setDebugRuns(result.runs)
    }).catch(() => { if (!controller.signal.aborted) setDebugError('Debugging history could not be loaded. Open Debug to retry.') })
    return () => controller.abort()
  }, [apiFetch, sourceId])
  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true); setError('')
      const endpoint = sourceId ? `/history/documents/${encodeURIComponent(sourceId)}?offset=${offset}` : `/history/documents?q=${encodeURIComponent(query)}&offset=${offset}`
      void apiFetch(endpoint, { signal: controller.signal }).then(apiJson<LibraryData | FileData>).then(result => {
        if (!Array.isArray('documents' in result ? result.documents : result.practice_sets)) throw new Error('Saved history could not be read.')
        if (!controller.signal.aborted) setData(result)
      }).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load history.') })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, query ? 200 : 0)
    return () => { clearTimeout(timer); controller.abort() }
  }, [apiFetch, sourceId, query, offset, attempt])
  async function open(id: string, practiceId?: string, retry = false) {
    setBusy(true); setError('')
    try {
      await beforeAction()
      const endpoint = retry ? `/history/practice-sets/${encodeURIComponent(practiceId!)}/retry` : `/sources/${encodeURIComponent(id)}/activate`
      const document = await apiFetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(practiceId ? { practice_id: practiceId } : {}) }).then(apiJson<SourceDocument>)
      onOpen(document)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open saved material.') }
    finally { setBusy(false) }
  }
  async function remove() {
    if (!sourceId || !window.confirm('Permanently delete this material and all its saved questions, answers and scores? This cannot be undone.')) return
    setBusy(true); setError('')
    try {
      await beforeAction()
      const result = await apiFetch(`/history/documents/${encodeURIComponent(sourceId)}`, { method: 'DELETE' }).then(apiJson<{ deleted_ids: string[] }>)
      onDeleted(result.deleted_ids)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not delete this material.') }
    finally { setBusy(false) }
  }
  const files = data && 'documents' in data ? data.documents : null
  const file = data && 'practice_sets' in data ? data : null
  return <main className="workspace history-page" id="history-page" tabIndex={-1}>
    <div className="page-heading"><div><h1>{sourceId && file ? file.filename : 'History'}</h1><p>{sourceId ? 'Saved practice for this material.' : 'Your files, practice sets and results.'}</p></div>{file && <button className="button button-primary" disabled={busy} onClick={() => { void open(file.source_id) }}>Open material <Icon name="arrow" size={17} /></button>}</div>
    {!sourceId && <label className="history-search"><Icon name="search" size={18} /><input aria-label="Search saved files" placeholder="Search your files…" value={query} onChange={event => { setQuery(event.target.value); setOffset(0) }} /></label>}
    {loading && <p className="page-loading" role="status"><ActivityOrb state="searching" /> Loading history…</p>}
    {error && <div className="error-banner" role="alert"><Icon name="info" /><div><p>{error}</p><button type="button" className="text-button" onClick={() => setAttempt(value => value + 1)}>Try again</button></div></div>}
    {!loading && files && <div className="history-list">{files.length ? files.map(item => <button type="button" className="history-file" key={item.id} disabled={busy} onClick={() => onSelect(item.id)}><span className="document-icon"><Icon name="file" size={24} /></span><span className="history-file-title"><strong>{item.filename}</strong><span>{item.kind === 'pdf' ? 'PDF' : 'Source / text'} · {item.practice_count} {item.practice_count === 1 ? 'practice set' : 'practice sets'}</span></span><span className="history-file-date">{date(item.last_opened_at)}</span><Icon name="chevron" size={17} /></button>) : <div className="page-empty"><Icon name="history" size={30} /><h2>{query ? 'No matching files' : 'Your history starts here'}</h2><p>{query ? 'Try a different filename.' : 'Uploaded material and your practice will appear here.'}</p></div>}</div>}
    {!loading && file && <><div className="history-sets">{file.practice_sets.length ? file.practice_sets.map(item => <section className="history-set" key={item.id}><div><h2>{date(item.created_at)}</h2><p>{item.answered} / {item.questions} answered{item.answered < item.questions ? ' · In progress' : ' · Complete'}</p></div><div className="history-set-actions">{item.score !== null && <span className="history-score">{item.score}%</span>}<button className="button button-secondary" disabled={busy} onClick={() => { void open(item.source_id, item.id) }}>{item.answered < item.questions ? 'Resume' : 'Review'}<Icon name="arrow" size={16} /></button><button className="text-button" disabled={busy} onClick={() => { void open(item.source_id, item.id, true) }}>Practice again</button></div></section>) : <div className="page-empty"><h2>No practice sets yet</h2><p>Open this material to generate your first set.</p></div>}</div><div className="history-delete"><button className="text-button danger-button" disabled={busy} onClick={() => { void remove() }}>Delete permanently</button></div></>}
    {!loading && data && <div className="list-pagination">{offset > 0 && <button className="button button-secondary" disabled={busy} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button>}{data.next_offset !== null && <button className="button button-secondary" disabled={busy} onClick={() => setOffset(data.next_offset!)}>Next page <Icon name="arrow" size={16} /></button>}</div>}
    {!sourceId && !query && <section className="debug-saved"><h2>Debugging practice</h2>{debugError && <p className="inline-error">{debugError}</p>}{debugRuns.length ? <div className="history-list">{debugRuns.map(item => <button className="history-file" key={item.id} disabled={busy} onClick={() => onDebug(item.id)}><Icon name="code" size={22} /><span className="history-file-title"><strong>Recording duration</strong><span>{item.complete ? 'Tests passed · Explanation saved' : 'In progress'} · {date(item.updated_at)}</span></span><Icon name="arrow" size={17} /></button>)}</div> : !debugError && <p className="field-note">Start a debugging challenge from Debug.</p>}</section>}
  </main>
}
