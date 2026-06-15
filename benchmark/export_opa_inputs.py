"""Export benchmark traces as OPA input JSON files, one per action.

Usage:
    python benchmark/export_opa_inputs.py

Produces: benchmark/opa_inputs/<scenario>/<case>/action_N.json
"""

import json
from pathlib import Path
from benchmark.traces import scenarios

OUT = Path("benchmark/opa_inputs")
OUT.mkdir(exist_ok=True)

for sc in scenarios:
    sc_dir = OUT / sc["name"]
    sc_dir.mkdir(exist_ok=True)
    for case in sc["cases"]:
        case_dir = sc_dir / case["name"]
        case_dir.mkdir(exist_ok=True)
        for i, (agent, tool, action_type, kwargs) in enumerate(case["trace"]):
            inp = {"agent": agent, "tool": tool, "action": action_type, "kwargs": kwargs}
            (case_dir / f"action_{i}.json").write_text(json.dumps(inp, indent=2))

print(f"Wrote OPA inputs to {OUT}")
