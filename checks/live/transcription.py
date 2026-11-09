def main():
    import os
    import sys
    from pathlib import Path

    import requests


    api_key = os.environ.get("VACHANA_API_KEY")
    if not api_key:
        raise SystemExit("VACHANA_API_KEY is not set in this terminal.")

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m checks.live.transcription path/to/audio.wav")

    audio_path = Path(sys.argv[1])
    if not audio_path.is_file():
        raise SystemExit(f"Audio file not found: {audio_path}")

    with audio_path.open("rb") as audio_file:
        response = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": api_key},
            files={"audio_file": (audio_path.name, audio_file, "audio/wav")},
            data={"model": "prisma-v3.0", "language_code": "indic-auto"},
            timeout=60,
        )

    print(f"HTTP {response.status_code}")
    try:
        print(response.json())
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()
