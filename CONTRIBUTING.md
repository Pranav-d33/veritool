# Contributing

## Adding a New Policy

1. **Lean theorem** — Add definitions to `Lean/Policy.lean`
2. **Z3 checker** — Create `verifier/<name>_policy.py` with a `check_<name>(**kwargs) -> dict` function
3. **Route** — Add `"tool_name": "<name>"` to `config.py:POLICY_ROUTES`
4. **Register** — Add `"<name>": check_<name>` to `Verifier._policies` in `verifier/verifier.py`
5. **Bridge spec** — Add `PolicySpec` in `bridge/__init__.py` (optional but recommended)
6. **Tests** — Create `tests/test_<name>.py` with policy tests, add integration tests to `tests/test_integration.py`

## Running Tests

```bash
# All tests
make test

# Specific test file
python -m pytest tests/test_tahoe.py -v

# With Lean verification
make verify
```

## Commit Convention

Each phase ends with one commit:

```
Phase N: <title> — <summary>
```

Every commit must:
- Compile Lean policy successfully
- Pass all tests for that phase
- Not break tests from prior phases

## Verification Requirements

- Z3 checks must complete in < 5 seconds
- Lean theorems must compile with `lean --run`
- Bridge round-trip tests must match hand-written Z3
- Path normalization must prevent directory traversal
