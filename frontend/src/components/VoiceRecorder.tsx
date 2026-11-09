import { useEffect, useRef, useState } from 'react'
import { recordingToWav } from '../audio/wav'

interface Props {
  disabled: boolean
  onBusyChange: (busy: boolean) => void
  onRecording: (file: File) => Promise<void>
  onError: (message: string) => void
}

interface Capture {
  recorder: MediaRecorder
  stream: MediaStream
  chunks: Blob[]
  interval: number
  timeout: number
}

function release(capture: Capture) {
  window.clearInterval(capture.interval)
  window.clearTimeout(capture.timeout)
  capture.stream.getTracks().forEach((track) => track.stop())
}

export default function VoiceRecorder({ disabled, onBusyChange, onRecording, onError }: Props) {
  const [phase, setPhase] = useState<'idle' | 'permission' | 'recording' | 'processing'>('idle')
  const [seconds, setSeconds] = useState(0)
  const [recording, setRecording] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const captureRef = useRef<Capture | null>(null)
  const attemptRef = useRef(0)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      const capture = captureRef.current
      if (capture) {
        capture.recorder.onstop = null
        capture.recorder.onerror = null
        if (capture.recorder.state !== 'inactive') capture.recorder.stop()
        release(capture)
      }
      onBusyChange(false)
    }
  }, [onBusyChange])

  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  function cancelRecording() {
    attemptRef.current++
    const capture = captureRef.current
    captureRef.current = null
    if (capture) {
      capture.recorder.onstop = null
      capture.recorder.onerror = null
      if (capture.recorder.state !== 'inactive') capture.recorder.stop()
      release(capture)
    }
    setPhase('idle')
    onBusyChange(false)
  }

  function stopRecording() {
    const capture = captureRef.current
    if (!capture || capture.recorder.state === 'inactive') return
    setPhase('processing')
    window.clearInterval(capture.interval)
    window.clearTimeout(capture.timeout)
    capture.recorder.stop()
    capture.stream.getTracks().forEach((track) => track.stop())
  }

  async function startRecording() {
    if (disabled || phase !== 'idle') return
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia
      || typeof MediaRecorder === 'undefined' || typeof OfflineAudioContext === 'undefined') {
      onError('Microphone recording needs a supported browser on localhost or HTTPS. You can upload a WAV file or type instead.')
      return
    }
    const attempt = ++attemptRef.current
    setPhase('permission')
    onBusyChange(true)
    let stream: MediaStream | null = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current || attempt !== attemptRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus']
        .find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      const capture: Capture = { recorder, stream, chunks: [], interval: 0, timeout: 0 }
      captureRef.current = capture
      recorder.ondataavailable = (event) => { if (event.data.size) capture.chunks.push(event.data) }
      recorder.onerror = () => {
        cancelRecording()
        onError('The microphone recording failed. Please retry, upload a WAV file, or type your answer.')
      }
      recorder.onstop = async () => {
        release(capture)
        captureRef.current = null
        if (!mountedRef.current || attempt !== attemptRef.current) return
        setPhase('processing')
        try {
          const file = await recordingToWav(new Blob(capture.chunks, { type: recorder.mimeType }))
          if (!mountedRef.current || attempt !== attemptRef.current) return
          setRecording(file)
          setPreviewUrl(URL.createObjectURL(file))
          await onRecording(file)
        } catch (error) {
          if (mountedRef.current) onError(error instanceof Error ? error.message : 'Could not prepare the recording. Please retry.')
        } finally {
          if (mountedRef.current && attempt === attemptRef.current) {
            setPhase('idle')
            onBusyChange(false)
          }
        }
      }
      recorder.start()
      const started = performance.now()
      setSeconds(0)
      setPhase('recording')
      capture.interval = window.setInterval(() => setSeconds(Math.min(60, Math.floor((performance.now() - started) / 1000))), 250)
      capture.timeout = window.setTimeout(stopRecording, 60_000)
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())
      if (!mountedRef.current || attempt !== attemptRef.current) return
      captureRef.current = null
      setPhase('idle')
      onBusyChange(false)
      const denied = error instanceof DOMException && error.name === 'NotAllowedError'
      onError(denied ? 'Microphone permission was denied. Allow access and retry, or upload a WAV file or type your answer.'
        : 'Could not start the microphone. Check that a microphone is connected, or upload a WAV file or type instead.')
    }
  }

  async function retryTranscription() {
    if (!recording || disabled || phase !== 'idle') return
    setPhase('processing')
    onBusyChange(true)
    try {
      await onRecording(recording)
    } finally {
      if (mountedRef.current) {
        setPhase('idle')
        onBusyChange(false)
      }
    }
  }

  const buttonClass = 'px-3 py-2 rounded border border-[#30363d] text-sm disabled:opacity-50 disabled:cursor-not-allowed'
  return (
    <div className="mb-5">
      <div className="flex flex-wrap gap-3 items-center">
        {phase === 'recording' ? (
          <button type="button" onClick={stopRecording} className={buttonClass}>
            Stop and transcribe
          </button>
        ) : (
          <button type="button" onClick={startRecording} disabled={disabled || phase !== 'idle'} className={buttonClass}>
            {phase === 'permission' ? 'Waiting for microphone…' : phase === 'processing' ? 'Preparing transcript…' : 'Record answer'}
          </button>
        )}
        {(phase === 'recording' || phase === 'permission') && (
          <button type="button" onClick={cancelRecording} className={buttonClass}>Cancel recording</button>
        )}
      </div>
      <p role="status" className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
        {phase === 'recording' ? `Recording: ${seconds} / 60 seconds. Stops automatically at 60 seconds.`
          : 'Record up to 60 seconds. On stop, audio is sent to Gnani Prisma. Review the transcript before submitting.'}
      </p>
      {recording && previewUrl && (
        <div className="mt-3">
          <audio controls src={previewUrl} aria-label="Your recorded answer" className="w-full" />
          <button type="button" disabled={disabled || phase !== 'idle'} onClick={retryTranscription} className={`${buttonClass} mt-2`}>
            Transcribe recording again
          </button>
        </div>
      )}
    </div>
  )
}
