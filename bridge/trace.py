from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    agent: str
    tool: str
    action_type: str
    args: dict[str, Any]
    resource: str | None = None
    timestamp: float = 0.0
