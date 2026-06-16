"""Ablation experiments for VeriTool paper.

Four experiments:
  1. Incremental vs batch (full-trace one-shot encoding)
  2. Solver swap (Z3 vs CVC5)
  3. Cross-invariant overhead (all 4 together vs individual)
  4. Trace depth saturation (latency vs trace size per invariant)

Usage:
    PYTHONPATH="." python3 benchmark/ablation_benchmark.py
    PYTHONPATH="." /tmp/cvc5_venv/bin/python3 benchmark/ablation_benchmark.py  # for solver swap
"""

import json, time, os, sys, statistics, copy, itertools
from pathlib import Path
sys.path.insert(0, os.path.abspath('.'))

sys.path.insert(0, "/tmp/tau2-bench/src")

from benchmark.taubench_benchmark import (
    load_taubench_traces, build_trace_set, agent_name, MONOTONIC_TOOLS,
    READ_TOOLS, WRITE_TOOLS, RESOURCE_KEY, make_veritool_action, tool_type,
)

from bridge.z3_encoder import check_all as z3_check_all
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)
from bridge.trace import Action

DATA_PATH = Path("benchmark/benchmark_data.json")
OUT = Path("benchmark/graphs")


def load_data():
    return json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else {}


def save_data(data):
    DATA_PATH.write_text(json.dumps(data, indent=2, default=str))


# ─── Shared helpers ────────────────────────────────────────────────────────

def make_actions_for_trace(trace):
    """Convert a trace dict to a list of Action objects."""
    domain = trace["domain"]
    default_agent = agent_name(domain)
    actions = []
    for act in trace["actions"]:
        agent = act.get("agent_override", default_agent)
        actions.append(make_veritool_action(domain, act, agent))
    return actions


def trace_invariants(invariant_type):
    """Return list with one invariant of the given type."""
    if invariant_type == "ordering":
        return [OrderingInvariant("WRITE", ["READ"], require_all=False)]
    elif invariant_type == "exclusive_access":
        return [ExclusiveAccessInvariant("WRITE")]
    elif invariant_type == "approval":
        return [ApprovalInvariant("WRITE", "APPROVE")]
    elif invariant_type == "monotonic":
        return [MonotonicInvariant("REFUEL", "gb_amount")]
    return []


def all_four_invariants():
    return [
        OrderingInvariant("WRITE", ["READ"], require_all=False),
        ExclusiveAccessInvariant("WRITE"),
        ApprovalInvariant("WRITE", "APPROVE"),
        MonotonicInvariant("REFUEL", "gb_amount"),
    ]


# ─── Ablation 1: Incremental vs Batch ──────────────────────────────────────

from z3 import Solver, Bool, And, Or, Not, sat


def check_ordering_batch(trace_actions, inv):
    """Z3 batch: encode ALL actions into one formula.
    
    ∃ i (is_write_i ∧ ¬has_read_before_i) → violation exists.
    """
    s = Solver()
    viol_terms = []
    for i, act in enumerate(trace_actions):
        if act.action_type != inv.before_type:
            continue
        if inv.require_all:
            missing = [p for p in inv.required_types
                       if not any(trace_actions[j].action_type == p for j in range(i))]
            if missing:
                viol_terms.append(And([Not(Bool(f"prereq_{i}_{p}")) for p in missing]))
        else:
            has_any = any(
                trace_actions[j].action_type in inv.required_types
                for j in range(i)
            )
            if not has_any:
                viol_terms.append(Bool(f"no_prior_{i}"))

    if not viol_terms:
        return {"status": "permitted"}
    s.add(Or(viol_terms))
    if s.check() == sat:
        return {"status": "violation", "reason": "batch encoding"}
    return {"status": "permitted"}


def check_exclusive_access_batch(trace_actions, inv):
    s = Solver()
    viol_terms = []
    for i, act in enumerate(trace_actions):
        if act.action_type != inv.action_type or not act.resource:
            continue
        conflict = any(
            trace_actions[j].action_type == inv.action_type
            and trace_actions[j].resource == act.resource
            and trace_actions[j].agent != act.agent
            for j in range(i)
        )
        if conflict:
            viol_terms.append(Bool(f"conflict_{i}"))
    if not viol_terms:
        return {"status": "permitted"}
    s.add(Or(viol_terms))
    if s.check() == sat:
        return {"status": "violation", "reason": "batch encoding"}
    return {"status": "permitted"}


