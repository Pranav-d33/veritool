from z3 import Solver, Bool, Not, sat, unknown

from bridge.trace import Action
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)


def check_ordering(trace: list[Action], current: Action, inv: OrderingInvariant) -> dict:
    if current.action_type != inv.before_type:
        return {"status": "permitted"}

    s = Solver()
    required_occurred = {}
    for t in inv.required_types:
        occurred = Bool(f"required_{t}")
        val = any(a.action_type == t for a in trace)
        s.add(occurred == val)
        required_occurred[t] = occurred

    s.add(current.action_type == inv.before_type)
    missing = [t for t in inv.required_types if not any(a.action_type == t for a in trace)]
    if not missing:
        return {"status": "permitted"}
    s.add(Not(required_occurred[missing[0]]))

    result = s.check()
    if result == sat:
        return {
            "status": "violation",
            "reason": f"Action '{current.action_type}' by '{current.agent}' requires prior {' ∨ '.join(inv.required_types)} — missing: {missing}",
            "witness": {"agent": current.agent, "tool": current.tool, "missing": missing},
        }
    return {"status": "permitted"}


def check_exclusive_access(trace: list[Action], current: Action, inv: ExclusiveAccessInvariant) -> dict:
    if current.action_type != inv.action_type or not current.resource:
        return {"status": "permitted"}

    for a in trace:
        if (
            a.action_type == inv.action_type
            and a.resource == current.resource
            and a.agent != current.agent
        ):
            return {
                "status": "violation",
                "reason": f"Resource '{current.resource}' is already held by agent '{a.agent}'",
                "witness": {"resource": current.resource, "existing_holder": a.agent, "requested_by": current.agent},
            }
    return {"status": "permitted"}


def check_approval(trace: list[Action], current: Action, inv: ApprovalInvariant) -> dict:
    if current.action_type != inv.action_type:
        return {"status": "permitted"}

    approved = any(
        a.action_type == inv.approver_type and a.agent != current.agent
        for a in trace
    )
    if not approved:
        return {
            "status": "violation",
            "reason": f"Action '{current.action_type}' by '{current.agent}' requires prior approval by another agent",
            "witness": {"agent": current.agent, "tool": current.tool, "action_type": current.action_type},
        }
    return {"status": "permitted"}


def check_monotonic(trace: list[Action], current: Action, inv: MonotonicInvariant, state: dict) -> dict:
    if current.action_type != inv.action_type:
        return {"status": "permitted"}

    val = current.args.get(inv.resource_key)
    if val is None or not isinstance(val, (int, float)):
        return {"status": "permitted"}

    prev = state.get(f"monotonic:{current.agent}:{current.resource or current.tool}", None)
    if prev is not None and val < prev:
        return {
            "status": "violation",
            "reason": f"Monotonic value decreased: {prev} → {val}",
            "witness": {"agent": current.agent, "resource": current.resource or current.tool, "previous": prev, "current": val},
        }
    return {"status": "permitted"}


def check_all(trace: list[Action], current: Action, invariants: list, state: dict) -> dict:
    for inv in invariants:
        handler = _dispatcher.get(type(inv))
        if handler is None:
            continue
        result = handler(trace, current, inv, state)
        if result["status"] == "violation":
            return result
    return {"status": "permitted"}


_dispatcher = {
    OrderingInvariant: lambda t, c, inv, s: check_ordering(t, c, inv),
    ExclusiveAccessInvariant: lambda t, c, inv, s: check_exclusive_access(t, c, inv),
    ApprovalInvariant: lambda t, c, inv, s: check_approval(t, c, inv),
    MonotonicInvariant: lambda t, c, inv, s: check_monotonic(t, c, inv, s),
}
