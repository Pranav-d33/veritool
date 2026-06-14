from pathlib import Path

import pytest

from cli.auto_generator import AutoGenerator
from cli.round_trip import round_trip_verify


REPO_ROOT = Path(__file__).resolve().parent.parent


def _cleanup_generated(policy_name: str):
    for f in (REPO_ROOT / "verifier").glob(f"{policy_name}_policy.py"):
        f.unlink(missing_ok=True)
    for f in (REPO_ROOT / "Lean").glob(f"{policy_name}.lean"):
        f.unlink(missing_ok=True)
    for f in (REPO_ROOT / "tests").glob(f"test_{policy_name}.py"):
        f.unlink(missing_ok=True)


@pytest.fixture
def gen():
    return AutoGenerator()


@pytest.fixture(autouse=True)
def cleanup_after():
    yield
    for pfile in (REPO_ROOT / "verifier").glob("*_policy.py"):
        if pfile.name not in ("tahoe_policy.py", "deletion_policy.py", "coordination_policy.py", "__init__.py"):
            pfile.unlink(missing_ok=True)
    for lfile in (REPO_ROOT / "Lean").glob("*.lean"):
        if lfile.name not in ("Policy.lean", "Verify.lean", "Invalid.lean"):
            lfile.unlink(missing_ok=True)
    for tfile in (REPO_ROOT / "tests").glob("test_*.py"):
        if tfile.name not in ("test_tahoe.py", "test_deletion.py", "test_schema.py",
                              "test_orchestrator.py", "test_bridge.py",
                              "test_integration.py", "test_e2e.py", "test_groq_client.py",
                              "test_auto_generator.py", "test_coordination.py",
                              "test_policy_store.py", "test_audit.py",
                              "test_integrations.py", "__init__.py"):
            tfile.unlink(missing_ok=True)


class TestAutoGeneratorParsing:
    def test_parse_price_floor(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        assert result["status"] == "ok"
        assert result["policy_name"] == "price_floor"

    def test_parse_file_write(self, gen):
        result = gen.generate("Block any file write outside /var/data")
        assert result["status"] == "ok"
        assert "policy" in result["policy_name"]

    def test_parse_sql_safety(self, gen):
        result = gen.generate("Block SQL queries that are not on the allowlist")
        assert result["status"] == "ok"
        assert result["policy_name"] == "sql_safety"

    def test_parse_rate_limit(self, gen):
        result = gen.generate("Limit API calls to 1000 per minute for pro accounts")
        assert result["status"] == "ok"
        assert result["policy_name"] == "rate_limit"

    def test_parse_role_hours(self, gen):
        result = gen.generate("Block admin actions after 10 PM")
        assert result["status"] == "ok"
        assert result["policy_name"] == "role_hours"

    def test_parse_api_access(self, gen):
        result = gen.generate("Only allow GET and POST to /api/v1/products")
        assert result["status"] == "ok"
        assert result["policy_name"] == "api_access"

    def test_parse_generic_fallback(self, gen):
        result = gen.generate("Custom validation for something unusual")
        assert result["status"] == "ok"

    def test_artifacts_generated(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        assert len(result["artifacts"]) >= 3
        any("Lean theorem" in a for a in result["artifacts"])
        any("Z3 encoding" in a for a in result["artifacts"])
        any("Test suite" in a for a in result["artifacts"])


class TestAutoGeneratorOutput:
    def test_lean_theorem_written(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        lean_path = REPO_ROOT / "Lean" / f"{result['policy_name']}.lean"
        assert lean_path.exists()
        content = lean_path.read_text()
        assert "floor_price" in content
        assert "theorem" in content

    def test_z3_checker_written(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        checker_path = REPO_ROOT / "verifier" / f"{result['policy_name']}_policy.py"
        assert checker_path.exists()
        content = checker_path.read_text()
        assert "def check_" in content

    def test_test_file_written(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        test_path = REPO_ROOT / "tests" / f"test_{result['policy_name']}.py"
        assert test_path.exists()
        content = test_path.read_text()
        assert "class Test" in content

    def test_generated_checker_importable(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        name = result["policy_name"]
        import importlib
        mod = importlib.import_module(f"verifier.{name}_policy")
        check_fn = getattr(mod, f"check_{name}")
        assert callable(check_fn)

    def test_generated_checker_works(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        name = result["policy_name"]
        import importlib
        mod = importlib.import_module(f"verifier.{name}_policy")
        check_fn = getattr(mod, f"check_{name}")
        r = check_fn("Tahoe", 1)
        assert r["status"] == "violation"

    def test_round_trip_price_floor(self, gen):
        result = gen.generate("Block vehicle sales below minimum price floor")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])

    def test_round_trip_file_access(self, gen):
        result = gen.generate("Block any file write outside /project/data")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])

    def test_round_trip_sql(self, gen):
        result = gen.generate("Block SQL queries that are not on the allowlist")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])

    def test_round_trip_rate_limit(self, gen):
        result = gen.generate("Limit API calls to 1000 per minute for pro accounts")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])

    def test_round_trip_role_hours(self, gen):
        result = gen.generate("Block admin actions after 10 PM")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])

    def test_round_trip_api_access(self, gen):
        result = gen.generate("Only allow GET and POST to /api/v1/products")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        assert rtv["passed"] is True, rtv.get("details", [])
