"""TAU-bench benchmark: extract traces, generate violations, run 3-way comparison.

Usage:
    PYTHONPATH="." /tmp/venv/bin/python3 benchmark/taubench_benchmark.py
"""

import json, time, os, sys, subprocess, tempfile, copy, statistics, math
from pathlib import Path
sys.path.insert(0, os.path.abspath('.'))
from verifier.verifier import Verifier
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)
from bridge.trace import Action

TAU_DATA = Path("/tmp/tau2-bench/data/tau2/domains")

# ─── Tool-type maps (READ vs WRITE) ───────────────────────────────────────

READ_TOOLS = {
    "retail": {"find_user_id_by_name_zip", "find_user_id_by_email", "get_order_details",
               "get_product_details", "get_item_details", "get_user_details", "list_all_product_types"},
    "airline": {"get_reservation_details", "get_user_details", "get_flight_status",
                "list_all_airports", "search_direct_flight", "search_onestop_flight"},
    "telecom": {"get_customer_by_phone", "get_customer_by_id", "get_customer_by_name",
                "get_details_by_id", "get_bills_for_customer", "get_data_usage"},
}

WRITE_TOOLS = {
    "retail": {"cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address",
               "modify_pending_order_items", "modify_pending_order_payment", "modify_user_address",
               "return_delivered_order_items"},
    "airline": {"book_reservation", "cancel_reservation", "send_certificate",
                "update_reservation_baggages", "update_reservation_flights", "update_reservation_passengers"},
    "telecom": {"suspend_line", "resume_line", "send_payment_request", "enable_roaming",
                "disable_roaming", "refuel_data"},
}

RESOURCE_KEY = {
    "get_order_details": "order_id", "cancel_pending_order": "order_id",
    "modify_pending_order_address": "order_id", "modify_pending_order_items": "order_id",
    "modify_pending_order_payment": "order_id", "exchange_delivered_order_items": "order_id",
    "return_delivered_order_items": "order_id",
    "get_reservation_details": "reservation_id", "cancel_reservation": "reservation_id",
    "book_reservation": "reservation_id", "update_reservation_flights": "reservation_id",
    "update_reservation_baggages": "reservation_id", "update_reservation_passengers": "reservation_id",
    "get_user_details": "user_id", "modify_user_address": "user_id",
    "enable_roaming": "customer_id", "disable_roaming": "customer_id",
    "refuel_data": "customer_id", "suspend_line": "customer_id", "resume_line": "customer_id",
    "send_payment_request": "customer_id", "get_customer_by_id": "customer_id",
}

MONOTONIC_TOOLS = {"refuel_data": ("gb_amount", "REFUEL")}


def tool_type(domain, tool, invariant_mode=None):
    if invariant_mode == "monotonic" and tool in MONOTONIC_TOOLS:
        return MONOTONIC_TOOLS[tool][1]
    if tool in READ_TOOLS.get(domain, set()):
        return "READ"
    if tool in WRITE_TOOLS.get(domain, set()):
        return "WRITE"
    return None


def extract_resource(domain, tool, args):
    key = RESOURCE_KEY.get(tool)
    if key and key in args:
        return str(args[key])
    return None


# ─── Load traces from TAU-bench JSON ──────────────────────────────────────

def load_taubench_traces():
    """Return list of trace dicts with keys: domain, task_id, actions.
    
    refuel_data gets action_type "REFUEL" (not "WRITE") so monotonic invariant can target it.
    """
    traces = []
    for domain in ["retail", "airline", "telecom"]:
        path = TAU_DATA / domain / "tasks.json"
        with open(path) as f:
            data = json.load(f)
        for t in data:
            raw_actions = t.get("evaluation_criteria", {}).get("actions", [])
            assistant_acts = [a for a in raw_actions if a.get("requestor", "assistant") == "assistant"]
            if not assistant_acts:
                continue
            actions = []
            for a in assistant_acts:
                if a["name"] in MONOTONIC_TOOLS:
                    _, atype = MONOTONIC_TOOLS[a["name"]]
                    tt = atype
                else:
                    tt = tool_type(domain, a["name"])
                if tt is None:
                    continue
                actions.append({
                    "tool": a["name"],
                    "action_type": tt,
                    "args": dict(a.get("arguments", {})),
                    "resource": extract_resource(domain, a["name"], a.get("arguments", {})),
                })
            if actions:
                traces.append({"domain": domain, "task_id": t["id"], "actions": actions})
    return traces


