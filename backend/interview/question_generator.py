import os
from typing import Any

import requests




GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


class QuestionGenerationError(RuntimeError):
    """Raised when a grounded question cannot be generated."""


def generate_question(snippet: dict[str, Any]) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise QuestionGenerationError("GROQ_API_KEY is not set.")

    content = snippet.get("content")
    if not isinstance(content, list) or not content:
        raise QuestionGenerationError("The snippet has no source content.")

    prompt = f"""Generate exactly one question answerable using only the evidence below.

Source path: {snippet["path"]}
Source lines: {snippet["start_line"]}-{snippet["end_line"]}

Evidence:
{chr(10).join(content)}

Rules:
- Ask exactly one question.
- Do not use information outside the evidence.
- Do not invent details.
- Return only the question, with no explanation.
"""

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.2,
            },
            timeout=30,
        )
    except requests.RequestException as error:
        raise QuestionGenerationError(
            f"Question provider request failed: {error}"
        ) from error

    if not response.ok:
        raise QuestionGenerationError(
            f"Question provider returned HTTP {response.status_code}."
        )

    try:
        result = response.json()
        raw_content = result["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise QuestionGenerationError(
            "Question provider returned an invalid response structure."
        ) from error

    if not isinstance(raw_content, str):
        raise QuestionGenerationError(
            "Question provider returned a non-string question."
        )

    question = raw_content.strip()
    if not question:
        raise QuestionGenerationError(
            "Question provider returned an empty question."
        )

    return question

    return question
