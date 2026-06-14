import json
import os

from config import GROQ_API_KEY, LLM_MODEL


try:
    from groq import Groq as GroqClient
    HAS_GROQ = True
except ImportError:
    GroqClient = None
    HAS_GROQ = False


class GroqClientError(Exception):
    pass


def _get_client():
    if not HAS_GROQ:
        raise GroqClientError("groq package not installed. Run: pip install groq")

    if not GROQ_API_KEY:
        raise GroqClientError("GROQ_API_KEY not set in environment")

    return GroqClient(api_key=GROQ_API_KEY)


def send_prompt(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
) -> dict:
    client = _get_client()
    model = model or LLM_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )

    content = response.choices[0].message.content
    if content is None:
        raise GroqClientError("Empty response from Groq API")

    return _extract_tool_call(content)


def _extract_tool_call(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise GroqClientError(
            f"Could not parse tool call from response:\n{content}"
        )
