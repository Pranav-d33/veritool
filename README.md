# VeriTool

Formal verification framework for LLM tool-calling. Z3 + Lean 4.

```
LLM → Interceptor → Z3 Policy Check → UNSAT = permit | SAT = block + counterexample
                    ↑
              Auto-generator — NL descriptions → formal specs (Lean + Z3)
```

## Quick Install

```bash
pip install z3-solver pytest
pip install -e ".[all]"        # includes dashboard, pandas, streamlit
lean --version && lean Lean/Policy.lean
veritool --help
```

## CLI Usage

```
veritool create "no file named payroll.csv may be deleted"     # NL → formal policy
veritool check tahoe --model Tahoe --price 45000               # decision for a case
veritool test tahoe                                            # run round-trip test matrix
veritool run Tahoe 40000 --verbose                             # unified check+explain
veritool status                                                # active policies summary
veritool hot-reload                                            # reload without restart
veritool rollback tahoe                                        # undo last revision
veritool verify all                                            # full round-trip sweep
veritool dashboard                                             # launch Streamlit UI
veritool wrap "def fn(**kw): ..." --tool-name submit_order     # wrap function as tool
```

## Demo

```bash
python demo_tahoe.py       # price floor checks
python demo_deletion.py    # file scope checks
```

## Supported Policy Types

| Type | Description | Example Violation |
|---|---|---|
| `price_floor` | Minimum price per item | `price < floor_price(model)` |
| `file_access` / `deletion` | Allowed file scope | `¬in_scope(target)` |
| `sql_safety` | Allowed query patterns | `¬allowed_query_pattern(query)` |
| `rate_limit` | Max calls per API key | `current_count ≥ max_per_minute(key)` |
| `role_hours` | Admin action time windows | `role=admin ∧ hour > 22` |
| `api_access` | Endpoint allowlist | `¬endpoint_allowed(path)` |
| `generic` | Custom constraints | user-defined |

## Multi-Agent Coordination

```python
from verifier.coordination_policy import CoordinationVerifier, Invariant

verifier = CoordinationVerifier()
verifier.add_invariant("seq", Invariant.SEQUENTIAL_ACCESS, resource="db")
verifier.add_invariant("lock", Invariant.LOCK_REQUIRED, resource="db")
```

Supported invariants: `SEQUENTIAL_ACCESS`, `LOCK_REQUIRED`, `APPROVAL_REQUIRED`, `MONOTONIC_ACCESS`, `ROLE_BASED_ACCESS`.

## LLM Integration

```python
from integrations.langchain_interceptor import LangChainVerifier
from integrations.crewaI_guard import CrewAIVerifier
from integrations.autogen_middleware import AutoGenMiddleware
```

All three wrappers intercept tool calls and block violations before runtime.

## Tests

```bash
make test           # all tests
make test-fast      # stop at first failure
make verify         # Lean theorem compilation check
make dashboard      # Streamlit monitoring UI
```

183 tests covering all modules.

## Project Structure

```
├── cli/                    # CLI commands + auto-generator + round-trip
├── bridge/                 # PolicySpec type system + Z3 encoder
├── verifier/               # Policy checkers + coordination verifier
├── policy_store/           # Versioned store + audit trail
├── dashboard/              # Streamlit monitoring UI
├── integrations/           # LangChain, CrewAI, AutoGen wrappers
├── Lean/Policy.lean        # Ground-truth theorems
├── Makefile                # test, verify, demo, dashboard targets
└── tests/                  # 183 tests — run with `make test`
```

## Fail-Closed Design

Unknown inputs are rejected at every layer:

| Layer | Unknown Behavior |
|---|---|
| Schema validation | Rejected — out-of-enum |
| Z3 policy check | Rejected — ForAll default-false |
| Lean theorem | Unprovable — `Option Nat` returns `none` |
| Coordination verifier | Rejected — unregistered agents |

## Architecture

```
LLM output → Interceptor → Schema validation → Z3 check → Coordinator → [block/permit]
                                                                 ↓
                                                          Policy Store (versioned)
                                                                 ↓
                                                          Audit Trail (JSONL)
```