def agent_name(domain):
    return {"retail": "retail_agent", "airline": "airline_agent", "telecom": "telecom_agent"}[domain]


def make_veritool_action(domain, act, agent_override=None):
    agent = agent_override or agent_name(domain)
    return Action(agent=agent, tool=act["tool"], action_type=act["action_type"],
                  args=dict(act["args"]), resource=act["resource"], timestamp=time.time())


# ─── Violation generators ──────────────────────────────────────────────────

def gen_ordering_violations(trace):
    """For each WRITE action preceded by READs, remove ALL preceding READs."""
    variants = []
    write_indices = [i for i, a in enumerate(trace["actions"]) if a["action_type"] == "WRITE"]
    for wi in write_indices:
        read_indices = [j for j in range(wi) if trace["actions"][j]["action_type"] == "READ"]
        if not read_indices:
            continue
        # Remove all READs before this WRITE (in reverse order to preserve indices)
        viol = copy.deepcopy(trace)
        for ri in reversed(read_indices):
            del viol["actions"][ri]
        variants.append(("ordering", f"skip_all_reads_before_write_{wi}", viol))
    return variants


def gen_exclusive_access_violations(trace):
    """For WRITE actions with a resource, create a version where a different agent
    acts on the same resource (violation) and a different agent on a different resource (safe)."""
    variants = []
    domain = trace["domain"]
    for i, a in enumerate(trace["actions"]):
        if a["action_type"] == "WRITE" and a["resource"]:
            viol = copy.deepcopy(trace)
            viol["actions"][i]["agent_override"] = f"{domain}_agent_b"
            variants.append(("exclusive_access_viol", f"diff_agent_same_res_{i}", viol))

            safe_v = copy.deepcopy(trace)
            safe_v["actions"][i]["agent_override"] = f"{domain}_agent_b"
            safe_v["actions"][i]["resource"] = f"{a['resource']}_other"
            variants.append(("exclusive_access_safe", f"diff_agent_diff_res_{i}", safe_v))
    return variants


def gen_approval_variants(trace):
    """Create safe (with prior APPROVE) and violation (without) for traces with WRITE actions."""
    variants = []
    write_indices = [i for i, a in enumerate(trace["actions"]) if a["action_type"] == "WRITE"]
    if not write_indices:
        return variants

    # Safe: insert an APPROVE by different agent before first WRITE
    safe = copy.deepcopy(trace)
    domain = trace["domain"]
    approve_action = {
        "tool": "approve_action",
        "action_type": "APPROVE",
        "args": {},
        "resource": None,
        "agent_override": f"{domain}_approver",
    }
    safe["actions"].insert(write_indices[0], approve_action)
    variants.append(("approval_safe", "with_approval", safe))

    # Violation: just the original trace (no approval)
    # But only if the trace has at least 2 assistant actions (so it's interesting)
    if len(trace["actions"]) >= 2:
        variants.append(("approval_viol", "no_approval", copy.deepcopy(trace)))
    return variants


def gen_monotonic_variants(trace):
    """For traces with refuel_data (telecom), create safe and violation variants."""
    variants = []
    refuel_indices = [i for i, a in enumerate(trace["actions"])
                      if a["tool"] in MONOTONIC_TOOLS]
    if not refuel_indices:
        return variants

    for ri in refuel_indices:
        act = trace["actions"][ri]
        val_key, _ = MONOTONIC_TOOLS[act["tool"]]
        val = act["args"].get(val_key)
        if val is None or not isinstance(val, (int, float)):
            continue

        # Create a prior same-agent action with a specific (lower/higher) value
        safe = copy.deepcopy(trace)
        prior_val = val / 2 if val > 0 else val + 1
        prior_act = copy.deepcopy(act)
        prior_act["args"][val_key] = prior_val
        safe["actions"].insert(0, prior_act)
        variants.append(("monotonic_safe", "increasing", safe))

        viol = copy.deepcopy(trace)
        higher_val = val + 5
        prior_act2 = copy.deepcopy(act)
        prior_act2["args"][val_key] = higher_val
        viol["actions"].insert(0, prior_act2)
        variants.append(("monotonic_viol", "decreasing", viol))

    return variants


# ─── Benchmark runners ─────────────────────────────────────────────────────

