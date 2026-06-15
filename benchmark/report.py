from benchmark.runner import run_all
from benchmark.traces import scenarios


def generate():
    results = run_all()
    scenario_map = {s["name"]: s for s in scenarios}

    total = 0
    passed = 0
    lines = ["# VeriTool Benchmark Report\n", "| Scenario | Case | Expected | Actual | Pass | Avg Latency (ms) |", "|---|---|---|---|---|---|"]

    for sc in scenarios:
        cases = results[sc["name"]]
        for c in cases:
            total += 1
            if c["passed"]:
                passed += 1
            avg_latency = f"{sum(c['latencies_ms'])/len(c['latencies_ms']):.3f}" if c["latencies_ms"] else "—"
            lines.append(f"| {sc['name']} | {c['name']} | {c['expected']} | {c['actual']} | {'✓' if c['passed'] else '✗'} | {avg_latency} |")

    pct = (passed / total) * 100 if total else 0
    lines.append(f"\n**{passed}/{total} passed ({pct:.0f}%)**\n")

    lines.append("## Scope Limitations\n")
    for sc in scenarios:
        lines.append(f"### {sc['name']}")
        lines.append(f"_{sc['opa_limit']}_")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate())
