# Architecture

## Core Data Model

```
Action { agent, tool, action_type, args, resource?, timestamp }
Trace  = [Action, ...]
```

Each tool is registered with an `action_type` (e.g., BUILD, DEPLOY, APPROVE) and an optional `resource_fn` that extracts a resource identifier from the arguments.

## Invariant Types

All invariants are checked at runtime against the accumulated trace:

```
OrderingInvariant(target, prereqs)
  Before any action of type `target`, all actions of types `prereqs` must exist in the trace.

ExclusiveAccessInvariant(action_type)
  No two agents may have actions of type `action_type` with the same resource.

ApprovalInvariant(action_type, approver_type)
  Actions of type `action_type` require a prior action of type `approver_type` by a different agent.

MonotonicInvariant(action_type)
  Values of the `value` argument for actions of type `action_type` must be non-decreasing per agent+resource.
```

## Verification Flow

```
User code → wrapped_fn(**kwargs)
                ↓
         Action(agent, tool, action_type, args, resource, timestamp)
                ↓
         For each invariant:
           Z3 encodes trace + current action → SAT / UNSAT
                ↓
         SAT → violation → return {"status": "blocked", "reason": ...}
         UNSAT → permitted → append action to trace, call original fn
```

## Z3 Encoding

For ordering invariants: encode which actions of each required type have occurred. If the current action is the target type and a prereq is missing, assert `Not(required_occurred[p])`. If Z3 returns SAT, a violation exists.

For exclusive access: check no prior action shares the same action type and resource.

For approval: check a prior action of the approver type by a different agent exists.

For monotonic: check prior counter value is ≤ current value.

## Lean Soundness

`Lean/Trace.lean` defines the invariant semantics as Lean propositions and proves:

- `ordering_invariant_nil`: empty trace satisfies any ordering invariant
- `ordering_invariant_snoc`: if a trace satisfies an ordering invariant and the next action is not the target (or all prereqs exist), the extended trace also satisfies the invariant

This establishes the soundness of incremental checking by structural induction over trace construction.

## Fail-Closed

Unknown responses at every layer:

| Layer | Unknown Behavior |
|---|---|
| Action type registration | Unregistered tool → uses tool name as action type |
| Z3 check | SAT → block with witness |
| Lean proof | Missed prereq → structurally unprovable |
