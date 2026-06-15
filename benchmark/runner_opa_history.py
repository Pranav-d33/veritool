"""OPA+history runner — generates per-scenario Rego policies.

Each scenario defines its own set of invariants (matching VeriTool).
We generate Rego rules from those invariants, mirroring how VeriTool
composes Z3 constraints from the same invariant list.

This is the fairest comparison: both systems receive identical
invariant definitions, same trace information.
"""

import subprocess
import time
import json
import tempfile
import os
from pathlib import Path

from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)
from benchmark.traces import scenarios


def _rego_from_invariants(invariants):
    """Generate a Rego policy from a list of invariant objects.

    Model: for each invariant, generate helper rules + a check rule.
    Allow = all check rules pass.
    """
    lines = ["package veritool_comparison", ""]

    helper_rules = []
    check_rules = []

    for inv in invariants:
        if isinstance(inv, OrderingInvariant):
            for prereq in inv.required_types:
                name = f"ordering_{inv.before_type}_{prereq}_in_history"
                helper_rules.append(f"""{name} if {{
    some a in input.history
    a.action == "{prereq}"
}}""")
            check_rules.append(f"""ordering_{inv.before_type}_ok if {{
    { '; '.join(f'ordering_{inv.before_type}_{p}_in_history' for p in inv.required_types) }
}}""")
            check_rules.append(f"""ordering_{inv.before_type}_ok if {{
    input.action != "{inv.before_type}"
}}""")

        elif isinstance(inv, ExclusiveAccessInvariant):
            name = f"conflicting_{inv.action_type}"
            helper_rules.append(f"""{name} if {{
    some a in input.history
    a.action == "{inv.action_type}"
    a.resource == input.resource
    a.agent != input.agent
}}""")
            check_rules.append(f"""exclusive_{inv.action_type}_ok if {{
    not {name}
}}""")
            check_rules.append(f"""exclusive_{inv.action_type}_ok if {{
    input.action != "{inv.action_type}"
}}""")

        elif isinstance(inv, ApprovalInvariant):
            name = f"approved_{inv.action_type}_by_other"
            helper_rules.append(f"""{name} if {{
    some a in input.history
    a.action == "{inv.approver_type}"
    a.agent != input.agent
}}""")
            check_rules.append(f"""approval_{inv.action_type}_ok if {{
    {name}
}}""")
            check_rules.append(f"""approval_{inv.action_type}_ok if {{
    input.action != "{inv.action_type}"
}}""")

        elif isinstance(inv, MonotonicInvariant):
            name = f"higher_prior_{inv.action_type}_same_agent"
            helper_rules.append(f"""{name} if {{
    some a in input.history
    a.action == "{inv.action_type}"
    a.agent == input.agent
    a.value > input.value
}}""")
            check_rules.append(f"""monotonic_{inv.action_type}_ok if {{
    not {name}
}}""")
            check_rules.append(f"""monotonic_{inv.action_type}_ok if {{
    input.action != "{inv.action_type}"
}}""")

    lines.extend(helper_rules)
    lines.append("")
    lines.extend(check_rules)
    lines.append("")

    # Allow = all check rules must pass
    check_names = sorted(set(r.split(" if")[0] for r in check_rules if " if " in r))
    if check_names:
        all_checks = " ; ".join(check_names)
        lines.append(f"allow if {{ {all_checks} }}")
    else:
        lines.append("allow if { true }")

    return "\n".join(lines)


def run_case_opa_history(case, rego_source=None):
    if rego_source is None:
        raise ValueError("rego_source required")

    history = []
    latencies_ms = []
    result_status = "permitted"
    result_detail = {}

    for agent, tool, action_type, kwargs in case["trace"]:
        inp = {
            "action": action_type,
            "agent": agent,
            "tool": tool,
            "kwargs": kwargs,
            "resource": kwargs.get("file") or kwargs.get("env") or "",
            "value": kwargs.get("value", 0),
            "history": history,
        }

        start = time.perf_counter()
        opa_out = subprocess.run(
            ["opa", "eval", "--format", "raw",
             "--data", rego_source,
             "-I",
             "data.veritool_comparison"],
            input=json.dumps(inp),
            capture_output=True, text=True, timeout=10,
        )
        elapsed = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed)

        stdout = opa_out.stdout.strip()
        has_allow = '"allow":true' in stdout

        if not has_allow:
            result_status = "blocked"
            result_detail = {"action": action_type, "agent": agent, "reason": "OPA block"}
            break

        history.append({
            "action": action_type,
            "agent": agent,
            "tool": tool,
            "kwargs": kwargs,
            "resource": kwargs.get("file") or kwargs.get("env") or "",
            "value": kwargs.get("value", 0),
        })

    return {
        "status": result_status,
        "latencies_ms": latencies_ms,
        "detail": result_detail,
    }


def run_all_history():
    results = {}
    for sc in scenarios:
        rego_src = _rego_from_invariants(sc["invariants"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
            f.write(rego_src)
            fpath = f.name
        try:
            for case in sc["cases"]:
                key = f"{sc['name']}/{case['name']}"
                r = run_case_opa_history(case, rego_source=fpath)
                results[key] = r
        finally:
            os.unlink(fpath)
    return results


if __name__ == "__main__":
    results = run_all_history()
    for key, r in results.items():
        n = len(r["latencies_ms"])
        avg = f"{sum(r['latencies_ms'])/n:.1f}ms" if n else "-"
        print(f"[{r['status'].upper()}] {key}: {r['status']} ({n} actions, avg {avg})")