def check_approval_batch(trace_actions, inv):
    s = Solver()
    viol_terms = []
    for i, act in enumerate(trace_actions):
        if act.action_type != inv.action_type:
            continue
        if not any(
            trace_actions[j].action_type == inv.approver_type
            and trace_actions[j].agent != act.agent
            for j in range(i)
        ):
            viol_terms.append(Bool(f"no_approval_{i}"))
    if not viol_terms:
        return {"status": "permitted"}
    s.add(Or(viol_terms))
    if s.check() == sat:
        return {"status": "violation", "reason": "batch encoding"}
    return {"status": "permitted"}


def check_monotonic_batch(trace_actions, inv):
    s = Solver()
    viol_terms = []
    for i, act in enumerate(trace_actions):
        if act.action_type != inv.action_type:
            continue
        val = act.args.get(inv.resource_key)
        if val is None or not isinstance(val, (int, float)):
            continue
        prior_vals = [
            trace_actions[j].args.get(inv.resource_key)
            for j in range(i)
            if trace_actions[j].action_type == inv.action_type
            and trace_actions[j].agent == act.agent
        ]
        prior_vals = [v for v in prior_vals if v is not None and isinstance(v, (int, float))]
        if prior_vals and max(prior_vals) > val:
            viol_terms.append(Bool(f"decrease_{i}"))
    if not viol_terms:
        return {"status": "permitted"}
    s.add(Or(viol_terms))
    if s.check() == sat:
        return {"status": "violation", "reason": "batch encoding"}
    return {"status": "permitted"}


BATCH_DISPATCH = {
    OrderingInvariant: check_ordering_batch,
    ExclusiveAccessInvariant: check_exclusive_access_batch,
    ApprovalInvariant: check_approval_batch,
    MonotonicInvariant: check_monotonic_batch,
}


def check_batch(trace_actions, invariants):
    for inv in invariants:
        handler = BATCH_DISPATCH.get(type(inv))
        if handler is None:
            continue
        result = handler(trace_actions, inv)
        if result["status"] == "violation":
            return result
    return {"status": "permitted"}


def run_incremental(trace_actions, invariants, check_fn):
    trace_prefix = []
    latencies = []
    result = "permitted"
    for act in trace_actions:
        t0 = time.perf_counter()
        r = check_fn(trace_prefix, act, invariants)
        elapsed = (time.perf_counter() - t0) * 1_000_000
        latencies.append(elapsed)
        if r["status"] == "violation":
            result = "blocked"
            break
        trace_prefix.append(act)
    return result, latencies


def run_batch(trace_actions, invariants):
    t0 = time.perf_counter()
    r = check_batch(trace_actions, invariants)
    elapsed = (time.perf_counter() - t0) * 1_000_000
    result = "blocked" if r["status"] == "violation" else "permitted"
    return result, [elapsed]


def ablation1_incremental_vs_batch(traces):
    print("\n# Ablation 1: Incremental vs Batch (one-shot) encoding\n")

    results = {}
    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        safe_traces, viol_traces = build_trace_set(traces, inv_type)
        all_test = (safe_traces + viol_traces)[:100]
        invariants = trace_invariants(inv_type)

        inc_times = []
        batch_times = []
        inc_correct = 0
        batch_correct = 0

        for t in all_test:
            acts = make_actions_for_trace(t)

            _, inc_lats = run_incremental(acts, invariants, z3_check_all)
            inc_times.append(sum(inc_lats))

            _, batch_lats = run_batch(acts, invariants)
            batch_times.append(sum(batch_lats))

            # Correctness check: result must match
            inc_r, _ = run_incremental(acts, invariants, z3_check_all)
            batch_r, _ = run_batch(acts, invariants)
            expected = "blocked" if t.get("_label") == "violation" else "permitted"
            if inc_r == expected:
                inc_correct += 1
            if batch_r == expected:
                batch_correct += 1

        results[inv_type] = {
            "n_traces": len(all_test),
            "inc_total_us": statistics.mean(inc_times),
            "batch_total_us": statistics.mean(batch_times),
            "inc_median_us": statistics.median(inc_times),
            "batch_median_us": statistics.median(batch_times),
            "inc_correct": inc_correct,
            "batch_correct": batch_correct,
            "speedup": statistics.mean(batch_times) / max(statistics.mean(inc_times), 1),
        }
        print(f"  {inv_type}: inc={results[inv_type]['inc_total_us']:.1f}us  "
              f"batch={results[inv_type]['batch_total_us']:.1f}us  "
              f"speedup={results[inv_type]['speedup']:.1f}x")

    return results


# ─── Ablation 2: Solver swap (Z3 vs CVC5) ──────────────────────────────────

def check_all_cvc5(trace, current, invariants):
    from bridge.cvc5_encoder import check_all as cvc5_check
    return cvc5_check(trace, current, invariants)


