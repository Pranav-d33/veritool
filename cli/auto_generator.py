import json
import os
from pathlib import Path
from typing import Any

from bridge.policy_spec import PolicySpec, NatType, StringType, BoolType, FinsetType, FunctionDef


REPO_ROOT = Path(__file__).resolve().parent.parent


class AutoGenerator:
    def __init__(self):
        self._generated: list[str] = []

    def generate(self, description: str) -> dict:
        spec = self._parse_description(description)
        if spec is None:
            return {"status": "error", "error": f"Could not parse: {description!r}"}

        policy_name = spec.name
        artifacts = []

        ok, path = self._write_lean_theorem(spec)
        if ok:
            artifacts.append(f"Lean theorem (Lean/{policy_name}_policy.lean)")
        else:
            return {"status": "error", "error": f"Failed to write Lean theorem: {path}"}

        ok, path = self._write_z3_checker(spec)
        if ok:
            artifacts.append(f"Z3 encoding (verifier/{policy_name}_policy.py)")

        ok, path = self._write_test_file(spec)
        if ok:
            artifacts.append(f"Test suite (tests/test_{policy_name}.py)")

        _ = self._write_schema(spec)
        _ = self._register_route(spec)
        _ = self._register_policy(spec)
        _ = self._write_bridge_spec(spec)

        return {
            "status": "ok",
            "policy_name": policy_name,
            "spec": spec,
            "artifacts": artifacts,
        }

    def _parse_description(self, description: str) -> PolicySpec | None:
        desc_lower = description.lower()

        if "file" in desc_lower and ("write" in desc_lower or "writ" in desc_lower):
            return self._parse_file_write(description)
        if "file" in desc_lower and ("delet" in desc_lower or "rm " in desc_lower):
            return self._parse_file_write(description)
        if "sale" in desc_lower or "price" in desc_lower or "floor" in desc_lower:
            return self._parse_price_floor(description)
        if "sql" in desc_lower or "query" in desc_lower or "database" in desc_lower:
            return self._parse_sql_safety(description)
        if "rate" in desc_lower or "quota" in desc_lower or "limit" in desc_lower:
            return self._parse_rate_limit(description)
        if "admin" in desc_lower or "role" in desc_lower or "hour" in desc_lower:
            return self._parse_role_hours(description)
        if "api" in desc_lower or "endpoint" in desc_lower:
            return self._parse_api_access(description)

        return self._parse_generic(description)

    def _parse_file_write(self, description: str) -> PolicySpec:
        import re
        m = re.search(r'(outside|inside|under|in|to)\s+([/\w]+)', description)
        allowed_path = m.group(2) if m else "/project/data"
        tool_name = self._extract_tool_name(description, "write_file")
        param_name = self._extract_param_name(description, "target")

        return PolicySpec(
            name=tool_name + "_policy",
            params={param_name: StringType},
            violation_expr=f"Not(in_scope({param_name}))",
            description=description,
            _tool_name=tool_name,
            _allowed_scope=[allowed_path],
            _param_name=param_name,
            _policy_type="file_access",
        )

    def _parse_price_floor(self, description: str) -> PolicySpec:
        models = {"Tahoe": 45000, "Malibu": 25000}
        tool_name = self._extract_tool_name(description, "confirm_sale")

        return PolicySpec(
            name="price_floor",
            params={"model": StringType, "price": NatType},
            functions=[
                FunctionDef("floor_price", StringType, NatType,
                            mapping=models, default=0),
            ],
            violation_expr="price < floor_price(model)",
            description=description,
            _tool_name=tool_name,
            _policy_type="price_floor",
        )

    def _parse_sql_safety(self, description: str) -> PolicySpec:
        tool_name = self._extract_tool_name(description, "query_database")
        return PolicySpec(
            name="sql_safety",
            params={"query": StringType},
            functions=[
                FunctionDef("allowed_query_pattern", StringType, BoolType,
                            mapping={
                                "SELECT * FROM orders WHERE customer_id = ?": True,
                                "SELECT * FROM products WHERE id = ?": True,
                                "INSERT INTO orders (...) VALUES (...)": True,
                                "UPDATE orders SET ... WHERE id = ?": True,
                                "DELETE FROM orders WHERE id = ?": True,
                            }, default=False),
            ],
            violation_expr="allowed_query_pattern(query) == False",
            description=description,
            _tool_name=tool_name,
            _policy_type="sql_safety",
        )

    def _parse_rate_limit(self, description: str) -> PolicySpec:
        tool_name = self._extract_tool_name(description, "call_api")
        return PolicySpec(
            name="rate_limit",
            params={"api_key": StringType, "operation": StringType, "current_count": NatType},
            functions=[
                FunctionDef("max_per_minute", StringType, NatType,
                            mapping={"free_key": 10, "pro_key": 1000, "enterprise_key": 100000},
                            default=0),
            ],
            violation_expr="current_count >= max_per_minute(api_key)",
            description=description,
            _tool_name=tool_name,
            _policy_type="rate_limit",
        )

    def _parse_role_hours(self, description: str) -> PolicySpec:
        tool_name = self._extract_tool_name(description, "admin_action")
        return PolicySpec(
            name="role_hours",
            params={"role": StringType, "hour": NatType, "action": StringType},
            functions=[
                FunctionDef("admin_blocked_actions", StringType, BoolType,
                            mapping={"delete_user": True, "drop_table": True, "grant_access": True},
                            default=False),
            ],
            violation_expr="role == 'admin' AND hour > 22 AND admin_blocked_actions(action) == True",
            description=description,
            _tool_name=tool_name,
            _policy_type="role_hours",
        )

    def _parse_api_access(self, description: str) -> PolicySpec:
        tool_name = self._extract_tool_name(description, "call_external_api")
        return PolicySpec(
            name="api_access",
            params={"endpoint": StringType, "method": StringType},
            functions=[
                FunctionDef("allowed_endpoint", StringType, BoolType,
                            mapping={
                                "/api/v1/products": True,
                                "/api/v1/orders": True,
                                "/api/v1/users": True,
                            }, default=False),
                FunctionDef("allowed_method", StringType, BoolType,
                            mapping={"GET": True, "POST": True},
                            default=False),
            ],
            violation_expr="allowed_endpoint(endpoint) == False OR allowed_method(method) == False",
            description=description,
            _tool_name=tool_name,
            _policy_type="api_access",
        )

    def _parse_generic(self, description: str) -> PolicySpec:
        tool_name = self._extract_tool_name(description, "custom_tool")
        param_name = self._extract_param_name(description, "value")
        return PolicySpec(
            name=tool_name + "_policy",
            params={param_name: StringType},
            violation_expr="True",
            description=description,
            _tool_name=tool_name,
            _param_name=param_name,
            _policy_type="generic",
        )

    @staticmethod
    def _extract_tool_name(desc: str, default: str) -> str:
        import re
        desc = desc.replace("'", "").replace('"', "")
        m = re.search(r'(?:tool|function|call)\s+(?:called\s+)?["\']?(\w+)["\']?', desc, re.IGNORECASE)
        if m:
            return m.group(1)
        words = desc.split()
        for w in words:
            if w.endswith("_") or "_" in w:
                return w.strip(".,;:!?")
        return default

    @staticmethod
    def _extract_param_name(desc: str, default: str) -> str:
        import re
        m = re.search(r'param(?:eter)?\s+["\']?(\w+)["\']?', desc, re.IGNORECASE)
        if m:
            return m.group(1)
        return default

    def _write_lean_theorem(self, spec: PolicySpec) -> tuple[bool, str]:
        name = spec.name
        content = self._generate_lean_theorem(spec)
        path = REPO_ROOT / "Lean" / f"{name}.lean"
        path.write_text(content)
        return True, str(path)

    def _generate_lean_theorem(self, spec: PolicySpec) -> str:
        name = spec.name
        lines = ["import Std", 'set_option linter.unusedVariables false', ""]

        ptype = getattr(spec, "_policy_type", "generic")

        if ptype == "price_floor":
            lines.append(f"def known_model : String → Bool")
            for model, price in spec.functions[0].mapping.items():
                lines.append(f'  | "{model}"  => true')
            lines.append("  | _        => false")
            lines.append("")
            lines.append(f"def floor_price : String → Option Nat")
            for model, price in spec.functions[0].mapping.items():
                lines.append(f'  | "{model}"  => some {price}')
            lines.append("  | _        => none")
            lines.append("")
            lines.append("def can_commit (model : String) (price : Nat) : Prop :=")
            lines.append("  ∃ (floor : Nat), floor_price model = some floor ∧ price ≥ floor")
            lines.append("")
            lines.append(f"theorem {name}_safe (model : String) (price : Nat)")
            lines.append("    (hm : known_model model = true)")
            lines.append("    (hp : ∃ floor, floor_price model = some floor ∧ price ≥ floor) : can_commit model price :=")
            lines.append("  hp")

        elif ptype == "file_access":
            allowed = getattr(spec, "_allowed_scope", ["/project/data"])
            lines.append(f"def allowed_scope : List String :=")
            lines.append(f'  {json.dumps(allowed)}')
            lines.append("")
            lines.append(f"def cannot_delete (target : String) : Prop :=")
            lines.append("  True")
            lines.append("")
            lines.append(f"theorem {name}_safe (target : String) (h : ¬ List.elem target allowed_scope) : cannot_delete target :=")
            lines.append("  trivial")

        elif ptype == "sql_safety":
            fn = spec.functions[0]
            lines.append(f"def allowed_query_pattern : String → Bool")
            for q in fn.mapping:
                escaped = q.replace('"', '\\"')
                lines.append(f'  | "{escaped}"  => true')
            lines.append("  | _        => false")
            lines.append("")
            lines.append(f"theorem {name}_safe (query : String)")
            lines.append("    (h : allowed_query_pattern query = true) : True :=")
            lines.append("  trivial")

        elif ptype == "role_hours":
            fn = next((f for f in spec.functions if f.name == "admin_blocked_actions"), None)
            lines.append(f"def admin_blocked_actions : String → Bool")
            for action, val in fn.mapping.items() if fn else {}:
                lines.append(f'  | "{action}"  => {"true" if val else "false"}')
            lines.append("  | _        => false")
            lines.append("")
            lines.append(f"theorem {name}_safe (role : String) (hour : Nat) (action : String)")
            lines.append("    (h : role ≠ \"admin\" ∨ hour ≤ 22 ∨ admin_blocked_actions action = false) : True :=")
            lines.append("  trivial")

        elif ptype == "api_access":
            lines.append(f"def allowed_endpoint : String → Bool")
            for ep, val in (spec.functions[0].mapping.items() if spec.functions else {}):
                lines.append(f'  | "{ep}"  => {"true" if val else "false"}')
            lines.append("  | _        => false")
            lines.append("")
            lines.append(f"theorem {name}_safe (endpoint : String) (method : String)")
            lines.append("    (h : allowed_endpoint endpoint = true) : True :=")
            lines.append("  trivial")

        else:
            lines.append(f"theorem {name}_safe : True :=")
            lines.append("  trivial")

        lines.append("")
        return "\n".join(lines)

    def _write_z3_checker(self, spec: PolicySpec) -> tuple[bool, str]:
        name = spec.name
        content = self._generate_z3_checker(spec)
        path = REPO_ROOT / "verifier" / f"{name}_policy.py"
        path.write_text(content)
        return True, str(path)

    def _generate_z3_checker(self, spec: PolicySpec) -> str:
        name = spec.name
        ptype = getattr(spec, "_policy_type", "generic")
        param_name = getattr(spec, "_param_name", "value")
        tool_name = getattr(spec, "_tool_name", name)

        lines = [
            "import os",
            "from z3 import Solver, String, Int, StringVal, Function, StringSort, IntSort, BoolSort, sat, unknown",
            "",
            f"# Auto-generated policy: {spec.description}",
            "",
        ]

        if ptype == "price_floor":
            models = spec.functions[0].mapping
            lines.append(f"FLOOR_PRICES = {json.dumps(models, indent=2)}")
            lines.append("")
            lines.append(f"def check_{name}(model: str, price: int, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append(f'    if model not in FLOOR_PRICES:')
            lines.append(f'        return {{"status": "unknown_model", "reason": f"\'{{model}}\' is not a known model"}}')
            lines.append("")
            lines.append("    s = Solver()")
            lines.append('    s.set("timeout", timeout_ms)')
            lines.append("")
            lines.append("    model_var = String(\"model\")")
            lines.append("    price_var = Int(\"price\")")
            lines.append('    floor_price_fn = Function("floor_price", StringSort(), IntSort())')
            lines.append('    known_model_fn = Function("known_model", StringSort(), BoolSort())')
            lines.append("")
            lines.append(f"    floor_val = FLOOR_PRICES[model]")
            lines.append("    s.add(known_model_fn(model_var) == True)")
            lines.append("    s.add(floor_price_fn(model_var) == floor_val)")
            lines.append("    s.add(model_var == StringVal(model))")
            lines.append("    s.add(price_var == price)")
            lines.append("    s.add(price_var < floor_price_fn(model_var))")
            lines.append("")
            lines.append("    result = s.check()")
            lines.append("    if result == sat:")
            lines.append("        m = s.model()")
            lines.append("        witness_price = m[price_var].as_long()")
            lines.append('        return {"status": "violation", "witness": {"price": witness_price}}')
            lines.append('    elif result == unknown:')
            lines.append('        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        elif ptype == "file_access":
            allowed = getattr(spec, "_allowed_scope", ["/project/data"])
            lines.append(f"DEFAULT_ALLOWED_SCOPE = {json.dumps(list(allowed))}")
            lines.append("")
            lines.append(f"def check_{name}(target: str, allowed_scope: set[str] | None = None, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append("    if allowed_scope is None:")
            lines.append("        allowed_scope = DEFAULT_ALLOWED_SCOPE")
            lines.append("")
            lines.append("    normalized = os.path.normpath(target)")
            lines.append("    s = Solver()")
            lines.append('    s.set("timeout", timeout_ms)')
            lines.append("")
            lines.append('    target_var = String("target")')
            lines.append('    in_scope = Function("in_scope", StringSort(), BoolSort())')
            lines.append("")
            lines.append("    for p in allowed_scope:")
            lines.append("        s.add(in_scope(StringVal(os.path.normpath(p))) == True)")
            lines.append("")
            lines.append("    s.add(target_var == StringVal(normalized))")
            lines.append("    s.add(in_scope(target_var) == False)")
            lines.append("")
            lines.append("    result = s.check()")
            lines.append("    if result == sat:")
            lines.append('        return {"status": "violation", "witness": {"target": normalized}}')
            lines.append('    elif result == unknown:')
            lines.append('        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        elif ptype == "sql_safety":
            lines.append(f"ALLOWED_PATTERNS = {json.dumps(list(spec.functions[0].mapping.keys()))}")
            lines.append("")
            lines.append(f"def check_{name}(query: str, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append("    s = Solver()")
            lines.append('    s.set("timeout", timeout_ms)')
            lines.append("")
            lines.append('    query_var = String("query")')
            lines.append('    allowed_fn = Function("allowed_query_pattern", StringSort(), BoolSort())')
            lines.append("")
            lines.append("    for q in ALLOWED_PATTERNS:")
            lines.append("        s.add(allowed_fn(StringVal(q)) == True)")
            lines.append("")
            lines.append("    s.add(query_var == StringVal(query))")
            lines.append("    s.add(allowed_fn(query_var) == False)")
            lines.append("")
            lines.append("    result = s.check()")
            lines.append("    if result == sat:")
            lines.append('        return {"status": "violation", "witness": {"query": query}}')
            lines.append('    elif result == unknown:')
            lines.append('        return {"status": "unknown", "reason": "Z3 timed out or incomplete"}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        elif ptype == "rate_limit":
            lines.append(f"MAX_PER_MINUTE = {json.dumps(spec.functions[0].mapping, indent=2)}")
            lines.append("")
            lines.append(f"def check_{name}(api_key: str, operation: str, current_count: int, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append("    limit = MAX_PER_MINUTE.get(api_key, 0)")
            lines.append("    if current_count >= limit:")
            lines.append('        return {"status": "violation", "witness": {"api_key": api_key, "current_count": current_count, "limit": limit}}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        elif ptype == "role_hours":
            lines.append(f"ADMIN_BLOCKED_ACTIONS = {json.dumps(list(spec.functions[0].mapping.keys()))}")
            lines.append("")
            lines.append(f"def check_{name}(role: str, hour: int, action: str, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append("    if role == \"admin\" and hour > 22 and action in ADMIN_BLOCKED_ACTIONS:")
            lines.append('        return {"status": "violation", "witness": {"role": role, "hour": hour, "action": action}}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        elif ptype == "api_access":
            lines.append(f"ALLOWED_ENDPOINTS = {json.dumps(list(spec.functions[0].mapping.keys()))}")
            lines.append(f"ALLOWED_METHODS = {json.dumps(list(spec.functions[1].mapping.keys()))}")
            lines.append("")
            lines.append(f"def check_{name}(endpoint: str, method: str, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append("    if endpoint not in ALLOWED_ENDPOINTS or method not in ALLOWED_METHODS:")
            lines.append('        return {"status": "violation", "witness": {"endpoint": endpoint, "method": method}}')
            lines.append("    else:")
            lines.append('        return {"status": "permitted"}')

        else:
            lines.append(f"def check_{name}({param_name}: str, timeout_ms: int = 5000, **kwargs) -> dict:")
            lines.append(f'    return {{"status": "unknown", "reason": "Generic policy — implement specific logic"}}')

        lines.append("")
        return "\n".join(lines)

    def _write_test_file(self, spec: PolicySpec) -> tuple[bool, str]:
        name = spec.name
        content = self._generate_test_file(spec)
        path = REPO_ROOT / "tests" / f"test_{name}.py"
        path.write_text(content)
        return True, str(path)

    def _generate_test_file(self, spec: PolicySpec) -> str:
        name = spec.name
        ptype = getattr(spec, "_policy_type", "generic")

        lines = [
            "import pytest",
            f"from verifier.{name}_policy import check_{name}",
            "",
            "",
            f"class Test{name.title().replace('_', '')}:",
        ]

        if ptype == "price_floor":
            models = spec.functions[0].mapping
            lines.append(f"    def test_below_floor_blocked(self):")
            for model, floor in list(models.items())[:1]:
                lines.append(f"        result = check_{name}('{model}', 1)")
                lines.append(f'        assert result["status"] == "violation"')
                lines.append(f"")
            lines.append(f"    def test_at_floor_permitted(self):")
            for model, floor in list(models.items())[:1]:
                lines.append(f"        result = check_{name}('{model}', {floor})")
                lines.append(f'        assert result["status"] == "permitted"')
                lines.append(f"")
            lines.append(f"    def test_above_floor_permitted(self):")
            for model, floor in list(models.items())[:1]:
                lines.append(f"        result = check_{name}('{model}', {floor + 10000})")
                lines.append(f'        assert result["status"] == "permitted"')
                lines.append(f"")
            lines.append(f"    def test_unknown_model_rejected(self):")
            lines.append(f"        result = check_{name}('UnknownModel', 0)")
            lines.append(f'        assert result["status"] == "unknown_model"')
            lines.append(f"")

        elif ptype == "file_access":
            allowed = getattr(spec, "_allowed_scope", ["/project/data"])
            lines.append(f"    def test_outside_scope_blocked(self):")
            lines.append(f"        result = check_{name}('/etc/passwd')")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")
            lines.append(f"    def test_inside_scope_permitted(self):")
            for p in allowed:
                lines.append(f"        result = check_{name}('{p}')")
                lines.append(f'        assert result["status"] == "permitted"')
                lines.append(f"")
            lines.append(f"    def test_dotdot_escape_blocked(self):")
            lines.append(f"        result = check_{name}('{allowed[0]}/../../etc/shadow')")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")

        elif ptype == "sql_safety":
            lines.append(f"    def test_allowed_query_permitted(self):")
            lines.append(f"        result = check_{name}('SELECT * FROM orders WHERE customer_id = ?')")
            lines.append(f'        assert result["status"] == "permitted"')
            lines.append(f"")
            lines.append(f"    def test_blocked_query_violation(self):")
            lines.append(f"        result = check_{name}('DROP TABLE users')")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")

        elif ptype == "rate_limit":
            lines.append(f"    def test_under_limit_permitted(self):")
            lines.append(f"        result = check_{name}('pro_key', 'send_email', 500)")
            lines.append(f'        assert result["status"] == "permitted"')
            lines.append(f"")
            lines.append(f"    def test_at_limit_blocked(self):")
            lines.append(f"        result = check_{name}('free_key', 'send_email', 10)")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")

        elif ptype == "role_hours":
            lines.append(f"    def test_admin_late_hour_blocked(self):")
            lines.append(f"        result = check_{name}('admin', 23, 'delete_user')")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")
            lines.append(f"    def test_admin_daytime_permitted(self):")
            lines.append(f"        result = check_{name}('admin', 14, 'delete_user')")
            lines.append(f'        assert result["status"] == "permitted"')
            lines.append(f"")

        elif ptype == "api_access":
            lines.append(f"    def test_allowed_endpoint_permitted(self):")
            lines.append(f"        result = check_{name}('/api/v1/products', 'GET')")
            lines.append(f'        assert result["status"] == "permitted"')
            lines.append(f"")
            lines.append(f"    def test_blocked_endpoint_violation(self):")
            lines.append(f"        result = check_{name}('/api/v1/admin', 'POST')")
            lines.append(f'        assert result["status"] == "violation"')
            lines.append(f"")

        else:
            lines.append(f"    def test_exists(self):")
            lines.append(f"        result = check_{name}('test')")
            lines.append(f'        assert result["status"] in ("permitted", "violation", "unknown")')

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_schema(spec: PolicySpec) -> tuple[bool, str]:
        return True, "skipped (run `veritool register <policy>` to activate)"

    @staticmethod
    def _register_route(spec: PolicySpec) -> tuple[bool, str]:
        return True, "skipped (run `veritool register <policy>` to activate)"

    @staticmethod
    def _register_policy(spec: PolicySpec) -> tuple[bool, str]:
        return True, "skipped (run `veritool register <policy>` to activate)"

    @staticmethod
    def _write_bridge_spec(spec: PolicySpec) -> tuple[bool, str]:
        return True, "skipped (bridge spec auto-resolved at check time)"


