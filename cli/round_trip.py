from bridge.policy_spec import PolicySpec
from bridge.z3_encoder import check_policy as bridge_check_policy


def round_trip_verify(policy_name: str, spec: PolicySpec) -> dict:
    ptype = getattr(spec, "_policy_type", "generic")
    details = []
    all_pass = True

    if ptype == "price_floor":
        test_cases = [
            ({"model": "Tahoe", "price": 1}, "violation", "price below floor"),
            ({"model": "Tahoe", "price": 45000}, "permitted", "price at floor"),
            ({"model": "Tahoe", "price": 100000}, "permitted", "price above floor"),
            ({"model": "Malibu", "price": 1}, "violation", "Malibu below floor"),
            ({"model": "Malibu", "price": 25000}, "permitted", "Malibu at floor"),
        ]
        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    elif ptype == "file_access":
        test_cases = [
            ({"target": "/etc/passwd"}, "violation", "outside scope"),
            ({"target": "/etc/shadow"}, "violation", "outside scope 2"),
            ({"target": "/"}, "violation", "root blocked"),
        ]
        allowed = getattr(spec, "_allowed_scope", ["/project/data"])
        for p in allowed:
            test_cases.append(({"target": p}, "permitted", f"inside scope ({p})"))

        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    elif ptype == "sql_safety":
        test_cases = [
            ({"query": "SELECT * FROM orders WHERE customer_id = ?"}, "permitted", "allowed SELECT"),
            ({"query": "DROP TABLE users"}, "violation", "blocked DROP"),
            ({"query": "DELETE FROM orders WHERE id = ?"}, "permitted", "allowed DELETE"),
            ({"query": "GRANT ALL PRIVILEGES TO admin"}, "violation", "blocked GRANT"),
        ]
        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    elif ptype == "rate_limit":
        test_cases = [
            ({"api_key": "free_key", "operation": "send_email", "current_count": 5}, "permitted", "under limit"),
            ({"api_key": "free_key", "operation": "send_email", "current_count": 10}, "violation", "at limit"),
            ({"api_key": "pro_key", "operation": "send_email", "current_count": 500}, "permitted", "pro under limit"),
            ({"api_key": "unknown_key", "operation": "send_email", "current_count": 1}, "violation", "unknown key (default 0)"),
        ]
        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    elif ptype == "role_hours":
        test_cases = [
            ({"role": "admin", "hour": 23, "action": "delete_user"}, "violation", "admin late delete_user"),
            ({"role": "admin", "hour": 14, "action": "delete_user"}, "permitted", "admin daytime"),
            ({"role": "user", "hour": 23, "action": "delete_user"}, "permitted", "non-admin late"),
            ({"role": "admin", "hour": 23, "action": "view_report"}, "permitted", "admin late non-blocked"),
        ]
        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    elif ptype == "api_access":
        test_cases = [
            ({"endpoint": "/api/v1/products", "method": "GET"}, "permitted", "allowed endpoint + method"),
            ({"endpoint": "/api/v1/admin", "method": "POST"}, "violation", "blocked endpoint"),
            ({"endpoint": "/api/v1/products", "method": "DELETE"}, "violation", "blocked method"),
        ]
        for params, expected, label in test_cases:
            result = bridge_check_policy(spec, params)
            if result["status"] != expected:
                all_pass = False
                details.append(f"FAIL: {label} — expected {expected}, got {result['status']}")
            else:
                details.append(f"PASS: {label}")

    else:
        details.append("SKIP: generic policy — no auto round-trip tests")

    return {"passed": all_pass, "details": details}
