import json
from typing import Any

from orchestrator import evaluate_tool_call
from verifier.coordination_policy import CoordinationVerifier, CoordinationPolicySpec


class VeriToolGuard:
    def __init__(self, crew: Any, coordination_policy: str | None = None):
        self._crew = crew
        self._coordination_policy = coordination_policy
        self._coordination_verifier = self._build_coordination_verifier()

    def _build_coordination_verifier(self) -> CoordinationVerifier | None:
        if not self._coordination_policy:
            return None
        spec = CoordinationPolicySpec(
            name=self._coordination_policy,
            agents=["researcher", "writer", "editor", "publisher"],
            invariants=[],
        )
        return CoordinationVerifier(spec)

    def guard(self, agent_name: str, tool_name: str, tool_input: dict) -> dict:
        raw = json.dumps({"tool": tool_name, "args": tool_input})
        result = evaluate_tool_call(raw)
        if result["decision"] == "blocked":
            return {"status": "blocked", "reason": result.get("reason", "Policy violation")}

        if self._coordination_verifier:
            from verifier.coordination_policy import AgentAction
            action = AgentAction(
                agent=agent_name,
                tool=tool_name,
                args=tool_input,
                timestamp=__import__("time").time(),
            )
            coord_result = self._coordination_verifier.check_action(action)
            if coord_result["decision"] == "blocked":
                return {"status": "blocked", "reason": f"Coordination: {coord_result.get('reason', '')}"}

        return {"status": "permitted"}

    def get_coordination_state(self) -> dict:
        if self._coordination_verifier:
            return self._coordination_verifier.get_state()
        return {}
