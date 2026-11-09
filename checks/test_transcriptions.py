from checks.auth_fixtures import authenticated_client
import io
import os
import unittest
import wave
from unittest.mock import Mock, patch

import requests

from backend.app import app, MAX_AUDIO_BYTES
from backend.speech.transcriber import TranscriptionError, transcribe_wav


def wav_bytes(seconds=0.01):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * int(8000 * seconds))
    return buffer.getvalue()


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.client = authenticated_client(app)

    def upload(self, data, filename="recording.wav"):
        response = self.client.post("/transcriptions", data={"audio_file": (io.BytesIO(data), filename)})
        self.addCleanup(response.close)
        self.addCleanup(response.request.environ["wsgi.input"].close)
        return response

    def test_valid_upload_uses_prisma_contract(self):
        audio = wav_bytes()
        reply = Mock(ok=True)
        reply.json.return_value = {"success": True, "transcript": "  A test answer.  "}
        with patch.dict(os.environ, {"VACHANA_API_KEY": "test-key"}), patch("backend.speech.transcriber.requests.post", return_value=reply) as post:
            response = self.upload(audio)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"transcript": "A test answer."})
        self.assertEqual(post.call_args.kwargs["files"]["audio_file"], ("recording.wav", audio, "audio/wav"))
        self.assertEqual(post.call_args.kwargs["data"]["model"], "prisma-v3.0")

    def test_invalid_uploads_do_not_call_provider(self):
        with patch("backend.app.transcribe_wav") as transcribe:
            self.assertEqual(self.client.post("/transcriptions").status_code, 400)
            self.assertEqual(self.upload(b"").status_code, 400)
            self.assertEqual(self.upload(b"not WAV", "recording.webm").status_code, 415)
            self.assertEqual(self.upload(b"not WAV").status_code, 415)
            self.assertEqual(self.upload(wav_bytes(61)).status_code, 400)
            self.assertEqual(self.upload(wav_bytes()[:-2]).status_code, 400)
            self.assertEqual(self.upload(b"x" * (MAX_AUDIO_BYTES + 1)).status_code, 413)
            self.assertEqual(self.upload(b"x" * (MAX_AUDIO_BYTES + 65537)).status_code, 413)
            transcribe.assert_not_called()

    def test_provider_failure_returns_safe_error(self):
        with patch("backend.app.transcribe_wav", side_effect=TranscriptionError("private provider detail")):
            response = self.upload(wav_bytes())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider detail", response.get_data(as_text=True))

    def test_invalid_provider_payloads_and_timeout(self):
        for payload in (None, [], {"success": False}, {"success": True, "transcript": 123}, {"success": True, "transcript": "  "}):
            with self.subTest(payload=payload):
                reply = Mock(ok=True)
                reply.json.return_value = payload
                with patch.dict(os.environ, {"VACHANA_API_KEY": "test-key"}), patch("backend.speech.transcriber.requests.post", return_value=reply):
                    with self.assertRaises(TranscriptionError):
                        transcribe_wav(wav_bytes(), "recording.wav")
        with patch.dict(os.environ, {"VACHANA_API_KEY": "test-key"}), patch("backend.speech.transcriber.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(TranscriptionError):
                transcribe_wav(wav_bytes(), "recording.wav")


if __name__ == "__main__":
    unittest.main()
