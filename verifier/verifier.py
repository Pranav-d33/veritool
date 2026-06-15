import time
from dataclasses import dataclass, field
from typing import Any, Callable

from bridge.trace import Action
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)
from bridge.z3_encoder import check_all
from config import VERIFICATION_TIMEOUT_MS


@dataclass
class Verifier:
    invariants: list = field(default_factory=list)
    action_type_map: dict[str, str] = field(default_factory=dict)
    resource_extractors: dict[str, Callable] = field(default_factory=dict)
    agent_name: str = "default"
    trace: list[Action] = field(default_factory=list)

    def register_tool(self, tool_name: str, action_type: str, resource_fn: Callable | None = None):
        self.action_type_map[tool_name] = action_type
        if resource_fn:
            self.resource_extractors[tool_name] = resource_fn

    def add_invariant(self, inv):
        self.invariants.append(inv)

    def wrap(self, fn: Callable, tool_name: str | None = None):
        import functools
        tn = tool_name or fn.__name__

        @functools.wraps(fn)
        def guarded(**kwargs):
            action_type = self.action_type_map.get(tn, tn)
            resource = None
            extractor = self.resource_extractors.get(tn)
            if extractor:
                resource = extractor(kwargs)

            action = Action(
                agent=self.agent_name,
                tool=tn,
                action_type=action_type,
                args=kwargs,
                resource=resource,
                timestamp=time.time(),
            )

            result = check_all(self.trace, action, self.invariants)
            if result["status"] == "violation":
                return {"status": "blocked", "reason": result.get("reason", ""), "witness": result.get("witness", {})}

            self.trace.append(action)
            return fn(**kwargs)

        return guarded

    def reset(self):
        self.trace.clear()
