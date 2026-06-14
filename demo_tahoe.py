#!/usr/bin/env python3
"""
Standalone demo: Tahoe price floor policy.

Runs two scenarios:
1. Violation: Tahoe at $1 (blocked by Z3)
2. Compliant: Tahoe at $50000 (permitted by Z3)
"""

import json
import sys

from orchestrator import evaluate_tool_call


def main():
    scenarios = [
        (
            "❌ Violation: Tahoe at $1",
            {"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1, "customer": "Bob"}},
            "blocked",
        ),
        (
            "✅ Compliant: Tahoe at $50000",
            {"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 50000, "customer": "Alice"}},
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
