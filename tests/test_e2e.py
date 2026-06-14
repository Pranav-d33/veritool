import json

from orchestrator import evaluate_tool_call
from verifier.verifier import Verifier


class TestE2ETahoe:
    def test_tahoe_violation(self):
        tool_call = {"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1, "customer": "Bob"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "blocked"

    def test_tahoe_compliance(self):
        tool_call = {"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 50000, "customer": "Alice"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "permitted"

    def test_malibu_violation(self):
        tool_call = {"tool": "confirm_sale", "args": {"model": "Malibu", "price": 1, "customer": "Bob"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "blocked"

    def test_malibu_compliance(self):
        tool_call = {"tool": "confirm_sale", "args": {"model": "Malibu", "price": 25000, "customer": "Alice"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "permitted"


class TestE2EDeletion:
    def test_deletion_violation(self):
        tool_call = {"tool": "delete_file", "args": {"target": "/etc/passwd"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "blocked"

    def test_deletion_compliance(self):
        tool_call = {"tool": "delete_file", "args": {"target": "/project/temp"}}
        result = evaluate_tool_call(json.dumps(tool_call))
        assert result["decision"] == "permitted"


class TestE2EDemoScripts:
    def test_demo_tahoe_exits_zero(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "demo_tahoe.py"],
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout, file=sys.stderr)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        assert result.returncode == 0

    def test_demo_deletion_exits_zero(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "demo_deletion.py"],
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout, file=sys.stderr)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        assert result.returncode == 0

    def test_demo_tahoe_violation_blocked(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "demo_tahoe.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert "BLOCKED" in result.stdout
        assert "PERMITTED" in result.stdout
        assert "All scenarios passed" in result.stdout

    def test_demo_deletion_blocked(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "demo_deletion.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert "BLOCKED" in result.stdout
        assert "PERMITTED" in result.stdout
        assert "All scenarios passed" in result.stdout
