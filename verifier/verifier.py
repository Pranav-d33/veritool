from verifier.tahoe_policy import check_sale
from verifier.deletion_policy import check_deletion
from verifier.schema import validate_tool_call, ValidationError
from config import VERIFICATION_TIMEOUT_MS


class Verifier:
    def __init__(self):
        self._policies: dict[str, callable] = {
            "tahoe": check_sale,
            "deletion": check_deletion,
        }

    def check(self, tool_name: str, args: dict) -> dict:
        route = self._resolve_route(tool_name)
        if route is None:
            return {"status": "unknown_tool", "reason": f"No policy for tool: {tool_name}"}

        try:
            validated_args = validate_tool_call(tool_name, args)
        except ValidationError as e:
            return {"status": "error", "reason": str(e)}

        check_fn = self._policies[route]
        try:
            result = check_fn(**validated_args, timeout_ms=VERIFICATION_TIMEOUT_MS)
        except TypeError as e:
            return {"status": "error", "reason": f"Argument mismatch: {e}"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

        return self._normalize(result)

    def _resolve_route(self, tool_name: str) -> str | None:
        from config import POLICY_ROUTES
        return POLICY_ROUTES.get(tool_name)

    @staticmethod
    def _normalize(result: dict) -> dict:
        mapping = {
            "violation": "blocked",
            "permitted": "permitted",
            "unknown": "unknown",
            "unknown_model": "blocked",
        }
        decision = mapping.get(result["status"], "error")
        return {
            "decision": decision,
            "reason": result.get("reason", result.get("witness", {})),
        }
