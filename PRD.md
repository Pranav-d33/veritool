# PRD: Z3 + Lean 4 Static Verifier for LLM Tool-Calling

## 1. Purpose

Build a verification pipeline that intercepts LLM-generated tool calls, formally checks them against a policy encoded as Lean 4 theorems (compiled to Z3 CHCs), and blocks unsafe calls with counterexamples before they reach the runtime.

## 2. Success Criteria

| # | Criterion | Verification |
|---|---|---|
| 1 | Tahoe sale at $1 is blocked with `price=1` witness | `python -m pytest tests/test_tahoe.py -v` |
| 2 | Tahoe sale at $50000 is permitted | same test suite |
| 3 | Delete `/home/user/docs/private.key` is blocked | `python -m pytest tests/test_deletion.py -v` |
| 4 | Delete `/project/temp/cleanup.sh` is permitted | same test suite |
| 5 | Lean `safe_sale` theorem compiles (`lean --run`) | `lean --make Lean/Policy.lean` |
| 6 | Lean → Z3 bridge round-trips: theorem → CHC → UNSAT for valid calls | `python -m pytest tests/test_bridge.py -v` |
| 7 | End-to-end: mock LLM output → orchestrator → Z3 → block/permit decision | `python -m pytest tests/test_e2e.py -v` |

## 3. Architecture

```
LLM (Groq API)
  ↓ tool call JSON
Orchestrator (orchestrator.py)
  ↓ parsed intent + args
Z3 Policy Check (z3/policy_check.py)
  ↓ UNSAT / SAT + model
[UNSAT] → Fire tool
[SAT]   → Return counterexample, block
            ↑
Lean 4 Policy (Lean/Policy.lean)
  ↓ compile to Z3 encoding
Bridge (bridge.py)
```

## 4. Phases & Deliverables

### Phase 1 — Tahoe Arithmetic Policy

**What:** Z3 encoding + Lean theorem for a minimum-price floor policy.

**Files:**
- `Lean/Policy.lean` — `floor_price` function + `safe_sale` theorem
- `z3/tahoe_policy.py` — Python Z3 encoding of floor-price constraint
- `tests/test_tahoe.py`

**Tests required:**
1. `test_sale_below_floor_blocked` — price=1, Tahoe → Z3 returns SAT with witness
2. `test_sale_at_floor_permitted` — price=45000, Tahoe → Z3 returns UNSAT
3. `test_sale_above_floor_permitted` — price=50000, Tahoe → Z3 returns UNSAT
4. `test_sale_unknown_model_defaults_to_zero` — price=0, "Ferrari" → Z3 returns... (define behavior: blocked because floor=0 and price=0, or permitted? Decide: price ≥ 0 is true, so permitted. Add test.)
5. `test_lean_theorem_compiles` — shell out to `lean --run` on a script that invokes `safe_sale` and exits 0
6. `test_counterexample_contains_price` — SAT result must include `price` binding

**Commit:** `git commit -m "Phase 1: Tahoe arithmetic policy — Z3 encoding + Lean theorem + tests"`

### Phase 2 — File Deletion Frame Policy

**What:** Frame-condition policy: files outside a declared `allowed_scope` cannot be deleted.

**Files:**
- `Lean/Policy.lean` — extend with `allowed_scope : Finset String` + `frame_safe` theorem
- `z3/deletion_policy.py` — Z3 encoding of set-membership constraint
- `tests/test_deletion.py`

**Tests required:**
1. `test_delete_outside_scope_blocked` — target="/etc/passwd" → SAT with witness
2. `test_delete_inside_scope_permitted` — target="/project/temp/foo" → UNSAT
3. `test_delete_root_blocked` — target="/" → SAT
4. `test_delete_dotdot_escape_blocked` — target="/project/temp/../../etc/shadow" → must normalize first, or ensure policy catches it. Add normalization test.
5. `test_empty_scope_all_deletions_blocked` — Finset.empty → any delete is SAT
6. `test_counterexample_contains_target_path` — SAT result includes `target` binding
7. `test_lean_frame_safe_compiles` — `lean --run` verification

**Commit:** `git commit -m "Phase 2: File deletion frame policy — Z3 encoding + Lean theorem + tests"`

### Phase 3 — Python Orchestrator + Tool Intercept