def ablation2_solver_swap(traces):
    print("\n# Ablation 2: Solver swap (Z3 vs CVC5)\n")

    from bridge.cvc5_encoder import check_all as cvc5_check

    results = {}
    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        safe_traces, viol_traces = build_trace_set(traces, inv_type)
        all_test = (safe_traces + viol_traces)[:50]
        invariants = trace_invariants(inv_type)

        z3_lats = []
        cvc5_lats = []
        z3_correct = 0
        cvc5_correct = 0

        for t in all_test:
            acts = make_actions_for_trace(t)
            expected = "blocked" if t.get("_label") == "violation" else "permitted"

            # Z3
            r, lats = run_incremental(acts, invariants, z3_check_all)
            z3_lats.append(sum(lats))
            if r == expected:
                z3_correct += 1

            # CVC5
            r2, lats2 = run_incremental(acts, invariants, cvc5_check)
            cvc5_lats.append(sum(lats2))
            if r2 == expected:
                cvc5_correct += 1

        results[inv_type] = {
            "n_traces": len(all_test),
            "z3_avg_us": statistics.mean(z3_lats),
            "cvc5_avg_us": statistics.mean(cvc5_lats),
            "z3_median_us": statistics.median(z3_lats),
            "cvc5_median_us": statistics.median(cvc5_lats),
            "z3_correct": z3_correct,
            "cvc5_correct": cvc5_correct,
        }
        ratio = results[inv_type]["z3_avg_us"] / max(results[inv_type]["cvc5_avg_us"], 1)
        print(f"  {inv_type}: Z3={results[inv_type]['z3_avg_us']:.1f}us  "
              f"CVC5={results[inv_type]['cvc5_avg_us']:.1f}us  "
              f"ratio={ratio:.2f}x")

    return results


# ─── Ablation 3: Cross-invariant overhead ──────────────────────────────────

def ablation3_cross_invariant(traces):
    print("\n# Ablation 3: Cross-invariant overhead\n")

    safe_traces_all = {}
    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        s, _ = build_trace_set(traces, inv_type)
        safe_traces_all[inv_type] = s[:30]

    # Use telecom traces (have refuel_data which exercises all 4 meaningfully)
    telecom_traces = [t for t in traces if t["domain"] == "telecom"][:40]

    results = {"individual": {}, "combined": {}}
    comb_invariants = all_four_invariants()

    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        test_traces = safe_traces_all[inv_type]

        # Individual
        ind_lats = []
        for t in test_traces:
            acts = make_actions_for_trace(t)
            _, lats = run_incremental(acts, trace_invariants(inv_type), z3_check_all)
            ind_lats.append(sum(lats))
        results["individual"][inv_type] = {
            "n_traces": len(test_traces),
            "avg_us": statistics.mean(ind_lats),
            "median_us": statistics.median(ind_lats),
        }

        # Combined (all 4 invariants)
        comb_lats = []
        for t in test_traces:
            acts = make_actions_for_trace(t)
            _, lats = run_incremental(acts, comb_invariants, z3_check_all)
            comb_lats.append(sum(lats))
        results["combined"][inv_type] = {
            "n_traces": len(test_traces),
            "avg_us": statistics.mean(comb_lats),
            "median_us": statistics.median(comb_lats),
            "overhead": statistics.mean(comb_lats) / max(statistics.mean(ind_lats), 1),
        }
        ov = results["combined"][inv_type]["overhead"]
        print(f"  {inv_type}: ind={results['individual'][inv_type]['avg_us']:.1f}us  "
              f"comb={results['combined'][inv_type]['avg_us']:.1f}us  "
              f"overhead={ov:.2f}x")

    return results


# ─── Ablation 4: Trace depth saturation ────────────────────────────────────