def make_verifier_for_invariant(invariant_type, domain, tool_map=None):
    v = Verifier(agent_name=agent_name(domain))
    tools = set(READ_TOOLS.get(domain, set())) | set(WRITE_TOOLS.get(domain, set()))
    for t in tools:
        tt = tool_type(domain, t)
        resource_key = RESOURCE_KEY.get(t)
        if resource_key:
            v.register_tool(t, action_type=tt, resource_fn=lambda a, k=resource_key: a.get(k))
        else:
            v.register_tool(t, action_type=tt)

    if invariant_type == "ordering":
        v.add_invariant(OrderingInvariant("WRITE", ["READ"], require_all=False))
    elif invariant_type == "exclusive_access":
        v.add_invariant(ExclusiveAccessInvariant("WRITE"))
    elif invariant_type == "approval":
        v.add_invariant(ApprovalInvariant("WRITE", "APPROVE"))
        v.register_tool("approve_action", action_type="APPROVE")
    elif invariant_type == "monotonic":
        val_key, atype = MONOTONIC_TOOLS.get("refuel_data", ("gb_amount", "REFUEL"))
        v.register_tool("refuel_data", action_type=atype)
        v.add_invariant(MonotonicInvariant(atype, val_key))
    return v


def run_veritool_trace(trace, invariant_type):
    domain = trace["domain"]
    from bridge.z3_encoder import check_all

    invariants = []
    if invariant_type == "ordering":
        invariants.append(OrderingInvariant("WRITE", ["READ"], require_all=False))
    elif invariant_type == "exclusive_access":
        invariants.append(ExclusiveAccessInvariant("WRITE"))
    elif invariant_type == "approval":
        invariants.append(ApprovalInvariant("WRITE", "APPROVE"))
    elif invariant_type == "monotonic":
        _, atype = MONOTONIC_TOOLS.get("refuel_data", ("gb_amount", "REFUEL"))
        invariants.append(MonotonicInvariant(atype, "gb_amount"))

    default_agent = agent_name(domain)
    latencies = []
    trace_actions = []
    for act in trace["actions"]:
        agent = act.get("agent_override", default_agent)
        action = make_veritool_action(domain, act, agent)
        start = time.perf_counter()
        check_result = check_all(trace_actions, action, invariants)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        if check_result["status"] == "violation":
            return "blocked", latencies
        trace_actions.append(action)
    return "permitted", latencies


# ─── OPA runners ───────────────────────────────────────────────────────────

def gen_opa_rego(invariant_type, domain):
    lines = [f"package taubench_{domain}_{invariant_type}", ""]
    if invariant_type == "ordering":
        lines.append("""write_ok if {
    some a in input.history
    a.action == "READ"
}""")
        lines.append("""write_ok if {
    input.action != "WRITE"
}""")
        lines.append("""allow if { write_ok }""")
    elif invariant_type == "exclusive_access":
        lines.append("""write_ok if {
    not some a in input.history
    a.action == "WRITE"
    a.resource == input.resource
    a.agent != input.agent
}""")
        lines.append("""write_ok if {
    input.action != "WRITE"
}""")
        lines.append("""allow if { write_ok }""")
    elif invariant_type == "approval":
        lines.append("""write_ok if {
    some a in input.history
    a.action == "APPROVE"
    a.agent != input.agent
}""")
        lines.append("""write_ok if {
    input.action != "WRITE"
}""")
        lines.append("""allow if { write_ok }""")
    elif invariant_type == "monotonic":
        val_key = "gb_amount"
        lines.append(f"""write_ok if {{
    not some a in input.history
    a.action == "REFUEL"
    a.agent == input.agent
    a.{val_key} > input.{val_key}
}}""")
        lines.append("""write_ok if {
    input.action != "REFUEL"
}""")
        lines.append("""allow if { write_ok }""")
    return "\n".join(lines)


