import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/context'
import { apiJson } from '../api'
import VoiceRecorder from '../components/VoiceRecorder'
import type { RecordingPhase } from '../components/VoiceRecorder'
import CodeEditor from '../debug/CodeEditor'
import ExecutionEvidence from '../incidents/ExecutionEvidence'
import type { Catalogue, Lab } from '../incidents/types'
import type { SourceDocument } from '../components/SourceUpload'
import '../incidents/incidents.css'

const ignorePhase = (_phase: RecordingPhase) => {}
const sameFiles = (a: Record<string, string>, b: Record<string, string>) => Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([key, value]) => b[key] === value)

export default function IncidentsPage({ labId, source, onOpen, onBusyChange, onSaveHandler }: {
  labId?: string; source: SourceDocument | null; onOpen: (id: string) => void
  onBusyChange: (value: boolean) => void; onSaveHandler: (handler: (() => Promise<void>) | null) => void
}) {
  const { apiFetch } = useAuth()
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null)
  const [lab, setLab] = useState<Lab | null>(null)
  const [files, setFiles] = useState<Record<string, string>>({})
  const [selected, setSelected] = useState('')
  const [instruction, setInstruction] = useState('')
  const [original, setOriginal] = useState<string | null>(null)
  const [reviewed, setReviewed] = useState(false)
  const [working, setWorking] = useState(false)
  const [recording, setRecording] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saveStatus, setSaveStatus] = useState('Saved')
  const [retry, setRetry] = useState(0)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const pending = useRef<{ files: Record<string, string>; instruction_draft: { text: string; original: string | null; reviewed: boolean }; dirty: boolean } | null>(null)
  const chain = useRef<Promise<void>>(Promise.resolve())
  const mounted = useRef(true)
  const evidencePanel = useRef<HTMLDivElement>(null)
  const codePanel = useRef<HTMLElement>(null)
  const running = lab?.status === 'preparing' || lab?.status === 'running'
  const busy = working || recording
  const save = useCallback(async () => {
    const snapshot = pending.current
    if (!labId || !snapshot?.dirty) return chain.current
    snapshot.dirty = false
    const operation = chain.current.catch(() => {}).then(async () => {
      const saved = await apiFetch(`/incidents/${labId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: snapshot.files, instruction_draft: snapshot.instruction_draft }) }).then(apiJson<Lab>)
      if (mounted.current) { setLab(saved); setSaveStatus(pending.current?.dirty ? 'Unsaved changes' : 'Saved') }
    })
    chain.current = operation
    try { await operation }
    catch (failure) { if (pending.current === snapshot) snapshot.dirty = true; if (mounted.current) setSaveStatus('Not saved · retry'); throw failure }
  }, [apiFetch, labId])
  useEffect(() => { onSaveHandler(save); return () => onSaveHandler(null) }, [save, onSaveHandler])
  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false) }, [busy, onBusyChange])
  useEffect(() => {
    mounted.current = true
    const warn = (event: BeforeUnloadEvent) => { if (pending.current?.dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => { mounted.current = false; window.removeEventListener('beforeunload', warn); void save().catch(() => {}) }
  }, [save])
  useEffect(() => {
    const timer = setTimeout(() => { if (!running) void save().catch(() => {}) }, 800)
    return () => clearTimeout(timer)
  }, [files, instruction, original, reviewed, running, save])
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const list = await apiFetch('/incidents').then(apiJson<Catalogue>)
        const value = labId ? await apiFetch(`/incidents/${labId}`).then(apiJson<Lab>) : null
        if (cancelled) return
        setCatalogue(list); setLab(value)
        if (value) { const draft = value.instruction_draft ?? { text: '', original: null, reviewed: false }; setFiles(value.files); setInstruction(draft.text); setOriginal(draft.original); setReviewed(draft.reviewed); setSelected(Object.keys(value.files)[0]); pending.current = { files: value.files, instruction_draft: draft, dirty: false } }
      } catch (failure) { if (!cancelled) setError(failure instanceof Error ? failure.message : 'Could not open incident projects.') }
      finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [apiFetch, labId, retry])
  useEffect(() => {
    if (!labId || !running) return
    let cancelled = false
    const timer = setInterval(() => {
      void apiFetch(`/incidents/${labId}`).then(apiJson<Lab>).then(value => {
        if (cancelled) return
        setLab(value)
        if (value.status !== 'preparing' && value.status !== 'running') {
          setFiles(value.files); setSelected(current => current in value.files ? current : Object.keys(value.files)[0]); pending.current = { files: value.files, instruction_draft: value.instruction_draft ?? { text: '', original: null, reviewed: false }, dirty: false }
          void apiFetch('/incidents').then(apiJson<Catalogue>).then(setCatalogue).catch(() => {})
        }
      }).catch(failure => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'Connection interrupted. Your job and project remain saved.') })
    }, 1800)
    return () => { cancelled = true; clearInterval(timer) }
  }, [apiFetch, labId, running])
  async function start(file?: File, useSource = false) {
    setWorking(true); setError('')
    try {
      let body: BodyInit, headers: Record<string, string> = {}
      if (file) { if (file.size > 1024 * 1024) throw new Error('Choose a Python app or ZIP up to 1 MiB.'); const form = new FormData(); form.append('project_file', file); body = form }
      else { body = JSON.stringify(useSource ? { source_id: source?.source_id } : { example: true }); headers = { 'Content-Type': 'application/json' } }
      const value = await apiFetch('/incidents', { method: 'POST', headers, body }).then(apiJson<Lab>)
      onOpen(value.id)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not start the isolated project.') }
    finally { setWorking(false) }
  }
  async function remove(id: string) {
    setWorking(true); setError('')
    try { const response = await apiFetch(`/incidents/${id}`, { method: 'DELETE' }); if (!response.ok) await apiJson(response); setCatalogue(await apiFetch('/incidents').then(apiJson<Catalogue>)); setDeleteId(null) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not delete this incident project.') }
    finally { setWorking(false) }
  }
  const updateInstruction = useCallback((text: string, transcript: string | null, confirmed: boolean) => {
    setInstruction(text); setOriginal(transcript); setReviewed(confirmed)
    if (pending.current) { pending.current = { files: pending.current.files, instruction_draft: { text, original: transcript, reviewed: confirmed }, dirty: true }; setSaveStatus('Unsaved changes') }
  }, [])
  const transcribe = useCallback(async (file: File) => {
    setWorking(true); setError('')
    try {
      const form = new FormData(); form.append('audio_file', file)
      const value = await apiFetch('/transcriptions', { method: 'POST', body: form }).then(apiJson<{ transcript: string }>)
      updateInstruction(value.transcript, value.transcript, false)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not transcribe this recording. Your instruction is unchanged.') }
    finally { setWorking(false) }
  }, [apiFetch, updateInstruction])
  async function plan(text = instruction, typed = false) {
    if (!labId) return
    setWorking(true); setError('')
    try {
      if (typed) updateInstruction(text, null, false)
      await save()
      const value = await apiFetch(`/incidents/${labId}/plan`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction: text, original_transcript: typed ? null : original, reviewed }) }).then(apiJson<Lab>)
      setLab(value)
      if (value.plan?.action === 'inspect') evidencePanel.current?.scrollIntoView({ block: 'start', behavior: 'instant' })
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not prepare an experiment. Your patch is saved.') }
    finally { setWorking(false) }
  }
  async function execute() {
    if (!labId || !lab?.plan) return
    setWorking(true); setError('')
    try { await save(); setLab(await apiFetch(`/incidents/${labId}/execute`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan_id: lab.plan.id }) }).then(apiJson<Lab>)) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not run this experiment. Your work is saved.') }
    finally { setWorking(false) }
  }
  function edit(value: string) {
    const next = { ...files, [selected]: value }
    setFiles(next); pending.current = { files: next, instruction_draft: pending.current?.instruction_draft ?? { text: instruction, original, reviewed }, dirty: true }; setSaveStatus('Unsaved changes')
  }
  const changed = !!lab && !sameFiles(files, lab.files)
  const ready = lab?.status === 'ready'
  const evidence = lab?.latest ?? lab?.broken_evidence
  const proposal = lab?.plan
  const canExecute = proposal && ['replay', 'test_fix', 'experiment'].includes(proposal.action)
  return <main className="workspace incident-page" id="incidents-page" tabIndex={-1}>
    <div className="incident-mode-switch"><a href="#/debug">Code repairs</a><span aria-current="page">Running incidents</span></div>
    <div className="page-heading"><div><h1>{lab ? lab.title : 'Investigate a running app'}</h1><p>{lab?.scenario?.description ?? 'Speak a hypothesis, run an experiment, inspect the evidence and test your repair.'}</p></div>{labId && <button className="text-button" disabled={busy} onClick={() => { void save().then(() => onOpen('')).catch(() => setError('Save the patch before leaving.')) }}>All incidents</button>}</div>
    {error && <div className="incident-error" role="alert"><p>{error}</p><button className="text-button" disabled={busy} onClick={() => { void save().then(() => { setLoading(true); setError(''); setRetry(value => value + 1) }).catch(() => setError('Your patch is still here. Retry saving before reloading the project.')) }}>Retry connection</button></div>}
    {loading && <p role="status">Opening incident projects…</p>}
    {catalogue && <p className="field-note">Incident runs: {catalogue.usage.remaining} / {catalogue.usage.limit} left today · resets at midnight UTC. Setup verifies the original and failure; each approved experiment uses another run.</p>}
    {catalogue && !catalogue.runner_available && <p className="incident-unavailable" role="status">Running incidents is not enabled on this server yet. Your code, saved evidence and existing code repairs remain available.</p>}
    {!labId && !loading && <>
      <section className="incident-entry" aria-label="Choose incident project"><div><h2>Try the last-seat incident</h2><p>A prepared Python booking app with real HTTP requests and a disposable SQLite database. Find why two customers can reserve one seat.</p><button className="button button-primary" disabled={busy || !catalogue?.runner_available || !catalogue.usage.remaining} onClick={() => { void start() }}>Start booking incident</button></div><div><h2>Use your application</h2><p>Upload a Python HTTP app or ZIP, up to 1 MiB. The original must start and pass the proposed checks before a controlled failure is introduced.</p><label className="incident-upload">Upload project<input type="file" accept=".py,.zip" disabled={busy || !catalogue?.runner_available || !catalogue.usage.remaining} onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; if (file) void start(file) }} /></label>{source?.filename.endsWith('.py') && <button className="text-button" disabled={busy || !catalogue?.runner_available || !catalogue.usage.remaining} onClick={() => { void start(undefined, true) }}>Use {source.filename} from Study</button>}<p className="field-note">Use local, disposable data. Omit credentials and generated folders. External services and automatic dependency installs are unsupported.</p></div></section>
      <section className="incident-history"><h2>Your incident projects</h2>{catalogue?.labs.length ? <ul>{catalogue.labs.map(item => <li key={item.id}><button className="text-button" disabled={busy} onClick={() => onOpen(item.id)}>{item.title}</button><span>{item.status} · {new Date(item.updated_at).toLocaleDateString()}</span>{deleteId === item.id ? <div><p>Delete this saved project, its code and execution evidence?</p><button className="text-button" disabled={busy} onClick={() => { void remove(item.id) }}>Confirm deletion</button><button className="text-button" disabled={busy} onClick={() => setDeleteId(null)}>Keep project</button></div> : <button className="text-button" disabled={busy || ['preparing', 'running'].includes(item.status)} onClick={() => setDeleteId(item.id)}>Delete</button>}</li>)}</ul> : <p>No incident projects yet.</p>}</section>
    </>}
    {lab && !loading && <>
      {running && <p className="incident-progress" role="status">{lab.status === 'preparing' ? 'Starting the original app, verifying its checks and reproducing the controlled failure…' : 'Running the approved experiment in a fresh sandbox…'} You can reopen this project if the connection drops.</p>}
      {lab.error && <p className="inline-error" role="alert">{lab.error}</p>}
      {lab.status === 'error' && <button className="button button-secondary" onClick={() => onOpen('')}>Choose another project</button>}
      {lab.scenario && <>
        <div className="incident-workbench"><section className="incident-investigation"><h2>Investigate aloud</h2><p>Try “Send two booking requests at the same time,” or explain what you think caused the failure.</p><VoiceRecorder recordLabel="Record investigation" disabled={working || running} onBusyChange={setRecording} onRecording={transcribe} onPhaseChange={ignorePhase} onError={setError} />
          <label htmlFor="incident-instruction">Instruction or hypothesis</label><textarea id="incident-instruction" rows={5} maxLength={4000} value={instruction} disabled={busy || running} onChange={event => updateInstruction(event.target.value, original, false)} />
          {original !== null && <div className="transcript-review"><details><summary>Original transcript</summary><p>{original}</p></details><p>Check paths, identifiers, numbers and “not/nahi.” Editing wording must not change your intended technical claim.</p><label className="transcript-confirm"><input type="checkbox" checked={reviewed} disabled={busy || running} onChange={event => updateInstruction(instruction, original, event.target.checked)} />I checked the transcript and it matches what I mean.</label><button className="text-button" onClick={() => updateInstruction(instruction, null, false)}>Use as a typed instruction</button></div>}
          <details className="incident-audio-upload"><summary>Upload investigation audio</summary><input aria-label="Investigation WAV" type="file" accept=".wav" disabled={busy || running} onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; if (file) void transcribe(file) }} /></details>
          <button className="button button-primary" disabled={busy || !ready || !instruction.trim() || (original !== null && !reviewed)} onClick={() => { void plan() }}>Prepare experiment</button>
          <div className="incident-shortcuts"><button className="text-button" disabled={busy || !ready} onClick={() => { void plan('Replay the incident', true) }}>Replay incident</button><button className="text-button" disabled={busy || !ready} onClick={() => { void plan('Show the failing trace', true) }}>Show trace</button><button className="text-button" disabled={busy || !ready} onClick={() => { void plan('Test my fix', true) }}>Test my fix</button></div>
          {proposal && <section className="incident-plan" aria-label="Experiment preview"><h3>{canExecute ? 'Review the experiment' : 'Investigation response'}</h3><p>{proposal.response}</p>{proposal.experiment && <><p>{proposal.experiment.concurrent ? 'Concurrent' : 'Sequential'} requests</p><pre>{JSON.stringify(proposal.experiment.requests, null, 2)}</pre></>}{proposal.action === 'replay' && <p>{lab.scenario.reproduction.name}</p>}{proposal.action === 'test_fix' && <p>Incident replay + {lab.scenario.regressions.length} regression checks. Each starts from clean data.</p>}{proposal.citations.map((citation, index) => <details key={index}><summary>{citation.path}:{citation.line_start}–{citation.line_end}</summary><pre>{citation.quote}</pre></details>)}{canExecute && <button className="button button-primary" disabled={busy || !ready || changed || saveStatus !== 'Saved' || !catalogue?.runner_available || !catalogue.usage.remaining} onClick={() => { void execute() }}>Run approved experiment</button>}</section>}
        </section><section className="incident-code" ref={codePanel}><div className="incident-section-heading"><h2>Project code</h2><span role="status">{saveStatus}</span></div><label>File<select aria-label="Project file" value={selected} disabled={busy || running} onChange={event => setSelected(event.target.value)}>{Object.keys(files).map(name => <option key={name}>{name}</option>)}</select></label>{selected in files && <CodeEditor code={files[selected]} startLine={1} label="Incident project code" maxLength={32768} disabled={busy || running} onChange={edit} />}<button className="text-button" disabled={busy || running || saveStatus === 'Saved'} onClick={() => { void save().catch(() => {}) }}>Save patch</button><p className="field-note">Code edits invalidate previous repair verification. “Test my fix” runs HTTP and database checks; an AI opinion alone cannot pass a repair.</p>
          {lab.solved && !changed ? <p className="incident-success" role="status">Repair verified against the incident and all regression checks.</p> : lab.latest && (!lab.current_execution || changed) ? <p className="field-note">Earlier execution belongs to a previous patch. Test the current code before drawing a conclusion.</p> : null}
        </section></div>
        <div ref={evidencePanel} tabIndex={-1}>{evidence && <ExecutionEvidence key={evidence.id || 'initial'} evidence={evidence} title={lab.latest ? 'Latest execution' : 'Reproduced incident'} />}</div>
        <details className="incident-reference"><summary>Original app: baseline verification</summary>{lab.baseline && <ExecutionEvidence evidence={lab.baseline} title="Uploaded original" />}</details>
        {lab.conversation.length > 1 && <details className="incident-conversation"><summary>Investigation conversation · {lab.conversation.length} turns</summary>{lab.conversation.map(turn => <article key={turn.id}><h3>Your investigation</h3><p>{turn.instruction}</p><h3>RepoViva</h3><p>{turn.response}</p></article>)}</details>}
      </>}
    </>}
  </main>
}