**What:** The middleware that sits between the LLM and the tool runtime.

**Files:**
- `orchestrator.py` — main entry point: parse LLM output, route to Z3, return decision
- `z3/verifier.py` — generic Z3 verification wrapper (loads policy encoding, checks SAT/UNSAT)
- `config.py` — Groq API key, model name, policy paths
- `tests/test_orchestrator.py`
- `tests/test_integration.py`

**Tests required:**
1. `test_parse_valid_tool_call` — JSON → `{"tool": "confirm_sale", "args": {...}}`
2. `test_parse_malformed_json` — raises `ParseError`
3. `test_parse_unknown_tool` — no matching policy → returns `{"status": "unknown_tool"}`
4. `test_orchestrator_blocks_violation` — mock Z3 returns SAT → result says `blocked`
5. `test_orchestrator_permits_compliant` — mock Z3 returns UNSAT → result says `permitted`
6. `test_orchestrator_returns_counterexample` — blocked response includes witness fields
7. `test_orchestrator_handles_z3_timeout` — Z3 takes > N seconds → graceful fallback
8. `test_integration_tahoe_blocks_1_dollar` — real Z3 call, Tahoe at $1 → blocked
9. `test_integration_deletion_blocks_etc_passwd` — real Z3 call → blocked

**Commit:** `git commit -m "Phase 3: Python orchestrator + tool intercept — middleware, verifier, integration tests"`

### Phase 4 — Lean → Z3 Bridge

**What:** Automated translation from Lean 4 policy types into Z3 CHC encoding. This is the novel contribution — makes the pipeline composable.

**Files:**
- `bridge.py` — Lean type AST → Z3 constraint tree
- `bridge/lean_parser.py` — parse/detect Lean theorem structure
- `bridge/z3_encoder.py` — map Lean types to Z3 sorts/assertions
- `tests/test_bridge.py`
- `tests/test_bridge_roundtrip.py`

**Tests required:**
1. `test_lean_nat_to_z3_int` — Lean `Nat` → Z3 `Int` with `(>= x 0)`
2. `test_lean_string_to_z3_string_sort` — Lean `String` → Z3 string sort
3. `test_lean_finset_to_z3_assert` — Lean `Finset String` → Z3 `(declare-fun in_scope (String) Bool)` + member assertions
4. `test_lean_theorem_to_chc` — `safe_sale` → Z3 `(assert (=> ...))`
5. `test_bridge_roundtrip_safe_sale_valid` — bridge-generated Z3 on valid price → UNSAT
6. `test_bridge_roundtrip_safe_sale_invalid` — bridge-generated Z3 on invalid price → SAT
7. `test_bridge_roundtrip_deletion_in_scope` — UNSAT
8. `test_bridge_roundtrip_deletion_out_of_scope` — SAT
9. `test_bridge_handles_unsupported_lean_type` — raises clear `BridgeError`
10. `test_bridge_matches_manual_encoding` — for each policy, bridge output == manual Z3 output (same set of models)

**Commit:** `git commit -m "Phase 4: Lean → Z3 bridge — automated theorem-to-CHC translation + round-trip tests"`

### Phase 5 — Groq LLM Integration + End-to-End Demo

**What:** Wire Groq API as the LLM backend; build a demo script that sends a prompt, intercepts the tool call, verifies it, and reports the result.

**Files:**
- `llm/groq_client.py` — Groq API wrapper
- `llm/prompts.py` — system prompt that instructs the model to call tools
- `demo.py` — end-to-end demo runner
- `demo_tahoe.py` — Tahoe scenario script
- `demo_deletion.py` — deletion scenario script
- `tests/test_groq_client.py`
- `tests/test_e2e.py`

**Tests required:**
1. `test_groq_client_returns_tool_call` — mock Groq API, verify tool call JSON extracted
2. `test_groq_client_handles_api_error` — 401/rate-limit → graceful error
3. `test_e2e_tahoe_violation` — full pipeline: prompt → Groq → parse → Z3 → blocked
4. `test_e2e_tahoe_compliance` — prompt with fair price → permitted
5. `test_e2e_deletion_violation` — prompt asking to delete outside scope → blocked
6. `test_e2e_deletion_compliance` — prompt asking to delete inside scope → permitted
7. `test_demo_script_exits_zero_on_violation` — `demo.py` exits 0
8. `test_demo_script_exits_zero_on_permission` — `demo.py` exits 0