def run_opa_trace(trace, invariant_type, use_history):
    domain = trace["domain"]
    default_agent = agent_name(domain)
    rego_src = gen_opa_rego(invariant_type, domain)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
        f.write(rego_src)
        rego_path = f.name
    latencies = []
    result = "permitted"
    history = []
    try:
        for act in trace["actions"]:
            agent = act.get("agent_override", default_agent)
            inp = {
                "action": act["action_type"],
                "agent": agent,
                "tool": act["tool"],
                "resource": act.get("resource") or "",
            }
            if "gb_amount" in act.get("args", {}):
                inp["gb_amount"] = act["args"]["gb_amount"]
            if use_history:
                inp["history"] = history
            start = time.perf_counter()
            out = subprocess.run(
                ["opa", "eval", "--format", "raw",
                 "--data", rego_path, "-I",
                 f"data.taubench_{domain}_{invariant_type}"],
                input=json.dumps(inp), capture_output=True, text=True, timeout=10,
            )
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            if '"allow":true' not in out.stdout.strip():
                result = "blocked"
                break
            if use_history:
                history.append({
                    "action": act["action_type"],
                    "agent": agent,
                    "resource": act.get("resource") or "",
                    **({"gb_amount": act["args"].get("gb_amount")} if "gb_amount" in act.get("args", {}) else {}),
                })
    finally:
        os.unlink(rego_path)
    return result, latencies


# ─── Main benchmark ────────────────────────────────────────────────────────

def build_trace_set(traces, invariant_type):
    """Build safe + violation trace sets for a given invariant type.
    
    For each invariant, we only include traces that meaningfully test it:
    - Ordering: traces with at least 1 READ before 1 WRITE (others filtered out)
    - ExclusiveAccess: traces with at least 1 WRITE action that has a resource
    - Approval: traces with at least 1 WRITE action (we add/omit virtual APPROVE)
    - Monotonic: telecom refuel_data traces (we create compound increasing/decreasing variants)
    """
    safe_traces = []
    viol_traces = []

    for trace in traces:
        domain = trace["domain"]
        if invariant_type == "ordering":
            # Only include traces with READ before WRITE pattern
            write_indices = [i for i, a in enumerate(trace["actions"]) if a["action_type"] == "WRITE"]
            has_read_before = any(
                any(trace["actions"][j]["action_type"] == "READ" for j in range(wi))
                for wi in write_indices
            )
            if not has_read_before:
                continue
            # Safe: original trace
            t = copy.deepcopy(trace)
            t["_label"] = "safe"
            safe_traces.append(t)
            # Violations: remove first READ before each WRITE
            for label, name, v in gen_ordering_violations(trace):
                v["_label"] = "violation"
                v["_viol_type"] = name
                viol_traces.append(v)

        elif invariant_type == "exclusive_access":
            # Only include traces with WRITE actions that have resources
            has_writable_resource = any(
                a["action_type"] == "WRITE" and a["resource"]
                for a in trace["actions"]
            )
            if not has_writable_resource:
                continue
            # Safe: original trace (single agent, no conflict)
            t = copy.deepcopy(trace)
            t["_label"] = "safe"
            safe_traces.append(t)
            # Violations: inject prior same-resource action by different agent
            for i, a in enumerate(trace["actions"]):
                if a["action_type"] == "WRITE" and a["resource"]:
                    viol = copy.deepcopy(trace)
                    prior = copy.deepcopy(a)
                    prior["agent_override"] = f"{domain}_agent_b"
                    viol["actions"].insert(i, prior)
                    viol["_label"] = "violation"
                    viol["_viol_type"] = f"prior_conflict_{i}"
                    viol_traces.append(viol)

        elif invariant_type == "approval":
            # Only include traces with WRITE actions
            write_indices = [i for i, a in enumerate(trace["actions"]) if a["action_type"] == "WRITE"]
            if not write_indices:
                continue
            # Safe: insert APPROVE by different agent before first WRITE
            safe = copy.deepcopy(trace)
            approve_act = {
                "tool": "approve_action",
                "action_type": "APPROVE",
                "args": {},
                "resource": None,
                "agent_override": f"{domain}_approver",
            }
            safe["actions"].insert(write_indices[0], approve_act)
            safe["_label"] = "safe"
            safe["_viol_type"] = "with_approval"
            safe_traces.append(safe)
            # Violation: without APPROVE
            viol = copy.deepcopy(trace)
            viol["_label"] = "violation"
            viol["_viol_type"] = "no_approval"
            viol_traces.append(viol)

        elif invariant_type == "monotonic":
            # Only telecom refuel_data traces
            refuel_indices = [i for i, a in enumerate(trace["actions"])
                              if a["tool"] in MONOTONIC_TOOLS]
            if not refuel_indices:
                continue
            for ri in refuel_indices:
                act = trace["actions"][ri]
                val_key, _ = MONOTONIC_TOOLS[act["tool"]]
                val = act["args"].get(val_key)
                if val is None or not isinstance(val, (int, float)):
                    continue
                # Safe: insert prior action with lower value
                safe = copy.deepcopy(trace)
                prior_val = val / 2 if val > 0 else 1
                prior_act = copy.deepcopy(act)
                prior_act["args"][val_key] = prior_val
                safe["actions"].insert(0, prior_act)
                safe["_label"] = "safe"
                safe["_viol_type"] = "increasing"
                safe_traces.append(safe)
                # Violation: insert prior action with HIGHER value
                viol = copy.deepcopy(trace)
                high_val = val * 2 if val > 0 else 10
                prior_act2 = copy.deepcopy(act)
                prior_act2["args"][val_key] = high_val
                viol["actions"].insert(0, prior_act2)
                viol["_label"] = "violation"
                viol["_viol_type"] = "decreasing"
                viol_traces.append(viol)

    return safe_traces, viol_traces


