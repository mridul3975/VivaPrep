import { useCallback, useEffect, useState } from 'react'
import VoiceRecorder from './components/VoiceRecorder'
import SourceUpload, { type SourceDocument } from './components/SourceUpload'
import './index.css'

// ── Types ──────────────────────────────────────────────────────────────────
interface Evidence {
  id?: string
  path: string
  start_line: number | null
  end_line: number | null
  citation_type?: 'lines' | 'page'
  page?: number | null
  content: string[]
}

interface QuestionResponse {
  turn_id: string
  question: string
  evidence: Evidence
  source_id?: string | null
  evidence_snippets: Evidence[]
}

interface Score {
  earned: number
  possible: number
  percentage: number | null
  excluded_criteria: number
}

interface GradedCriterion {
  id: string
  description: string
  status: 'met' | 'partial' | 'missed' | 'contradicted' | 'unverified'
  points: number
  max_points: number
  explanation: string
  quote: string
  evidence: Evidence
}

interface Claim {
  claim: string
  label: 'supported' | 'contradicted' | 'unverified'
  explanation: string
  quote: string | null
}

interface AnswerResponse {
  turn_id: string
  question: string
  claims: Claim[]
  evidence: Evidence
  source_id: string
  evidence_snippets: Evidence[]
  score: Score
  criteria: GradedCriterion[]
  reference_answer: string
}

function isEvidence(value: unknown): value is Evidence {
  if (!value || typeof value !== 'object') return false
  const evidence = value as Evidence
  return typeof evidence.path === 'string'
    && (evidence.citation_type === 'page' ? Number.isInteger(evidence.page)
      : Number.isInteger(evidence.start_line) && Number.isInteger(evidence.end_line))
    && Array.isArray(evidence.content)
    && evidence.content.every((line) => typeof line === 'string')
}

function isQuestionResponse(value: unknown): value is QuestionResponse {
  if (!value || typeof value !== 'object') return false
  const turn = value as QuestionResponse
  return typeof turn.turn_id === 'string' && !!turn.turn_id.trim()
    && typeof turn.question === 'string' && !!turn.question.trim()
    && isEvidence(turn.evidence)
    && typeof turn.source_id === 'string'
    && Array.isArray(turn.evidence_snippets) && turn.evidence_snippets.length > 0
    && turn.evidence_snippets.every(isEvidence)
}

function isAnswerResponse(value: unknown): value is AnswerResponse {
  if (!isQuestionResponse(value)) return false
  const response = value as AnswerResponse
  return typeof response.reference_answer === 'string' && !!response.reference_answer.trim()
    && !!response.score && Number.isFinite(response.score.earned) && Number.isFinite(response.score.possible)
    && (response.score.percentage === null || (Number.isFinite(response.score.percentage) && response.score.percentage >= 0 && response.score.percentage <= 100))
    && Array.isArray(response.criteria) && response.criteria.length > 0
    && response.criteria.every((item) => item && typeof item.description === 'string'
      && ['met', 'partial', 'missed', 'contradicted', 'unverified'].includes(item.status)
      && typeof item.explanation === 'string' && typeof item.quote === 'string' && isEvidence(item.evidence))
    && Array.isArray(response.claims) && response.claims.every((claim) =>
    claim && typeof claim.claim === 'string'
    && ['supported', 'contradicted', 'unverified'].includes(claim.label)
    && typeof claim.explanation === 'string'
    && (typeof claim.quote === 'string' || claim.quote === null))
}

async function readResponse(response: Response): Promise<unknown> {
  let data
  try {
    data = await response.json()
  } catch {
    throw new Error('The server returned an unreadable response. Please retry.')
  }
  if (!response.ok) {
    throw new Error(typeof data?.error === 'string' ? data.error : 'The request failed. Please retry.')
  }
  return data
}

// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  const [backendReady, setBackendReady] = useState(false)
  const [backendError, setBackendError] = useState('')
  const [backendAttempt, setBackendAttempt] = useState(0)
  const [loadingQuestion, setLoadingQuestion] = useState(false)
  const [submittingAnswer, setSubmittingAnswer] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [recordingBusy, setRecordingBusy] = useState(false)
  const [uploadingSource, setUploadingSource] = useState(true)
  const [activeSource, setActiveSource] = useState<SourceDocument | null>(null)
  const [transcriptionNotice, setTranscriptionNotice] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [turn, setTurn] = useState<QuestionResponse | null>(null)
  const [questionSet, setQuestionSet] = useState<QuestionResponse[]>([])
  const [questionIndex, setQuestionIndex] = useState(0)
  const [results, setResults] = useState<Record<string, AnswerResponse>>({})
  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)
  const [showEvidence, setShowEvidence] = useState(true)

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 8000)
    async function checkBackend() {
      try {
        const response = await fetch('/health', { cache: 'no-store', signal: controller.signal })
        const data = await response.json()
        if (!response.ok || data.api_version !== 'study-v2') {
          throw new Error('The backend is running an older version. Restart Flask with python -m backend.app, then retry the connection.')
        }
        if (active) setBackendReady(true)
      } catch (error) {
        if (active) setBackendError(error instanceof Error && error.message.includes('older version')
          ? error.message : 'Cannot connect to the current backend. Start Flask, then retry the connection.')
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void checkBackend()
    return () => { active = false; controller.abort(); window.clearTimeout(timeout) }
  }, [backendAttempt])

  const handleSourceChange = useCallback((source: SourceDocument | null) => {
    setActiveSource(source)
    setTurn(null)
    setQuestionSet([])
    setResults({})
    setQuestionIndex(0)
    setAnswer('')
    setFeedback(null)
    setError(null)
    setTranscriptionNotice('')
  }, [])

  // 1. Generate Question
  async function generateQuestion() {
    if (!backendReady || !activeSource || loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource) return
    setLoadingQuestion(true)
    setError(null)
    setTranscriptionNotice('')

    try {
      const res = await fetch('/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: activeSource.source_id, count: 3 }),
      })
      const data = await readResponse(res)
      if (!data || typeof data !== 'object' || !('questions' in data) || !Array.isArray(data.questions)
        || !data.questions.length || !data.questions.every(isQuestionResponse)) {
        throw new Error('The backend did not return the current question format. Restart Flask and reload, then upload your file again.')
      }
      if (!data.questions.every((item) => item.source_id === activeSource.source_id)) {
        throw new Error('The backend used a different source. Restart Flask, reload, and upload your material again.')
      }
      setQuestionSet(data.questions)
      setQuestionIndex(0)
      setResults({})
      setTurn(data.questions[0])
      setFeedback(null)
      setAnswer('')
    } catch (error) {
      setError(error instanceof TypeError ? 'Could not reach the server. Please retry.'
        : error instanceof Error ? error.message : 'Could not generate a question. Please retry.')
    } finally {
      setLoadingQuestion(false)
    }
  }

  // 2. Submit Answer
  async function submitAnswer(e: React.FormEvent) {
    e.preventDefault()
    if (!turn || !answer.trim() || submittingAnswer || loadingQuestion || transcribing || recordingBusy || uploadingSource) return

    setSubmittingAnswer(true)
    setError(null)
    setFeedback(null)
    setTranscriptionNotice('')

    try {
      const res = await fetch('/answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          turn_id: turn.turn_id,
          answer: answer.trim(),
        }),
      })

      const data = await readResponse(res)
      if (!isAnswerResponse(data) || data.turn_id !== turn.turn_id) {
        throw new Error('The server returned invalid feedback. Please retry.')
      }
      setFeedback(data)
      setResults((previous) => ({ ...previous, [data.turn_id]: data }))
    } catch (error) {
      setError(error instanceof TypeError ? 'Could not reach the server. Your answer is preserved; please retry.'
        : error instanceof Error ? error.message : 'Evaluation failed. Your answer is preserved; please retry.')
    } finally {
      setSubmittingAnswer(false)
    }
  }

  function nextQuestion() {
    if (!feedback || questionIndex + 1 >= questionSet.length) return
    const next = questionIndex + 1
    setQuestionIndex(next)
    setTurn(questionSet[next])
    setAnswer('')
    setFeedback(null)
    setError(null)
    setTranscriptionNotice('')
  }

  async function uploadAudio(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = '' // Allow retrying the same file after a failure.
    if (!file || !turn || loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource) return
    await transcribeFile(file)
  }

  async function transcribeFile(file: File) {
    setError(null)
    setTranscriptionNotice('')
    if (!file.name.toLowerCase().endsWith('.wav')) {
      setError('Choose a WAV recording. Your current answer has been kept.')
      return
    }
    if (file.size === 0 || file.size > 10 * 1024 * 1024) {
      setError('Choose a non-empty WAV file up to 10 MiB. Your current answer has been kept.')
      return
    }

    setTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('audio_file', file)
      const response = await fetch('/transcriptions', {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(70_000),
      })
      const data = await readResponse(response)
      if (!data || typeof data !== 'object' || !('transcript' in data)
        || typeof data.transcript !== 'string' || !data.transcript.trim()) {
        throw new Error('The server returned no usable transcript. Please try another recording.')
      }
      const transcript = data.transcript.trim()
      if (transcript.length > 4000) {
        throw new Error('The transcript exceeds the 4,000-character answer limit. Try a shorter recording.')
      }
      setAnswer(transcript)
      setFeedback(null)
      setTranscriptionNotice('Transcript loaded. Review or edit it, then click Submit Answer.')
    } catch (error) {
      const message = error instanceof Error && error.name === 'TimeoutError'
        ? 'Transcription timed out. Please retry.'
        : error instanceof TypeError ? 'Could not reach the transcription service. Please retry.'
        : error instanceof Error ? error.message : 'Transcription failed. Please retry.'
      setError(`${message} Your current answer has been kept.`)
    } finally {
      setTranscribing(false)
    }
  }

  // Helper for label badge styling
  function getBadgeStyle(label: Claim['label']) {
    switch (label) {
      case 'supported':
        return {
          bg: 'rgba(63, 185, 80, 0.15)',
          color: 'var(--accent)',
          border: '1px solid rgba(63, 185, 80, 0.4)',
        }
      case 'contradicted':
        return {
          bg: 'rgba(248, 81, 73, 0.15)',
          color: 'var(--warn)',
          border: '1px solid rgba(248, 81, 73, 0.4)',
        }
      case 'unverified':
      default:
        return {
          bg: 'rgba(88, 166, 255, 0.15)',
          color: 'var(--info)',
          border: '1px solid rgba(88, 166, 255, 0.4)',
        }
    }
  }

  const activeEvidence = feedback?.evidence ?? turn?.evidence
  const evidenceList = feedback?.evidence_snippets ?? turn?.evidence_snippets ?? []
  const completed = Object.values(results)
  const totalEarned = completed.reduce((sum, item) => sum + item.score.earned, 0)
  const totalPossible = completed.reduce((sum, item) => sum + item.score.possible, 0)
  const evidenceLocation = (evidence: Evidence) => evidence.citation_type === 'page'
    ? `Page ${evidence.page}` : `Lines ${evidence.start_line}–${evidence.end_line}`

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight mb-1" style={{ color: 'var(--text)' }}>
          RepoViva
        </h1>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Upload material, answer AI-generated questions, and review source-backed scores.
        </p>
      </header>

      {backendReady ? <SourceUpload disabled={loadingQuestion || submittingAnswer || transcribing || recordingBusy}
        onBusyChange={setUploadingSource} onSourceChange={handleSourceChange} />
        : !backendError && <p role="status" className="mb-6">Connecting to the backend…</p>}
      <h2 className="text-base font-semibold mb-3 break-words">
        {activeSource ? `Practice: ${activeSource.filename}` : 'Upload material to begin'}
      </h2>

      {/* 1. Generate Question Button */}
      <section className="mb-6 flex flex-wrap items-center gap-4">
        <button
          onClick={generateQuestion}
          disabled={!backendReady || !activeSource || loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource}
          className="px-5 py-2.5 rounded text-sm font-medium transition-all active:scale-[0.98]"
          style={{
            background: loadingQuestion ? 'var(--border)' : 'var(--accent)',
            color: '#0d1117',
            cursor: !backendReady || !activeSource || loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource ? 'not-allowed' : 'pointer',
          }}
        >
          {loadingQuestion ? 'Generating questions and answers…' : turn ? 'Generate new set' : 'Generate questions'}
        </button>

        {turn && (
          <span className="text-xs" style={{ color: 'var(--muted)' }}>
            Turn ID: <code className="px-1.5 py-0.5 rounded bg-[#161b22] border border-[#30363d]">{turn.turn_id.slice(0, 8)}…</code>
          </span>
        )}
      </section>

      {/* Global Error Banner */}
      {(error || backendError) && (
        <div
          role="alert"
          className="mb-6 text-sm px-4 py-3 rounded border"
          style={{ background: '#251214', color: 'var(--warn)', borderColor: '#5a1d22' }}
        >
          {error || backendError}
          {backendError && <button type="button" className="block mt-3 underline" onClick={() => {
            setBackendError(''); setBackendReady(false); setBackendAttempt((value) => value + 1)
          }}>Retry connection</button>}
        </div>
      )}

      {/* Question Card */}
      {turn && (
        <section
          className="mb-6 p-5 rounded-lg border transition-all"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs uppercase tracking-widest font-semibold" style={{ color: 'var(--muted)' }}>
              Question {questionIndex + 1} of {questionSet.length}
            </p>
            <button
              aria-expanded={showEvidence}
              aria-controls="source-evidence"
              onClick={() => setShowEvidence((prev) => !prev)}
              className="text-xs hover:underline cursor-pointer"
              style={{ color: 'var(--info)' }}
            >
              {showEvidence ? 'Hide Source Evidence' : 'Show Source Evidence'}
            </button>
          </div>

          <p className="text-base font-medium mb-3" style={{ color: 'var(--text)' }}>
            {turn.question}
          </p>

          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            Source: <span className="font-mono break-all">{turn.evidence.path}</span> ({evidenceLocation(turn.evidence)})
          </p>
        </section>
      )}

      {/* 5. Evidence Panel (Source Code Snippet) */}
      {turn && showEvidence && activeEvidence && (
        <section
          id="source-evidence"
          className="mb-6 rounded-lg border overflow-hidden"
          style={{ background: '#0a0d12', borderColor: 'var(--border)' }}
        >
          <div
            className="px-4 py-2 text-xs border-b flex flex-col sm:flex-row gap-1 justify-between sm:items-center"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--muted)' }}
          >
            <span className="min-w-0 break-all">Evidence File: <strong className="text-[#e6edf3]">{activeEvidence.path}</strong></span>
            <span className="shrink-0">{evidenceLocation(activeEvidence)}</span>
          </div>

          <div className="p-3 overflow-auto max-h-96 text-xs font-mono">
            {evidenceList.map((evidence, section) => <div key={evidence.id ?? section} className="mb-4">
              <p className="mb-2" style={{ color: 'var(--muted)' }}>{evidenceLocation(evidence)}</p>
              {evidence.content.map((line, idx) => <div key={idx} className="flex leading-5 w-max min-w-full">
                {evidence.citation_type !== 'page' && <span className="w-10 select-none text-right pr-4 shrink-0" style={{ color: 'var(--muted)' }}>{(evidence.start_line ?? 1) + idx}</span>}
                <span className="whitespace-pre text-[#c9d1d9]">{line || ' '}</span>
              </div>)}
            </div>)}
          </div>
        </section>
      )}

      {/* 2 & 3. Answer Text Area & Submit Button */}
      {turn && (
        <section
          className="mb-8 p-5 rounded-lg border"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <form onSubmit={submitAnswer}>
            <VoiceRecorder
              key={turn.turn_id}
              disabled={loadingQuestion || submittingAnswer || transcribing || uploadingSource}
              onBusyChange={setRecordingBusy}
              onRecording={transcribeFile}
              onError={(message) => { setError(message); setTranscriptionNotice('') }}
            />
            <div className="mb-5">
              <label htmlFor="audio-file" className="block text-sm font-medium mb-2">
                Upload audio (WAV)
              </label>
              <input
                id="audio-file"
                type="file"
                accept=".wav,audio/wav,audio/x-wav"
                onChange={uploadAudio}
                disabled={loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource}
                aria-describedby="audio-help"
                className="block w-full min-w-0 text-sm file:mr-3 file:rounded file:border file:border-[#30363d] file:bg-[#161b22] file:px-3 file:py-2 file:text-[#e6edf3] disabled:opacity-60"
              />
              <p id="audio-help" className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
                Up to 60 seconds and 10 MiB. Sent to Gnani Prisma for transcription.
                A successful upload replaces your draft. You can edit it before submitting.
              </p>
              <p role="status" className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>
                {transcribing ? 'Transcribing your recording…' : transcriptionNotice}
              </p>
            </div>
            <label htmlFor="answer" className="block text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: 'var(--muted)' }}>
              Your Answer
            </label>

            <textarea
              id="answer"
              aria-describedby="answer-count"
              value={answer}
              onChange={(e) => { setAnswer(e.target.value); setFeedback(null) }}
              disabled={submittingAnswer || loadingQuestion || transcribing || recordingBusy || uploadingSource}
              placeholder="Answer the question in your own words…"
              rows={4}
              maxLength={4000}
              className="w-full p-3 rounded text-sm font-mono border transition-all resize-y"
              style={{
                background: '#0d1117',
                color: 'var(--text)',
                borderColor: 'var(--border)',
              }}
            />

            <div className="mt-3 flex flex-wrap gap-3 items-center justify-between">
              <span id="answer-count" className="text-xs" style={{ color: 'var(--muted)' }}>
                {answer.length} / 4000 characters
              </span>

              <button
                type="submit"
                disabled={submittingAnswer || loadingQuestion || transcribing || recordingBusy || uploadingSource || !answer.trim()}
                className="px-5 py-2 rounded text-sm font-medium transition-all active:scale-[0.98]"
                style={{
                  background: submittingAnswer || loadingQuestion || transcribing || recordingBusy || uploadingSource || !answer.trim() ? 'var(--border)' : '#58a6ff',
                  color: '#0d1117',
                  cursor: submittingAnswer || loadingQuestion || transcribing || recordingBusy || uploadingSource || !answer.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                {submittingAnswer ? 'Evaluating Answer…' : 'Submit Answer'}
              </button>
            </div>
          </form>
        </section>
      )}

      {/* 4. Feedback Display (Claims, Verdicts, Explanations, Quotes) */}
      {feedback && (
        <section
          className="p-5 rounded-lg border"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <h2 className="text-base font-semibold mb-4" style={{ color: 'var(--text)' }}>
            Evaluation Feedback
          </h2>

          <p className="text-xl font-semibold mb-2" aria-label="Practice score">
            {feedback.score.percentage === null ? 'Not enough evidence to score' : `Score: ${feedback.score.percentage}%`}
          </p>
          <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
            {feedback.score.earned} / {feedback.score.possible} points.
            {feedback.score.excluded_criteria > 0 && ` ${feedback.score.excluded_criteria} criteria excluded because source evidence is insufficient.`}
          </p>
          <ul className="space-y-4 mb-5">
            {feedback.criteria.map((criterion) => <li key={criterion.id} className="text-sm">
              <p><strong>{criterion.description}</strong> — {criterion.status} ({criterion.points}/{criterion.max_points})</p>
              <p className="mt-1" style={{ color: 'var(--muted)' }}>{criterion.explanation}</p>
              <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>{criterion.evidence.path} · {evidenceLocation(criterion.evidence)}</p>
              <pre className="mt-1 overflow-auto text-xs p-2 rounded" style={{ background: 'var(--bg)' }}>{criterion.quote}</pre>
            </li>)}
          </ul>
          <details className="mb-5">
            <summary className="cursor-pointer text-sm font-semibold">AI reference answer</summary>
            <p className="mt-3 whitespace-pre-wrap text-sm">{feedback.reference_answer}</p>
          </details>
          {questionSet.length > 1 && <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
            Reviewed {completed.length} / {questionSet.length} questions.
            {totalPossible > 0 && ` Set score so far: ${Math.round(100 * totalEarned / totalPossible)}%.`}
          </p>}
          {questionIndex + 1 < questionSet.length && <button type="button" className="px-4 py-2 rounded border border-[#30363d] mb-5 disabled:opacity-50"
            disabled={loadingQuestion || submittingAnswer || transcribing || recordingBusy || uploadingSource} onClick={nextQuestion}>Next question</button>}

          {feedback.claims.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              No distinct claims could be evaluated from your response.
            </p>
          ) : (
            <div className="space-y-4">
              {feedback.claims.map((claim, idx) => {
                const badge = getBadgeStyle(claim.label)
                return (
                  <div
                    key={idx}
                    className="p-4 rounded border text-sm"
                    style={{ background: '#0d1117', borderColor: 'var(--border)' }}
                  >
                    {/* Claim Header & Label */}
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider"
                        style={{ background: badge.bg, color: badge.color, border: badge.border }}
                      >
                        {claim.label}
                      </span>
                      <strong className="text-[#e6edf3] break-words min-w-0">{claim.claim}</strong>
                    </div>

                    {/* Explanation */}
                    <p className="text-xs mb-3 leading-relaxed" style={{ color: '#8b949e' }}>
                      {claim.explanation}
                    </p>

                    {/* Verbatim Source Quote (if present) */}
                    {claim.quote && (
                      <div
                        className="p-2.5 rounded border text-xs font-mono"
                        style={{ background: '#161b22', borderColor: '#30363d' }}
                      >
                        <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--muted)' }}>
                          Cited Source Evidence:
                        </p>
                        <pre className="whitespace-pre-wrap text-[#c9d1d9]">{claim.quote}</pre>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </section>
      )}
    </main>
  )
}
