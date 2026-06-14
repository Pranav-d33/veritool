# Contributing

## Adding a New Policy

1. Add a `PolicySpec` in `bridge/__init__.py`
2. Set `_policy_type` to one of the supported types
3. Add tests using `bridge_check(policy_name, params)`
4. Add a Lean theorem stub in `Lean/Policy.lean`

No separate `verifier/<name>.py` file needed. The bridge encoder handles all 7 policy types automatically.

If you need a new policy type:
1. Add the branch to `compile_policy` and `check_policy` in `bridge/z3_encoder.py`
2. Add the inference keyword to `auto_generator.py`
3. Document it in `README.md#Supported Policy Types`

## Adding a New Integration

1. Add a wrapper in `integrations/<name>.py`
2. Use `bridge.bridge_check` for the Z3 check
3. Follow the intercept-before-execute pattern

## Running Tests

```bash
make test             # all 183 tests
make test-fast        # stop at first failure
make verify           # Lean theorem compilation
make dashboard        # Streamlit monitoring UI
```

## Commit Convention

```
<module>: <description>
```

Every commit must pass all tests and compile Lean policies.
