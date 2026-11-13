import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/context'
import { apiJson } from '../api'
import Icon from '../components/Icon'
import ActivityOrb from '../components/ActivityOrb'
import type { SpeechReview } from '../components/TranscriptReview'
import DebugAnswerField, { type AnswerField } from '../debug/DebugAnswerField'
import DebugDefenseResult, { type DefenseResult } from '../debug/DebugDefenseResult'
import type { SourceDocument } from '../components/SourceUpload'
import { runInSandbox, type DebugTest, type TestObservation } from '../debug/runner'
import CodeEditor, { CodeTokens } from '../debug/CodeEditor'
import '../debug/exercise.css'
import '../debug/setup.css'

interface Scenario {
  id: string; title: string; project: string; language: string; starter_code: string; tests: DebugTest[]; contract: string; provenance: string
  reference_code?: string; function_name: string; execution_mode: 'javascript' | 'local'; verification_steps: string[]
  source?: { filename: string; start_line: number; end_line: number }
}
interface RunSummary { id: string; updated_at: string; complete: boolean; tests_passed: boolean; solution_passed: boolean; title: string; filename: string }
interface SolutionResult { verdict: 'correct' | 'incorrect' | 'uncertain'; score: number | null; method: 'reference' | 'ai_review'; explanation: string }
interface DebugRun {
  id: string; code: string; hypothesis: string; explanation: string; hints: string[]; total_hints: number
  scenario: Scenario; complete: boolean; tests_passed: boolean; tests_current: boolean
  solution_result?: SolutionResult; solution_current: boolean
  failing_input?: string; speech_reviews?: Record<string, SpeechReview>; defense_result?: DefenseResult; defense_current: boolean
  test_result?: { results: TestObservation[] }; context?: { filename: string; snippet: { content: string[]; start_line: number; end_line: number } }
}
type Draft = Pick<DebugRun, 'code' | 'hypothesis' | 'explanation'> & { failing_input: string; speech_reviews: Record<string, SpeechReview> }
const draftPayload = (draft: Draft) => ({ ...draft, speech_reviews: Object.fromEntries(Object.entries(draft.speech_reviews).map(([key, review]) => [key, { receipt_id: review.receipt_id, reviewed: review.reviewed }])) })
const vivaSpeech = (reviews?: Record<string, SpeechReview>) => JSON.stringify(['explanation', 'failing_input'].map(key => reviews?.[key] ?? null))
const date = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export default function DebugPage({ runId, source, onOpen, onSourceChange, onBusyChange, onSaveHandler }: {
  runId?: string; source: SourceDocument | null; onOpen: (id: string) => void
  onSourceChange: (source: SourceDocument) => void
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
  const [checkedCode, setCheckedCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [activeRecording, setActiveRecording] = useState<AnswerField | null>(null)
  const recordingBusy = activeRecording !== null
  const recordingChange = useCallback((field: AnswerField, value: boolean) => {
    setActiveRecording(current => value ? field : current === field ? null : current)
  }, [])
  const [reviewing, setReviewing] = useState(false)
  const [sectionId, setSectionId] = useState('')
  const [validation, setValidation] = useState<'checking' | 'ready' | 'invalid'>('checking')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [saveStatus, setSaveStatus] = useState('')
  const [attempt, setAttempt] = useState(0)
  const pending = useRef<{ value: Draft; dirty: boolean } | null>(null)
  const chain = useRef<Promise<void>>(Promise.resolve())
  const mounted = useRef(true)
  const runnerController = useRef<AbortController | null>(null)
  const resultPanel = useRef<HTMLDivElement | null>(null)
  const defensePanel = useRef<HTMLDivElement | null>(null)
  function revealResult() {
    window.requestAnimationFrame(() => { resultPanel.current?.focus({ preventScroll: true }); resultPanel.current?.scrollIntoView({ block: 'nearest' }) })
  }
  const busy = working || recordingBusy
  const save = useCallback(async () => {
    const item = pending.current
    if (!runId || !item?.dirty) return chain.current
    item.dirty = false
    const operation = chain.current.catch(() => {}).then(async () => {
      await apiFetch(`/debug/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draftPayload(item.value)) }).then(apiJson<DebugRun>)
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
      if (runId && item?.dirty) void apiFetch(`/debug/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draftPayload(item.value)) }).catch(() => {})
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
          setRun(data); setScenario(data.scenario); setDraft({ code: data.code, hypothesis: data.hypothesis, explanation: data.explanation, failing_input: data.failing_input ?? '', speech_reviews: data.speech_reviews ?? {} }); setSaveStatus('Saved')
          setCheckedCode(data.solution_current ? data.code : null)
          if (data.test_result) { setLatest(data.test_result.results); if (data.tests_current) setTestedCode(data.code) }
          if (data.scenario.execution_mode === 'javascript') {
            const before = await runInSandbox(data.scenario.starter_code, data.scenario.tests, controller.signal, data.scenario.function_name)
            const reference = data.scenario.reference_code
              ? await runInSandbox(data.scenario.reference_code, data.scenario.tests, controller.signal, data.scenario.function_name)
              : null
            if (!controller.signal.aborted) {
              setBaseline(before)
              setValidation(reference && (!reference.every(item => item.passed) || before.every(item => item.passed)) ? 'invalid' : 'ready')
            }
          } else setValidation('ready')
        } else {
          const saved = await apiFetch('/debug/runs', { signal: controller.signal }).then(apiJson<{ runs: RunSummary[] }>)
          if (!controller.signal.aborted) setRuns(saved.runs)
        }
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load debugging practice.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [apiFetch, runId, attempt])
  function updateDraft(next: Draft) {
    pending.current = { value: next, dirty: true }
    setDraft(next); setSaveStatus('Unsaved changes'); setNotice('')
  }
  function edit(key: 'code' | AnswerField, value: string) {
    if (!draft) return
    const reviews = { ...draft.speech_reviews }
    if (reviews[key]) reviews[key] = { ...reviews[key], reviewed: false }
    updateDraft({ ...draft, [key]: value, speech_reviews: reviews })
  }
  useEffect(() => {
    if (!draft || !pending.current?.dirty) return
    const timer = window.setTimeout(() => { void save().catch(() => {}) }, 700)
    return () => clearTimeout(timer)
  }, [draft, save])
  async function start() {
    if (!source || busy) return
    setWorking(true); setError('')
    try {
      const data = await apiFetch('/debug/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source_id: source.source_id, snippet_id: selectedSection?.id }) }).then(apiJson<DebugRun>)
      onOpen(data.id)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not start this challenge.') }
    finally { setWorking(false) }
  }
  async function test() {
    if (!draft || !runId || !scenario || busy || validation !== 'ready' || scenario.execution_mode !== 'javascript') return
    setWorking(true); setError(''); setNotice('')
    const code = draft.code
    const controller = new AbortController()
    runnerController.current = controller
    try {
      await save()
      const results = await runInSandbox(code, scenario.tests, controller.signal, scenario.function_name)
      if (!mounted.current) return
      setLatest(results); setTestedCode(code)
      const data = await apiFetch(`/debug/runs/${runId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ test_result: { tested_code: code, results } }) }).then(apiJson<DebugRun>)
      if (mounted.current) { setRun(data); setSaveStatus('Saved'); setNotice(results.every(item => item.passed) ? 'All tests passed. Explain why your change works.' : 'Some tests are still failing. Use the results to refine your hypothesis.'); revealResult() }
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
  async function checkSolution() {
    if (!draft || !runId || !scenario || busy) return
    if (scenario.execution_mode === 'javascript' && validation === 'ready') { await test(); return }
    setWorking(true); setError(''); setNotice('')
    const code = draft.code
    try {
      await save()
      const data = await apiFetch(`/debug/runs/${encodeURIComponent(runId)}/check`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) }).then(apiJson<DebugRun>)
      if (mounted.current) { setRun(data); setCheckedCode(code); setSaveStatus('Saved'); revealResult() }
    } catch (failure) { if (mounted.current) setError(failure instanceof Error ? failure.message : 'Could not check this solution. Retry.') }
    finally { if (mounted.current) setWorking(false) }
  }
  async function transcribe(field: AnswerField, file: File) {
    setError(''); setNotice('')
    try {
      if (!runId || !draft) return
      await save()
      const data = new FormData(); data.append('audio_file', file); data.append('debug_run_id', runId); data.append('debug_field', field)
      const result = await apiFetch('/transcriptions', { method: 'POST', body: data }).then(apiJson<{ transcript: string; speech_review: SpeechReview }>)
      if (!result.transcript?.trim() || !result.speech_review?.receipt_id) throw new Error('No speech was transcribed. Try again or type your explanation.')
      updateDraft({ ...draft, [field]: result.transcript, speech_reviews: { ...draft.speech_reviews, [field]: result.speech_review } })
      setNotice('Transcript added. Check what was heard before submitting your viva.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not transcribe the explanation.') }
  }
  async function defend() {
    if (!runId || busy) return
    setWorking(true); setReviewing(true); setError(''); setNotice('')
    try {
      await save()
      const result = await apiFetch(`/debug/runs/${encodeURIComponent(runId)}/defend`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).then(apiJson<DebugRun>)
      if (mounted.current) {
        setRun(result)
        window.requestAnimationFrame(() => { defensePanel.current?.focus({ preventScroll: true }); defensePanel.current?.scrollIntoView({ block: 'nearest' }) })
      }
    } catch (failure) { if (mounted.current) setError(failure instanceof Error ? failure.message : 'Could not review your viva. Retry shortly.') }
    finally { if (mounted.current) { setWorking(false); setReviewing(false) } }
  }
  function answerField(field: AnswerField, label: string, recordLabel: string, placeholder?: string) {
    if (!draft) return null
    return <DebugAnswerField field={field} label={label} recordLabel={recordLabel} value={draft[field]} placeholder={placeholder}
      review={draft.speech_reviews[field]} busy={busy} recordingDisabled={working || (activeRecording !== null && activeRecording !== field)}
      onChange={value => edit(field, value)} onRecording={transcribe} onRecordingBusy={recordingChange} onError={setError}
      onConfirm={value => updateDraft({ ...draft, speech_reviews: { ...draft.speech_reviews, [field]: { ...draft.speech_reviews[field], reviewed: value } } })}
      onTyped={() => { const reviews = { ...draft.speech_reviews }; delete reviews[field]; updateDraft({ ...draft, speech_reviews: reviews }) }} />
  }
  const codeFile = source?.kind === 'text' && /\.(js|mjs|cjs|jsx|ts|tsx|py|java|c|h|cpp|hpp|cs|go|rs|rb|php|swift|kt|sql|sh)$/i.test(source.filename)
  const selectedSection = source?.snippets.find(item => item.id === sectionId) ?? source?.snippets[0]
  async function upload(file?: File) {
    if (!file || busy) return
    setWorking(true); setError('')
    try {
      if (!file.size || file.size > 256 * 1024) throw new Error('Choose a non-empty source file up to 256 KiB.')
      const body = new FormData(); body.append('source_file', file)
      const result = await apiFetch('/sources', { method: 'POST', body }).then(apiJson<SourceDocument>)
      onSourceChange(result); setSectionId('')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not upload this file.') }
    finally { setWorking(false) }
  }
  async function chooseExample() {
    if (busy) return
    setWorking(true); setError('')
    try {
      const result = await apiFetch('/sources/example', { method: 'POST' }).then(apiJson<SourceDocument>)
      onSourceChange(result); setSectionId('')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open the Python example.') }
    finally { setWorking(false) }
  }
  const current = draft?.code === testedCode
  const solutionCurrent = draft?.code === checkedCode
  const solution = run?.solution_result
  const passing = (!!latest && current && latest.every(item => item.passed)) || (!!solution && solutionCurrent && solution.verdict === 'correct')
  const defenseCurrent = passing && !!run?.defense_current && draft?.code === run.code && draft.explanation === run.explanation && draft.failing_input === run.failing_input && vivaSpeech(draft.speech_reviews) === vivaSpeech(run.speech_reviews)
  const complete = defenseCurrent && !!run?.defense_result?.passed
  const speechPending = !!draft && ['explanation', 'failing_input'].some(field => draft.speech_reviews[field] && !draft.speech_reviews[field].reviewed)
  const beforeCount = baseline?.filter(item => item.passed).length
  const afterCount = latest?.filter(item => item.passed).length
  const score = solution && solutionCurrent ? solution.score : latest && current ? Math.round((afterCount ?? 0) / (scenario?.tests.length || 1) * 100) : null
  async function chooseExercise() {
    try { await save(); onOpen('') } catch { setError('Your draft could not be saved. Retry before leaving.') }
  }
  return <main className={`workspace debug-page ${runId ? 'debug-exercise' : 'debug-setup'}`} id="debug-page" tabIndex={-1}>
    {!runId && <div className="incident-mode-switch"><span aria-current="page">Code repairs</span><a href="#/incidents">Running incidents</a></div>}
    {runId ? <div className="exercise-toolbar"><button className="text-button" disabled={busy} onClick={() => { void chooseExercise() }}><Icon name="arrow" size={14} className="rotate-180" />Exercises</button><div className="debug-save-state" role="status"><span className={saveStatus === 'Saved' ? 'save-indicator is-saved' : 'save-indicator'} />{saveStatus}<span aria-hidden="true">·</span><button type="button" className="text-button" disabled={busy} onClick={() => { void save().catch(() => {}) }}>Save progress</button></div></div> : <div className="page-heading"><div><h1>Debug your project</h1><p>Start with your uploaded code or choose a new source file.</p></div></div>}
    {loading && <p className="page-loading" role="status"><ActivityOrb state="searching" /> Loading challenge…</p>}
    {error && <div className="error-banner" role="alert"><Icon name="info" /><div><p>{error}</p>{loading === false && !scenario && <><button className="text-button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>Retry</button>{runId && <button className="text-button" onClick={() => onOpen('')}>Choose your source file</button>}</>}</div></div>}
    {!loading && !runId && <>
      <section className="debug-source-setup" aria-labelledby="debug-source-heading">
        <div className="debug-setup-options">
          <div className="debug-example-option"><button type="button" className="button button-secondary" disabled={busy} onClick={() => { void chooseExample() }}>Use Python example<Icon name="code" size={16} /></button><p>Try the same prime checker from Study, with a prepared bug to repair. No AI generation allowance needed.</p></div>
          <div className="debug-file-option">
            <div className="debug-file-option-heading"><div><h2 id="debug-source-heading">{source ? source.filename : 'Choose your source file'}</h2><p>{!source ? 'Upload your own code or choose the Python example.' : !codeFile ? 'This material is for Study. Upload a source code file for Debug.' : source.prepared_example ? 'Prepared Python example: repair one deliberate bug in the prime checker.' : 'AI will introduce one deliberate bug for you to diagnose and repair.'}</p></div><label className="button button-secondary debug-file-picker">{source ? 'Upload another file' : 'Upload source file'}<input aria-label="Upload debugging source" type="file" accept=".py,.js,.jsx,.ts,.tsx,.java,.c,.cpp,.h,.hpp,.mjs,.cjs,.go,.rs,.rb,.php,.cs,.swift,.kt,.sql,.sh" disabled={busy} onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; void upload(file) }} /></label></div>
            {codeFile && source && <div className="debug-section-config"><div><label htmlFor="debug-section-select">Start from section</label><p>The selected section and up to two following sections are used to find a complete function.</p></div><select id="debug-section-select" aria-label="Source section" disabled={busy} value={selectedSection?.id ?? ''} onChange={event => setSectionId(event.target.value)}>{source.snippets.map(item => <option key={item.id} value={item.id}>Lines {item.start_line}–{item.end_line}</option>)}</select></div>}
          </div>
        </div>
        {codeFile && source && <>
          {selectedSection && <details className="debug-setup-preview" open><summary>Uploaded code · lines {selectedSection.start_line}–{selectedSection.end_line}</summary><div className="debug-preview-code"><div className="debug-preview-lines" aria-hidden="true">{selectedSection.content.map((_, index) => <div key={index}>{(selectedSection.start_line ?? 1) + index}</div>)}</div><pre tabIndex={0} aria-label="Uploaded source code"><CodeTokens code={selectedSection.content.join('\n')} /></pre></div></details>}
          <div className="debug-setup-create"><button className="button button-primary" disabled={busy} onClick={() => { void start() }}>{working ? <><ActivityOrb state="composing" />Creating your exercise…</> : <>Create debugging exercise<Icon name="arrow" size={17} /></>}</button><p>{source.prepared_example ? 'Prepared exercise and restoring the original are free. A different repair may use an AI review allowance.' : 'Uses 1 question-set allowance. JavaScript runs tests here; other languages use source comparison or AI review.'}</p></div>
        </>}
      </section>
      <section className="debug-saved"><h2>Saved debugging practice</h2>{runs.length ? <div className="history-list">{runs.map(item => <button className="history-file" key={item.id} disabled={busy} onClick={() => onOpen(item.id)}><Icon name="code" size={23} /><span className="history-file-title"><strong>{item.title}</strong><span>{item.filename} · {item.complete ? 'Repair and viva complete' : item.solution_passed ? 'Repair accepted · Viva pending' : 'In progress'} · {date(item.updated_at)}</span></span><span>Resume</span><Icon name="arrow" size={17} /></button>)}</div> : <p className="field-note">Exercises from your files will appear here and in History.</p>}</section>
    </>}
    {!loading && run && scenario && draft && <>
      <section className="debug-brief"><h1>{scenario.title.split(' ').map((word, index) => <span key={index} className={index < 2 ? 'exercise-title-accent' : undefined}>{word}{' '}</span>)}</h1><p>{scenario.contract}</p><p className="field-note">{scenario.provenance}</p></section>
      <div className="debug-layout">
        <section className="debug-editor-area" aria-label="Repair your code">
          <div className="exercise-file-meta"><h2>{scenario.project}</h2><span>{scenario.language} · UTF-8</span>{scenario.source && <span className="exercise-line-range">Lines {scenario.source.start_line}–{scenario.source.end_line}</span>}</div>
          <div className="exercise-editor-frame">
            <div className="exercise-editor-title"><div className="editor-window-dots" aria-hidden="true"><i /><i /><i /></div><span>{scenario.project}</span><span>UTF-8</span></div>
            <CodeEditor code={draft.code} startLine={scenario.source?.start_line ?? 1} disabled={busy} onChange={value => edit('code', value)} />
            <div className="debug-editor-actions"><button className="button button-primary" disabled={busy || !draft.code.trim() || validation === 'checking'} onClick={() => { void checkSolution() }}>{working ? <><ActivityOrb state="solving" />Checking…</> : <>Check solution <Icon name="arrow" size={15} /></>}</button><button className="text-button" disabled={busy} onClick={() => { if (window.confirm('Restore the broken starting code? Your hypothesis, explanation and previous results will be kept.')) edit('code', scenario.starter_code) }}>Reset code</button><span className="editor-action-caption">Free source comparisons</span></div>
          </div>
          <p className="field-note exercise-cost-note">Source comparisons and browser tests are free. An AI review of a different repair uses 1 answer-review allowance.</p>
        </section>
        <section className="debug-results" aria-labelledby="debug-tests-heading"><div className="section-heading"><h2 id="debug-tests-heading">Solution result</h2>{score !== null && <span className={passing ? 'exercise-score is-correct' : 'exercise-score'}>{score} / 100</span>}</div>
      <div className={`debug-solution-result ${passing ? 'is-correct' : ''}`} ref={resultPanel} tabIndex={-1} role="status" aria-live="polite">
        {solution && solutionCurrent ? <><h3><Icon name={solution.verdict === 'correct' ? 'check' : 'info'} size={16} />{solution.verdict === 'correct' ? solution.method === 'reference' ? 'Correct implementation restored' : 'Repair accepted' : solution.verdict === 'incorrect' ? 'Keep going' : 'Review inconclusive'}</h3><p>{solution.explanation}</p>{solution.method === 'ai_review' && <p className="field-note">AI code review · code was not executed. This assessment can make mistakes.</p>}</>
          : latest && current ? <><h3><Icon name={passing ? 'check' : 'info'} size={16} />{passing ? 'All tests passed' : 'Keep going'}</h3><p>{passing ? 'Your repair passes every generated test.' : `${afterCount} of ${scenario.tests.length} tests passed. Inspect the failing cases below.`}</p><p className="field-note">Score is the percentage of generated tests passed.</p></>
          : <p>{solution || latest ? 'Code changed. Check your solution again for an updated score.' : 'Repair the code, then select Check solution to get your result here.'}</p>}
        <button className="text-button exercise-next" disabled={busy} onClick={() => { void chooseExercise() }}>Choose another file or exercise<Icon name="arrow" size={12} /></button>
      </div>
      {scenario.execution_mode === 'javascript' ? <>
        {validation === 'invalid' && <p className="field-note">The generated tests could not validate this exercise. Check solution will use source comparison or AI review instead.</p>}
        <div className="test-comparison"><p><span>Before</span><strong>{baseline ? `${beforeCount} / ${scenario.tests.length} passed` : 'Running baseline…'}</strong></p><p><span>After</span><strong>{latest ? `${afterCount} / ${scenario.tests.length} passed` : 'Not run yet'}</strong></p></div>
        {latest && !current && <p className="test-stale" role="status">Code changed since the last run. Run tests again.</p>}
        <ul className="debug-test-list">{scenario.tests.map((item, index) => { const result = latest?.[index]; return <li key={item.id}><div><Icon name={result ? result.passed ? 'check' : 'close' : 'minus'} size={17} /><strong>{item.name}</strong></div><code>{scenario.function_name}({item.args.map(value => JSON.stringify(value)).join(', ')}) → {JSON.stringify(item.expected)}</code><p>{result ? result.error || `Returned ${JSON.stringify(result.actual)} · ${result.passed ? 'Passed' : 'Failed'}` : baseline?.[index] ? `Before: ${baseline[index].passed ? 'passed' : 'failed'}` : 'Pending'}</p></li> })}</ul>
        <p className="field-note">Generated tests are checked against your uploaded excerpt and executed in your browser. They are practice evidence, not a complete correctness proof.</p>
      </> : null}
      </section></div>
      <details className="exercise-hints" open><summary><span>Hints</span><span className="hint-count">{run.hints.length}/{run.total_hints} revealed</span></summary><div className="exercise-hints-content">{run.hints.map((text, index) => <p key={text}><span>{String(index + 1).padStart(2, '0')}</span>{text}</p>)}{run.hints.length === 0 && <p className="field-note">Need a starting point? Reveal one hint at a time.</p>}<button className="text-button" disabled={busy || run.hints.length >= run.total_hints} onClick={() => { void hint() }}>{run.hints.length === run.total_hints ? 'All hints revealed' : 'Reveal next hint'}</button></div></details>
      {scenario.reference_code && <details className="debug-project-context exercise-source"><summary>Compare with uploaded source</summary><p className="field-note">This reveals the original excerpt before the practice bug was introduced.</p><pre>{scenario.reference_code}</pre></details>}
      <section className="debug-reasoning" aria-labelledby="debug-reasoning-heading">
        <details className="debug-hypothesis"><summary onClick={event => { if (activeRecording === 'hypothesis') event.preventDefault() }}>Your starting hypothesis (optional)</summary>{answerField('hypothesis', 'Your hypothesis', 'Record hypothesis', 'What might cause the failure?')}</details>
        <div className="section-heading"><h2 id="debug-reasoning-heading">Defend your repair</h2><span className="muted">Type or speak</span></div>
        <p>{passing ? 'Your repair is accepted. Now show that you understand it.' : 'First repair the code and check your solution. You can draft your answers below.'}</p>
        <div className="debug-explanation-grid">
          {answerField('explanation', 'Why the fix works', 'Record explanation', 'Why did it fail, and why does your change restore the intended behavior?')}
          {answerField('failing_input', 'Input that exposes the bug', 'Record input trace', 'Give an input, the broken and repaired outcomes, and why they differ.')}
        </div>
        <p className="field-note">Edit and confirm spoken answers before submission. Drafts save automatically. Each new viva review uses 1 answer-review allowance; unchanged submissions reuse the saved review.</p>
        <button className="button button-primary" disabled={busy || !passing || !draft.explanation.trim() || !draft.failing_input.trim() || speechPending || defenseCurrent} onClick={() => { void defend() }}>{reviewing ? <><ActivityOrb state="solving" />Reviewing viva…</> : defenseCurrent ? 'Viva reviewed' : 'Submit viva answers'}</button>
        {speechPending && <p className="field-note">Check and confirm each spoken answer to enable submission.</p>}
        {error && <p className="error-message" role="alert">{error}</p>}
        {notice && <p className="debug-notice" role="status">{notice}</p>}
        <div className="debug-viva-feedback" ref={defensePanel} tabIndex={-1} aria-live="polite">{run.defense_result && <DebugDefenseResult result={run.defense_result} current={defenseCurrent} />}</div>
        <div className="debug-completion" role="status"><Icon name={complete ? 'check' : 'info'} size={20} /><p>{complete ? 'Repair accepted and both viva answers demonstrate understanding.' : passing ? 'Repair accepted. Explain the cause and an exposing input, then submit your viva.' : 'Repair the code, check your solution, then defend your change.'}</p></div>
      </section>
      <div className="history-delete"><button className="text-button danger-button" disabled={busy} onClick={() => { if (!window.confirm('Permanently delete this debugging run?')) return; setWorking(true); void apiFetch(`/debug/runs/${runId}`, { method: 'DELETE' }).then(response => { if (!response.ok) throw new Error('Could not delete the run.'); pending.current = null; onOpen('') }).catch(failure => setError(failure.message)).finally(() => setWorking(false)) }}>Delete this run</button></div>
    </>}
  </main>
}
