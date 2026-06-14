# Z3 + Lean 4 Static Verifier for LLM Tool-Calling

A verification pipeline that intercepts LLM-generated tool calls, formally checks them against policies encoded as Lean 4 theorems (compiled to Z3 CHCs), and blocks unsafe calls with counterexamples before they reach the runtime.

## Architecture

```
LLM (Groq API)
  ↓ tool call JSON
Orchestrator (orchestrator.py)
  ↓ parsed intent + args
Z3 Policy Check (verifier/)
  ↓ UNSAT / SAT + model
[UNSAT] → Fire tool
[SAT]   → Return counterexample, block policy violation
            ↑
Lean 4 Policy (Lean/Policy.lean)
  ↓ compile to Z3 encoding
Bridge (bridge/)
```

## Quick Start

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install z3-solver pytest

# Verify Lean 4 is installed
lean --version

# Run all tests
make test

# Run demo scenarios (without LLM — uses mock tool calls)
make demo

# Verify Lean theorems compile
make verify
```

## Demo Scenarios

| Scenario | Tool Call | Verdict |
|---|---|---|
| Tahoe at $1 | `confirm_sale(Tahoe, 1)` | ❌ BLOCKED (below $45000 floor) |
| Tahoe at $50000 | `confirm_sale(Tahoe, 50000)` | ✅ PERMITTED |
| Delete /etc/passwd | `delete_file(/etc/passwd)` | ❌ BLOCKED (outside scope) |
| Delete /project/temp | `delete_file(/project/temp)` | ✅ PERMITTED |

```bash
# Run specific scenarios
python demo.py tahoe-violation
python demo.py tahoe-compliant
python demo.py deletion-violation
python demo.py deletion-compliant

# Or run standalone scripts
python demo_tahoe.py
python demo_deletion.py
```

## LLM Integration (Optional)

Set your Groq API key to use a real LLM:

```bash
export GROQ_API_KEY=gsk_...
export LLM_MODEL=mixtral-8x7b-32768    # default
pip install groq

# Run with real LLM
python demo.py tahoe-violation
```

Without the API key, `demo.py` falls back to mock tool calls.

## Adding a New Policy

1. **Lean theorem**: Add the policy to `Lean/Policy.lean`
2. **Z3 encoding**: Add a checker in `verifier/` (see `tahoe_policy.py`)
3. **Register**: Add route in `config.py` `POLICY_ROUTES`
4. **Bridge spec** (optional): Add a `PolicySpec` in `bridge/__init__.py`
5. **Tests**: Add test file in `tests/`

## Project Structure

```
├── Lean/Policy.lean          # Ground-truth policy theorems
├── verifier/
│   ├── tahoe_policy.py        # Tahoe price floor check
│   ├── deletion_policy.py     # File deletion frame check
│   └── verifier.py            # Generic verifier wrapper
├── bridge/
│   ├── policy_spec.py         # Lean-mirroring type system
│   └── z3_encoder.py          # Policy spec → Z3 constraints
├── llm/
│   ├── groq_client.py         # Groq API wrapper
│   └── prompts.py             # System prompts
├── orchestrator.py            # Main entry point
├── config.py                  # Configuration
├── demo*.py                   # Demo scripts
└── tests/                     # 102+ tests
```

## Commit History

| Phase | Description | Tests |
|---|---|---|
| 1 | Tahoe arithmetic policy | 25 |
| 2 | File deletion frame policy | 18 |
| 3 | Orchestrator + tool intercept | 20 |
| 4 | Lean → Z3 bridge | 19 |
| 5 | Groq LLM integration + e2e | 20 |
| 6 | Docs, CI, polish | — |