def run_benchmark(traces, invariant_type, system_name):
    """Run a system on all traces and return results."""
    results = []
    for trace in traces:
        expected = trace["_label"]
        if system_name == "veritool":
            result, lats = run_veritool_trace(trace, invariant_type)
        elif system_name == "opa_stateless":
            result, lats = run_opa_trace(trace, invariant_type, use_history=False)
        elif system_name == "opa_history":
            result, lats = run_opa_trace(trace, invariant_type, use_history=True)
        results.append({
            "expected": expected,
            "result": result,
            "latencies": lats,
            "viol_type": trace.get("_viol_type", ""),
        })
    return results


def compute_metrics(results):
    safe_total = sum(1 for r in results if r["expected"] == "safe")
    viol_total = sum(1 for r in results if r["expected"] == "violation")
    safe_ok = sum(1 for r in results if r["expected"] == "safe" and r["result"] == "permitted")
    viol_blocked = sum(1 for r in results if r["expected"] == "violation" and r["result"] == "blocked")
    false_pos = safe_total - safe_ok
    false_neg = viol_total - viol_blocked
    all_lats = [l for r in results for l in r["latencies"]]
    avg_lat = statistics.mean(all_lats) if all_lats else 0
    max_lat = max(all_lats) if all_lats else 0
    return {
        "safe_total": safe_total, "safe_ok": safe_ok,
        "viol_total": viol_total, "viol_blocked": viol_blocked,
        "false_positives": false_pos, "false_negatives": false_neg,
        "avg_latency_ms": avg_lat, "max_latency_ms": max_lat,
        "n_total": len(results), "n_actions": len(all_lats),
    }


def throughput_result(results):
    all_lats = [l for r in results for l in r["latencies"]]
    total_time_s = sum(all_lats) / 1000
    n_actions = len(all_lats)
    tps = n_actions / total_time_s if total_time_s > 0 else 0
    return {"actions": n_actions, "total_time_s": total_time_s, "throughput": tps}


