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
Tool Call → Verifier.wrap() → Z3 encodes all 4 invariants as SMT constraints → UNSAT (permit) / SAT (block + counterexample)
                                                                                        ↑
                                                                              Lean proves:
                                                                              Z3 encoding ⊧ invariant semantics
```

Four invariant types, all encoded as Z3 satisfiability queries:

| Invariant | Checks |
|-----------|--------|
| `OrderingInvariant("DEPLOY", ["BUILD", "TEST"])` | Before any DEPLOY, BUILD and TEST must have completed |
| `ExclusiveAccessInvariant("WRITE")` | No two agents concurrently WRITE to the same resource |
| `ApprovalInvariant("DEPLOY", "APPROVE")` | DEPLOY requires prior APPROVE by a different agent |
| `MonotonicInvariant("SPEND", resource_key="value")` | Values can only increase (per-agent, per-resource) |

Each check creates a `z3.Solver`, encodes the violation condition as a SAT query, and returns a counterexample model on violation. This uniform SMT pipeline enables formal soundness proofs in Lean.

## Why Z3 + Lean?

Existing policy engines (OPA/Rego, AWS Cedar) check single actions against static rules. They cannot enforce invariants that span multiple agents across sequences of actions — e.g., "no deploy without prior build and test."

Z3 encodes the accumulated action trace and invariants as SMT constraints. Lean proves the encoding is sound — each invariant is defined as a Lean `Prop` with nil/snoc structural induction theorems showing that a Z3 permit preserves the invariant.

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

deploy = v.wrap(deploy_to_production)
build  = v.wrap(run_build)
test   = v.wrap(run_tests)

assert build() == ...
assert test() == ...
assert deploy(env="prod") == ...  # only permitted if BUILD + TEST completed

v.reset()  # clear trace for a new session
```

## Project Structure

```
bridge/          # Action trace model + invariant types + Z3 encoding
verifier/        # Generic Verifier with wrap()
Lean/Trace.lean  # Soundness proofs for invariant encoding (3 invariants proved)
policy_store/    # Versioned policy store + audit trail
tests/           # pytest suite
benchmark/       # Scalability, throughput, 3-way OPA comparison
```

## Tests

```bash
make test      # 14 tests, all pass
make verify    # Lean theorem compilation check
```

## Benchmark Results

Full results in [`BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md).

### Detection Rate

| System | Correct | Rate |
|--------|---------|------|
| OPA (stateless) | 14/24 | 58% |
| OPA+history | 24/24 | 100% |
| **VeriTool** | **24/24** | **100%** |

### Latency & Throughput

| System | μs/action | Actions/sec |
|--------|-----------|-------------|
| **VeriTool** | **175** | **5,703** |
| OPA stateless | 10,262 | 97 |
| OPA+history | 11,188 | 89 |

VeriTool is **~60x faster** than OPA across both stateless and history modes.

### Scalability

All invariants remain sub-millisecond up to 1000-trace entries. Per-check latency grows near-constantly (2-3x from size 1 to 1000).

### Formal Soundness

Three of four invariant types are proved correct in Lean via structural induction:

- `ordering_invariant` — nil/snoc theorems
- `exclusive_access_invariant` — nil/snoc theorems
- `approval_invariant` — nil/snoc theorems

Each theorem's `hcase` (safety condition) corresponds exactly to the Z3 encoder's violation check.

### Reproduce

```bash
make all   # Lean verify → tests → benchmark → 3-way OPA comparison
```

Requires OPA installed:
```bash
curl -sL -o /usr/local/bin/opa https://github.com/open-policy-agent/opa/releases/download/v1.2.0/opa_linux_amd64_static
chmod +x /usr/local/bin/opa
```

## Docker

```bash
docker build -t veritool .
docker run --rm veritool make all
```

The Dockerfile pins Python 3.13, Lean 4.15.0, OPA 1.2.0.

## License

Apache 2.0