def ablation4_trace_depth_saturation(traces):
    print("\n# Ablation 4: Trace depth saturation\n")

    sizes = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    results = {}

    # Build synthetic traces of each size for each invariant type
    for inv_type in ["ordering", "exclusive_access", "approval", "monotonic"]:
        invariants = trace_invariants(inv_type)
        inv_results = {"sizes": sizes, "mean_us": [], "median_us": [], "stdev_us": []}

        for sz in sizes:
            lats = []
            n_samples = max(20, 200 // max(sz, 1))

            for _ in range(n_samples):
                acts = build_synthetic_trace(sz, inv_type, traces)
                if acts is None:
                    continue
                _, per_action_lats = run_incremental(acts, invariants, z3_check_all)
                lats.append(sum(per_action_lats))

            if lats:
                inv_results["mean_us"].append(statistics.mean(lats))
                inv_results["median_us"].append(statistics.median(lats))
                inv_results["stdev_us"].append(statistics.stdev(lats) if len(lats) > 1 else 0)
            else:
                inv_results["mean_us"].append(0)
                inv_results["median_us"].append(0)
                inv_results["stdev_us"].append(0)

        results[inv_type] = inv_results
        print(f"  {inv_type}: 1→{sizes[-1]}: "
              f"{results[inv_type]['mean_us'][0]:.1f}us → {results[inv_type]['mean_us'][-1]:.1f}us")

    return results


_TRACE_CACHE = {}

def get_batch_trace(inv_type, traces):
    """Cached build_trace_set to avoid re-filtering on every call."""
    if inv_type not in _TRACE_CACHE:
        safe, viol = build_trace_set(traces, inv_type)
        _TRACE_CACHE[inv_type] = (safe, viol)
    return _TRACE_CACHE[inv_type]


def build_synthetic_trace(size, inv_type, real_traces):
    """Build a synthetic trace of given size for the invariant type."""
    safe_traces, _ = get_batch_trace(inv_type, real_traces)
    if not safe_traces:
        return None
    base = copy.deepcopy(safe_traces[0])
    acts = base["actions"]
    if not acts:
        return None

    # Pad or truncate to size by repeating the last action
    result = []
    for i in range(size):
        src = acts[min(i, len(acts) - 1)]
        result.append(Action(
            agent=src.get("agent_override", agent_name(base["domain"])),
            tool=src["tool"],
            action_type=src["action_type"],
            args=dict(src.get("args", {})),
            resource=src.get("resource"),
            timestamp=float(i),
        ))
    return result


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  VeriTool Ablation Experiments")
    print("=" * 60)

    print("\nLoading TAU-bench traces...")
    traces = load_taubench_traces()
    print(f"  Loaded {len(traces)} traces")

    results = {}

    results["ablation1_incremental_vs_batch"] = ablation1_incremental_vs_batch(traces)
    results["ablation2_solver_swap"] = ablation2_solver_swap(traces)

    # ─── Cross-invariant ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["ablation3_cross_invariant"] = ablation3_cross_invariant(traces)
    print(f"  Cross-invariant took {time.perf_counter()-t0:.1f}s")

    # ─── Trace depth ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["ablation4_trace_depth"] = ablation4_trace_depth_saturation(traces)
    print(f"  Trace depth took {time.perf_counter()-t0:.1f}s")

    # ─── Save ─────────────────────────────────────────────────────────────
    data = load_data()
    for k, v in results.items():
        data[k] = v
    save_data(data)
    print(f"\nResults saved to {DATA_PATH}")

    # ─── Print summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  ABLATION SUMMARY")
    print(f"{'='*60}\n")

    a1 = results["ablation1_incremental_vs_batch"]
    print("Ablation 1: Incremental vs Batch (avg μs)")
    print(f"  {'Invariant':<20} {'Incremental':>12} {'Batch':>12} {'Speedup':>10}")
    for inv, v in a1.items():
        print(f"  {inv:<20} {v['inc_total_us']:>10.1f}us {v['batch_total_us']:>10.1f}us {v['speedup']:>8.1f}x")

    a2 = results["ablation2_solver_swap"]
    print("\nAblation 2: Z3 vs CVC5 (avg μs)")
    print(f"  {'Invariant':<20} {'Z3':>12} {'CVC5':>12} {'Ratio':>10}")
    for inv, v in a2.items():
        ratio = v['z3_avg_us'] / max(v['cvc5_avg_us'], 1)
        print(f"  {inv:<20} {v['z3_avg_us']:>10.1f}us {v['cvc5_avg_us']:>10.1f}us {ratio:>8.2f}x")

    a3 = results["ablation3_cross_invariant"]
    print("\nAblation 3: Cross-invariant overhead (avg μs)")
    print(f"  {'Invariant':<20} {'Individual':>12} {'Combined':>12} {'Overhead':>10}")
    for inv in a3["individual"]:
        ind = a3["individual"][inv]["avg_us"]
        comb = a3["combined"][inv]["avg_us"]
        ov = a3["combined"][inv]["overhead"]
        print(f"  {inv:<20} {ind:>10.1f}us {comb:>10.1f}us {ov:>8.2f}x")

    a4 = results["ablation4_trace_depth"]
    print("\nAblation 4: Trace depth saturation (avg μs)")
    for inv, v in a4.items():
        print(f"  {inv:<20} size 1: {v['mean_us'][0]:.1f}us  →  size {v['sizes'][-1]}: {v['mean_us'][-1]:.1f}us")

    print("\nDone.")


if __name__ == "__main__":
    main()
