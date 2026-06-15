"""Scalability benchmark: latency vs trace size per invariant type.

Usage:
    PYTHONPATH="." python3 benchmark/scalability.py
"""

import time
import statistics
from verifier.verifier import Verifier
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)

TRACE_SIZES = [0, 1, 10, 100, 1000]
TRIALS = 20


def _make_trace(v, size: int, action_type: str, agent: str = "alice"):
    """Pre-fill a verifier's trace with `size` valid entries."""
    for i in range(size):
        v.trace.append(type("Action", (), {
            "agent": agent, "tool": f"step_{i}", "action_type": action_type,
            "args": {"value": i}, "resource": f"res_{i % 10}",
            "timestamp": 0.0,
        })())


def bench_ordering(sizes):
    results = []
    for size in sizes:
        latencies = []
        for _ in range(TRIALS):
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
        })
    return results


def bench_exclusive_access(sizes):
    results = []
    for size in sizes:
        latencies = []
        for _ in range(TRIALS):
            v = Verifier()
            v.register_tool("write", action_type="WRITE", resource_fn=lambda a: a.get("file"))
            v.add_invariant(ExclusiveAccessInvariant("WRITE"))
            _make_trace(v, size, "WRITE", agent="alice")
            fn = v.wrap(lambda **kw: None, tool_name="write")
            v.agent_name = "bob"
            start = time.perf_counter()
            fn(file="new.txt")  # different resource, will be permitted
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
        })
    return results


def bench_approval(sizes):
    results = []
    for size in sizes:
        latencies = []
        for _ in range(TRIALS):
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
        })
    return results


def bench_monotonic(sizes):
    results = []
    for size in sizes:
        latencies = []
        for _ in range(TRIALS):
            v = Verifier()
            v.register_tool("spend", action_type="SPEND")
            v.add_invariant(MonotonicInvariant("SPEND"))
            _make_trace(v, size, "SPEND", agent="alice")
            fn = v.wrap(lambda **kw: None, tool_name="spend")
            start = time.perf_counter()
            fn(value=size + 1)  # higher than any prior, permitted
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed)
        results.append({
            "trace_size": size,
            "mean_us": statistics.mean(latencies),
            "stdev_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_us": min(latencies),
            "max_us": max(latencies),
        })
    return results


def bench_composite(sizes):
    """All 4 invariants active simultaneously."""
    results = []
    for size in sizes:
        latencies = []
        for _ in range(TRIALS):
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
        })
    return results


def print_table(name, results):
    print(f"\n## {name}")
    print(f"| Trace size | Mean (μs) | Stdev (μs) | Min (μs) | Max (μs) |")
    print("|---|---|---|---|---|")
    for r in results:
        print(f"| {r['trace_size']:>10} | {r['mean_us']:>9.1f} | {r['stdev_us']:>9.1f} | {r['min_us']:>8.1f} | {r['max_us']:>8.1f} |")
    # Compute scale factor
    if len(results) >= 2:
        small = results[0]["mean_us"]
        large = results[-1]["mean_us"]
        ratio = large / small if small > 0 else float('inf')
        print(f"\n  Cost ratio (size {results[0]['trace_size']} → {results[-1]['trace_size']}): {ratio:.1f}x")


if __name__ == "__main__":
    print("# VeriTool Scalability Benchmark\n")
    print(f"_Invariant types: ordering, exclusive_access, approval, monotonic, composite (all 4)_")
    print(f"_Trace sizes: {TRACE_SIZES}_")
    print(f"_Trials per cell: {TRIALS}_\n")

    for name, fn in [
        ("OrderingInvariant", bench_ordering),
        ("ExclusiveAccessInvariant", bench_exclusive_access),
        ("ApprovalInvariant", bench_approval),
        ("MonotonicInvariant", bench_monotonic),
        ("Composite (all 4)", bench_composite),
    ]:
        results = fn(TRACE_SIZES)
        print_table(name, results)
