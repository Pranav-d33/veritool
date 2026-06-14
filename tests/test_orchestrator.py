import json
from unittest.mock import Mock

import pytest

from orchestrator import evaluate_tool_call, parse_tool_call, ParseError
from verifier.verifier import Verifier


class TestParseToolCall:
    def test_parse_valid_tool_call(self):
        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1}})
        result = parse_tool_call(raw)
        assert result["tool"] == "confirm_sale"
        assert result["args"]["model"] == "Tahoe"
        assert result["args"]["price"] == 1

    def test_parse_malformed_json(self):
        with pytest.raises(ParseError, match="Invalid JSON"):
            parse_tool_call("{bad json}")

    def test_parse_missing_tool(self):
        raw = json.dumps({"args": {}})
        with pytest.raises(ParseError, match="Missing 'tool'"):
            parse_tool_call(raw)

    def test_parse_missing_args(self):
        raw = json.dumps({"tool": "confirm_sale"})
        with pytest.raises(ParseError, match="Missing 'args'"):
            parse_tool_call(raw)

    def test_parse_args_not_dict(self):
        raw = json.dumps({"tool": "confirm_sale", "args": "not a dict"})
        with pytest.raises(ParseError, match="'args' must be a dict"):
            parse_tool_call(raw)


class TestOrchestrator:
    def test_orchestrator_blocks_violation(self):
        mock_verifier = Mock(spec=Verifier)
        mock_verifier.check.return_value = {"decision": "blocked", "reason": {"price": 1}}

        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1}})
        result = evaluate_tool_call(raw, verifier=mock_verifier)

        assert result["decision"] == "blocked"
        assert result["tool"] == "confirm_sale"

    def test_orchestrator_permits_compliant(self):
        mock_verifier = Mock(spec=Verifier)
        mock_verifier.check.return_value = {"decision": "permitted", "reason": {}}

        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 50000}})
        result = evaluate_tool_call(raw, verifier=mock_verifier)

        assert result["decision"] == "permitted"

    def test_orchestrator_returns_counterexample(self):
        mock_verifier = Mock(spec=Verifier)
        mock_verifier.check.return_value = {"decision": "blocked", "reason": {"price": 1}}

        raw = json.dumps({"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1}})
        result = evaluate_tool_call(raw, verifier=mock_verifier)

        assert result["decision"] == "blocked"

    def test_orchestrator_handles_malformed_json(self):
        result = evaluate_tool_call("{bad}")
        assert result["decision"] == "error"
        assert "Invalid JSON" in result["reason"]

    def test_orchestrator_handles_unknown_tool(self):
        raw = json.dumps({"tool": "unknown_tool", "args": {}})
        result = evaluate_tool_call(raw)
        assert result["reason"] == f"No policy for tool: unknown_tool"
