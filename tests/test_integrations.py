import json
import pytest

from integrations.langchain import VeriToolInterceptor
from integrations.crewai import VeriToolGuard
from integrations.autogen import VeriToolMiddleware


class MockAgent:
    def __init__(self):
        self._tool_results = {}

    def _run_tool(self, tool_name: str, tool_input: dict, **kwargs):
        return {"result": "ok", "tool": tool_name}

    def register_tool_result(self, tool_name: str, result: dict):
        self._tool_results[tool_name] = result


class TestLangChainIntegration:
    def test_interceptor_checks_tool_call(self):
        interceptor = VeriToolInterceptor(MockAgent())
        result = interceptor.check_tool_call("confirm_sale", {"model": "Tahoe", "price": 1})
        assert result["decision"] == "blocked"

    def test_interceptor_permits_compliant(self):
        interceptor = VeriToolInterceptor(MockAgent())
        result = interceptor.check_tool_call("confirm_sale", {"model": "Tahoe", "price": 50000})
        assert result["decision"] == "permitted"

    def test_interceptor_wrap_returns_agent(self):
        agent = MockAgent()
        interceptor = VeriToolInterceptor(agent)
        wrapped = interceptor.wrap()
        assert wrapped is agent


class TestCrewAIIntegration:
    def test_guard_tahoe_violation(self):
        guard = VeriToolGuard(None)
        result = guard.guard("sales_agent", "confirm_sale", {"model": "Tahoe", "price": 1})
        assert result["status"] == "blocked"

    def test_guard_tahoe_permitted(self):
        guard = VeriToolGuard(None)
        result = guard.guard("sales_agent", "confirm_sale", {"model": "Tahoe", "price": 50000})
        assert result["status"] == "permitted"

    def test_guard_deletion_violation(self):
        guard = VeriToolGuard(None)
        result = guard.guard("devops_agent", "delete_file", {"target": "/etc/passwd"})
        assert result["status"] == "blocked"

    def test_guard_deletion_permitted(self):
        guard = VeriToolGuard(None)
        result = guard.guard("devops_agent", "delete_file", {"target": "/project/temp"})
        assert result["status"] == "permitted"

    def test_coordination_state_empty(self):
        guard = VeriToolGuard(None)
        assert guard.get_coordination_state() == {}


class TestAutoGenIntegration:
    def test_middleware_state(self):
        agent = MockAgent()
        middleware = VeriToolMiddleware(agent)
        state = middleware.get_state()
        assert "policies" in state

    def test_middleware_with_coordination(self):
        from verifier.coordination_policy import CoordinationPolicySpec
        spec = CoordinationPolicySpec(
            name="test_coord",
            agents=["a", "b"],
            invariants=[],
        )
        middleware = VeriToolMiddleware(MockAgent())
        middleware.with_coordination(spec)
        state = middleware.get_state()
        assert "coordination" in state

    def test_middleware_intercept_wraps_function(self):
        middleware = VeriToolMiddleware(MockAgent())
        def dummy(sender, msg):
            return msg
        wrapped = middleware.intercept(dummy)
        result = wrapped(None, {"content": "hello"})
        assert result == {"content": "hello"}

    def test_middleware_blocks_tool_call(self):
        middleware = VeriToolMiddleware(MockAgent())
        def dummy(sender, msg):
            return msg
        wrapped = middleware.intercept(dummy)
        message = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "confirm_sale",
                        "arguments": json.dumps({"model": "Tahoe", "price": 1}),
                    },
                }
            ]
        }
        result = wrapped(None, message)
        assert "blocked" in result.get("content", "").lower()

    def test_middleware_permits_valid_call(self):
        middleware = VeriToolMiddleware(MockAgent())
        def dummy(sender, msg):
            return msg
        wrapped = middleware.intercept(dummy)
        message = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "confirm_sale",
                        "arguments": json.dumps({"model": "Tahoe", "price": 50000}),
                    },
                }
            ]
        }
        result = wrapped(None, message)
        assert result == message
