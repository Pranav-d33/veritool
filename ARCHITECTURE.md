# Architecture

## System Design

```
┌─────────────────────────────────────────────────────────┐
│  CLI (veritool)                                         │
│  ┌──────────┐ ┌────────────┐ ┌───────────┐             │
│  │ create   │ │ check/test │ │ hot-reload│             │
│  ├──────────┤ ├────────────┤ ├───────────┤             │
│  │ run      │ │ status     │ │ rollback  │             │
│  ├──────────┤ ├────────────┤ ├───────────┤             │
│  │ verify   │ │ dashboard  │ │ wrap      │             │
│  └──────────┘ └────────────┘ └───────────┘             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Bridge                                                │
│  ┌───────────────┐  ┌──────────────────────────────┐   │
│  │ PolicySpec    │  │ z3_encoder                   │   │
│  │ (type system) │  │ ├─ compile_policy(spec)→Z3  │   │
│  │ Nat→Int       │  │ └─ check_policy(spec,params)│   │
│  │ Finset→Fn     │  │    → {permitted/violation}  │   │
│  └───────────────┘  └──────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Verifier                                              │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ Policy Checkers  │  │ CoordinationVerifier     │    │
│  │ (7 policy types) │  │ ├─ SEQUENTIAL_ACCESS     │    │
│  └──────────────────┘  │ ├─ LOCK_REQUIRED         │    │
│                        │ ├─ APPROVAL_REQUIRED     │    │
│                        │ ├─ MONOTONIC_ACCESS      │    │
│                        │ └─ ROLE_BASED_ACCESS     │    │
│                        └──────────────────────────┘    │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Policy Store + Audit                                   │
│  ┌────────────────┐  ┌──────────────────────────┐      │
│  │ VersionedStore │  │ AuditTrail               │      │
│  │ ├─ hot-reload  │  │ ├─ JSONL logging         │      │
│  │ ├─ rollback    │  │ ├─ query/filter          │      │
│  │ └─ manifest    │  │ ├─ stats                 │      │
│  │                │  │ └─ CSV export            │      │
│  └────────────────┘  └──────────────────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Integrations + Dashboard                               │
│  ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐   │
│  │LangChain │ │CrewAI   │ │AutoGen   │ │Streamlit │   │
│  │Interceptor│ │Guard    │ │Middleware│ │Dashboard │   │
│  └──────────┘ └─────────┘ └──────────┘ └──────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Core Types (`bridge/policy_spec.py`)

| Type | Lean Equivalent | Z3 Sort |
|---|---|---|
| `NatType` | `Nat` | `IntSort()` |
| `StringType` | `String` | `StringSort()` |
| `BoolType` | `Bool` | `BoolSort()` |
| `FinsetType(elem)` | `Finset elem` | `Function(ElemSort, BoolSort())` |

`PolicySpec` is a declarative struct: functions with mappings, param types, violation expression. The encoder compiles it to Z3 constraints; `check_policy` adds param bindings and the violation check.

## Auto-Generator (`cli/auto_generator.py`)

Natural language → formal spec:

1. Parse description for keywords: "price", "file", "SQL", "rate", "role", "API", "access"
2. Infer policy type, function names, mapping patterns from phrasing
3. Generate `PolicySpec` + Lean theorem stub + Z3 checker + test file
4. Run round-trip verification on generated test matrix

## Coordination Verifier (`verifier/coordination_policy.py`)

Tracks agent actions and checks invariants in a sequence-orientated model:

- **SEQUENTIAL**: no two agents access the same resource concurrently
- **LOCK**: a lock must be held before accessing a resource
- **APPROVAL**: sensitive actions require a prior approval action
- **MONOTONIC**: state values can only increase
- **ROLE**: only designated roles may access a resource

Uses Python-level tracking (not Z3) to avoid false positives from uninterpreted functions.

## Policy Store (`policy_store/store.py`)

Versioned by policy name. Each version stores the serialized spec + timestamp. Hot-reload watches for manifest changes. Rollback restores the previous version and resets the hot-reload watcher.

## Audit Trail (`policy_store/audit.py`)

Every check is logged as JSONL. Queryable by policy, decision, time range. Exportable to CSV.

## Integrations

All three wrappers follow the same pattern: intercept tool calls → call `bridge_check` → permit or block with counterexample.

- **LangChain**: wraps tool executors via `__call__`
- **CrewAI**: wraps tool instances via `__call__`
- **AutoGen**: wraps tool schemas via `register_for_llm`

## Adding a New Policy

1. Add `PolicySpec` in `bridge/__init__.py` — no `verifier/*.py` file needed
2. Policy type routing is automatic via `_policy_type` field
3. Tests use `bridge_check` for all policy types

The bridge is the single path. No separate hand-written Z3 checkers.
