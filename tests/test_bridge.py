from z3 import IntSort, StringSort, BoolSort

from bridge.policy_spec import NatType, StringType, BoolType, FinsetType, BridgeError
from bridge.z3_encoder import _z3_sort
from bridge import TAHOE_SPEC, DELETION_SPEC, bridge_check
from verifier.tahoe_policy import check_sale as manual_tahoe
from verifier.deletion_policy import check_deletion as manual_deletion


class TestTypeMapping:
    def test_lean_nat_to_z3_int(self):
        assert _z3_sort(NatType) == IntSort()

    def test_lean_string_to_z3_string_sort(self):
        assert _z3_sort(StringType) == StringSort()

    def test_lean_bool_to_z3_bool(self):
        assert _z3_sort(BoolType) == BoolSort()

    def test_lean_finset_of_string(self):
        result = _z3_sort(FinsetType(StringType))
        assert result == StringSort()

    def test_lean_finset_of_nat(self):
        result = _z3_sort(FinsetType(NatType))
        assert result == IntSort()


class TestBridgeTahoe:
    def test_bridge_tahoe_invalid_price_sat(self):
        result = bridge_check("tahoe", {"model": "Tahoe", "price": 1})
        assert result["status"] == "violation"

    def test_bridge_tahoe_valid_price_unsat(self):
        result = bridge_check("tahoe", {"model": "Tahoe", "price": 45000})
        assert result["status"] == "permitted"

    def test_bridge_tahoe_high_price_unsat(self):
        result = bridge_check("tahoe", {"model": "Tahoe", "price": 100000})
        assert result["status"] == "permitted"

    def test_bridge_tahoe_malibu_invalid(self):
        result = bridge_check("tahoe", {"model": "Malibu", "price": 1})
        assert result["status"] == "violation"

    def test_bridge_tahoe_malibu_valid(self):
        result = bridge_check("tahoe", {"model": "Malibu", "price": 25000})
        assert result["status"] == "permitted"


class TestBridgeDeletion:
    def test_bridge_deletion_out_of_scope_sat(self):
        result = bridge_check("deletion", {"target": "/etc/passwd"})
        assert result["status"] == "violation"

    def test_bridge_deletion_in_scope_unsat(self):
        result = bridge_check("deletion", {"target": "/project/temp"})
        assert result["status"] == "permitted"

    def test_bridge_deletion_second_allowed(self):
        result = bridge_check("deletion", {"target": "/project/output"})
        assert result["status"] == "permitted"

    def test_bridge_deletion_dotdot_escape(self):
        result = bridge_check("deletion", {"target": "/project/temp/../../etc/shadow"})
        assert result["status"] == "violation"


class TestBridgeMatchesManual:
    def test_matches_manual_tahoe_valid(self):
        b = bridge_check("tahoe", {"model": "Tahoe", "price": 50000})
        m = manual_tahoe(model="Tahoe", price=50000)
        assert b["status"] == m["status"]

    def test_matches_manual_tahoe_invalid(self):
        b = bridge_check("tahoe", {"model": "Tahoe", "price": 1})
        m = manual_tahoe(model="Tahoe", price=1)
        assert b["status"] == m["status"]

    def test_matches_manual_deletion_valid(self):
        b = bridge_check("deletion", {"target": "/project/temp"})
        m = manual_deletion(target="/project/temp")
        assert b["status"] == m["status"]

    def test_matches_manual_deletion_invalid(self):
        b = bridge_check("deletion", {"target": "/etc/passwd"})
        m = manual_deletion(target="/etc/passwd")
        assert b["status"] == m["status"]

    def test_bridge_unknown_policy_returns_error(self):
        result = bridge_check("nonexistent", {})
        assert result["status"] == "error"
