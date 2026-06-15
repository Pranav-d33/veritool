from z3 import Solver, Bool, And, Or, Not, String, StringVal, Real, sat

from bridge.trace import Action
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)


def _maybe_skip(current: Action, action_type: str) -> bool:
    return current.action_type != action_type


def check_ordering(trace: list[Action], current: Action, inv: OrderingInvariant) -> dict:
    if _maybe_skip(current, inv.before_type):
        return {"status": "permitted"}

    s = Solver()
    missing = []
    for p in inv.required_types:
        occurred = Bool(f"prereq_{p}")
        val = any(a.action_type == p for a in trace)
        s.add(occurred == val)
        if not val:
            missing.append(p)

    if not missing:
        return {"status": "permitted"}

    s.add(And([Not(Bool(f"prereq_{p}")) for p in missing]))

    if s.check() == sat:
        return {
            "status": "violation",
            "reason": f"Action '{current.action_type}' by '{current.agent}' requires prior {' ∨ '.join(inv.required_types)} — missing: {missing}",
            "witness": {"agent": current.agent, "tool": current.tool, "missing": missing},
        }
    return {"status": "permitted"}


def check_exclusive_access(trace: list[Action], current: Action, inv: ExclusiveAccessInvariant) -> dict:
    if _maybe_skip(current, inv.action_type) or not current.resource:
        return {"status": "permitted"}

    s = Solver()
    has_conflict = Bool("has_conflict")
    val = any(
        a.action_type == inv.action_type and a.resource == current.resource and a.agent != current.agent
        for a in trace
    )
    s.add(has_conflict == val)
    s.add(has_conflict)

    if s.check() == sat:
        return {
            "status": "violation",
            "reason": f"Resource '{current.resource}' is already held by another agent",
            "witness": {"resource": current.resource, "requested_by": current.agent},
        }
    return {"status": "permitted"}


def check_approval(trace: list[Action], current: Action, inv: ApprovalInvariant) -> dict:
    if _maybe_skip(current, inv.action_type):
        return {"status": "permitted"}

    s = Solver()
    has_approval = Bool("has_approval")
    val = any(a.action_type == inv.approver_type and a.agent != current.agent for a in trace)
    s.add(has_approval == val)
    s.add(Not(has_approval))

    if s.check() == sat:
        return {
            "status": "violation",
            "reason": f"Action '{current.action_type}' by '{current.agent}' requires prior approval by a different agent",
            "witness": {"agent": current.agent, "tool": current.tool, "action_type": current.action_type},
        }
    return {"status": "permitted"}


def check_monotonic(trace: list[Action], current: Action, inv: MonotonicInvariant) -> dict:
    if _maybe_skip(current, inv.action_type):
        return {"status": "permitted"}

    val = current.args.get(inv.resource_key)
    if val is None or not isinstance(val, (int, float)):
        return {"status": "permitted"}

    s = Solver()
    cur_val = Real("cur_val")
    s.add(cur_val == val)

    prior_values = [a.args.get(inv.resource_key) for a in trace
                    if a.action_type == inv.action_type and a.agent == current.agent]
    prior_values = [v for v in prior_values if v is not None and isinstance(v, (int, float))]

    if not prior_values:
        return {"status": "permitted"}

    max_prior = max(prior_values)
    max_sym = Real("max_prior")
    s.add(max_sym == max_prior)
    s.add(max_sym > cur_val)

    if s.check() == sat:
        return {
            "status": "violation",
            "reason": f"Monotonic value decreased: prior max {max_prior} → {val}",
            "witness": {"agent": current.agent, "tool": current.tool, "previous_max": max_prior, "current": val},
        }
    return {"status": "permitted"}


def check_all(trace: list[Action], current: Action, invariants: list) -> dict:
    for inv in invariants:
        handler = _dispatcher.get(type(inv))
        if handler is None:
            continue
        result = handler(trace, current, inv)
        if result["status"] == "violation":
            return result
    return {"status": "permitted"}


_dispatcher = {
    OrderingInvariant: check_ordering,
    ExclusiveAccessInvariant: check_exclusive_access,
    ApprovalInvariant: check_approval,
    MonotonicInvariant: check_monotonic,
}
