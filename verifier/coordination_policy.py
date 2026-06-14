import time
from dataclasses import dataclass, field
from typing import Any

from z3 import (
    Solver, Bool, String, Int, BoolVal, StringVal, IntVal,
    Function, StringSort, BoolSort, IntSort, sat, unknown,
)

from config import VERIFICATION_TIMEOUT_MS


@dataclass
class Invariant:
    name: str
    formula: str
    description: str = ""


@dataclass
class CoordinationPolicySpec:
    name: str
    agents: list[str] = field(default_factory=list)
    invariants: list[Invariant] = field(default_factory=list)
    description: str = ""


@dataclass
class AgentAction:
    agent: str
    tool: str
    args: dict
    timestamp: float


class CoordinationVerifier:
    def __init__(self, spec: CoordinationPolicySpec):
        self.spec = spec
        self.history: list[AgentAction] = []
        self._agent_state: dict[str, dict[str, Any]] = {}

    def check_action(self, action: AgentAction) -> dict:
        for invariant in self.spec.invariants:
            result = self._check_invariant(invariant, action)
            if result["status"] == "violation":
                return {
                    "status": "violation",
                    "decision": "blocked",
                    "invariant": invariant.name,
                    "reason": result.get("reason", ""),
                    "witness": result.get("witness", {}),
                    "agent": action.agent,
                    "tool": action.tool,
                }
        self.history.append(action)
        self._update_state(action)
        return {"status": "permitted", "decision": "permitted"}

    def _check_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        name = invariant.name.lower()

        if "write_before_publish" in name or "sequence" in name:
            return self._check_sequence_invariant(invariant, action)
        if "exclusive" in name or "lock" in name:
            return self._check_locking_invariant(invariant, action)
        if "editor" in name or "approve" in name or "review" in name:
            return self._check_approval_invariant(invariant, action)
        if "monotonic" in name or "counter" in name:
            return self._check_monotonic_invariant(invariant, action)
        if "role" in name or "agent_type" in name:
            return self._check_role_invariant(invariant, action)

        return {"status": "permitted", "reason": "No matching invariant handler — default permit"}

    def _check_sequence_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        allowed_writers = [a for a in self.spec.agents if a != action.agent]
        has_write = any(
            h.agent != action.agent and h.tool != "publish"
            for h in self.history
        )
        if action.tool in ("publish", "publish_to_production", "deploy") and not has_write:
            return {
                "status": "violation",
                "reason": f"No prior write action found — publish requires at least one write from another agent",
                "witness": {"agent": action.agent, "tool": action.tool},
            }
        return {"status": "permitted"}

    def _check_locking_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        file_key = action.args.get("target", action.args.get("file", ""))
        if not file_key:
            return {"status": "permitted"}

        for h in self.history:
            h_file = h.args.get("target", h.args.get("file", ""))
            if h_file == file_key and h.agent != action.agent:
                lock_held = self._agent_state.get(h.agent, {}).get(f"lock:{file_key}", False)
                if lock_held:
                    return {
                        "status": "violation",
                        "reason": f"File '{file_key}' is locked by agent '{h.agent}'",
                        "witness": {"file": file_key, "locked_by": h.agent, "requested_by": action.agent},
                    }
        return {"status": "permitted"}

    def _check_approval_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        if action.tool in ("publish", "publish_to_production", "deploy"):
            has_approval = any(
                h.agent == "editor" and h.tool in ("approve", "approve_content", "approve_deploy")
                for h in self.history
            )
            if not has_approval:
                return {
                    "status": "violation",
                    "reason": f"Action '{action.tool}' by '{action.agent}' requires prior editor approval",
                    "witness": {"agent": action.agent, "tool": action.tool},
                }
        return {"status": "permitted"}

    def _check_monotonic_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        counter_key = action.args.get("counter", action.args.get("count", ""))
        if not counter_key:
            return {"status": "permitted"}
        new_val = action.args.get("value", action.args.get("amount", 0))
        prev_val = self._agent_state.get(action.agent, {}).get(f"counter:{counter_key}", 0)
        if isinstance(new_val, (int, float)) and new_val < prev_val:
            return {
                "status": "violation",
                "reason": f"Counter '{counter_key}' decreased from {prev_val} to {new_val}",
                "witness": {"counter": counter_key, "previous": prev_val, "current": new_val},
            }
        return {"status": "permitted"}

    def _check_role_invariant(self, invariant: Invariant, action: AgentAction) -> dict:
        role = action.args.get("role", action.agent)
        blocked_roles = {"admin"}
        allowed_actions_for_role = {
            "admin": ["read", "view"],
        }
        if role in blocked_roles:
            blocked = allowed_actions_for_role.get(role, [])
            if action.tool not in blocked:
                return {
                    "status": "violation",
                    "reason": f"Role '{role}' is restricted — action '{action.tool}' not allowed",
                    "witness": {"role": role, "tool": action.tool},
                }
        return {"status": "permitted"}

    def get_state(self) -> dict:
        return {
            "agents": self.spec.agents,
            "invariants": [i.name for i in self.spec.invariants],
            "history_count": len(self.history),
            "agent_states": self._agent_state,
        }

    def _update_state(self, action: AgentAction):
        if action.agent not in self._agent_state:
            self._agent_state[action.agent] = {}
        self._agent_state[action.agent]["last_action"] = action.tool
        self._agent_state[action.agent]["last_timestamp"] = action.timestamp
        if "lock" in action.tool.lower():
            file_key = action.args.get("target", action.args.get("file", ""))
            self._agent_state[action.agent][f"lock:{file_key}"] = True
        if "unlock" in action.tool.lower():
            file_key = action.args.get("target", action.args.get("file", ""))
            self._agent_state[action.agent][f"lock:{file_key}"] = False

        counter_key = action.args.get("counter", action.args.get("count", ""))
        if counter_key:
            new_val = action.args.get("value", action.args.get("amount", 0))
            if isinstance(new_val, (int, float)):
                self._agent_state[action.agent][f"counter:{counter_key}"] = new_val
