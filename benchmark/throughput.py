"""Throughput benchmark: actions/second for VeriTool vs OPA.

Usage:
    PYTHONPATH="." python3 benchmark/throughput.py
"""

import time
import statistics
import json
import subprocess
import tempfile
import os

from verifier.verifier import Verifier
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    MonotonicInvariant,
)

TRIALS = 3


def _rego_for_comparison():
    return """package veritool_comparison
ordering_BUILD_in_history if { some a in input.history; a.action == "BUILD" }
ordering_TEST_in_history if { some a in input.history; a.action == "TEST" }
ordering_DEPLOY_ok if { ordering_BUILD_in_history; ordering_TEST_in_history }
ordering_DEPLOY_ok if { input.action != "DEPLOY" }
exclusive_WRITE_conflict if { some a in input.history; a.action == "WRITE"; a.resource == input.resource; a.agent != input.agent }
exclusive_WRITE_ok if { not exclusive_WRITE_conflict }
exclusive_WRITE_ok if { input.action != "WRITE" }
allow if { ordering_DEPLOY_ok; exclusive_WRITE_ok }
"""


def bench_veritool(batch_size):
    latencies = []
    for _ in range(TRIALS):
        v = Verifier(agent_name="ci")
        v.register_tool("build", action_type="BUILD")
        v.register_tool("test", action_type="TEST")
        v.register_tool("write", action_type="WRITE", resource_fn=lambda a: a.get("file"))
        v.register_tool("spend", action_type="SPEND")
        v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD", "TEST"]))
        v.add_invariant(ExclusiveAccessInvariant("WRITE"))
        v.add_invariant(MonotonicInvariant("SPEND"))

        build = v.wrap(lambda **kw: None, tool_name="build")
        test = v.wrap(lambda **kw: None, tool_name="test")
        write = v.wrap(lambda **kw: None, tool_name="write")
        spend = v.wrap(lambda **kw: None, tool_name="spend")

        start = time.perf_counter()
        for i in range(batch_size):
            build()
            test()
            write(file=f"res_{i % 10}")
            spend(value=i)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed / (batch_size * 4))

    avg = statistics.mean(latencies)
    return 1.0 / avg, avg * 1_000_000


def bench_opa_stateless(batch_size):
    rego_src = _rego_for_comparison()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
        f.write(rego_src)
        fpath = f.name

    latencies = []
    try:
        for _ in range(TRIALS):
            start = time.perf_counter()
            for i in range(batch_size):
                for action in ["BUILD", "TEST", "WRITE"]:
                    inp = {"action": action, "agent": "ci",
                           "resource": f"res_{i % 10}" if action == "WRITE" else "", "value": 0}
                    subprocess.run(
                        ["opa", "eval", "--format", "raw", "--data", fpath, "-I",
                         "data.veritool_comparison"],
                        input=json.dumps(inp), capture_output=True, text=True, timeout=10,
                    )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed / (batch_size * 3))
    finally:
        os.unlink(fpath)

    avg = statistics.mean(latencies)
    return 1.0 / avg, avg * 1_000_000


def bench_opa_history(batch_size):
    rego_src = _rego_for_comparison()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
        f.write(rego_src)
        fpath = f.name

    latencies = []
    try:
        for _ in range(TRIALS):
            history = []
            start = time.perf_counter()
            for i in range(batch_size):
                for action in ["BUILD", "TEST", "WRITE"]:
                    inp = {"action": action, "agent": "ci",
                           "resource": f"res_{i % 10}" if action == "WRITE" else "",
                           "value": 0, "history": history}
                    subprocess.run(
                        ["opa", "eval", "--format", "raw", "--data", fpath, "-I",
                         "data.veritool_comparison"],
                        input=json.dumps(inp), capture_output=True, text=True, timeout=10,
                    )
                    history.append({"action": action, "agent": "ci",
                                    "resource": f"res_{i % 10}" if action == "WRITE" else "",
                                    "value": 0})
            elapsed = time.perf_counter() - start
            latencies.append(elapsed / (batch_size * 3))
    finally:
        os.unlink(fpath)

    avg = statistics.mean(latencies)
    return 1.0 / avg, avg * 1_000_000


if __name__ == "__main__":
    print("# VeriTool Throughput Benchmark\n")
    print("## VeriTool (all batch sizes)\n")
    print("| Batch | Actions/sec | μs/action |")
    print("|---|---|---|")
    for bs in [1, 10, 100, 1000]:
        tput, lat = bench_veritool(bs)
        print(f"| {bs} | {tput:>10,.0f} | {lat:>8.1f} |")

    print("\n## Cross-system comparison (batch=100)\n")
    print("| System | Actions/sec | μs/action |")
    print("|---|---|---|")

    vt_t, vt_l = bench_veritool(100)
    print(f"| **VeriTool** | {vt_t:>10,.0f} | {vt_l:>8.1f} |")

    opa_t, opa_l = bench_opa_stateless(100)
    print(f"| OPA stateless | {opa_t:>10,.0f} | {opa_l:>8.1f} |")

    opah_t, opah_l = bench_opa_history(100)
    print(f"| OPA+history | {opah_t:>10,.0f} | {opah_l:>8.1f} |")

    print(f"\n**VeriTool speedup vs OPA stateless:** {opa_l/vt_l:.0f}x")
    print(f"**VeriTool speedup vs OPA+history:** {opah_l/vt_l:.0f}x")
