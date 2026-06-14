import json

import pytest

from orchestrator import evaluate_tool_call
from verifier.verifier import Verifier


@pytest.fixture
def verifier():
    return Verifier()


class TestIntegrationTahoe:
    def test_blocks_1_dollar_tahoe(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "blocked"

    def test_blocks_below_floor(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 44999}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "blocked"

    def test_permits_at_floor(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 45000}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "permitted"

    def test_permits_above_floor(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 50000}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "permitted"

    def test_blocks_malibu_below_floor(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Malibu", "price": 1}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "blocked"

    def test_permits_malibu_at_floor(self, verifier):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Malibu", "price": 25000}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "permitted"


class TestIntegrationDeletion:
    def test_blocks_etc_passwd(self, verifier):
        raw = json.dumps({"tool": "delete_file", "args": {"target": "/etc/passwd"}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "blocked"

    def test_permits_project_temp(self, verifier):
        raw = json.dumps({"tool": "delete_file", "args": {"target": "/project/temp"}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "permitted"

    def test_permits_project_output(self, verifier):
        raw = json.dumps({"tool": "delete_file", "args": {"target": "/project/output"}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "permitted"

    def test_blocks_dotdot_escape(self, verifier):
        raw = json.dumps({"tool": "delete_file", "args": {"target": "/project/temp/../../etc/shadow"}})
        result = evaluate_tool_call(raw, verifier=verifier)
        assert result["decision"] == "blocked"
