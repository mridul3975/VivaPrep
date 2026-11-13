import os

import requests


PRISMA_URL = "https://api.vachana.ai/stt/v3"


class TranscriptionError(RuntimeError):
    """Prisma could not return a usable transcript."""


def transcribe_wav(audio: bytes, filename: str) -> str:
    api_key = os.getenv("VACHANA_API_KEY")
    if not api_key:
        raise TranscriptionError("Transcription provider is not configured.")

    try:
        response = requests.post(
            PRISMA_URL,
            headers={"X-API-Key-ID": api_key},
            files={"audio_file": (filename, audio, "audio/wav")},
            data={"model": "prisma-v3.0", "language_code": "indic-auto", "format": "codemix", "enable_substitution": "false"},
            timeout=60,
        )
    except requests.RequestException as error:
        raise TranscriptionError("Transcription provider request failed.") from error

    if not response.ok:
        raise TranscriptionError(f"Transcription provider returned HTTP {response.status_code}.")

    try:
        result = response.json()
    except ValueError as error:
        raise TranscriptionError("Transcription provider returned invalid JSON.") from error

    if not isinstance(result, dict) or result.get("success") is not True:
        raise TranscriptionError("Transcription provider did not report success.")
    transcript = result.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise TranscriptionError("Transcription provider returned no usable transcript.")
    return transcript.strip()
