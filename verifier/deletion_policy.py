import os
from z3 import Solver, String, StringVal, Function, StringSort, BoolSort, sat, unknown

DEFAULT_ALLOWED_SCOPE = {"/project/temp", "/project/output"}


def check_deletion(
    target_path: str,
    allowed_scope: set[str] | None = None,
    timeout_ms: int = 5000,
) -> dict:
    if allowed_scope is None:
        allowed_scope = DEFAULT_ALLOWED_SCOPE

    normalized = os.path.normpath(target_path)
    s = Solver()
    s.set("timeout", timeout_ms)

    target_var = String("target")
    in_scope = Function("in_scope", StringSort(), BoolSort())

    for p in allowed_scope:
        s.add(in_scope(StringVal(os.path.normpath(p))) == True)

    s.add(target_var == StringVal(normalized))
    s.add(in_scope(target_var) == False)

    result = s.check()
    if result == sat:
        return {
            "status": "violation",
            "witness": {"target": normalized},
        }
    elif result == unknown:
        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}
    else:
        return {"status": "permitted"}
