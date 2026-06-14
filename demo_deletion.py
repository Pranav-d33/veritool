#!/usr/bin/env python3
"""
Standalone demo: File deletion frame policy.

Runs two scenarios:
1. Violation: Delete /etc/passwd (blocked by Z3)
2. Compliant: Delete /project/temp/old.log (permitted by Z3)
"""

import json
import sys

from orchestrator import evaluate_tool_call


def main():
    scenarios = [
        (
            "❌ Violation: Delete /etc/passwd",
            {"tool": "delete_file", "args": {"target": "/etc/passwd"}},
            "blocked",
        ),
        (
            "✅ Compliant: Delete /project/temp/old.log",
            {"tool": "delete_file", "args": {"target": "/project/temp"}},
            "permitted",
        ),
    ]

    all_pass = True
    for label, tool_call, expected in scenarios:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        print(f"  Tool call: {json.dumps(tool_call)}")

        raw = json.dumps(tool_call)
        result = evaluate_tool_call(raw)
        decision = result["decision"]

        if decision == "blocked":
            print(f"  → BLOCKED (witness: {result.get('reason', {})})")
        elif decision == "permitted":
            print(f"  → PERMITTED")
        else:
            print(f"  → ERROR: {result.get('reason', 'unknown')}")

        if decision != expected:
            print(f"  ✗ FAIL: expected {expected}, got {decision}")
            all_pass = False
        else:
            print(f"  ✓ PASS")

    print(f"\n{'='*60}")
    print(f"  {'All scenarios passed!' if all_pass else 'Some scenarios failed!'}")
    print(f"{'='*60}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
