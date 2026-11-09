"""Validated JSON requests to the configured Groq model."""
import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


class ProviderError(RuntimeError):
    pass


def json_completion(system, prompt, schema, name):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ProviderError("Groq is not configured.")
    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": name, "strict": True, "schema": schema,
                }},
                "max_tokens": 4000,
                "temperature": 0.2,
            },
            timeout=45,
        )
    except requests.RequestException as error:
        raise ProviderError("Groq request failed.") from error
    if not response.ok:
        raise ProviderError(f"Groq returned HTTP {response.status_code}.")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("Missing JSON content")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Expected an object")
        return result
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise ProviderError("Groq returned an invalid structured response.") from error


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def source_packet(snippets):
    parts = []
    for snippet in snippets:
        location = (f"Page {snippet['page']}" if snippet.get('citation_type') == 'page'
                    else f"Lines {snippet['start_line']}-{snippet['end_line']}")
        parts.append(f"Snippet ID: {snippet['id']}\nFile: {snippet['path']}\n{location}\n" + "\n".join(snippet['content']))
    return "\n\n---\n\n".join(parts)


def validate_citation(snippet_id, quote, snippets):
    if not isinstance(snippet_id, str) or not isinstance(quote, str) or not quote.strip():
        raise ValueError("Missing evidence citation")
    snippet = next((item for item in snippets if str(item['id']) == snippet_id), None)
    if snippet is None or quote not in "\n".join(snippet['content']):
        raise ValueError("Citation does not match the supplied evidence")
    return snippet
