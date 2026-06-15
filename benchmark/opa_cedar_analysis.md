# OPA/Cedar Comparison

VeriTool targets **trace invariants** — properties that span multiple actions across agents. Existing policy engines evaluate single requests in isolation. This is a fundamentally different class of safety property.

## OPA/Rego

OPA evaluates `allow { conditions }` against a single `input`. Rego has no concept of a session, an action sequence, or state across evaluations.

### A Rego rule for deploy safety

```rego
# This checks a SINGLE deploy request.
# It CANNOT check "did BUILD run earlier in this session?"
allow {
    input.action == "deploy"
    input.user == "ci"
    # Missing: check that BUILD happened before this deploy
}
```

Rego policies answer: *"given this one request, is it allowed?"*
VeriTool answers: *"given this request AND all previous requests, is the sequence safe?"*

### Why Rego can't express ordering invariants

Rego has no mutable state across evaluations. Each `opa eval` call is stateless. You could build external state (Redis, database) and query it from Rego via `http.send`, but:

1. That's not Rego's model — you're building a custom state machine outside OPA
2. The formal guarantees vanish — there's no proof that the external state machine is correct
3. The latency of external calls for every check defeats the purpose of an in-process verifier

### Why Rego can't express exclusivity

Rego has no concept of "holding" a resource. You could simulate it by passing all current holders as part of `input`, but that requires the caller to know who holds what — defeating the point of verification.

## AWS Cedar

Cedar evaluates `permit(principal, action, resource)` or `forbid(principal, action, resource)` against a known entity hierarchy. It's single-request, like OPA.

### A Cedar policy for deploy safety

```cedar
permit(
    principal in [Agent::"ci"],
    action == Action::"deploy",
    resource in [Environment::"prod"]
);
```

This permits ci to deploy to prod. It does not and cannot check whether BUILD completed first.

### Cedar for agentic AI

AWS published a [sample for Cedar + agentic AI](https://github.com/aws-samples/sample-cedar-agentic-ai-authorization) that enforces authorization at three layers:

- L1: Agent → Tool (can this agent invoke this tool?)
- L2: Agent → Agent (can this agent delegate to that agent?)
- L3: User → Agent (did the originating user have the right?)

All three are **single-action authorization checks**. None check cross-action ordering, exclusivity, or monotonicity.

## Why Trace Invariants Are Different

| Dimension | OPA / Cedar | VeriTool |
|-----------|------------|----------|
| Unit of evaluation | Single request | Action sequence (trace) |
| State across checks | None | Accumulated trace |
| Cross-action properties | Impossible | Ordering, exclusivity, approval, monotonic |
| Formal proof of engine | Not user-facing | Lean theorems for invariant encoding |
| Agent identity tracking | Request-time only | Across actions in a session |
| Resource exclusivity | Not modeled | Tracked per-agent per-resource |

## What This Means

For single-action authorization (can Alice read file X?), OPA and Cedar are the right tools. For multi-agent coordination safety (no one deploys without build + test + approval, no two agents write to the same resource concurrently), they cannot express the required properties. This is the gap VeriTool fills.
