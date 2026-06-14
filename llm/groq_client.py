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
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise GroqClientError(
            f"Could not parse tool call from response:\n{content}"
        )

    return _normalize_tool_call(data)


def _normalize_tool_call(data: dict) -> dict:
    if "tool" in data and "args" in data:
        result = {"tool": data["tool"], "args": _coerce_types(data["args"])}
        return result

    if "name" in data and "parameters" in data:
        result = {"tool": data["name"], "args": _coerce_types(data["parameters"])}
        return result

    if "function" in data and isinstance(data["function"], dict):
        fn = data["function"]
        args_raw = fn.get("arguments", fn.get("parameters", {}))
        if isinstance(args_raw, str):
            args_raw = json.loads(args_raw)
        result = {"tool": fn.get("name", data.get("name", "unknown")), "args": _coerce_types(args_raw)}
        return result

    if "tool" in data:
        result = {"tool": data["tool"], "args": _coerce_types({k: v for k, v in data.items() if k != "tool"})}
        return result

    raise GroqClientError(
        f"Could not interpret tool call format:\n{json.dumps(data, indent=2)}"
    )


_NUMERIC_FIELDS = {"price", "count", "amount", "quantity", "index", "id"}
_BOOL_FIELDS = {"active", "enabled", "confirmed"}


def _coerce_types(args: dict) -> dict:
    coerced = {}
    for k, v in args.items():
        if isinstance(v, str) and k in _NUMERIC_FIELDS:
            try:
                coerced[k] = int(v)
            except ValueError:
                try:
                    coerced[k] = float(v)
                except ValueError:
                    coerced[k] = v
        else:
            coerced[k] = v
    return coerced
