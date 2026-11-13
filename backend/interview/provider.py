"""Validated JSON requests to the configured Groq model."""
import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


class ProviderError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def json_completion(system, prompt, schema, name, timeout=45, max_tokens=4000):
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
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise ProviderError("Groq request failed.") from error
    if not response.ok:
        raise ProviderError(f"Groq returned HTTP {response.status_code}.", response.status_code)
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
        numbered = "\n".join(f"[L{index}] {line}" for index, line in enumerate(snippet['content'], 1))
        parts.append(f"Snippet ID: {snippet['id']}\nFile: {snippet['path']}\n{location}\nEvidence lines (local to this snippet):\n" + numbered)
    return "\n\n---\n\n".join(parts)


def validate_citation(snippet_id, quote, snippets):
    if not isinstance(snippet_id, str) or not isinstance(quote, str) or not quote.strip():
        raise ValueError("Missing evidence citation")
    snippet = next((item for item in snippets if str(item['id']) == snippet_id), None)
    if snippet is None or quote not in "\n".join(snippet['content']):
        raise ValueError("Citation does not match the supplied evidence")
    return snippet


def resolve_line_citation(snippet_id, line_start, line_end, snippets):
    """Copy citation text from original evidence instead of trusting model quotes."""
    snippet = next((item for item in snippets if str(item['id']) == snippet_id), None)
    if snippet is None:
        raise ValueError("Unknown evidence snippet ID")
    if type(line_start) is not int or type(line_end) is not int or not 1 <= line_start <= line_end <= len(snippet['content']):
        raise ValueError(f"Invalid line range for snippet {snippet_id}; available lines are 1 to {len(snippet['content'])}")
    lines = snippet['content'][line_start - 1:line_end]
    quote = "\n".join(lines)
    if not quote.strip():
        raise ValueError("Cited evidence lines are blank")
    evidence = {**snippet, "content": lines}
    if snippet.get('citation_type') != 'page':
        evidence['start_line'] = snippet['start_line'] + line_start - 1
        evidence['end_line'] = snippet['start_line'] + line_end - 1
    return quote, evidence


def citation_properties(snippets, nullable=False):
    ids = [str(item['id']) for item in snippets]
    lines = list(range(1, max(len(item['content']) for item in snippets) + 1))
    return {
        "snippet_id": {"type": ["string", "null"] if nullable else "string", "enum": ids + ([None] if nullable else [])},
        "line_start": {"type": ["integer", "null"] if nullable else "integer", "enum": lines + ([None] if nullable else [])},
        "line_end": {"type": ["integer", "null"] if nullable else "integer", "enum": lines + ([None] if nullable else [])},
    }
