import json
from typing import Any, Callable

from orchestrator import evaluate_tool_call
from verifier.coordination_policy import CoordinationVerifier, CoordinationPolicySpec


class VeriToolMiddleware:
    def __init__(self, agent: Any, policies: list[str] | None = None):
        self._agent = agent
        self._policies = policies or []
        self._coordination_verifier: CoordinationVerifier | None = None

    def with_coordination(self, spec: CoordinationPolicySpec):
        self._coordination_verifier = CoordinationVerifier(spec)
        return self

    def intercept(self, func: Callable) -> Callable:
        def wrapper(sender: Any, message: dict, *args, **kwargs) -> Any:
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    tool_name = tc.get("function", {}).get("name", tc.get("name", ""))
                    arguments = tc.get("function", {}).get("arguments", "{}")
                    if isinstance(arguments, str):
                        tool_input = json.loads(arguments)
                    else:
                        tool_input = arguments

                    raw = json.dumps({"tool": tool_name, "args": tool_input})
                    result = evaluate_tool_call(raw)

                    if result["decision"] == "blocked":
                        return {
                            "role": "tool",
                            "content": f"🛑 VeriTool blocked this action: {result.get('reason', 'Policy violation')}. "
                                       f"The operation was not executed.",
                            "tool_call_id": tc.get("id", ""),
                        }

                    if self._coordination_verifier:
                        from verifier.coordination_policy import AgentAction
                        import time
                        action = AgentAction(
                            agent=getattr(sender, "name", "unknown"),
                            tool=tool_name,
                            args=tool_input,
                            timestamp=time.time(),
                        )
                        coord_result = self._coordination_verifier.check_action(action)
                        if coord_result["decision"] == "blocked":
                            return {
                                "role": "tool",
                                "content": f"🛑 VeriTool coordination policy blocked this action: "
                                           f"{coord_result.get('reason', 'Invariant violated')}",
                                "tool_call_id": tc.get("id", ""),
                            }

            return func(sender, message, *args, **kwargs)
        return wrapper

    def get_state(self) -> dict:
        state = {"policies": self._policies}
        if self._coordination_verifier:
            state["coordination"] = self._coordination_verifier.get_state()
        return state
