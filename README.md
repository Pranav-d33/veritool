# VeriTool

Runtime trace invariant verification for multi-agent LLM systems. Z3 + Lean 4.

```python
v = Verifier()

v.register_tool("deploy", action_type="DEPLOY", resource_fn=lambda a: a.get("env"))
v.register_tool("build",  action_type="BUILD")
v.register_tool("test",   action_type="TEST")

v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD", "TEST"]))

deploy = v.wrap(my_deploy_fn)
build  = v.wrap(my_build_fn)
test   = v.wrap(my_test_fn)
```

Every tool call is checked against accumulated action traces before execution. Violations are blocked with counterexamples.

## Architecture

```
Tool Call → Verifier.wrap() → Check trace against invariants (Z3) → Permit / Block
                                    ↓
                              Trace appended on permit
                                    ↓
                              Lean proves invariant encoding sound
```

Four invariant types, all enforced via Z3:

| Invariant | Checks |
|-----------|--------|
| `OrderingInvariant("DEPLOY", ["BUILD", "TEST"])` | Before any DEPLOY, BUILD and TEST must have completed |
| `ExclusiveAccessInvariant("WRITE")` | No two agents concurrently WRITE to the same resource |
| `ApprovalInvariant("DEPLOY", "APPROVE")` | DEPLOY requires prior APPROVE by a different agent |
| `MonotonicInvariant("COUNTER")` | Counter values can only increase |

## Why Z3 + Lean?

Existing policy engines (OPA/Rego, AWS Cedar) check single actions against static rules. They cannot enforce invariants that span multiple agents across sequences of actions — e.g., "no deploy without prior build and test."

Z3 encodes the accumulated action trace and invariants as quantified SMT constraints. Lean proves the encoding is sound — if Z3 permits an action, no trace satisfying the invariants can produce a violation.

**Related work**: [Lean4Agent](https://arxiv.org/abs/2606.06523) (UIUC, June 2026) uses Lean 4 for design-time workflow verification. VeriTool targets runtime interception with Z3 for fast SMT checking and Lean for proof of encoding correctness.

## Usage

```python
from verifier.verifier import Verifier
from bridge.invariant import OrderingInvariant, ExclusiveAccessInvariant

v = Verifier(agent_name="ci-bot")
v.register_tool("deploy", action_type="DEPLOY", resource_fn=lambda a: a.get("env"))
v.register_tool("build", action_type="BUILD")
v.register_tool("test", action_type="TEST")
v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD", "TEST"]))
v.add_invariant(ExclusiveAccessInvariant("DEPLOY"))

# Wrap any function — works with LangChain, CrewAI, AutoGen, or raw Python
deploy = v.wrap(deploy_to_production)
build  = v.wrap(run_build)
test   = v.wrap(run_tests)

assert build() == ...
assert test() == ...
assert deploy(env="prod") == ...  # only permitted if BUILD + TEST completed

v.reset()  # clear trace + state for a new session
```

## Project Structure

```
bridge/          # Action trace model + invariant types + Z3 encoding
verifier/        # Generic Verifier with wrap()
Lean/Trace.lean  # Soundness proofs for invariant encoding
policy_store/    # Versioned policy store + audit trail
tests/           # pytest suite
```

## Tests

```bash
make test      # 14 tests, all pass
make verify    # Lean theorem compilation check
```

## Benchmark Results

VeriTool is benchmarked against OPA/Rego (industry-standard policy engine) on 24 test cases across 4 invariant types.

### Detection Rate

| System | Correct | Rate | Missed |
|--------|---------|------|--------|
| OPA (stateless, standard deployment) | 14/24 | 58% | 10 |
| OPA+history (caller accumulates trace) | 24/24 | 100% | 0 |
| **VeriTool** | **24/24** | **100%** | **0** |

OPA's stateless model evaluates each request independently — it has no memory of prior actions. Every missed case is a trace invariant OPA cannot enforce:

- **Ordering**: OPA permits `DEPLOY` without prior `BUILD`
- **Exclusive access**: OPA permits two agents writing the same file
- **Self-approval**: OPA permits `DEPLOY` approved by the same agent
- **Monotonicity**: OPA permits decreasing spend values

OPA+history matches VeriTool on detection rate, but requires the caller to manually accumulate and pass the action history on every eval — shifting verification burden out of the policy engine.

### Latency

| System | Per-action latency |
|--------|-------------------|
| OPA (stateless) | ~9.0ms |
| OPA+history | ~9.9ms |
| **VeriTool** | **~0.13ms** |

VeriTool is ~60x faster because Z3 runs in-process. OPA requires a subprocess invocation with JSON serialization per action.

### Key Advantages

| Dimension | OPA (stateless) | OPA+history | VeriTool |
|-----------|----------------|-------------|----------|
| Detection rate | 58% | 100% | 100% |
| State management | None needed | Caller accumulates | `wrap()` automatic |
| Formal proof | No | No | Lean theorems |
| Invariant definition | Rego rules | Rego rules per-scenario | Z3 declarative constraints |
| Per-action latency | ~9ms | ~10ms | ~0.1ms |

### Reproduce

```bash
make all   # Lean verify → tests → benchmark → 3-way OPA comparison
```

Requires OPA installed: `curl -sL -o /usr/local/bin/opa https://github.com/open-policy-agent/opa/releases/download/v1.2.0/opa_linux_amd64_static && chmod +x /usr/local/bin/opa`

## Docker

```bash
docker build -t veritool .
docker run --rm veritool make all
```

The Dockerfile pins Python 3.13, Lean 4.15.0, OPA 1.2.0. Build it on a machine with Docker daemon available (not available in this environment).

## License

Apache 2.0
