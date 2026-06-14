import subprocess
import sys
from pathlib import Path

import pytest

from verifier.tahoe_policy import check_sale, FLOOR_PRICES

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTahoePolicy:
    def test_sale_below_floor_blocked(self):
        result = check_sale("Tahoe", 1)
        assert result["status"] == "violation"
        assert result["witness"]["price"] == 1

    def test_sale_at_floor_permitted(self):
        result = check_sale("Tahoe", 45000)
        assert result["status"] == "permitted"

    def test_sale_above_floor_permitted(self):
        result = check_sale("Tahoe", 50000)
        assert result["status"] == "permitted"

    def test_sale_just_below_floor_blocked(self):
        result = check_sale("Tahoe", 44999)
        assert result["status"] == "violation"
        assert result["witness"]["price"] == 44999

    def test_malibu_below_floor_blocked(self):
        result = check_sale("Malibu", 1)
        assert result["status"] == "violation"

    def test_malibu_at_floor_permitted(self):
        result = check_sale("Malibu", 25000)
        assert result["status"] == "permitted"

    def test_unknown_model_defaults_to_zero_floor(self):
        result = check_sale("Ferrari", 0)
        assert result["status"] == "permitted"

    def test_unknown_model_with_price_above_zero_permitted(self):
        result = check_sale("Ferrari", 100)
        assert result["status"] == "permitted"

    def test_counterexample_contains_price(self):
        for model in ("Tahoe", "Malibu"):
            result = check_sale(model, 1)
            assert result["status"] == "violation"
            assert "witness" in result
            assert "price" in result["witness"]

    def test_negative_price_handled(self):
        result = check_sale("Tahoe", -1)
        assert result["status"] == "violation"

    def test_zero_price_on_known_model_blocked(self):
        result = check_sale("Tahoe", 0)
        assert result["status"] == "violation"

    @pytest.mark.parametrize("model,price", [
        ("Tahoe", 45000),
        ("Tahoe", 100000),
        ("Malibu", 25000),
        ("Malibu", 99999),
        ("Ferrari", 0),
        ("Ferrari", 1),
        ("NonExistent", 0),
    ])
    def test_all_permitted_cases(self, model, price):
        result = check_sale(model, price)
        assert result["status"] == "permitted"

    @pytest.mark.parametrize("model,price", [
        ("Tahoe", 44999),
        ("Tahoe", 1),
        ("Malibu", 24999),
        ("Malibu", 0),
    ])
    def test_all_blocked_cases(self, model, price):
        result = check_sale(model, price)
        assert result["status"] == "violation"


class TestLeanVerification:
    def _lean(self, path, expect_fail=False):
        result = subprocess.run(
            ["lean", str(path)],
            capture_output=True, text=True,
            timeout=120,
        )
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if expect_fail:
            assert result.returncode != 0, (
                f"Lean should have failed but succeeded:\n{result.stdout}"
            )
        else:
            assert result.returncode == 0, (
                f"Lean verification failed:\n{result.stderr}"
            )
        return result

    def test_lean_theorem_compiles(self):
        self._lean(REPO_ROOT / "Lean" / "Verify.lean")

    def test_lean_policy_compiles(self):
        self._lean(REPO_ROOT / "Lean" / "Policy.lean")

    def test_lean_rejects_invalid_price(self):
        self._lean(REPO_ROOT / "Lean" / "Invalid.lean", expect_fail=True)
