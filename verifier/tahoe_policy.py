from z3 import Solver, String, Int, StringVal, Function, StringSort, IntSort, BoolSort, sat, unknown

FLOOR_PRICES = {
    "Tahoe": 45000,
    "Malibu": 25000,
}


def check_sale(model: str, price: int, timeout_ms: int = 5000, **kwargs) -> dict:
    if model not in FLOOR_PRICES:
        return {"status": "unknown_model", "reason": f"'{model}' is not a known model"}

    s = Solver()
    s.set("timeout", timeout_ms)

    model_var = String("model")
    price_var = Int("price")
    floor_price_fn = Function("floor_price", StringSort(), IntSort())
    known_model_fn = Function("known_model", StringSort(), BoolSort())

    floor_val = FLOOR_PRICES[model]
    s.add(known_model_fn(model_var) == True)
    s.add(floor_price_fn(model_var) == floor_val)
    s.add(model_var == StringVal(model))
    s.add(price_var == price)

    s.add(price_var < floor_price_fn(model_var))

    result = s.check()
    if result == sat:
        m = s.model()
        witness_price = m[price_var].as_long()
        return {
            "status": "violation",
            "witness": {"price": witness_price},
        }
    elif result == unknown:
        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}
    else:
        return {"status": "permitted"}
