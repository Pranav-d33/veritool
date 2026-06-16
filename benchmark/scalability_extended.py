"""Extended scalability benchmark: push to 10K, 100K, 1M trace entries."""
import time
import statistics
import sys
from verifier.verifier import Verifier
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)

SIZES = [0, 1, 10, 100, 1000, 10_000, 100_000]
TRIALS = {
    0: 20, 1: 20, 10: 20, 100: 20, 1000: 10,
    10_000: 5, 100_000: 3,
}


def _make_trace(v, size, action_type, agent="alice"):
    for i in range(size):
        v.trace.append(type("Action", (), {
            "agent": agent, "tool": f"step_{i}", "action_type": action_type,
            "args": {"value": i}, "resource": f"res_{i % 10}",
            "timestamp": 0.0,
        })())


def bench_ordering(sizes):
    results = []
    for size in sizes:
        trials = TRIALS[size]
        latencies = []
        for _ in range(trials):
            v = Verifier()
            v.register_tool("a", action_type="A")
            v.register_tool("b", action_type="B")
            v.add_invariant(OrderingInvariant("B", ["A"]))
            _make_trace(v, size, "A")
            fn = v.wrap(lambda **kw: None, tool_name="b")
            start = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
            "trials": trials,
        })
        print(f"  ordering size={size:>8}: {results[-1]['mean_us']:>8.1f}μs")
        sys.stdout.flush()
    return results


def bench_exclusive_access(sizes):
    results = []
    for size in sizes:
        trials = TRIALS[size]
        latencies = []
        for _ in range(trials):
            v = Verifier()
            v.register_tool("write", action_type="WRITE", resource_fn=lambda a: a.get("file"))
            v.add_invariant(ExclusiveAccessInvariant("WRITE"))
            _make_trace(v, size, "WRITE", agent="alice")
            fn = v.wrap(lambda **kw: None, tool_name="write")
            v.agent_name = "bob"
            start = time.perf_counter()
            fn(file="new.txt")
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
            "trials": trials,
        })
        print(f"  excl_access size={size:>8}: {results[-1]['mean_us']:>8.1f}μs")
        sys.stdout.flush()
    return results


def bench_approval(sizes):
    results = []
    for size in sizes:
        trials = TRIALS[size]
        latencies = []
        for _ in range(trials):
            v = Verifier()
            v.register_tool("approve", action_type="APPROVE")
            v.register_tool("deploy", action_type="DEPLOY")
            v.add_invariant(ApprovalInvariant("DEPLOY", "APPROVE"))
            _make_trace(v, size, "APPROVE", agent="qa")
            fn = v.wrap(lambda **kw: None, tool_name="deploy")
            start = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
            "trials": trials,
        })
        print(f"  approval size={size:>8}: {results[-1]['mean_us']:>8.1f}μs")
        sys.stdout.flush()
    return results


def bench_monotonic(sizes):
    results = []
    for size in sizes:
        trials = TRIALS[size]
        latencies = []
        for _ in range(trials):
            v = Verifier()
            v.register_tool("spend", action_type="SPEND")
            v.add_invariant(MonotonicInvariant("SPEND"))
            _make_trace(v, size, "SPEND", agent="alice")
            fn = v.wrap(lambda **kw: None, tool_name="spend")
            start = time.perf_counter()
            fn(value=size + 1)
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
            "trials": trials,
        })
        print(f"  monotonic size={size:>8}: {results[-1]['mean_us']:>8.1f}μs")
        sys.stdout.flush()
    return results


def bench_composite(sizes):
    """All 4 invariants active simultaneously."""
    results = []
    for size in sizes:
        trials = TRIALS[size]
        latencies = []
        for _ in range(trials):
            v = Verifier()
            v.register_tool("build", action_type="BUILD")
            v.register_tool("test", action_type="TEST")
            v.register_tool("write", action_type="WRITE", resource_fn=lambda a: a.get("file"))
            v.register_tool("spend", action_type="SPEND")
            v.register_tool("deploy", action_type="DEPLOY", resource_fn=lambda a: a.get("env"))
            v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD", "TEST"]))
            v.add_invariant(ExclusiveAccessInvariant("DEPLOY"))
            v.add_invariant(MonotonicInvariant("SPEND"))
            _make_trace(v, size, "BUILD", agent="ci")
            _make_trace(v, size, "TEST", agent="ci")
            fn = v.wrap(lambda **kw: None, tool_name="deploy")
            start = time.perf_counter()
            fn(env="prod")
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
            "trials": trials,
        })
        print(f"  composite size={size:>8}: {results[-1]['mean_us']:>8.1f}μs")
        sys.stdout.flush()
    return results


def print_table(name, results):
    print(f"\n**{name}**")
    print("| Trace size | Trials | Mean (μs) | Stdev (μs) | Min (μs) | Max (μs) |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['trace_size']:>10} | {r['trials']:>6} | {r['mean_us']:>9.1f} | {r['stdev_us']:>9.1f} | {r['min_us']:>8.1f} | {r['max_us']:>8.1f} |")
    if len(results) >= 2:
        small = next(r for r in results if r['trace_size'] == 1)
        large = results[-1]
        ratio_nz = large['mean_us'] / small['mean_us'] if small['mean_us'] > 0 else float('inf')
        print(f"  Cost ratio (size 1 → {large['trace_size']}): {ratio_nz:.1f}x")


if __name__ == "__main__":
    print("# Extended Scalability Benchmark\n")
    print(f"_Invariant types: ordering, exclusive_access, approval, monotonic, composite (all 4)_")
    print(f"_Trace sizes: {SIZES}_")
    print(f"_Trials per cell: varies ({dict(TRIALS)})_\n")

    for name, fn in [
        ("OrderingInvariant", bench_ordering),
        ("ExclusiveAccessInvariant", bench_exclusive_access),
        ("ApprovalInvariant", bench_approval),
        ("MonotonicInvariant", bench_monotonic),
        ("Composite (all 4)", bench_composite),
    ]:
        print(f"\nRunning {name}...")
        sys.stdout.flush()
        results = fn(SIZES)
        print_table(name, results)
