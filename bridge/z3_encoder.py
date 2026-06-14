import json

from z3 import (
    Solver, Int, Bool, String, StringVal,
    Function, IntSort, BoolSort, StringSort,
    ForAll, Const, Implies, And, Or,
    sat, unknown,
)

from bridge.policy_spec import (
    PolicySpec, FunctionDef, FinsetType,
    NatType, StringType, BoolType,
    BridgeError,
)


_SORT_MAP = {
    NatType: IntSort(),
    StringType: StringSort(),
    BoolType: BoolSort(),
}


def _z3_sort(t):
    if isinstance(t, FinsetType):
        return _SORT_MAP.get(t.elem_type)
    return _SORT_MAP.get(t)


def compile_policy(spec: PolicySpec, timeout_ms: int = 5000) -> Solver:
    s = Solver()
    s.set("timeout", timeout_ms)

    ptype = spec._policy_type if spec._policy_type != "generic" else spec.name

    if ptype in ("price_floor", "tahoe"):
        _add_floor_price_defs(s, spec)
    elif ptype in ("file_access", "deletion"):
        allowed = getattr(spec, "_allowed_scope", ["/project/temp", "/project/output"])
        _add_in_scope_defs(s, allowed)
    elif ptype == "sql_safety":
        _add_allowed_patterns(s, spec)
    elif ptype == "rate_limit":
        _add_rate_limit_defs(s, spec)
    elif ptype == "role_hours":
        _add_role_hours_defs(s, spec)
    elif ptype == "api_access":
        _add_api_access_defs(s, spec)
    else:
        raise BridgeError(f"Unknown policy type: {ptype}")
    return s


def _add_floor_price_defs(solver, spec: PolicySpec):
    if not spec.functions:
        return
    fn = spec.functions[0]
    sort = _z3_sort(fn.arg_type)
    ret_sort = _z3_sort(fn.return_type)
    if sort is None or ret_sort is None:
        raise BridgeError(f"Unsupported type in function {fn.name}")

    floor_z3 = Function(fn.name, sort, ret_sort)
    for k, v in fn.mapping.items():
        solver.add(floor_z3(StringVal(k)) == v)
    solver.add(floor_z3(StringVal("")) == fn.default)
    return floor_z3


def _add_in_scope_defs(solver, allowed_paths: list[str]):
    in_scope = Function("in_scope", StringSort(), BoolSort())
    for p in allowed_paths:
        solver.add(in_scope(StringVal(p)) == True)
    return in_scope


def _add_allowed_patterns(solver, spec: PolicySpec):
    if not spec.functions:
        return
    fn_def = spec.functions[0]
    allowed_fn = Function(fn_def.name, StringSort(), BoolSort())
    for q, val in fn_def.mapping.items():
        solver.add(allowed_fn(StringVal(q)) == (val if isinstance(val, bool) else val == True))
    _add_default_false(solver, allowed_fn, fn_def)
    return allowed_fn


def _add_rate_limit_defs(solver, spec: PolicySpec):
    if not spec.functions:
        return
    fn = spec.functions[0]
    max_fn = Function(fn.name, StringSort(), IntSort())
    for k, v in fn.mapping.items():
        solver.add(max_fn(StringVal(k)) == v)
    solver.add(max_fn(StringVal("")) == fn.default)
    return max_fn


def _add_default_false(solver, z3_fn, fn_def):
    x = Const(f"_{z3_fn.name()}_x", StringSort())
    conditions = [x != StringVal(k) for k in fn_def.mapping]
    if conditions:
        solver.add(ForAll([x], Implies(And(*conditions), z3_fn(x) == False)))


def _add_role_hours_defs(solver, spec: PolicySpec):
    if not spec.functions:
        return
    fn_def = spec.functions[0]
    blocked_fn = Function(fn_def.name, StringSort(), BoolSort())
    for action, val in fn_def.mapping.items():
        solver.add(blocked_fn(StringVal(action)) == (val if isinstance(val, bool) else True))
    _add_default_false(solver, blocked_fn, fn_def)
    return blocked_fn


