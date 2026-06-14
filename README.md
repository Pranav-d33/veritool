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

# Run all tests (102 tests)
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

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  LLM (Groq API)         ← optional, mocked by default │
│    ↓ tool call JSON                                   │
│  orchestrator.py         ← parse, route, decide       │
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