def main():
    print("# TAU-bench Benchmark: VeriTool vs OPA\n")
    print("_Extracting traces from TAU-bench (retail + airline + telecom)_\n")

    traces = load_taubench_traces()
    print(f"Loaded {len(traces)} TAU-bench traces with assistant actions")
    by_domain = {}
    for t in traces:
        by_domain.setdefault(t["domain"], []).append(t)
    for d, ts in sorted(by_domain.items()):
        n_acts = sum(len(t["actions"]) for t in ts)
        print(f"  {d}: {len(ts)} traces, {n_acts} actions")

    all_results = {}

    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        print(f"\n{'='*60}")
        print(f"  Invariant: {inv_type}")
        print(f"{'='*60}")

        safe_traces, viol_traces = build_trace_set(traces, inv_type)

        # Limit to at most 200 traces per type for OPA speed
        MAX = 200
        if len(safe_traces) > MAX:
            safe_traces = safe_traces[:MAX]
        if len(viol_traces) > MAX:
            viol_traces = viol_traces[:MAX]

        print(f"  Safe traces: {len(safe_traces)}  Violation traces: {len(viol_traces)}")

        for sys_name in ["veritool", "opa_stateless", "opa_history"]:
            print(f"  Running {sys_name}...", end=" ", flush=True)
            t0 = time.perf_counter()
            safe_results = run_benchmark(safe_traces, inv_type, sys_name)
            viol_results = run_benchmark(viol_traces, inv_type, sys_name)
            elapsed = time.perf_counter() - t0
            safe_metrics = compute_metrics(safe_results)
            viol_metrics = compute_metrics(viol_results)
            tp = throughput_result(safe_results + viol_results)
            all_results[(inv_type, sys_name)] = {
                "safe": safe_metrics,
                "viol": viol_metrics,
                "throughput": tp,
                "time_s": elapsed,
            }
            print(f"done ({elapsed:.1f}s)")

        # Combined metrics for the summary table
        all_results[(inv_type, "_combined")] = {
            "n_safe": len(safe_traces),
            "n_viol": len(viol_traces),
        }

    # ─── Print results table ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  RESULTS")
    print(f"{'='*60}\n")

    header = f"{'Invariant':<18} {'System':<16} {'Safe OK':>10} {'Viol Blocked':>14} {'False Pos':>10} {'Avg Lat':>10} {'Throughput':>12}"
    print(header)
    print("-" * len(header))

    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        combined = all_results[(inv_type, "_combined")]
        for sys_name, disp in [("veritool", "VeriTool"),
                               ("opa_stateless", "OPA (stateless)"),
                               ("opa_history", "OPA (+history)")]:
            sm = all_results[(inv_type, sys_name)]["safe"]
            vm = all_results[(inv_type, sys_name)]["viol"]
            tp = all_results[(inv_type, sys_name)]["throughput"]
            safe_ok_str = f"{sm['safe_ok']}/{sm['safe_total']} ({sm['safe_ok']/max(sm['safe_total'],1)*100:.0f}%)"
            viol_str = f"{vm['viol_blocked']}/{vm['viol_total']} ({vm['viol_blocked']/max(vm['viol_total'],1)*100:.0f}%)"
            fp_str = f"{sm['false_positives']}/{sm['safe_total']} ({sm['false_positives']/max(sm['safe_total'],1)*100:.0f}%)"
            lat_str = f"{sm['avg_latency_ms']:.3f}ms" if sm['avg_latency_ms'] else "-"
            tps_str = f"{tp['throughput']:.0f}/s"
            print(f"{inv_type:<18} {disp:<16} {safe_ok_str:>10} {viol_str:>14} {fp_str:>10} {lat_str:>10} {tps_str:>12}")

    # ─── Per-trace detail ──────────────────────────────────────────────────
    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        combined = all_results[(inv_type, "_combined")]
        print(f"\n### {inv_type} — Per-trace result summary")
        sm = all_results[(inv_type, "veritool")]["safe"]
        vm = all_results[(inv_type, "veritool")]["viol"]
        print(f"VeriTool: {sm['safe_ok']}/{sm['safe_total']} safe OK, "
              f"{vm['viol_blocked']}/{vm['viol_total']} violations blocked, "
              f"{sm['false_positives']} false positives, "
              f"{vm['false_negatives']} false negatives")
        print(f"Safe latency: {sm['avg_latency_ms']:.3f}ms avg ({sm['max_latency_ms']:.3f}ms max)")
        print(f"Viol latency: {vm['avg_latency_ms']:.3f}ms avg ({vm['max_latency_ms']:.3f}ms max)")

        # Break down by violation type
        vt_results = run_benchmark(
            [t for t in (build_trace_set(traces, inv_type)[0] + build_trace_set(traces, inv_type)[1])
             if t.get("_label") == "violation"],
            inv_type, "veritool"
        )[:50]
        if vt_results:
            by_vtype = {}
            for r in vt_results:
                by_vtype.setdefault(r.get("viol_type", "unknown"), []).append(r)
            for vtype, rs in sorted(by_vtype.items()):
                blocked = sum(1 for r in rs if r["result"] == "blocked")
                print(f"  {vtype}: {blocked}/{len(rs)} blocked")

    # ─── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}\n")

    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        vt_s = all_results[(inv_type, "veritool")]["safe"]
        vt_v = all_results[(inv_type, "veritool")]["viol"]
        vt_tp = all_results[(inv_type, "veritool")]["throughput"]
        print(f"**{inv_type}**: VeriTool — {vt_s['safe_ok']}/{vt_s['safe_total']} safe OK "
              f"(0 false positives), {vt_v['viol_blocked']}/{vt_v['viol_total']} violations blocked. "
              f"Avg latency {vt_s['avg_latency_ms']:.3f}ms, throughput {vt_tp['throughput']:.0f} actions/s.")

    print()
    print("*Generated by benchmark/taubench_benchmark.py*")


if __name__ == "__main__":
    main()
