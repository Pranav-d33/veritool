from bridge.policy_spec import PolicySpec, NatType, StringType, FinsetType, FunctionDef, BridgeError
from bridge.z3_encoder import check_policy, compile_policy

TAHOE_SPEC = PolicySpec(
    name="tahoe",
    _policy_type="tahoe",
    params={"model": StringType, "price": NatType},
    functions=[
        FunctionDef("floor_price", StringType, NatType,
                    mapping={"Tahoe": 45000, "Malibu": 25000}, default=0),
    ],
    violation_expr="price < floor_price(model)",
    description="Tahoe/Malibu minimum price policy",
)

DELETION_SPEC = PolicySpec(
    name="deletion",
    _policy_type="deletion",
    params={"target": StringType},
    violation_expr="Not(in_scope(target))",
    _allowed_scope=["/project/temp", "/project/output"],
    description="File deletion frame policy requiring target in allowed scope",
)


def bridge_check(policy_name: str, params: dict | None = None, timeout_ms: int = 5000) -> dict:
    spec_map = {
        "tahoe": TAHOE_SPEC,
        "deletion": DELETION_SPEC,
    }
    spec = spec_map.get(policy_name)
    if spec is None:
        return {"status": "error", "reason": f"Unknown policy: {policy_name}"}
    return check_policy(spec, params=params, timeout_ms=timeout_ms)


__all__ = [
    "PolicySpec", "NatType", "StringType", "FinsetType", "FunctionDef", "BridgeError",
    "check_policy", "compile_policy",
    "TAHOE_SPEC", "DELETION_SPEC", "bridge_check",
]
