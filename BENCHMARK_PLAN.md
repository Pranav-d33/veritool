# Benchmark Plan

## Goal

Prove that VeriTool detects multi-agent trace invariant violations that existing policy engines (OPA, Cedar, guardrails) cannot.

## Benchmark Design

### Trace Scenarios

Each scenario has a name, invariants, a set of traces with labels (safe/violation), and a column showing why OPA/Cedar can't catch it.

| # | Scenario | Invariant | Traces | OPA/Cedar gap |
|---|----------|-----------|--------|---------------|
| 1 | **Deploy pipeline** | `Ordering("DEPLOY", ["BUILD","TEST","APPROVE"])` | 4 traces: valid sequence, missing build, missing test, missing approve | OPA checks each action independently. Cannot express "before action X, action Y must have occurred earlier in the session." |
| 2 | **Concurrent writes** | `ExclusiveAccess("WRITE")` | 4 traces: sequential writes (ok), same-agent (ok), cross-agent same resource (violation), cross-agent different resource (ok) | OPA can check `agent == resource.owner` at a point, but cannot track "who currently holds this resource across calls." |
| 3 | **Self-approval** | `Approval("DEPLOY","APPROVE")` | 4 traces: different-agent approval (ok), same-agent approval (violation), no approval (violation), multiple approvals (ok) | OPA doesn't model action sequences. The concept of "a prior action by a different agent" is inherently sequential. |
| 4 | **Monotonic budget** | `Monotonic("SPEND")` | 4 traces: increasing (ok), decreasing (violation), same value (ok), reset between agents (ok) | OPA has no concept of stateful counters across calls in a session. |
| 5 | **Mixed: deploy with exclusivity** | `Ordering + ExclusiveAccess` | 4 traces: valid, missing build, concurrent deploy, both violations | Composite invariants. OPA can't express either individually, let alone combined. |
| 6 | **Empty edge cases** | All of the above | 2 traces: empty action list (vacuously safe), single action (safe or violation depending on type) | Verifies vacuous truth and base cases. |
| 7 | **No-op actions** | All of the above | 2 traces: actions of unrelated types interspersed (safe), unrelated actions + violation (still caught) | Verifies that irrelevant actions don't interfere with invariant checking. |

### Trace Format

```python
# A trace is a list of (agent, tool, action_type, kwargs) tuples
# along with the expected result for each invariant.

Trace = list[tuple[str, str, str, dict]]

scenarios = [
    {
        "name": "deploy_pipeline",
        "invariants": [OrderingInvariant("DEPLOY", ["BUILD","TEST","APPROVE"])],
        "cases": [
            {
                "name": "valid_sequence",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("ci", "test", "TEST", {}),
                    ("qa", "approve", "APPROVE", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "permitted",
            },
            {
                "name": "missing_build",
                "trace": [
                    ("ci", "test", "TEST", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
                "reason_contains": "BUILD",
            },
            ...
        ],
    },
    ...
]
```

### Comparison Methodology

For each scenario, document:

1. **VeriTool**: runs all invariants via Z3 encoding, returns permit/block
2. **OPA attempt**: show the Rego rule that would be needed. Demonstrate it can't express cross-action constraints because Rego evaluates each input independently.
3. **Cedar attempt**: show the Cedar policy. Demonstrate it's limited to `principal, action, resource` at a single point.
4. **Manual guard attempt**: show the Python if-else. Demonstrate it works for simple cases but doesn't scale (no quantified reasoning, no formal proof).

### Metrics Collected

```
Per scenario:
  - traces total
  - correct permits
  - correct blocks
  - false positives (incorrectly blocked)
  - false negatives (incorrectly permitted)
  - detection rate (TP / (TP + FN))
  - precision (TP / (TP + FP))
  - avg latency per check (ms)

Aggregate:
  - overall detection rate
  - overall precision
  - max / min / avg latency
  - latency p50, p95, p99
```

### Implementation Plan

1. `benchmark/traces.py` — all trace scenarios as data
2. `benchmark/runner.py` — runs VeriTool against all traces, collects latency and correctness
3. `benchmark/report.py` — prints markdown report with metrics table
4. `benchmark/opa_cedar_analysis.md` — explains the comparison for each scenario

### What This Proves

After this benchmark, you can claim:

> VeriTool achieves X% detection rate and Y% precision on Z trace invariant scenarios. Existing policy engines (OPA/Rego, AWS Cedar) cannot express Z of these invariants because they lack the ability to reason about action sequences. VeriTool is the first runtime verifier for multi-agent trace invariants with formal soundness guarantees.

That's the research claim.
