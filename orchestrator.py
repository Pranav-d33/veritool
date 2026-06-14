import json

from verifier.verifier import Verifier


class ParseError(Exception):
    pass


_verifier: Verifier | None = None


def _get_verifier() -> Verifier:
    global _verifier
    if _verifier is None:
        _verifier = Verifier()
    return _verifier


def parse_tool_call(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}")

    if "tool" not in data:
        raise ParseError("Missing 'tool' field")
    if "args" not in data:
        raise ParseError("Missing 'args' field")
    if not isinstance(data["args"], dict):
        raise ParseError("'args' must be a dict")

    return data


def evaluate_tool_call(tool_call_json: str, verifier: Verifier | None = None) -> dict:
    if verifier is None:
        verifier = _get_verifier()

    try:
        parsed = parse_tool_call(tool_call_json)
    except ParseError as e:
        return {"decision": "error", "reason": str(e)}

    result = verifier.check(parsed["tool"], parsed["args"])
    result["tool"] = parsed["tool"]
    result["args"] = parsed["args"]
    return result