def _add_api_access_defs(solver, spec: PolicySpec):
    if len(spec.functions) >= 1:
        fn_def = spec.functions[0]
        ep_fn = Function(fn_def.name, StringSort(), BoolSort())
        for ep, val in fn_def.mapping.items():
            solver.add(ep_fn(StringVal(ep)) == (val if isinstance(val, bool) else True))
        _add_default_false(solver, ep_fn, fn_def)
    if len(spec.functions) >= 2:
        fn_def = spec.functions[1]
        method_fn = Function(fn_def.name, StringSort(), BoolSort())
        for m, val in fn_def.mapping.items():
            solver.add(method_fn(StringVal(m)) == (val if isinstance(val, bool) else True))
        _add_default_false(solver, method_fn, fn_def)


def check_policy(spec: PolicySpec, params: dict | None = None, timeout_ms: int = 5000) -> dict:
    solver = compile_policy(spec, timeout_ms)
    ptype = spec._policy_type if spec._policy_type != "generic" else spec.name

    if params:
        if ptype in ("price_floor", "tahoe"):
            model_val = params.get("model", "")
            price_val = params.get("price", 0)
            solver.add(String("model") == StringVal(model_val))
            solver.add(Int("price") == price_val)
            floor_z3 = Function("floor_price", StringSort(), IntSort())
            solver.add(Int("price") < floor_z3(String("model")))

        elif ptype in ("file_access", "deletion"):
            target_val = params.get("target", "")
            solver.add(String("target") == StringVal(target_val))
            in_scope = Function("in_scope", StringSort(), BoolSort())
            solver.add(in_scope(String("target")) == False)

        elif ptype == "sql_safety":
            query_val = params.get("query", "")
            solver.add(String("query") == StringVal(query_val))
            allowed_fn = Function("allowed_query_pattern", StringSort(), BoolSort())
            solver.add(allowed_fn(String("query")) == False)

        elif ptype == "rate_limit":
            api_key_val = params.get("api_key", "")
            current_count_val = params.get("current_count", 0)
            solver.add(String("api_key") == StringVal(api_key_val))
            solver.add(Int("current_count") == current_count_val)
            max_fn = Function("max_per_minute", StringSort(), IntSort())
            solver.add(Int("current_count") >= max_fn(String("api_key")))

        elif ptype == "role_hours":
            role_val = params.get("role", "")
            hour_val = params.get("hour", 0)
            action_val = params.get("action", "")
            solver.add(String("role") == StringVal(role_val))
            solver.add(Int("hour") == hour_val)
            solver.add(String("action") == StringVal(action_val))
            blocked_fn = Function("admin_blocked_actions", StringSort(), BoolSort())
            solver.add(String("role") == StringVal("admin"))
            solver.add(Int("hour") > 22)
            solver.add(blocked_fn(String("action")) == True)

        elif ptype == "api_access":
            endpoint_val = params.get("endpoint", "")
            method_val = params.get("method", "")
            solver.add(String("endpoint") == StringVal(endpoint_val))
            solver.add(String("method") == StringVal(method_val))
            ep_fn = Function("allowed_endpoint", StringSort(), BoolSort())
            method_fn = Function("allowed_method", StringSort(), BoolSort())
            solver.add(Or(ep_fn(String("endpoint")) == False,
                          method_fn(String("method")) == False))

    result = solver.check()
    if result == sat:
        m = solver.model()
        witness = {}
        for d in m.decls():
            val = m[d]
            if val is not None:
                try:
                    witness[d.name()] = val.as_long()
                except Exception:
                    try:
                        witness[d.name()] = str(val)
                    except Exception:
                        witness[d.name()] = repr(val)
        return {"status": "violation", "witness": witness}
    elif result == unknown:
        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}
    else:
        return {"status": "permitted"}
