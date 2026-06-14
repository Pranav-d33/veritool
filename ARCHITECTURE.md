# Architecture

## System Design

The verifier is structured as a layered pipeline. Each layer has a single responsibility, and data flows in one direction — from the LLM output to a block/permit decision.

```
Layer 1: Interface      (orchestrator.py)
Layer 2: Routing        (verifier/verifier.py)
Layer 3: Policy Check   (verifier/tahoe_policy.py, verifier/deletion_policy.py)
Layer 4: Theorem Spec   (bridge/ — automated encoding from Lean types)
Layer 5: Ground Truth   (Lean/Policy.lean)
```

## Data Flow

### 1. Orchestrator (`orchestrator.py`)

Accepts raw JSON tool calls from LLM output. Validates structure (`tool` + `args` fields). Returns a decision dict:

```python
{
    "decision": "blocked" | "permitted" | "unknown_tool" | "error",
    "reason": "...",
    "tool": "confirm_sale",
    "args": {...}
}
```

### 2. Verifier (`verifier/verifier.py`)

Routes tool names to policy checkers via `config.py:POLICY_ROUTES`. Maintains a registry of `{route_name: check_fn}`. Each check function accepts `(**kwargs)` and returns a result dict.

### 3. Policy Checkers

Each policy checker:
1. Creates a Z3 solver
2. Encodes the policy as constraints
3. Asserts the violation condition
4. Returns SAT (violation) or UNSAT (safe)

**Tahoe policy** (`verifier/tahoe_policy.py`):
```
floor_price: String → Nat
violation ← price < floor_price(model)
```

**Deletion policy** (`verifier/deletion_policy.py`):
```
in_scope: String → Bool
violation ← target not in scope
```

### 4. Bridge (`bridge/`)

Maps Lean 4 types to Z3 sorts:

| Lean Type | Z3 Sort |
|---|---|
| `Nat` | `IntSort()` with `>= 0` |
| `String` | `StringSort()` |
| `Bool` | `BoolSort()` |
| `Finset String` | `Function(StringSort(), BoolSort())` |

Policy specs (`PolicySpec`) describe a policy declaratively. The encoder (`z3_encoder.py`) compiles specs to Z3 constraints.

### 5. Ground Truth (`Lean/Policy.lean`)

The Lean theorem is the authoritative policy statement. Z3 must agree with it. The bridge ensures agreement by generating Z3 encoding from the same structure.

## Key Design Decisions

### Fail-Closed

If Z3 times out or returns `unknown`, the tool call is **blocked**. Safety-critical systems must default to blocking.

### Path Normalization

File paths are normalized (`os.path.normpath`) before Z3 checking. This prevents `../../etc/shadow` style escapes.

### Policy Functions Accept `**kwargs`

Policy checkers accept `**kwargs` to ignore LLM-provided arguments that aren't part of the policy check (e.g., `customer` name in a sale).

## Adding a New Policy

1. Write a Lean theorem in `Lean/Policy.lean`
2. Create `verifier/<policy>.py` with a check function
3. Add route in `config.py:POLICY_ROUTES`
4. Add bridge spec in `bridge/__init__.py` (optional)
5. Add tests in `tests/test_<policy>.py`

The Lean theorem and Z3 encoding must agree on all inputs. The bridge round-trip tests enforce this.