**Commit:** `git commit -m "Phase 5: Groq LLM integration + end-to-end demo — full pipeline wired"`

### Phase 6 — Documentation, CI, and Polish

**Files:**
- `README.md` — architecture diagram, setup, usage, demo walkthrough
- `ARCHITECTURE.md` — detailed system design
- `CONTRIBUTING.md` — how to add new policies
- `Makefile` — `make test`, `make verify`, `make demo`
- `.github/workflows/ci.yml` — run tests on push/PR
- `pyproject.toml` — project metadata, dependencies
- `Lean/lakefile.lean` — Lean package config (if needed)

**Tests required:**
1. `make test` runs all tests and exits 0
2. `make verify` runs Lean compilation and exits 0
3. `make demo` runs both scenarios without errors
4. CI passes on clean repo

**Commit:** `git commit -m "Phase 6: Documentation, CI, and polish — README, Makefile, GitHub Actions"`

## 5. Non-Functional Requirements

| Requirement | Specification |
|---|---|
| **LLM Backend** | Groq API (`groq` Python SDK). Model: TBD (likely `mixtral-8x7b-32768` or `llama-3.3-70b`). Configured via `GROQ_API_KEY` env var. |
| **Z3** | `z3-solver` Python package (not the SMT-LIB CLI). All checks via Python API. |
| **Lean 4** | Lean 4 compiler (`lean`) on `$PATH`. Policy file compiled once; bridge reads `.olean` or source AST. |
| **Verification Budget** | Each Z3 check must complete in < 5 seconds. Configure timeout in `Verifier` class. |
| **Graceful Degradation** | If Z3 times out or Lean compilation fails, tool call is BLOCKED by default (fail-closed). |
| **Python** | 3.11+ |
| **Logging** | `structlog`-based structured logging. Every verification decision logged with: timestamp, tool, args, result, Z3 model, elapsed ms. |

## 6. Commit Strategy

Every phase ends with exactly one commit. No "WIP" or "fixup" commits on main. The commit message follows the format:

```
Phase N: <title> — <summary of what> + <what was verified>
```

Each commit must:
1. Compile Lean policy successfully
2. Pass all tests for that phase
3. Not break tests from prior phases

**Exception:** If a phase reveals a bug in a prior phase's code, fix it in the current phase's commit and note it in the commit message body.

## 7. Repository Structure

```
.
├── Lean/
│   └── Policy.lean
├── z3/
│   ├── __init__.py
│   ├── tahoe_policy.py
│   ├── deletion_policy.py
│   └── verifier.py
├── bridge/
│   ├── __init__.py
│   ├── lean_parser.py
│   └── z3_encoder.py
├── llm/
│   ├── __init__.py
│   ├── groq_client.py
│   └── prompts.py
├── tests/
│   ├── __init__.py
│   ├── test_tahoe.py
│   ├── test_deletion.py
│   ├── test_orchestrator.py
│   ├── test_integration.py
│   ├── test_bridge.py
│   ├── test_bridge_roundtrip.py
│   ├── test_groq_client.py
│   └── test_e2e.py
├── orchestrator.py
├── bridge.py
├── config.py
├── demo.py
├── demo_tahoe.py
├── demo_deletion.py
├── Makefile
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── CONTRIBUTING.md
└── PRD.md
```

## 8. Decisions Log (to be filled during implementation)

| Decision | Options | Chosen | Rationale |
|---|---|---|---|
| LLM model | `mixtral-8x7b-32768`, `llama-3.3-70b`, `llama-3.1-8b` | TBD | Will decide based on tool-calling reliability during Phase 5 |
| Lean → Z3 bridge approach | Source parsing vs `.olean` reading vs manual encoding per type | TBD | Source parsing is most portable; `.olean` gives types. Evaluate in Phase 4. |
| Path normalization | Pure Python vs library | TBD | `os.path.normpath` on the tool-call arg before verification |
| Fail-closed on timeout | yes / no | **yes** | Safety-critical system must default to blocking |
| Test framework | `pytest` vs `unittest` | **pytest** | Richer fixture system, better parametrization for policy variants |
