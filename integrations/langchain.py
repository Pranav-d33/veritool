import json
from typing import Any

from orchestrator import evaluate_tool_call


class VeriToolInterceptor:
    def __init__(self, agent: Any, policies: list[str] | None = None):
        self._agent = agent
        self._policies = policies or []
        self._original_tool_fn = None

    def wrap(self):
        if hasattr(self._agent, "_run_tool"):
            self._original_tool_fn = self._agent._run_tool
            self._agent._run_tool = self._intercepted_tool
        return self._agent

    def _intercepted_tool(self, tool_name: str, tool_input: dict, **kwargs) -> Any:
        raw = json.dumps({"tool": tool_name, "args": tool_input})
        result = evaluate_tool_call(raw)
        if result["decision"] == "blocked":
            raise PermissionError(
                f"VeriTool blocked {tool_name}: {result.get('reason', 'Policy violation')}"
            )
        if self._original_tool_fn:
            return self._original_tool_fn(tool_name, tool_input, **kwargs)
        raise RuntimeError("No tool function available")

    def check_tool_call(self, tool_name: str, tool_input: dict) -> dict:
        raw = json.dumps({"tool": tool_name, "args": tool_input})
        return evaluate_tool_call(raw)
