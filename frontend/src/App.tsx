import { useCallback, useEffect, useState } from 'react'
import VoiceRecorder, { type RecordingPhase } from './components/VoiceRecorder'
import SourceUpload, { type SourceDocument } from './components/SourceUpload'
import Icon from './components/Icon'
import ActivityOrb from './components/ActivityOrb'
import type { OrbState } from 'thinking-orbs'
import { useAuth } from './auth/context'
import AccountControls from './auth/AccountControls'
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
  return (
    typeof evidence.path === 'string' &&
    (evidence.citation_type === 'page'
      ? Number.isInteger(evidence.page)
      : Number.isInteger(evidence.start_line) &&
        Number.isInteger(evidence.end_line)) &&
    Array.isArray(evidence.content) &&
    evidence.content.every((line) => typeof line === 'string')
  )
}
function isQuestionResponse(value: unknown): value is QuestionResponse {
  if (!value || typeof value !== 'object') return false
  const turn = value as QuestionResponse
  return (
    typeof turn.turn_id === 'string' &&
    !!turn.turn_id.trim() &&
    typeof turn.question === 'string' &&
    !!turn.question.trim() &&
    isEvidence(turn.evidence) &&
    typeof turn.source_id === 'string' &&
    Array.isArray(turn.evidence_snippets) &&
    turn.evidence_snippets.length > 0 &&
    turn.evidence_snippets.every(isEvidence)
  )
}
function isAnswerResponse(value: unknown): value is AnswerResponse {
  if (!isQuestionResponse(value)) return false
  const response = value as AnswerResponse
  return (
    typeof response.reference_answer === 'string' &&
    !!response.reference_answer.trim() &&
    !!response.score &&
    Number.isFinite(response.score.earned) &&
    Number.isFinite(response.score.possible) &&
    (response.score.percentage === null ||
      (Number.isFinite(response.score.percentage) &&
        response.score.percentage >= 0 &&
        response.score.percentage <= 100)) &&
    Array.isArray(response.criteria) &&
    response.criteria.length > 0 &&
    response.criteria.every(
      (item) =>
        item &&
        typeof item.description === 'string' &&
        ['met', 'partial', 'missed', 'contradicted', 'unverified'].includes(
          item.status,
        ) &&
        typeof item.explanation === 'string' &&
        typeof item.quote === 'string' &&
        isEvidence(item.evidence),
    ) &&
    Array.isArray(response.claims) &&
    response.claims.every(
      (claim) =>
        claim &&
        typeof claim.claim === 'string' &&
        ['supported', 'contradicted', 'unverified'].includes(claim.label) &&
        typeof claim.explanation === 'string' &&
        (typeof claim.quote === 'string' || claim.quote === null),
    )
  )
}
interface SavedPractice {
  questions: QuestionResponse[]
  results: Record<string, AnswerResponse>
  answers: Record<string, string>
}
function isSavedPractice(
  value: unknown,
  sourceId: string,
): value is SavedPractice {
  if (!value || typeof value !== 'object') return false
  const saved = value as SavedPractice
  return (
    Array.isArray(saved.questions) &&
    saved.questions.length > 0 &&
    saved.questions.every(
      (question) =>
        isQuestionResponse(question) && question.source_id === sourceId,
    ) &&
    !!saved.results &&
    typeof saved.results === 'object' &&
    Object.entries(saved.results).every(
      ([id, answer]) =>
        isAnswerResponse(answer) &&
        answer.turn_id === id &&
        saved.questions.some((question) => question.turn_id === id),
    ) &&
    !!saved.answers &&
    typeof saved.answers === 'object' &&
    Object.values(saved.answers).every((answer) => typeof answer === 'string')
  )
}
async function readResponse(response: Response): Promise<unknown> {
  let data
  try {
    data = await response.json()
  } catch {
    throw new Error('The server returned an unreadable response. Please retry.')
  }
  if (!response.ok) {
    throw new Error(
      typeof data?.error === 'string'
        ? data.error
        : 'The request failed. Please retry.',
    )
  }
  return data
}
// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  const { apiFetch } = useAuth()
  const [backendReady, setBackendReady] = useState(false)
  const [backendError, setBackendError] = useState('')
  const [backendAttempt, setBackendAttempt] = useState(0)
  const [loadingQuestion, setLoadingQuestion] = useState(false)
  const [submittingAnswer, setSubmittingAnswer] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [recordingBusy, setRecordingBusy] = useState(false)
  const [recordingPhase, setRecordingPhase] = useState<RecordingPhase>('idle')
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
        const response = await fetch('/health', {
          cache: 'no-store',
          signal: controller.signal,
        })
        const data = await response.json()
        if (!response.ok || data.api_version !== 'study-v2') {
          throw new Error(
            'The backend is running an older version. Restart Flask with python -m backend.app, then retry the connection.',
          )
        }
        if (active) setBackendReady(true)
      } catch (error) {
        if (active)
          setBackendError(
            error instanceof Error && error.message.includes('older version')
              ? error.message
              : 'Cannot connect to the current backend. Start Flask, then retry the connection.',
          )
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void checkBackend()
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [backendAttempt])
  const handleSourceChange = useCallback((source: SourceDocument | null) => {
    setActiveSource(source)
    setRecordingPhase('idle')
    setTurn(null)
    setQuestionSet([])
    setResults({})
    setQuestionIndex(0)
    setAnswer('')
    setFeedback(null)
    setError(null)
    setTranscriptionNotice('')
    if (source?.saved_practice) {
      if (!isSavedPractice(source.saved_practice, source.source_id)) {
        setError(
          'Your material was restored, but the saved practice could not be read. Generate a new set to continue.',
        )
        return
      }
      const saved = source.saved_practice
      const unanswered = saved.questions.findIndex(
        (question) => !saved.results[question.turn_id],
      )
      const index = unanswered >= 0 ? unanswered : saved.questions.length - 1
      const question = saved.questions[index]
      setQuestionSet(saved.questions)
      setQuestionIndex(index)
      setTurn(question)
      setResults(saved.results)
      setFeedback(saved.results[question.turn_id] ?? null)
      setAnswer(saved.answers[question.turn_id] ?? '')
    }
  }, [])
  // 1. Generate Question
  async function generateQuestion() {
    if (
      !backendReady ||
      !activeSource ||
      loadingQuestion ||
      submittingAnswer ||
      transcribing ||
      recordingBusy ||
      uploadingSource
    )
      return
    setLoadingQuestion(true)
    setError(null)
    setTranscriptionNotice('')
    try {
      const res = await apiFetch('/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: activeSource.source_id, count: 3 }),
      })
      const data = await readResponse(res)
      if (
        !data ||
        typeof data !== 'object' ||
        !('questions' in data) ||
        !Array.isArray(data.questions) ||
        !data.questions.length ||
        !data.questions.every(isQuestionResponse)
      ) {
        throw new Error(
          'The backend did not return the current question format. Restart Flask and reload, then upload your file again.',
        )
      }
      if (
        !data.questions.every(
          (item) => item.source_id === activeSource.source_id,
        )
      ) {
        throw new Error(
          'The backend used a different source. Restart Flask, reload, and upload your material again.',
        )
      }
      setQuestionSet(data.questions)
      setQuestionIndex(0)
      setResults({})
      setTurn(data.questions[0])
      setFeedback(null)
      setAnswer('')
    } catch (error) {
      setError(
        error instanceof TypeError
          ? 'Could not reach the server. Please retry.'
          : error instanceof Error
            ? error.message
            : 'Could not generate a question. Please retry.',
      )
    } finally {
      setLoadingQuestion(false)
    }
  }
  // 2. Submit Answer
  async function submitAnswer(e: React.FormEvent) {
    e.preventDefault()
    if (
      !turn ||
      !answer.trim() ||
      submittingAnswer ||
      loadingQuestion ||
      transcribing ||
      recordingBusy ||
      uploadingSource
    )
      return
    setSubmittingAnswer(true)
    setError(null)
    setFeedback(null)
    setTranscriptionNotice('')
    try {
      const res = await apiFetch('/answers', {
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
      setError(
        error instanceof TypeError
          ? 'Could not reach the server. Your answer is preserved; please retry.'
          : error instanceof Error
            ? error.message
            : 'Evaluation failed. Your answer is preserved; please retry.',
      )
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
    if (
      !file ||
      !turn ||
      loadingQuestion ||
      submittingAnswer ||
      transcribing ||
      recordingBusy ||
      uploadingSource
    )
      return
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
      setError(
        'Choose a non-empty WAV file up to 10 MiB. Your current answer has been kept.',
      )
      return
    }
    setTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('audio_file', file)
      const response = await apiFetch('/transcriptions', {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(70_000),
      })
      const data = await readResponse(response)
      if (
        !data ||
        typeof data !== 'object' ||
        !('transcript' in data) ||
        typeof data.transcript !== 'string' ||
        !data.transcript.trim()
      ) {
        throw new Error(
          'The server returned no usable transcript. Please try another recording.',
        )
      }
      const transcript = data.transcript.trim()
      if (transcript.length > 4000) {
        throw new Error(
          'The transcript exceeds the 4,000-character answer limit. Try a shorter recording.',
        )
      }
      setAnswer(transcript)
      setFeedback(null)
      setTranscriptionNotice(
        'Transcript loaded. Review or edit it, then click Submit Answer.',
      )
    } catch (error) {
      const message =
        error instanceof Error && error.name === 'TimeoutError'
          ? 'Transcription timed out. Please retry.'
          : error instanceof TypeError
            ? 'Could not reach the transcription service. Please retry.'
            : error instanceof Error
              ? error.message
              : 'Transcription failed. Please retry.'
      setError(`${message} Your current answer has been kept.`)
    } finally {
      setTranscribing(false)
    }
  }
  const completed = Object.values(results)
  const totalEarned = completed.reduce(
    (sum, item) => sum + item.score.earned,
    0,
  )
  const totalPossible = completed.reduce(
    (sum, item) => sum + item.score.possible,
    0,
  )
  const evidenceList =
    feedback?.evidence_snippets ?? turn?.evidence_snippets ?? []
  const busy =
    loadingQuestion ||
    submittingAnswer ||
    transcribing ||
    recordingBusy ||
    uploadingSource
  const evidenceLocation = (evidence: Evidence) =>
    evidence.citation_type === 'page'
      ? `Page ${evidence.page}`
      : `Lines ${evidence.start_line}–${evidence.end_line}`
  const reviewStatus = (status: GradedCriterion['status']) =>
    ({
      met: 'Met',
      partial: 'Partly met',
      missed: 'Missed',
      contradicted: 'Contradicted',
      unverified: 'Unverified',
    })[status]
  type Activity = {
    state: OrbState
    active: boolean
    title: string
    detail: string
  }
  const inProgress: Activity | null =
    !backendReady && !backendError
      ? {
          state: 'connecting',
          active: true,
          title: 'Connecting your workspace',
          detail: 'Getting the study tools ready.',
        }
      : loadingQuestion
        ? {
            state: 'composing',
            active: true,
            title: 'Building your questions',
            detail: 'Turning your material into a source-backed practice set.',
          }
        : submittingAnswer
          ? {
              state: 'solving',
              active: true,
              title: 'Reviewing your answer',
              detail:
                'Comparing your meaning with the reference and original evidence.',
            }
          : recordingPhase === 'permission'
            ? {
                state: 'connecting',
                active: true,
                title: 'Waiting for your microphone',
                detail: 'Allow microphone access to record your answer.',
              }
            : recordingPhase === 'recording'
              ? {
                  state: 'listening',
                  active: true,
                  title: 'Listening to your answer',
                  detail:
                    'Stop when you are ready. You can edit the transcript next.',
                }
              : transcribing || recordingPhase === 'processing'
                ? {
                    state: 'weaving',
                    active: true,
                    title: 'Preparing your transcript',
                    detail: 'Turning your recording into words you can review.',
                  }
                : uploadingSource && backendReady
                  ? {
                      state: 'searching',
                      active: true,
                      title: 'Reading your material',
                      detail:
                        'Extracting the text that will support your questions.',
                    }
                  : null
  const activity: Activity =
    inProgress ??
    (error || backendError
      ? {
          state: 'breathing',
          active: false,
          title: 'Needs your attention',
          detail: 'Check the message above, then try again.',
        }
      : feedback
        ? {
            state: 'breathing',
            active: false,
            title: 'Your review is ready',
            detail:
              'See what matched, what was missing, and the source behind it.',
          }
        : turn
          ? {
              state: 'breathing',
              active: false,
              title: 'Your turn',
              detail:
                'Say it out loud or write it down. Submit when you are ready.',
            }
          : activeSource
            ? {
                state: 'breathing',
                active: false,
                title: 'Your material is ready',
                detail:
                  'Generate your questions when you are ready to practice.',
              }
            : {
                state: 'breathing',
                active: false,
                title: 'Ready for your material',
                detail:
                  'Upload a PDF or source file to build your practice session.',
              })
  const workspaceHeading = (
    <div className={`workspace-heading ${!turn ? 'study-introduction' : ''}`}>
      <div>
        <h1>
          {turn ? (
            'Put it in your own words.'
          ) : (
            <>
              <span>Know it.</span>
              <span>Explain it.</span>
            </>
          )}
        </h1>
        <p>
          {turn
            ? 'Take your time. Review your answer, then see how it holds up.'
            : 'Practice with questions built from your notes. Explain them in your own words, then check the evidence.'}
        </p>
      </div>
      {turn && (
        <div
          className="set-progress"
          aria-label={`${completed.length} of ${questionSet.length} questions reviewed`}
        >
          <span>
            {completed.length}
            <span className="muted"> / {questionSet.length} reviewed</span>
          </span>
          <div className="progress-segments">
            {questionSet.map((question) => (
              <span
                key={question.turn_id}
                className={
                  results[question.turn_id]
                    ? 'is-complete'
                    : question.turn_id === turn.turn_id
                      ? 'is-current'
                      : ''
                }
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
  const generationButton = (
    <button
      type="button"
      aria-label={turn ? 'Generate new set' : undefined}
      aria-busy={loadingQuestion}
      className="button button-primary"
      onClick={generateQuestion}
      disabled={!backendReady || !activeSource || busy}
    >
      {loadingQuestion ? (
        <>
          <ActivityOrb state="composing" />
          Generating your questions…
        </>
      ) : (
        <>
          {turn ? (
            <>
              <span className="action-label-full">Generate new set</span>
              <span className="action-label-compact">New set</span>
            </>
          ) : (
            'Generate questions'
          )}
          <Icon name="arrow" size={18} />
        </>
      )}
    </button>
  )
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to study workspace
      </a>
      <header className="app-header">
        <a className="brand" href="#workspace" aria-label="RepoViva study desk">
          <span className="brand-mark">
            <Icon name="book" size={22} />
          </span>
          <span>
            RepoViva<span className="brand-period">.</span>
          </span>
        </a>
        <nav className="workspace-nav">
          <a
            href="#workspace"
            className="nav-item is-active"
            aria-current="page"
          >
            <Icon name="desk" />
            Study desk
          </a>
          <a
            href="#source-material"
            className="nav-item"
            aria-label="Your material"
          >
            <Icon name="file" />
            <span className="nav-label-full">Your material</span>
            <span className="nav-label-compact" aria-hidden="true">
              Material
            </span>
          </a>
          <button
            type="button"
            className="nav-item"
            disabled={!feedback}
            aria-label="Answer review"
            onClick={() =>
              document
                .getElementById('review')
                ?.scrollIntoView({ block: 'start' })
            }
          >
            <Icon name="review" />
            <span className="nav-label-full">Answer review</span>
            <span className="nav-label-compact" aria-hidden="true">
              Review
            </span>
          </button>
        </nav>
        <div className="header-session">
          <div className="connection" role="status">
            <span className={`status-dot ${backendReady ? 'is-ready' : ''}`} />
            {backendReady
              ? 'Ready to practice'
              : backendError
                ? 'Backend unavailable'
                : 'Connecting…'}
          </div>
          <AccountControls />
        </div>
      </header>
      <main
        id="workspace"
        className={`workspace ${turn ? 'workspace-practice' : 'workspace-welcome'}`}
        tabIndex={-1}
      >
        {turn && workspaceHeading}
        {(error || backendError) && (
          <div role="alert" className="error-banner">
            <Icon name="info" />
            <div>
              <strong>Let’s try that again.</strong>
              <p>{error || backendError}</p>
              {backendError && (
                <button
                  className="text-button"
                  type="button"
                  onClick={() => {
                    setBackendError('')
                    setBackendReady(false)
                    setBackendAttempt((value) => value + 1)
                  }}
                >
                  Retry connection <Icon name="refresh" size={15} />
                </button>
              )}
            </div>
          </div>
        )}
        <div className={`preparation-grid ${turn ? 'has-questions' : ''}`}>
          {!turn && workspaceHeading}
          <div className="material-area" id="source-material">
            {backendReady ? (
              <SourceUpload
                compact={!!turn}
                practiceAction={turn ? generationButton : undefined}
                disabled={
                  loadingQuestion ||
                  submittingAnswer ||
                  transcribing ||
                  recordingBusy
                }
                onBusyChange={setUploadingSource}
                onSourceChange={handleSourceChange}
              />
            ) : (
              <section
                className="material-panel connection-panel"
                aria-label="Material upload"
              >
                <h2>Your material starts here.</h2>
                <p>
                  {backendError
                    ? 'Reconnect to the backend to upload your material.'
                    : 'Getting your workspace ready…'}
                </p>
                <div className="skeleton-line" />
                <div className="skeleton-line short" />
              </section>
            )}
          </div>
          {!turn && (
            <>
              <div className="start-action">
                {generationButton}
                <p className="start-hint">
                  {activeSource
                    ? 'Reference answers stay hidden until you submit.'
                    : 'Upload your material to start. Up to 3 questions per set.'}
                </p>
              </div>
              <section
                className="start-panel session-console"
                aria-labelledby="session-heading"
              >
                <div className="session-console-heading">
                  <h2 id="session-heading">Your practice session</h2>
                  <Icon name="mic" size={20} />
                </div>
                <div
                  className="orb-stage"
                  role="status"
                  aria-live="polite"
                  aria-atomic="true"
                >
                  <ActivityOrb
                    size={64}
                    state={activity.state}
                    active={activity.active}
                  />
                  <strong>{activity.title}</strong>
                  <p>{activity.detail}</p>
                </div>
                <dl className="session-facts">
                  <div>
                    <dt>Material</dt>
                    <dd>
                      {activeSource ? activeSource.filename : 'Awaiting upload'}
                    </dd>
                  </div>
                  <div>
                    <dt>Evidence</dt>
                    <dd>
                      {activeSource
                        ? `${activeSource.snippet_count} extracted ${activeSource.snippet_count === 1 ? 'snippet' : 'snippets'}`
                        : 'From your file'}
                    </dd>
                  </div>
                  <div>
                    <dt>Answer format</dt>
                    <dd>Voice or text</dd>
                  </div>
                </dl>
                <ol className="practice-steps">
                  <li>
                    <span>1</span>
                    <div>
                      <strong>Make it a question.</strong>
                      <p>AI builds a set from your material.</p>
                    </div>
                  </li>
                  <li>
                    <span>2</span>
                    <div>
                      <strong>Put it in your words.</strong>
                      <p>Record, type, and refine your answer.</p>
                    </div>
                  </li>
                  <li>
                    <span>3</span>
                    <div>
                      <strong>See what holds up.</strong>
                      <p>Review your score and original evidence.</p>
                    </div>
                  </li>
                </ol>
              </section>
            </>
          )}
        </div>
        {turn && (
          <div className="practice-grid">
            <div className="practice-column">
              <section
                className="question-panel"
                aria-labelledby="question-heading"
              >
                <div className="question-meta">
                  <span>
                    Question {questionIndex + 1} of {questionSet.length}
                  </span>
                  <span
                    className="question-activity"
                    role="status"
                    aria-live="polite"
                  >
                    <ActivityOrb
                      state={activity.state}
                      active={activity.active}
                    />
                    <span>{activity.title}</span>
                  </span>
                </div>
                <h2 id="question-heading">{turn.question}</h2>
                <p className="source-caption">
                  <Icon name="file" size={15} />
                  <span>
                    {turn.evidence.path}{' '}
                    <span className="muted">
                      · {evidenceLocation(turn.evidence)}
                    </span>
                  </span>
                </p>
              </section>
              <section
                className="answer-panel"
                aria-labelledby="answer-heading"
              >
                <form onSubmit={submitAnswer}>
                  <div className="section-heading">
                    <h2 id="answer-heading">Your answer</h2>
                    <span>Make it yours.</span>
                  </div>
                  <VoiceRecorder
                    key={turn.turn_id}
                    disabled={
                      loadingQuestion ||
                      submittingAnswer ||
                      transcribing ||
                      uploadingSource
                    }
                    onBusyChange={setRecordingBusy}
                    onPhaseChange={setRecordingPhase}
                    onRecording={transcribeFile}
                    onError={(message) => {
                      setError(message)
                      setTranscriptionNotice('')
                    }}
                  />
                  <label className="sr-only" htmlFor="answer">
                    Your answer
                  </label>
                  <textarea
                    id="answer"
                    aria-describedby="answer-help answer-count"
                    value={answer}
                    onChange={(e) => {
                      setAnswer(e.target.value)
                      setFeedback(null)
                    }}
                    disabled={
                      submittingAnswer ||
                      loadingQuestion ||
                      transcribing ||
                      recordingBusy ||
                      uploadingSource
                    }
                    placeholder="Explain it the way you understand it…"
                    rows={6}
                    maxLength={4000}
                  />
                  <div className="answer-draft-meta">
                    <span id="answer-help">
                      Type here, or edit your voice transcript.
                    </span>
                    <span id="answer-count">
                      {answer.length.toLocaleString()} / 4,000
                    </span>
                  </div>
                  <details className="audio-upload">
                    <summary>
                      <Icon name="upload" size={16} />
                      Use an audio file instead
                    </summary>
                    <div className="audio-upload-content">
                      <label htmlFor="audio-file">Upload audio (WAV)</label>
                      <input
                        id="audio-file"
                        type="file"
                        accept=".wav,audio/wav,audio/x-wav"
                        onChange={uploadAudio}
                        disabled={busy}
                        aria-describedby="audio-help"
                      />
                      <p id="audio-help">
                        Up to 60 seconds and 10 MiB. Gnani Prisma transcribes
                        the audio and replaces your draft. Review it before
                        submitting.
                      </p>
                    </div>
                  </details>
                  <p role="status" className="transcript-status">
                    {transcribing
                      ? 'Transcribing your recording…'
                      : transcriptionNotice}
                  </p>
                  <div className="answer-submit-row">
                    <p>Checked against your uploaded material.</p>
                    <button
                      type="submit"
                      aria-busy={submittingAnswer}
                      className="button button-primary"
                      disabled={busy || !answer.trim()}
                    >
                      {submittingAnswer ? (
                        <>
                          <ActivityOrb state="solving" />
                          Reviewing your answer…
                        </>
                      ) : (
                        <>
                          Submit Answer
                          <Icon name="arrow" size={17} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </section>
              {feedback && (
                <section
                  id="review"
                  className="review-panel"
                  aria-labelledby="review-heading"
                >
                  <div className="review-topline">
                    <div>
                      <h2 id="review-heading">Answer review</h2>
                      <p>Here’s what your material supports.</p>
                    </div>
                    <div className="score" aria-label="Practice score">
                      <strong>
                        {feedback.score.percentage === null
                          ? '—'
                          : `${feedback.score.percentage}%`}
                      </strong>
                      <span>
                        {feedback.score.percentage === null
                          ? 'Insufficient evidence'
                          : `${feedback.score.earned} / ${feedback.score.possible} points`}
                      </span>
                    </div>
                  </div>
                  {feedback.score.excluded_criteria > 0 && (
                    <p className="review-note">
                      {feedback.score.excluded_criteria} criteria excluded
                      because source evidence is insufficient.
                    </p>
                  )}
                  <ul className="criteria-list">
                    {feedback.criteria.map((criterion) => (
                      <li key={criterion.id}>
                        <div className="criterion-heading">
                          <Icon
                            name={
                              criterion.status === 'met'
                                ? 'check'
                                : criterion.status === 'contradicted' ||
                                    criterion.status === 'missed'
                                  ? 'close'
                                  : 'minus'
                            }
                            size={18}
                          />
                          <strong>{criterion.description}</strong>
                          <span
                            className={`verdict verdict-${criterion.status}`}
                          >
                            {reviewStatus(criterion.status)} ·{' '}
                            {criterion.points}/{criterion.max_points}
                          </span>
                        </div>
                        <p>{criterion.explanation}</p>
                        <details className="criterion-evidence">
                          <summary>
                            View evidence{' '}
                            <span>
                              {criterion.evidence.path} ·{' '}
                              {evidenceLocation(criterion.evidence)}
                            </span>
                          </summary>
                          <pre>{criterion.quote}</pre>
                        </details>
                      </li>
                    ))}
                  </ul>
                  <details className="reference-answer">
                    <summary>
                      AI reference answer
                      <Icon name="chevron" size={16} />
                    </summary>
                    <p>{feedback.reference_answer}</p>
                  </details>
                  <details className="claim-details">
                    <summary>
                      Evidence check{' '}
                      <span>
                        {feedback.claims.length} factual{' '}
                        {feedback.claims.length === 1 ? 'claim' : 'claims'}
                      </span>
                    </summary>
                    {feedback.claims.length === 0 ? (
                      <p>
                        No distinct factual claims could be evaluated from your
                        response.
                      </p>
                    ) : (
                      feedback.claims.map((claim, idx) => (
                        <div className="claim" key={idx}>
                          <div className="claim-heading">
                            <span className={`verdict verdict-${claim.label}`}>
                              {claim.label}
                            </span>
                            <strong>{claim.claim}</strong>
                          </div>
                          <p>{claim.explanation}</p>
                          {claim.quote && <pre>{claim.quote}</pre>}
                        </div>
                      ))
                    )}
                  </details>
                  <div className="review-footer">
                    <p>
                      {completed.length} of {questionSet.length} reviewed
                      {totalPossible > 0
                        ? ` · Set score so far: ${Math.round((100 * totalEarned) / totalPossible)}%`
                        : ''}
                    </p>
                    {questionIndex + 1 < questionSet.length ? (
                      <button
                        type="button"
                        className="button button-primary"
                        disabled={busy}
                        onClick={nextQuestion}
                      >
                        Next question
                        <Icon name="arrow" size={17} />
                      </button>
                    ) : (
                      <span className="set-complete">
                        <Icon name="check" size={17} />
                        Set complete
                      </span>
                    )}
                  </div>
                  <p className="assessment-note">
                    AI-assisted practice feedback. Check the evidence when a
                    judgment seems off.
                  </p>
                </section>
              )}
            </div>
            <aside
              className="evidence-panel"
              aria-labelledby="evidence-heading"
            >
              <div className="evidence-heading">
                <h2 id="evidence-heading">
                  <Icon name="book" size={18} />
                  Source evidence
                </h2>
                <button
                  type="button"
                  className="text-button"
                  aria-expanded={showEvidence}
                  aria-controls="source-evidence"
                  onClick={() => setShowEvidence((value) => !value)}
                >
                  {showEvidence ? 'Hide' : 'Show'}
                </button>
              </div>
              <p className="evidence-intro">
                The original text behind your questions.
              </p>
              {showEvidence && (
                <div id="source-evidence" className="evidence-sections">
                  {evidenceList.map((evidence, section) => (
                    <section
                      key={evidence.id ?? section}
                      className="evidence-section"
                    >
                      <div className="evidence-file">
                        <span>{evidence.path}</span>
                        <span>{evidenceLocation(evidence)}</span>
                      </div>
                      <div className="source-lines">
                        {evidence.content.map((line, idx) => (
                          <div key={idx} className="source-line">
                            {evidence.citation_type !== 'page' && (
                              <span className="line-number">
                                {(evidence.start_line ?? 1) + idx}
                              </span>
                            )}
                            <span>{line || ' '}</span>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              )}
              <p className="evidence-footnote">
                <Icon name="info" size={14} />
                <span>
                  {turn.evidence.citation_type === 'page'
                    ? 'PDF formatting can affect extraction. Check tables and equations against the original.'
                    : 'Original lines are preserved, including blank lines and indentation.'}
                </span>
              </p>
            </aside>
          </div>
        )}
        <footer className="workspace-footer">
          <span>Made for understanding.</span>
          <span>Questions from your material. Answers in your words.</span>
        </footer>
      </main>
    </div>
  )
}
