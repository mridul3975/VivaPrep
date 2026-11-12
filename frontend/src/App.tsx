import { useCallback, useEffect, useRef, useState } from 'react'
import VoiceRecorder, { type RecordingPhase } from './components/VoiceRecorder'
import DebugPage from './pages/DebugPage'
import SourceUpload, { type SourceDocument } from './components/SourceUpload'
import Icon from './components/Icon'
import ActivityOrb from './components/ActivityOrb'
import UiloraEffect from './components/UiloraEffect'
import type { OrbState } from 'thinking-orbs'
import { useAuth } from './auth/context'
import AccountControls from './auth/AccountControls'
import GuestAccess from './auth/GuestAccess'
import TranscriptReview, { type SpeechReview } from './components/TranscriptReview'
import HistoryPage from './pages/HistoryPage'
import ProfilePage from './pages/ProfilePage'
import { useNavigation, type Route } from './navigation'
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
  parent_turn_id?: string | null
  parent_answer?: string | null
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
  speech_review?: SpeechReview
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
  speech_reviews?: Record<string, SpeechReview>
  practice_id?: string
  drafts?: Record<string, string>
  resume_turn_id?: string | null
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
  const { apiFetch, storageMode } = useAuth()
  const { route, navigate, back, depth } = useNavigation()
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
  const [storedTurn, setTurn] = useState<QuestionResponse | null>(null)
  const turn = route.page === 'setup' ? null : storedTurn
  const [questionSet, setQuestionSet] = useState<QuestionResponse[]>([])
  const [questionIndex, setQuestionIndex] = useState(0)
  const [results, setResults] = useState<Record<string, AnswerResponse>>({})
  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)
  const [speechReviews, setSpeechReviews] = useState<Record<string, SpeechReview>>({})
  const speechReview = storedTurn ? speechReviews[storedTurn.turn_id] : undefined
  const [showEvidence, setShowEvidence] = useState(true)
  const [sourceOverride, setSourceOverride] = useState<SourceDocument | null | undefined>()
  const [draftError, setDraftError] = useState('')
  const [navigationError, setNavigationError] = useState('')
  const [debugBusy, setDebugBusy] = useState(false)
  const debugSave = useRef<(() => Promise<void>) | null>(null)
  const registerDebugSave = useCallback((handler: (() => Promise<void>) | null) => { debugSave.current = handler }, [])
  const draft = useRef<{ turnId: string; answer: string; dirty: boolean; speech_review?: { receipt_id: string; reviewed: boolean } } | null>(null)
  const draftChain = useRef<Promise<void>>(Promise.resolve())
  const saveDraft = useCallback(async () => {
    const pending = draft.current
    if (!pending?.dirty || storageMode !== 'postgresql') return draftChain.current
    pending.dirty = false
    const operation = draftChain.current.catch(() => {}).then(async () => {
      const response = await apiFetch(`/history/turns/${encodeURIComponent(pending.turnId)}/draft`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer: pending.answer, speech_review: pending.speech_review }),
      })
      await readResponse(response)
    })
    draftChain.current = operation
    try { await operation; setDraftError('') }
    catch (failure) {
      if (draft.current === pending) pending.dirty = true
      setDraftError('Your draft could not be saved. Keep this page open and retry.')
      throw failure
    }
  }, [apiFetch, storageMode])
  useEffect(() => {
    if (!storedTurn || feedback || storageMode !== 'postgresql') { draft.current = null; return }
    if (submittingAnswer) return
    draft.current = { turnId: storedTurn.turn_id, answer, dirty: true, speech_review: speechReview ? {receipt_id:speechReview.receipt_id,reviewed:speechReview.reviewed} : undefined }
    const timer = window.setTimeout(() => { void saveDraft().catch(() => {}) }, 600)
    return () => window.clearTimeout(timer)
  }, [storedTurn, answer, feedback, storageMode, submittingAnswer, saveDraft, speechReview])
  useEffect(() => {
    const departing = () => {
      const pending = draft.current
      if (pending?.dirty && storageMode === 'postgresql') {
        void apiFetch(`/history/turns/${encodeURIComponent(pending.turnId)}/draft`, {
          method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer: pending.answer, speech_review: pending.speech_review }),
        }).catch(() => {})
      }
    }
    window.addEventListener('pagehide', departing)
    return () => window.removeEventListener('pagehide', departing)
  }, [apiFetch, storageMode])
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 30_000)
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
    draft.current = null
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
      setSpeechReviews({ ...Object.fromEntries(Object.entries(saved.results).filter(([id,result]) => result.speech_review && !Object.hasOwn(saved.drafts ?? {},id)).map(([id,result]) => [id,result.speech_review!])), ...saved.speech_reviews })
      const unanswered = saved.questions.findIndex(
        (question) => !saved.results[question.turn_id],
      )
      const resumed = saved.questions.findIndex(question => question.turn_id === saved.resume_turn_id)
      const index = resumed >= 0 ? resumed : unanswered >= 0 ? unanswered : saved.questions.length - 1
      const question = saved.questions[index]
      setQuestionSet(saved.questions)
      setQuestionIndex(index)
      setTurn(question)
      setResults(saved.results)
      const hasDraft = saved.drafts && Object.hasOwn(saved.drafts, question.turn_id)
      setFeedback(hasDraft ? null : saved.results[question.turn_id] ?? null)
      setAnswer(saved.drafts?.[question.turn_id] ?? saved.answers[question.turn_id] ?? '')
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
      await saveDraft()
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
      navigate({ page: 'study' })
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
    if (speechReview && !speechReview.reviewed) { setError('Check and confirm the transcript before submitting.'); return }
    setSubmittingAnswer(true)
    setError(null)
    setFeedback(null)
    setTranscriptionNotice('')
    try {
      await saveDraft()
      const res = await apiFetch('/answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          turn_id: turn.turn_id,
          answer: answer.trim(),
          speech_review: speechReview ? {receipt_id:speechReview.receipt_id,reviewed:speechReview.reviewed} : undefined,
        }),
      })
      const data = await readResponse(res)
      if (!isAnswerResponse(data) || data.turn_id !== turn.turn_id) {
        throw new Error('The server returned invalid feedback. Please retry.')
      }
      setFeedback(data)
      draft.current = null
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
  async function askFollowup() {
    if (!turn || !feedback || busy || turn.parent_turn_id) return
    setLoadingQuestion(true); setError(null)
    try {
      const response = await apiFetch(`/viva/turns/${encodeURIComponent(turn.turn_id)}/follow-up`, { method: 'POST' })
      const child = await readResponse(response)
      if (!isQuestionResponse(child) || child.parent_turn_id !== turn.turn_id || child.source_id !== turn.source_id) throw new Error('The follow-up did not match this question. Retry.')
      const next = questionSet.filter(question => question.turn_id !== child.turn_id)
      const index = next.findIndex(question => question.turn_id === turn.turn_id) + 1
      next.splice(index, 0, child)
      setQuestionSet(next); setQuestionIndex(index); setTurn(child); setAnswer(''); setFeedback(results[child.turn_id] ?? null); setTranscriptionNotice(''); draft.current = null
      window.requestAnimationFrame(() => { const heading = document.getElementById('question-heading'); heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: 'start', behavior: 'instant' }) })
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not prepare the follow-up. Your answer is saved.') }
    finally { setLoadingQuestion(false) }
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
      if (turn) formData.append('turn_id', turn.turn_id)
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
      const review = 'speech_review' in data ? data.speech_review as SpeechReview : null
      if (turn && (!review || typeof review.receipt_id !== 'string' || typeof review.reviewed !== 'boolean' || review.original_transcript !== transcript || !Array.isArray(review.checks) || !review.checks.every(check => typeof check.heard === 'string' && typeof check.source_term === 'string' && typeof check.message === 'string'))) throw new Error('The transcript review could not be read. Retry.')
      setAnswer(transcript)
      if (turn && review) setSpeechReviews(previous => ({...previous,[turn.turn_id]:review}))
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
  function editAnswer(value: string) {
    setAnswer(value); setFeedback(null)
    if (turn && speechReview) setSpeechReviews(previous => ({...previous,[turn.turn_id]:{...speechReview,reviewed:false}}))
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
    uploadingSource || debugBusy
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
            'Practice'
          ) : (
            <>
              <span>Know it.</span>
              <span>Explain it.</span>
            </>
          )}
        </h1>
        {!turn && (
          <p>
            Practice with questions built from your notes. Explain them in your
            own words, then check the evidence.
          </p>
        )}
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
      onClick={() => {
        if (route.page === 'setup' && storedTurn) navigate({ page: 'study' })
        else void generateQuestion()
      }}
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
            'New set'
          ) : (
            route.page === 'setup' && storedTurn ? 'Continue practice' : 'Generate questions'
          )}
          <Icon name="arrow" size={18} />
        </>
      )}
    </button>
  )
  async function go(next: Route) {
    if (busy) return
    setNavigationError('')
    try { await saveDraft(); await debugSave.current?.(); navigate(next) }
    catch { setNavigationError('Your draft could not be saved, so this page stayed open. Please try again.') }
  }
  function openSaved(source: SourceDocument) {
    handleSourceChange(source)
    setSourceOverride(source)
    navigate({ page: 'study' })
  }
  const studyVisible = route.page === 'study' || route.page === 'setup'
  useEffect(() => {
    const destination = route.page === 'study' || route.page === 'setup' ? 'workspace' : `${route.page}-page`
    document.getElementById(destination)?.focus({ preventScroll: true })
  }, [route.page, route.sourceId, route.runId])
  return (
    <div className={`app-shell ${route.page === 'debug' ? route.runId ? 'debug-exercise-shell' : 'debug-setup-shell' : ''}`}>
      <a className="skip-link" href="#workspace" onClick={event => {
        event.preventDefault()
        document.getElementById(studyVisible ? 'workspace' : `${route.page}-page`)?.focus()
      }}>
        Skip to content
      </a>
      <header className="app-header">
        <a className="brand" href="#/study" aria-label="RepoViva study desk" onClick={event => { event.preventDefault(); void go({ page: 'study' }) }}>
          <span className="brand-mark"><UiloraEffect variant="aurora" />
            <Icon name="book" size={22} />
          </span>
          <span>
            RepoViva<span className="brand-period">.</span>
          </span>
        </a>
        <nav className="workspace-nav">
          <button type="button" className={`nav-item ${studyVisible ? 'is-active' : ''}`} aria-current={studyVisible ? 'page' : undefined} disabled={busy} onClick={() => { void go({ page: 'study' }) }}><Icon name="desk" />Study</button>
          <button type="button" className={`nav-item ${route.page === 'debug' ? 'is-active' : ''}`} aria-current={route.page === 'debug' ? 'page' : undefined} disabled={busy} onClick={() => { void go({ page: 'debug' }) }}><Icon name="code" />Debug</button>
          <button type="button" className={`nav-item ${route.page === 'history' ? 'is-active' : ''}`} aria-current={route.page === 'history' ? 'page' : undefined} disabled={busy} onClick={() => { void go({ page: 'history' }) }}><Icon name="history" />History</button>
          <button type="button" className={`nav-item ${route.page === 'profile' ? 'is-active' : ''}`} aria-current={route.page === 'profile' ? 'page' : undefined} disabled={busy} onClick={() => { void go({ page: 'profile' }) }}><Icon name="profile" />Profile</button>
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
          <AccountControls disabled={busy} beforeSignIn={async () => { await saveDraft(); await debugSave.current?.() }} />
        </div>
      </header>
      <GuestAccess disabled={busy} beforeSignIn={async () => { await saveDraft(); await debugSave.current?.() }} />
      <div className="page-back-bar" hidden={route.page === 'debug' && !!route.runId}><button type="button" className="text-button back-button" disabled={busy || (depth === 0 && studyVisible && !turn)} onClick={() => {
        if (busy) return
        setNavigationError('')
        void saveDraft().then(() => debugSave.current?.()).then(() => { if (depth === 0 && turn && studyVisible) navigate({ page: 'setup' }); else back() }).catch(() => setNavigationError('Your draft could not be saved, so this page stayed open. Please try again.'))
      }}><Icon name="arrow" size={17} className="rotate-180" />Back</button></div>
      {navigationError && <div className="page-back-bar"><p className="inline-error" role="alert">{navigationError}</p></div>}
      {route.page === 'history' && <HistoryPage key={route.sourceId || 'files'} sourceId={route.sourceId} beforeAction={saveDraft} onDebug={runId => navigate({ page: 'debug', runId })} onSelect={id => navigate({ page: 'history', sourceId: id })} onOpen={openSaved} onDeleted={ids => {
        if (activeSource && ids.includes(activeSource.source_id)) { handleSourceChange(null); setSourceOverride(null) }
        navigate({ page: 'history' })
      }} />}
      {route.page === 'profile' && <ProfilePage />}
      {route.page === 'debug' && <DebugPage key={route.runId || 'catalogue'} runId={route.runId} source={activeSource} onSourceChange={source => { handleSourceChange(source); setSourceOverride(source) }} onOpen={runId => navigate({ page: 'debug', runId: runId || undefined })} onBusyChange={setDebugBusy} onSaveHandler={registerDebugSave} />}
      <main
        id="workspace"
        hidden={!studyVisible}
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
          <section
            className={`material-area ${!turn ? 'start-panel session-console' : ''}`}
            id="source-material"
            aria-labelledby={!turn ? 'session-heading' : undefined}
          >
            {!turn && <UiloraEffect variant="aurora" />}
            {!turn && (
              <div
                className="session-console-heading flex items-center justify-center min-h-[150px]"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%' }}
              >
                <div className="setup-activity" role="status" aria-live="polite">
                  <ActivityOrb
                    size={64}
                    state={activity.state}
                    active={activity.active}
                  />
                  <span className="sr-only">{activity.title}</span>
                </div>
              </div>
            )}
            {backendReady ? (
              <SourceUpload
                restoredSource={sourceOverride}
                beforeSourceChange={saveDraft}
                compact={!!turn}
                embedded={!turn}
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
                <UiloraEffect variant="aurora" />
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
            {!turn && (
              <div className="start-action">
                {generationButton}
              </div>
            )}
          </section>
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
                    {turn.parent_turn_id ? 'Viva follow-up' : 'Question'} {questionIndex + 1} of {questionSet.length}
                  </span>
                  {activity.active && (
                    <span
                      className="question-activity"
                      role="status"
                      aria-live="polite"
                    >
                      <ActivityOrb state={activity.state} />
                      <span>{activity.title}</span>
                    </span>
                  )}
                </div>
                <h2 id="question-heading" tabIndex={-1}>{turn.question}</h2>
                {turn.parent_turn_id && <details className="viva-parent-answer"><summary>Your earlier answer</summary><p>{turn.parent_answer}</p></details>}
                {!feedback && <p className="viva-answer-guide">Explain your reasoning in your own words. Record your answer or type below, then review it before submitting.</p>}
              </section>
              <section
                className="answer-panel"
                aria-labelledby="answer-heading"
              >
                <form onSubmit={submitAnswer}>
                  <div className="section-heading">
                    <h2 id="answer-heading">Your answer</h2>
                  </div>
                  {studyVisible && <VoiceRecorder
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
                  />}
                  <label className="sr-only" htmlFor="answer">
                    Your answer
                  </label>
                  <textarea
                    id="answer"
                    aria-describedby="answer-help answer-count"
                    value={answer}
                    onChange={(e) => {
                      editAnswer(e.target.value)
                    }}
                    disabled={
                      submittingAnswer ||
                      loadingQuestion ||
                      transcribing ||
                      recordingBusy ||
                      uploadingSource
                    }
                    placeholder="Type your answer…"
                    rows={6}
                    maxLength={4000}
                  />
                  <span id="answer-help" className="sr-only">
                    Type here, or edit your voice transcript.
                  </span>
                  {draftError && <p className="inline-error" role="alert">{draftError}<button type="button" className="text-button" onClick={() => { void saveDraft().catch(() => {}) }}>Retry save</button></p>}
                  {speechReview && turn && <TranscriptReview review={speechReview} answer={answer} disabled={busy} onAnswer={editAnswer} onConfirm={reviewed => setSpeechReviews(previous => ({...previous,[turn.turn_id]:{...speechReview,reviewed}}))} onTyped={() => { setSpeechReviews(previous => { const next={...previous}; delete next[turn.turn_id]; return next }); setFeedback(null) }} />}
                  <div className="answer-draft-meta">
                    <details className="audio-upload">
                      <summary>
                        <Icon name="upload" size={16} />
                        Upload audio
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
                          WAV, up to 60 seconds and 10 MiB. Transcription replaces
                          your draft; review it before submitting.
                        </p>
                      </div>
                    </details>
                    <span id="answer-count">
                      {answer.length.toLocaleString()} / 4,000
                    </span>
                  </div>
                  <p role="status" className="transcript-status">
                    {transcribing
                      ? 'Transcribing your recording…'
                      : transcriptionNotice}
                  </p>
                  <div className="answer-submit-row">
                    <button
                      type="submit"
                      aria-busy={submittingAnswer}
                      className="button button-primary"
                      disabled={busy || !answer.trim() || (!!speechReview && !speechReview.reviewed)}
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
                    {questionSet.length > 1 && totalPossible > 0 && (
                      <p>
                        Set score: {Math.round((100 * totalEarned) / totalPossible)}%
                      </p>
                    )}
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
                  {!turn.parent_turn_id && storageMode === 'postgresql' && <div className="viva-followup"><button type="button" className="button button-secondary" disabled={busy} onClick={() => { void askFollowup() }}>{loadingQuestion ? 'Preparing follow-up…' : questionSet.some(question => question.parent_turn_id === turn.turn_id) ? 'Open viva follow-up' : 'Continue with a follow-up'}<Icon name="arrow" size={16} /></button><p>{activeSource?.prepared_example ? 'Prepared example follow-up · Free' : 'One follow-up based on your submitted answer and source. Uses 1 question-set allowance; reopening it is free.'}</p></div>}
                  <p className="assessment-note">
                    {activeSource?.prepared_example ? 'Source-backed feedback. Check the explanation against the code.' : 'AI feedback. Verify uncertain results against the source.'}
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
              {turn.evidence.citation_type === 'page' && (
                <p className="evidence-footnote">
                  <Icon name="info" size={14} />
                  <span>Check PDF tables and equations against the original.</span>
                </p>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  )
}
