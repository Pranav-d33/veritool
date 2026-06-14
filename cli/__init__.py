import argparse
import json
import sys

from cli.auto_generator import AutoGenerator
from cli.round_trip import round_trip_verify


def main():
    parser = argparse.ArgumentParser(
        prog="veritool",
        description="VeriTool — Formal verification framework for LLM tool-calling",
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Start verifier with specified policies")
    p_run.add_argument("policies", nargs="+", help="Policy names or YAML files")

    p_check = sub.add_parser("check", help="One-shot check a tool call")
    p_check.add_argument("tool_call", help="JSON string or file path")

    p_create = sub.add_parser("create", help="Generate policy from natural language")
    p_create.add_argument("description", help="Policy description in plain English")

    p_test = sub.add_parser("test", help="Run policy test suite")
    p_test.add_argument("policy", nargs="?", help="Policy name (omit for all)")

    p_status = sub.add_parser("status", help="Show runtime status and metrics")
    p_hot = sub.add_parser("hot-reload", help="Deploy policy without restart")
    p_hot.add_argument("policy_file", help="Path to policy YAML file")
    p_rollback = sub.add_parser("rollback", help="Revert to previous policy version")
    p_rollback.add_argument("version", help="Version to rollback to")

    p_dashboard = sub.add_parser("dashboard", help="Launch monitoring dashboard")
    p_dashboard.add_argument("--port", type=int, default=8501)

    p_verify = sub.add_parser("verify", help="CI/CD — run all checks before deploy")
    p_wrap = sub.add_parser("wrap", help="Auto-wrap a supported framework")
    p_wrap.add_argument("framework", choices=["langchain", "crewai", "autogen"])

    args = parser.parse_args()

    if args.command == "create":
        _cmd_create(args.description)
    elif args.command == "check":
        _cmd_check(args.tool_call)
    elif args.command == "test":
        _cmd_test(args.policy)
    elif args.command == "run":
        _cmd_run(args.policies)
    elif args.command == "status":
        _cmd_status()
    elif args.command == "hot-reload":
        _cmd_hot_reload(args.policy_file)
    elif args.command == "rollback":
        _cmd_rollback(args.version)
    elif args.command == "dashboard":
        _cmd_dashboard(args.port)
    elif args.command == "verify":
        _cmd_verify()
    elif args.command == "wrap":
        _cmd_wrap(args.framework)
    else:
        parser.print_help()
        sys.exit(1)


def _cmd_create(description: str):
    gen = AutoGenerator()
    result = gen.generate(description)
    if result["status"] == "ok":
        print(f"  Policy '{result['policy_name']}' created")
        for artifact in result["artifacts"]:
            print(f"  ✓ Generated {artifact}")
        rtv = round_trip_verify(result["policy_name"], result["spec"])
        if rtv["passed"]:
            print(f"  ✓ Round-trip verification: PASSED")
            if rtv.get("details"):
                for d in rtv["details"]:
                    print(f"    → {d}")
        else:
            print(f"  ✗ Round-trip verification: FAILED — {rtv.get('error', '')}")
    else:
        print(f"  ✗ Error: {result.get('error', 'Generation failed')}")
        sys.exit(1)


def _cmd_check(tool_call: str):
    try:
        raw = json.loads(tool_call)
    except json.JSONDecodeError:
        try:
            with open(tool_call) as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("  ✗ Error: Provide valid JSON string or path to JSON file")
            sys.exit(1)

    from orchestrator import evaluate_tool_call
    result = evaluate_tool_call(json.dumps(raw))
    print(json.dumps(result, indent=2))


def _cmd_test(policy: str | None):
    import subprocess, sys as _sys
    cmd = [_sys.executable, "-m", "pytest", "tests/", "-v"]
    if policy:
        test_file = f"tests/test_{policy}.py"
        cmd = [_sys.executable, "-m", "pytest", test_file, "-v"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        _sys.exit(result.returncode)


def _cmd_run(policies: list[str]):
    from verifier.verifier import Verifier
    v = Verifier()
    print(f"  Verifier running with {len(policies)} policy(ies): {', '.join(policies)}")
    for p in policies:
        if p not in v._policies and p != "all":
            print(f"  ⚠ Policy '{p}' not registered")
    print(f"  Listening for tool calls...")


def _cmd_status():
    from pathlib import Path
    from policy_store.store import PolicyStore
    store = PolicyStore(Path("policy_store"))
    store.load()
    print(f"  Policy Store: {'healthy' if store.policies else 'empty'}")
    print(f"  Active policies: {len(store.policies)}")
    for name in store.policies:
        print(f"    - {name}")
    from config import POLICY_ROUTES
    print(f"  Routes: {len(POLICY_ROUTES)}")
    for tool, policy in POLICY_ROUTES.items():
        print(f"    {tool} → {policy}")


def _cmd_hot_reload(policy_file: str):
    from pathlib import Path
    from policy_store.store import PolicyStore
    store = PolicyStore(Path("policy_store"))
    store.hot_reload(Path(policy_file))
    print(f"  ✓ Hot-reload complete: {policy_file}")


def _cmd_rollback(version: str):
    from pathlib import Path
    from policy_store.store import PolicyStore
    store = PolicyStore(Path("policy_store"))
    store.rollback(version)
    print(f"  ✓ Rolled back to {version}")


def _cmd_dashboard(port: int):
    print(f"  Launching dashboard on port {port}...")
    print(f"  Run: streamlit run dashboard/app.py --server.port={port}")


def _cmd_verify():
    import subprocess, sys as _sys
    print("  Running verification checks...")
    r1 = subprocess.run([_sys.executable, "-m", "pytest", "tests/", "-x", "-q"], capture_output=True, text=True)
    print(r1.stdout)
    if r1.returncode != 0:
        print("  ✗ Tests failed")
        print(r1.stderr)
        _sys.exit(1)
    r2 = subprocess.run(["lean", "Lean/Policy.lean"], capture_output=True, text=True)
    if r2.returncode == 0:
        print("  ✓ Lean theorem compiles")
    else:
        print("  ✗ Lean theorem failed")
        print(r2.stderr)
        _sys.exit(1)
    print("  ✓ All checks passed")


def _cmd_wrap(framework: str):
    print(f"  Wrapping {framework}...")
    print(f"  Import veritool.integrations.{framework} and apply middleware")
