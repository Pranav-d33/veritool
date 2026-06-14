from z3 import (
    Solver, Int, Bool, String, StringVal,
    Function, IntSort, BoolSort, StringSort,
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

    if spec.name == "tahoe":
        _add_floor_price_defs(s, spec)
    elif spec.name == "deletion":
        _add_in_scope_defs(s, spec)
    else:
        raise BridgeError(f"Unknown policy: {spec.name}")
    return s


def _add_floor_price_defs(solver, spec: PolicySpec):
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


def _add_in_scope_defs(solver, spec: PolicySpec):
    in_scope = Function("in_scope", StringSort(), BoolSort())
    allowed_paths = {"/project/temp", "/project/output"}
    for p in allowed_paths:
        solver.add(in_scope(StringVal(p)) == True)
    return in_scope


def check_policy(spec: PolicySpec, params: dict | None = None, timeout_ms: int = 5000) -> dict:
    solver = compile_policy(spec, timeout_ms)

    if params:
        if spec.name == "tahoe":
            model_val = params.get("model", "")
            price_val = params.get("price", 0)
            solver.add(String("model") == StringVal(model_val))
            solver.add(Int("price") == price_val)

            floor_z3 = Function("floor_price", StringSort(), IntSort())
            solver.add(Int("price") < floor_z3(String("model")))

        elif spec.name == "deletion":
            target_val = params.get("target", "")
            solver.add(String("target") == StringVal(target_val))
            in_scope = Function("in_scope", StringSort(), BoolSort())
            solver.add(in_scope(String("target")) == False)

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
