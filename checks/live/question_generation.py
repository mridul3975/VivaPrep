def main():
    import json
    import os
    from pathlib import Path

    import requests
    from dotenv import load_dotenv

    from backend.evidence.read import read


    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("GROQ_API_KEY is not set in .env")

    project_root = Path(__file__).resolve().parents[2]
    sample_path = project_root / "samples" / "read.py"

    records = read(str(sample_path))
    if not records:
        raise SystemExit(f"No snippets were loaded from {sample_path}")

    snippets = records[0]

    prompt = f"""
    Generate exactly one question answerable using only the evidence below.


    Source path: {snippets['path']}
    Source lines: {snippets['start_line']}-{snippets['end_line']}

    Evidence:
    {chr(10).join(snippets['content'])}

    Rules:
    - Ask exactly one question.
    - Do not use information outside the evidence.
    - Do not invent details.
    - Return only the question, with no explanation.
    """

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "max_tokens": 300,
            "temperature": 0.2,
        },
        timeout=30,
    )

    print(f"HTTP {response.status_code}")

    if not response.ok:
        print(response.text)
        raise SystemExit("Request failed")

    result = response.json()
    question = result["choices"][0]["message"]["content"].strip()

    print(f"Generated question:\n{question}")

    print("\nEvidence used for question generation:")
    print(f'{snippets["path"]}:{snippets["start_line"]}-{snippets["end_line"]}')


if __name__ == "__main__":
    main()
