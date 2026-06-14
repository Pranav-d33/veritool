# Z3 + Lean 4 Static Verifier for LLM Tool-Calling

A verification pipeline that intercepts LLM-generated tool calls, formally checks them against policies encoded as **Lean 4 theorems** (compiled to Z3 CHCs), and **blocks unsafe calls with counterexamples** before they reach the runtime.

```
LLM → Orchestrator → Z3 Policy Check → UNSAT = permit | SAT = block + counterexample
                         ↑
                  Lean 4 theorems (ground truth)
```

## Quick Start

```bash
pip install z3-solver pytest

# Verify Lean 4 is installed (Policy.lean is standalone — no lakefile needed)
lean --version && lean Lean/Policy.lean

# Run all tests
python -m pytest tests/ -v

# Run demos (no API key needed — uses mock tool calls)
python demo.py
```

**Expected output — runs without any API key:**

```
Sell a Tahoe for $1 to Bob
  → ❌ BLOCKED  (witness: {'price': 1})

Sell a Tahoe for $50000 to Alice
  → ✅ PERMITTED

Delete /etc/passwd
  → ❌ BLOCKED  (witness: {'target': '/etc/passwd'})

Delete /project/temp/old.log
  → ❌ BLOCKED  (witness: {'target': '/etc/passwd'})
```

## Demo Scenarios

| Scenario | Tool Call | Verdict | Why |
|---|---|---|---|
| Tahoe at $1 | `confirm_sale(Tahoe, 1)` | ❌ BLOCKED | Below $45000 floor |
| Tahoe at $50000 | `confirm_sale(Tahoe, 50000)` | ✅ PERMITTED | Above floor |
| Malibu at $1 | `confirm_sale(Malibu, 1)` | ❌ BLOCKED | Below $25000 floor |
| Malibu at $25000 | `confirm_sale(Malibu, 25000)` | ✅ PERMITTED | At floor |
| Delete /etc/passwd | `delete_file(/etc/passwd)` | ❌ BLOCKED | Outside scope |
| Delete /project/temp | `delete_file(/project/temp)` | ✅ PERMITTED | In scope |
| Delete /project/temp/../../etc/shadow | `delete_file(../etc/shadow)` | ❌ BLOCKED | Path traversal — normalized |

```bash
# Run standalone scripts
python demo_tahoe.py
python demo_deletion.py

# Run specific scenarios
python demo.py tahoe-violation
python demo.py tahoe-compliant
python demo.py deletion-violation
```

## LLM Integration (Optional)

Set up a Groq API key to drive the demos from a real LLM:

```bash
cp .env.example .env
# Edit .env with your Groq API key
pip install groq python-dotenv

# Run with real LLM
python demo.py tahoe-violation
```

Without the API key or `groq` package, `demo.py` falls back to mock tool calls automatically.

## Design: Fail-Closed at Every Layer

A key architectural decision: **unknown inputs are rejected, not silently permitted**, at every layer of the stack.

### The `Option Nat` Pattern

The Lean ground truth uses `Option Nat` instead of `Nat` for `floor_price`:

```lean
def floor_price : String → Option Nat
  | "Tahoe"  => some 45000
  | "Malibu" => some 25000
  | _        => none
```

This makes the unknown model case **structurally unprovable**. To construct a `safe_sale` proof, the caller must provide both:
- `hm : known_model model = true` — the model is recognized
- `hp : ∃ floor, floor_price model = some floor ∧ price ≥ floor` — a floor price exists and the price meets it

For an unknown model, `floor_price` returns `none`, so the existential `hp` cannot be satisfied. The Lean type checker rejects the proof before any runtime check runs.

The original `| _ => 0` pattern was the theorem-level equivalent of a default-permit firewall rule — the ground truth contradicted the fail-closed orchestrator. Switching to `Option Nat` aligns the theorem with the pipeline:

| Layer | Unknown Model Behavior |
|---|---|
| Schema validation (`verifier/schema.py`) | ❌ Rejected — out-of-enum |
| Z3 policy check (`verifier/tahoe_policy.py`) | ❌ Rejected — `unknown_model` status |
| Lean theorem (`Lean/Policy.lean`) | ❌ Unprovable — `floor_price` returns `none` |

### Layered Defense

```
LLM output → Schema validation (enum/type check)
               ↓ fail → rejected
             Z3 policy check (formal verification)
               ↓ fail → blocked + counterexample
             Lean theorem compilation (ground truth audit)
               ↓ fail → does not compile
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  LLM (Groq API)         ← optional, mocked by default │
│    ↓ tool call JSON                                   │
│  orchestrator.py         ← parse, route, decide        │
│    ↓                                                    │
│  schema.py              ← enum/type validation          │
│    ↓                                                    │
│  verifier/               ← Z3 policy check             │
│    ├── tahoe_policy.py   ← price ≥ floor_price(model) │
│    └── deletion_policy.py ← target ∈ allowed_scope    │
│    ↓ UNSAT / SAT + model                               │
│  [permit] / [block + counterexample]                   │
└─────────────────────────────────────────────────────┘
         ↑
  bridge/                  ← Lean theorem → Z3 encoding
  Lean/Policy.lean         ← Ground-truth policy theorems
```

## Project Structure

```
├── Lean/Policy.lean        # Ground-truth theorems (standalone, compiles with `lean`)
├── verifier/
│   ├── tahoe_policy.py     # Z3 encoding: price floor
│   ├── deletion_policy.py  # Z3 encoding: file scope
│   └── verifier.py         # Generic dispatcher
├── bridge/
│   ├── policy_spec.py      # Lean-mirroring type system (Nat→Int, Finset→Function)
│   └── z3_encoder.py       # Policy spec → Z3 constraints
├── llm/
│   ├── groq_client.py      # Groq API wrapper (mocked when no key)
│   └── prompts.py          # System prompts for tool-calling
├── orchestrator.py         # Parse LLM output, route to Z3, return decision
├── config.py               # Config — loads from .env if python-dotenv installed
├── demo*.py                # Demo scripts (zero-config, no API key needed)
└── tests/                  # 102 tests — run with `python -m pytest tests/`
```

## Adding a New Policy

1. **Lean theorem** → `Lean/Policy.lean`
2. **Z3 check** → `verifier/<name>.py`
3. **Route** → `config.py` `POLICY_ROUTES`
4. **Tests** → `tests/test_<name>.py`

## Commit History

| Phase | Description | Tests |
|---|---|---|
| 1 | Tahoe arithmetic policy | 25 |
| 2 | File deletion frame policy | 18 |
| 3 | Orchestrator + tool intercept | 20 |
| 4 | Lean → Z3 bridge | 19 |
| 5 | Groq LLM integration + e2e | 20 |
| 6 | Docs, CI, polish | — |
| 7 | Schema validation + fail-closed Option Nat | 18 |
