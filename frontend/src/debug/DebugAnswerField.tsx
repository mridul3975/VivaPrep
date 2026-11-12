import { useCallback } from 'react'
import VoiceRecorder, { type RecordingPhase } from '../components/VoiceRecorder'
import TranscriptReview, { type SpeechReview } from '../components/TranscriptReview'

export type AnswerField = 'hypothesis' | 'explanation' | 'failing_input'
const ignorePhase = (_phase: RecordingPhase) => {}

export default function DebugAnswerField({ field, label, recordLabel, value, placeholder, review, busy, recordingDisabled, onChange, onRecording, onRecordingBusy, onError, onConfirm, onTyped }: {
  field: AnswerField; label: string; recordLabel: string; value: string; placeholder?: string; review?: SpeechReview
  busy: boolean; recordingDisabled: boolean
  onChange: (value: string) => void; onRecording: (field: AnswerField, file: File) => Promise<void>
  onRecordingBusy: (field: AnswerField, value: boolean) => void; onError: (message: string) => void
  onConfirm: (value: boolean) => void; onTyped: () => void
}) {
  // Stable per-field callbacks keep other recorders' rerenders from cancelling capture.
  const captureBusy = useCallback((value: boolean) => onRecordingBusy(field, value), [field, onRecordingBusy])
  const capture = useCallback((file: File) => onRecording(field, file), [field, onRecording])
  return <div className="debug-answer-field" role="group" aria-label={label}>
    <label htmlFor={`debug-answer-${field}`}>{label}</label>
    <VoiceRecorder recordLabel={recordLabel} disabled={recordingDisabled} onBusyChange={captureBusy} onRecording={capture} onPhaseChange={ignorePhase} onError={onError} />
    <textarea id={`debug-answer-${field}`} rows={5} maxLength={4000} disabled={busy} value={value} placeholder={placeholder} onChange={event => onChange(event.target.value)} />
    {review && <TranscriptReview review={review} answer={value} disabled={busy} onAnswer={onChange} onConfirm={onConfirm} onTyped={onTyped} />}
  </div>
}
