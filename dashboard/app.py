import json
import time
from pathlib import Path

import streamlit as st
import pandas as pd

st.set_page_config(page_title="VeriTool Dashboard", layout="wide")
st.title("🔒 VeriTool — Formal Verification Dashboard")

AUDIT_DIR = Path(__file__).resolve().parent.parent / "audit_logs"

st.sidebar.header("Controls")
refresh = st.sidebar.button("Refresh")
auto_refresh = st.sidebar.checkbox("Auto-refresh (5s)")
policy_filter = st.sidebar.selectbox("Decision Filter", ["All", "blocked", "permitted", "error"])

col1, col2, col3, col4 = st.columns(4)
stats_placeholder = {
    "total": 0, "blocked": 0, "permitted": 0, "errors": 0,
    "avg_z3_ms": 0.0, "block_rate": 0.0,
}

records: list[dict] = []
if AUDIT_DIR.exists():
    for log_file in sorted(AUDIT_DIR.glob("*.jsonl"), reverse=True)[:5]:
        for line in log_file.read_text().strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

if policy_filter != "All":
    records = [r for r in records if r.get("decision") == policy_filter]

df = pd.DataFrame(records) if records else pd.DataFrame()

with col1:
    st.metric("Total Checks", len(records))
with col2:
    blocked = sum(1 for r in records if r.get("decision") == "blocked")
    st.metric("Blocked", blocked)
with col3:
    permitted = sum(1 for r in records if r.get("decision") == "permitted")
    st.metric("Permitted", permitted)
with col4:
    block_rate = round(blocked / len(records) * 100, 1) if records else 0
    st.metric("Block Rate", f"{block_rate}%")

st.subheader("Live Audit Trail")
if not df.empty:
    cols = ["timestamp", "tool", "decision", "agent", "z3_check_ms", "lean_theorem"]
    cols = [c for c in cols if c in df.columns]
    display = df[cols].copy()
    if "timestamp" in display.columns:
        display["timestamp"] = pd.to_datetime(display["timestamp"], unit="s")
    st.dataframe(display.sort_values("timestamp", ascending=False), use_container_width=True)
else:
    st.info("No audit records found. Run the verifier to see results.")

st.subheader("Violation Heatmap")
if not df.empty and "tool" in df.columns and "decision" in df.columns:
    heatmap = df.groupby(["tool", "decision"]).size().unstack(fill_value=0)
    st.bar_chart(heatmap)
else:
    st.info("Insufficient data for heatmap.")

st.subheader("Recent Counterexamples")
blocked_records = [r for r in records if r.get("decision") == "blocked"]
for r in blocked_records[:5]:
    with st.expander(f"🚫 {r.get('tool', 'unknown')} — {r.get('reason', '')}"):
        st.json(r)

if auto_refresh:
    time.sleep(5)
    st.rerun()
