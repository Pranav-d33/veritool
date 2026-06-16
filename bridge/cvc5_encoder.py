import cvc5
from bridge.trace import Action
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)


def _maybe_skip(current: Action, action_type: str) -> bool:
    return current.action_type != action_type


def _boolean(tm: cvc5.TermManager, name: str):
    return tm.mkConst(tm.getBooleanSort(), name)


def _real(tm: cvc5.TermManager, name: str):
    return tm.mkConst(tm.getRealSort(), name)


def _mk_and(tm: cvc5.TermManager, terms: list):
    if not terms:
        return tm.mkTrue()
    result = terms[0]
    for t in terms[1:]:
        result = tm.mkTerm(cvc5.Kind.AND, result, t)
    return result


def _mk_or(tm: cvc5.TermManager, terms: list):
    if not terms:
        return tm.mkFalse()
    result = terms[0]
    for t in terms[1:]:
        result = tm.mkTerm(cvc5.Kind.OR, result, t)
    return result


def check_ordering(trace: list[Action], current: Action, inv: OrderingInvariant) -> dict:
    if _maybe_skip(current, inv.before_type):
        return {"status": "permitted"}

    missing = []
    for p in inv.required_types:
        val = any(a.action_type == p for a in trace)
        if not val:
            missing.append(p)

    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)

    if inv.require_all:
        if not missing:
            return {"status": "permitted"}
        terms = [tm.mkTerm(cvc5.Kind.NOT, _boolean(tm, f"prereq_{p}")) for p in missing]
        solver.assertFormula(_mk_and(tm, terms))
    else:
        present = [p for p in inv.required_types if p not in missing]
        if present:
            return {"status": "permitted"}
        terms = [tm.mkTerm(cvc5.Kind.NOT, _boolean(tm, f"prereq_{p}")) for p in missing]
        solver.assertFormula(_mk_and(tm, terms))

    if solver.checkSat().isSat():
        return {
            "status": "violation",
            "reason": f"Action '{current.action_type}' by '{current.agent}' requires prior {' ∧ '.join(inv.required_types) if inv.require_all else ' ∨ '.join(inv.required_types)} — missing: {missing}",
            "witness": {"agent": current.agent, "tool": current.tool, "missing": missing},
        }
    return {"status": "permitted"}


def check_exclusive_access(trace: list[Action], current: Action, inv: ExclusiveAccessInvariant) -> dict:
    if _maybe_skip(current, inv.action_type) or not current.resource:
        return {"status": "permitted"}

    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)

    has_conflict_bool = _boolean(tm, "has_conflict")
    has_conflict = any(
        a.action_type == inv.action_type and a.resource == current.resource and a.agent != current.agent
        for a in trace
    )

    solver.assertFormula(tm.mkTerm(cvc5.Kind.EQUAL, has_conflict_bool,
                         tm.mkTrue() if has_conflict else tm.mkFalse()))
    solver.assertFormula(has_conflict_bool)

    if solver.checkSat().isSat():
        return {
            "status": "violation",
            "reason": f"Resource '{current.resource}' is already held by another agent",
            "witness": {"resource": current.resource, "requested_by": current.agent},
        }
    return {"status": "permitted"}


def check_approval(trace: list[Action], current: Action, inv: ApprovalInvariant) -> dict:
    if _maybe_skip(current, inv.action_type):
        return {"status": "permitted"}

    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)

    has_approval = tm.mkTerm(cvc5.Kind.NOT, _boolean(tm, "has_approval"))
    val = any(a.action_type == inv.approver_type and a.agent != current.agent for a in trace)
    if val:
        return {"status": "permitted"}
    solver.assertFormula(has_approval)

    if solver.checkSat().isSat():
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

    prior_values = [a.args.get(inv.resource_key) for a in trace
                    if a.action_type == inv.action_type and a.agent == current.agent]
    prior_values = [v for v in prior_values if v is not None and isinstance(v, (int, float))]

    if not prior_values:
        return {"status": "permitted"}

    max_prior = max(prior_values)

    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)

    cur_val = _real(tm, "cur_val")
    max_sym = _real(tm, "max_prior")

    solver.assertFormula(tm.mkTerm(cvc5.Kind.EQUAL, cur_val, tm.mkReal(val)))
    solver.assertFormula(tm.mkTerm(cvc5.Kind.EQUAL, max_sym, tm.mkReal(max_prior)))
    solver.assertFormula(tm.mkTerm(cvc5.Kind.GT, max_sym, cur_val))

    if solver.checkSat().isSat():
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
