/** Decode the browser's recording and encode real mono, 16-bit PCM WAV audio. */
export async function recordingToWav(recording: Blob): Promise<File> {
  // decodeAudioData resamples to this context's sample rate without audio playback.
  const context = new OfflineAudioContext(1, 1, 16000)
  const audio = await context.decodeAudioData(await recording.arrayBuffer())
  if (audio.duration > 30) throw new Error('Keep recordings under 30 seconds. Please record a shorter answer; audio was not truncated.')
  const frames = audio.length
  if (frames < audio.sampleRate / 4) {
    throw new Error('The recording is too short. Please record at least a second.')
  }

  const buffer = new ArrayBuffer(44 + frames * 2)
  const view = new DataView(buffer)
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i))
  }
  text(0, 'RIFF')
  view.setUint32(4, 36 + frames * 2, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // Mono
  view.setUint32(24, audio.sampleRate, true)
  view.setUint32(28, audio.sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, frames * 2, true)

  const channels = Array.from({ length: audio.numberOfChannels }, (_, i) => audio.getChannelData(i))
  for (let i = 0; i < frames; i++) {
    const sample = channels.reduce((sum, channel) => sum + channel[i], 0) / channels.length
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  return new File([buffer], 'recording.wav', { type: 'audio/wav' })
}
