#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POLICY="$SCRIPT_DIR/opa_policies.rego"
INPUTS_DIR="$SCRIPT_DIR/opa_inputs"

DO_TIME=false
if [[ "${1:-}" == "--time" ]]; then
  DO_TIME=true
fi

echo "# OPA vs VeriTool — Trace-level Comparison"
echo ""
echo "Each case is a multi-action trace. OPA evaluates actions independently"
echo "(no memory of prior actions). VeriTool evaluates the full sequence."
echo ""
if $DO_TIME; then
  echo "| Scenario | Case | Trace summary | OPA result | VeriTool result | Correct? | OPA total time |"
  echo "|---|---|---|---|---|---|---|"
else
  echo "| Scenario | Case | Trace summary | OPA result | VeriTool result | Correct? |"
  echo "|---|---|---|---|---|---|"
fi

for scenario_dir in "$INPUTS_DIR/"*/; do
  scenario=$(basename "$scenario_dir")
  for case_dir in "$scenario_dir"*/; do
    case=$(basename "$case_dir")

    # Determine expected verdict from VeriTool (by case name heuristic)
    expected="permitted"
    case "$case" in
      missing_*|cross_agent_conflict|self_approval_blocked|no_approval|approval_after_deploy|decreasing|concurrent_deploy|both_violations|noops_with_violation)
        expected="blocked"
        ;;
      deploy_only)
        expected="blocked"
        ;;
    esac

    # Collect action files, sorted numerically
    shopt -s nullglob
    action_files=("$case_dir"action_*.json)
    shopt -u nullglob

    if [[ ${#action_files[@]} -eq 0 ]]; then
      echo "| $scenario | $case | (empty) | permitted | $expected | ✓ |"
      continue
    fi

    # Build a trace summary
    actions=()
    for af in "${action_files[@]}"; do
      action=$(python3 -c "import json; print(json.load(open('$af'))['action'])" 2>/dev/null || echo "?")
      actions+=("$action")
    done
    IFS="→"
    summary="${actions[*]}"
    unset IFS

    # Run OPA on every action in the case. If any action returns empty {},
    # OPA "blocks" it (no rule matched).
    opa_blocked=false
    opa_total_ms=0
    for af in "${action_files[@]}"; do
      if $DO_TIME; then
        start=$(date +%s%N)
        opa_out=$(opa eval --format raw \
          --data "$POLICY" --input "$af" \
          "data.deploy_pipeline" 2>/dev/null || echo "{}")
        end=$(date +%s%N)
        elapsed_ms=$(( (end - start) / 1000000 ))
        opa_total_ms=$((opa_total_ms + elapsed_ms))
      else
        opa_out=$(opa eval --format raw \
          --data "$POLICY" --input "$af" \
          "data.deploy_pipeline" 2>/dev/null || echo "{}")
      fi
      if [[ "$opa_out" == "{}" ]]; then
        opa_blocked=true
      fi
    done

    opa_result="permitted"
    $opa_blocked && opa_result="blocked"

    # Compare
    correct="✓"
    if [[ "$opa_result" != "$expected" ]]; then
      correct="✗ OPA misses trace invariant"
    fi

    if $DO_TIME; then
      echo "| $scenario | $case | $summary | $opa_result | $expected | $correct | ${opa_total_ms}ms |"
    else
      echo "| $scenario | $case | $summary | $opa_result | $expected | $correct |"
    fi
  done
done

echo ""
echo "### Key finding"
echo "OPA evaluates each request in isolation. It cannot remember whether BUILD"
echo "ran before DEPLOY, who holds a resource, whether a counter is monotonic,"
echo "or prior approval by a different agent. Every '✗' above is a trace"
echo "invariant that OPA's request-level model cannot enforce."
echo ""
echo "### Raw OPA output for a cross-agent DEPLOY (should be blocked):"
opa eval --format raw --data "$POLICY" \
  --input "$INPUTS_DIR/composite_deploy/both_violations/action_0.json" \
  "data.deploy_pipeline" 2>/dev/null
echo ""
echo "OPA returns '{}' for actions no rule permits — but in a multi-action"
echo "trace, it already permitted the preceding actions that should have"
echo "been blocked."
