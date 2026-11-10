import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/context'
import { apiJson } from '../api'
import Icon from '../components/Icon'
import ActivityOrb from '../components/ActivityOrb'
import VoiceRecorder, { type RecordingPhase } from '../components/VoiceRecorder'
import type { SourceDocument } from '../components/SourceUpload'
import { runInSandbox, type DebugTest, type TestObservation } from '../debug/runner'

interface Scenario { id: string; title: string; project: string; language: string; starter_code: string; tests: DebugTest[]; contract: string; provenance: string }
interface RunSummary { id: string; updated_at: string; complete: boolean; tests_passed: boolean }
interface DebugRun {
  id: string; code: string; hypothesis: string; explanation: string; hints: string[]; total_hints: number
  scenario: Scenario; complete: boolean; tests_passed: boolean; tests_current: boolean
  test_result?: { results: TestObservation[] }; context?: { filename: string; snippet: { content: string[]; start_line: number; end_line: number } }
}
type Draft = Pick<DebugRun, 'code' | 'hypothesis' | 'explanation'>
const date = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export default function DebugPage({ runId, source, onOpen, onBusyChange, onSaveHandler }: {
  runId?: string; source: SourceDocument | null; onOpen: (id: string) => void
  onBusyChange: (value: boolean) => void; onSaveHandler: (handler: (() => Promise<void>) | null) => void
}) {
  const { apiFetch } = useAuth()
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [run, setRun] = useState<DebugRun | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [baseline, setBaseline] = useState<TestObservation[] | null>(null)
  const [latest, setLatest] = useState<TestObservation[] | null>(null)
  const [testedCode, setTestedCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [recordingBusy, setRecordingBusy] = useState(false)
  const [voiceTarget, setVoiceTarget] = useState<'hypothesis' | 'explanation'>('hypothesis')
  const [includeSource, setIncludeSource] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [saveStatus, setSaveStatus] = useState('')
  const [attempt, setAttempt] = useState(0)
  const pending = useRef<{ value: Draft; dirty: boolean } | null>(null)
  const chain = useRef<Promise<void>>(Promise.resolve())
  const mounted = useRef(true)
  const runnerController = useRef<AbortController | null>(null)
  const busy = working || recordingBusy
  const save = useCallback(async () => {
    const item = pending.current
    if (!runId || !item?.dirty) return chain.current
    item.dirty = false
    const operation = chain.current.catch(() => {}).then(async () => {
      await apiFetch(`/debug/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item.value) }).then(apiJson<DebugRun>)
    })
    chain.current = operation
    try { await operation; if (mounted.current) setSaveStatus(pending.current?.dirty ? 'Unsaved changes' : 'Saved') }
    catch (failure) {
      if (pending.current === item) item.dirty = true
      if (mounted.current) setSaveStatus('Not saved. Retry before leaving.')
      throw failure
    }
  }, [apiFetch, runId])
  useEffect(() => { onSaveHandler(save); return () => onSaveHandler(null) }, [save, onSaveHandler])
  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false) }, [busy, onBusyChange])
  useEffect(() => {
    mounted.current = true
    const departing = () => {
      const item = pending.current
      if (runId && item?.dirty) void apiFetch(`/debug/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item.value) }).catch(() => {})
    }
    window.addEventListener('pagehide', departing)
    return () => { mounted.current = false; runnerController.current?.abort(); window.removeEventListener('pagehide', departing); departing() }
  }, [apiFetch, runId])
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        if (runId) {
          const data = await apiFetch(`/debug/runs/${encodeURIComponent(runId)}`, { signal: controller.signal }).then(apiJson<DebugRun>)
          if (controller.signal.aborted) return
          setRun(data); setScenario(data.scenario); setDraft({ code: data.code, hypothesis: data.hypothesis, explanation: data.explanation }); setSaveStatus('Saved')
          if (data.test_result) { setLatest(data.test_result.results); if (data.tests_current) setTestedCode(data.code) }
          const before = await runInSandbox(data.scenario.starter_code, data.scenario.tests, controller.signal)
          if (!controller.signal.aborted) setBaseline(before)
        } else {
          const [catalogue, saved] = await Promise.all([
            apiFetch('/debug/challenges', { signal: controller.signal }).then(apiJson<{ challenges: Scenario[] }>),
            apiFetch('/debug/runs', { signal: controller.signal }).then(apiJson<{ runs: RunSummary[] }>),
          ])
          if (!controller.signal.aborted) { setScenario(catalogue.challenges[0]); setRuns(saved.runs) }
        }
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load debugging practice.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [apiFetch, runId, attempt])
  function edit(key: keyof Draft, value: string) {
    if (!draft) return
    const next = { ...draft, [key]: value }
    pending.current = { value: next, dirty: true }
    setDraft(next); setSaveStatus('Unsaved changes'); setNotice('')
  }
  useEffect(() => {
    if (!draft || !pending.current?.dirty) return
    const timer = window.setTimeout(() => { void save().catch(() => {}) }, 700)
    return () => clearTimeout(timer)
  }, [draft, save])
  async function start() {
    if (!scenario || busy) return
    setWorking(true); setError('')
    try {
      const data = await apiFetch('/debug/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario_id: scenario.id, ...(includeSource && source?.kind === 'text' ? { source_id: source.source_id } : {}) }) }).then(apiJson<DebugRun>)
      onOpen(data.id)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not start this challenge.') }
    finally { setWorking(false) }
  }
  async function test() {
    if (!draft || !runId || !scenario || busy) return
    setWorking(true); setError(''); setNotice('')
    const code = draft.code
    const controller = new AbortController()
    runnerController.current = controller
    try {
      await save()
      const results = await runInSandbox(code, scenario.tests, controller.signal)
      if (!mounted.current) return
      setLatest(results); setTestedCode(code)
      const data = await apiFetch(`/debug/runs/${runId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ test_result: { tested_code: code, results } }) }).then(apiJson<DebugRun>)
      if (mounted.current) { setRun(data); setSaveStatus('Saved'); setNotice(results.every(item => item.passed) ? 'All tests passed. Explain why your change works.' : 'Some tests are still failing. Use the results to refine your hypothesis.') }
    } catch (failure) { if (mounted.current) setError(failure instanceof Error ? failure.message : 'Could not run the tests.') }
    finally { if (mounted.current) setWorking(false) }
  }
  async function hint() {
    if (!runId || !run || busy) return
    setWorking(true); setError('')
    try {
      await save()
      const data = await apiFetch(`/debug/runs/${runId}/hint`, { method: 'POST' }).then(apiJson<DebugRun>)
      setRun(data)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not load the next hint.') }
    finally { setWorking(false) }
  }
  async function transcribe(file: File) {
    setError(''); setNotice('')
    try {
      const data = new FormData(); data.append('audio_file', file)
      const result = await apiFetch('/transcriptions', { method: 'POST', body: data }).then(apiJson<{ transcript: string }>)
      if (!result.transcript?.trim()) throw new Error('No speech was transcribed. Try again or type your explanation.')
      edit(voiceTarget, result.transcript)
      setNotice('Transcript added. You can edit it below; changes save automatically.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not transcribe the explanation.') }
  }
  const phaseChange = useCallback((_phase: RecordingPhase) => {}, [])
  const current = draft?.code === testedCode
  const passing = !!latest && current && latest.every(item => item.passed)
  const complete = passing && !!draft?.hypothesis.trim() && !!draft.explanation.trim()
  const beforeCount = baseline?.filter(item => item.passed).length
  const afterCount = latest?.filter(item => item.passed).length
  return <main className="workspace debug-page" id="debug-page" tabIndex={-1}>
    <div className="page-heading"><div><h1>{runId ? 'Find it. Fix it. Explain it.' : 'Debugging practice'}</h1><p>{runId ? 'A controlled bug, a testable fix, and your reasoning.' : 'Learn to diagnose a feature by making its tests pass.'}</p></div>{runId && <div className="debug-save-state" role="status">{saveStatus}<button type="button" className="text-button" disabled={busy} onClick={() => { void save().catch(() => {}) }}>Save progress</button></div>}</div>
    {loading && <p className="page-loading" role="status"><ActivityOrb state="searching" /> Loading challenge…</p>}
    {error && <div className="error-banner" role="alert"><Icon name="info" /><div><p>{error}</p>{loading === false && !scenario && <button className="text-button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>Retry</button>}</div></div>}
    {!loading && !runId && scenario && <>
      <section className="challenge-intro"><div><h2>{scenario.title}</h2><p>{scenario.project} · JavaScript</p><p className="challenge-contract">Inspect the validator, explain your hypothesis, then repair it against ten executable tests.</p><p className="field-note">{scenario.provenance}</p>{source?.kind === 'text' && <label className="debug-context-choice"><input type="checkbox" checked={includeSource} onChange={event => setIncludeSource(event.target.checked)} /> Attach {source.filename} as project context</label>}<button className="button button-primary" disabled={busy} onClick={() => { void start() }}>{working ? 'Starting…' : 'Start challenge'}<Icon name="arrow" size={18} /></button></div><div className="challenge-case"><span>Reproduce the bug</span><code>validateRecording(30000, 30)</code><p>Expected <strong>true</strong> · Currently <strong>false</strong></p><p className="field-note">No AI call is needed to run this challenge. Voice transcription uses your daily allowance.</p></div></section>
      <section className="debug-saved"><h2>Saved debugging practice</h2>{runs.length ? <div className="history-list">{runs.map(item => <button className="history-file" key={item.id} onClick={() => onOpen(item.id)}><Icon name="code" size={23} /><span className="history-file-title"><strong>Recording duration</strong><span>{item.complete ? 'Tests passed · Explanation saved' : item.tests_passed ? 'Tests passed · Explanation pending' : 'In progress'} · {date(item.updated_at)}</span></span><span>Resume</span><Icon name="arrow" size={17} /></button>)}</div> : <p className="field-note">Your practice will appear here and in History.</p>}</section>
    </>}
    {!loading && run && scenario && draft && <>
      <div className="debug-brief"><h2>{scenario.title}</h2><p>{scenario.contract}</p><p className="field-note">Practice copy · Your original project is unchanged.</p></div>
      <div className="debug-layout"><section className="debug-editor-area" aria-labelledby="debug-code-heading"><div className="section-heading"><h2 id="debug-code-heading">Repair the validator</h2><span className="muted">JavaScript</span></div><label htmlFor="debug-code" className="sr-only">Challenge code</label><textarea id="debug-code" className="debug-code" value={draft.code} maxLength={12000} spellCheck={false} autoCapitalize="off" autoCorrect="off" disabled={busy} onChange={event => edit('code', event.target.value)} /><div className="debug-editor-actions"><button className="button button-primary" disabled={busy || !draft.code.trim()} onClick={() => { void test() }}>{working ? <><ActivityOrb state="solving" />Working…</> : <>Run tests <Icon name="arrow" size={17} /></>}</button><button className="text-button" disabled={busy} onClick={() => { if (window.confirm('Restore the broken starting code? Your hypothesis, explanation and previous results will be kept.')) edit('code', scenario.starter_code) }}>Reset code</button></div>
      <div className="debug-hints"><div><h3>Hints</h3><span>{run.hints.length} / {run.total_hints} revealed</span></div>{run.hints.map((text, index) => <p key={text}><strong>Hint {index + 1}.</strong> {text}</p>)}<button className="text-button" disabled={busy || run.hints.length >= run.total_hints} onClick={() => { void hint() }}>{run.hints.length === run.total_hints ? 'All hints revealed' : 'Reveal next hint'}</button></div>
      {run.context && <details className="debug-project-context"><summary>Project context · {run.context.filename}</summary><p className="field-note">Reference snapshot, lines {run.context.snippet.start_line}–{run.context.snippet.end_line}. The exercise is a separate practice function.</p><pre>{run.context.snippet.content.join('\n')}</pre></details>}
      </section><section className="debug-results" aria-labelledby="debug-tests-heading"><div className="section-heading"><h2 id="debug-tests-heading">Test evidence</h2></div><div className="test-comparison"><p><span>Before</span><strong>{baseline ? `${beforeCount} / ${scenario.tests.length} passed` : 'Running baseline…'}</strong></p><p><span>After</span><strong>{latest ? `${afterCount} / ${scenario.tests.length} passed` : 'Not run yet'}</strong></p></div>{latest && !current && <p className="test-stale" role="status">Code changed since the last run. Run tests again.</p>}<ul className="debug-test-list">{scenario.tests.map((item, index) => { const result = latest?.[index]; return <li key={item.id}><div><Icon name={result ? result.passed ? 'check' : 'close' : 'minus'} size={17} /><strong>{item.name}</strong></div><code>({item.args.map(value => JSON.stringify(value)).join(', ')}) → {String(item.expected)}</code><p>{result ? result.error || `Returned ${String(result.actual)} · ${result.passed ? 'Passed' : 'Failed'}` : baseline?.[index] ? `Before: ${baseline[index].passed ? 'passed' : 'failed'}` : 'Pending'}</p></li> })}</ul><p className="field-note">Executed in your browser. These are practice results, not a certified assessment.</p></section></div>
      <section className="debug-reasoning" aria-labelledby="debug-reasoning-heading"><div className="section-heading"><h2 id="debug-reasoning-heading">Explain your reasoning</h2><span className="muted">Type or speak</span></div><div className="debug-explanation-grid"><label>Before the fix: your hypothesis<textarea aria-label="Your hypothesis" rows={4} maxLength={4000} disabled={busy} value={draft.hypothesis} onChange={event => edit('hypothesis', event.target.value)} placeholder="What do you think causes the failure, and what would you inspect first?" /></label><label>After the fix: why it works<textarea aria-label="Why the fix works" rows={4} maxLength={4000} disabled={busy} value={draft.explanation} onChange={event => edit('explanation', event.target.value)} placeholder="Explain the cause, your change, and which tests support it." /></label></div><div className="debug-voice"><label>Put transcript in<select aria-label="Transcript destination" value={voiceTarget} disabled={busy} onChange={event => setVoiceTarget(event.target.value as 'hypothesis' | 'explanation')}><option value="hypothesis">Hypothesis</option><option value="explanation">Why the fix works</option></select></label><VoiceRecorder disabled={working} onBusyChange={setRecordingBusy} onPhaseChange={phaseChange} onRecording={transcribe} onError={setError} /></div><p className="field-note">Edit the transcript as needed. Your explanations save automatically; AI does not decide whether the code passes.</p>{notice && <p className="debug-notice" role="status">{notice}</p>}<div className="debug-completion" role="status"><Icon name={complete ? 'check' : 'info'} size={20} /><p>{complete ? 'Tests passed and both explanations are recorded.' : passing ? 'Your code passes. Add your hypothesis and explanation to finish.' : 'Reproduce the failure, test your fix, and explain the result.'}</p></div></section>
      <div className="history-delete"><button className="text-button danger-button" disabled={busy} onClick={() => { if (!window.confirm('Permanently delete this debugging run?')) return; setWorking(true); void apiFetch(`/debug/runs/${runId}`, { method: 'DELETE' }).then(response => { if (!response.ok) throw new Error('Could not delete the run.'); pending.current = null; onOpen('') }).catch(failure => setError(failure.message)).finally(() => setWorking(false)) }}>Delete this run</button></div>
    </>}
  </main>
}
