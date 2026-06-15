import time

from verifier.verifier import Verifier
from benchmark.traces import scenarios


def run_scenario(scenario):
    v = Verifier()
    for inv in scenario["invariants"]:
        v.add_invariant(inv)

    tool_registry = {}
    for case in scenario["cases"]:
        for agent, tool, action_type, kwargs in case["trace"]:
            if tool not in tool_registry:
                resource_fn = _infer_resource_fn(action_type)
                v.register_tool(tool, action_type, resource_fn)
                wrapped = v.wrap(lambda **kw: {"status": "executed", **kw}, tool_name=tool)
                tool_registry[tool] = wrapped

    results = []
    for case in scenario["cases"]:
        v.reset()
        latencies = []
        result = None
        for agent, tool, action_type, kwargs in case["trace"]:
            v.agent_name = agent
            fn = tool_registry[tool]
            start = time.perf_counter()
            result = fn(**kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            if isinstance(result, dict) and result.get("status") == "blocked":
                break

        actual = _classify(result) if result is not None else "permitted"
        passed = actual == case["expect"]
        results.append({
            "name": case["name"],
            "expected": case["expect"],
            "actual": actual,
            "passed": passed,
            "latencies_ms": latencies,
        })

    return results


def _infer_resource_fn(action_type):
    if action_type in ("WRITE", "DEPLOY"):
        return lambda a: a.get("file") or a.get("env")
    return None


def _classify(result):
    if isinstance(result, dict) and result.get("status") == "blocked":
        return "blocked"
    return "permitted"


def run_all():
    all_results = {}
    for sc in scenarios:
        all_results[sc["name"]] = run_scenario(sc)
    return all_results


if __name__ == "__main__":
    results = run_all()
    total = 0
    passed = 0
    for name, cases in results.items():
        for c in cases:
            total += 1
            if c["passed"]:
                passed += 1
            status = "PASS" if c["passed"] else "FAIL"
            print(f"[{status}] {name}/{c['name']}: expected={c['expected']} actual={c['actual']}")
    print(f"\n{passed}/{total} passed")
