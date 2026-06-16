from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrderingInvariant:
    before_type: str
    required_types: list[str]
    require_all: bool = True

    def __post_init__(self):
        assert self.required_types, "must require at least one prior action type"


@dataclass(frozen=True)
class ExclusiveAccessInvariant:
    action_type: str


@dataclass(frozen=True)
class ApprovalInvariant:
    action_type: str
    approver_type: str


@dataclass(frozen=True)
class MonotonicInvariant:
    action_type: str
    resource_key: str = "value"
