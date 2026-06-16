"""Generate benchmark graphs from benchmark_data.json."""
import json, sys, itertools
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

DATA = Path("benchmark/benchmark_data.json")
OUT = Path("benchmark/graphs")

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 9,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

COLORS = {
    "OrderingInvariant": "#2196F3",
    "ExclusiveAccessInvariant": "#FF5722",
    "ApprovalInvariant": "#4CAF50",
    "MonotonicInvariant": "#9C27B0",
    "Composite (all 4)": "#FF9800",
}
LINESTYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]

def load():
    return json.loads(DATA.read_text())


def fig1_scalability(data):
    """Trace size vs latency for all 5 invariant types (log-log)."""
    sc = data["scalability"]
    fig, ax = plt.subplots(figsize=(8, 5))

    for i, (name, vals) in enumerate(sc.items()):
        sizes = vals["sizes"]
        means = vals["mean_us"]
        stdevs = vals["stdev_us"]
        color = COLORS.get(name, f"C{i}")
        ax.errorbar(sizes[1:], means[1:], yerr=stdevs[1:],
                     label=name, color=color, marker="o", capsize=3,
                     linestyle=LINESTYLES[i % len(LINESTYLES)],
                     markersize=4, linewidth=1.5)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Trace size (entries)")
    ax.set_ylabel("Latency (μs)")
    ax.set_title("VeriTool Scalability: Latency vs Trace Size")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xlim(0.9, 200_000)
    ax.set_ylim(3, 200_000)
    fig.tight_layout()
    path = OUT / "scalability.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig2_latency_comparison(data):
    """3-way latency comparison bar chart."""
    ad = data["agentdojo_banking_3way"]
    ob = data["original_benchmark_3way"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

    # Left: AgentDojo banking latency
    sys_names = [s.replace("OPA ", "OPA\n") for s in ad["system"]]
    lats = ad["avg_latency_ms"]
    bars1 = ax1.bar(sys_names, lats, color=["#4CAF50", "#FF5722", "#2196F3"],
                     width=0.5, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars1, lats):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"{val:.2f}ms", ha="center", va="bottom", fontsize=9)
    ax1.set_ylabel("Avg latency per trace (ms)")
    ax1.set_title("AgentDojo Banking (39 traces)")
    ax1.grid(axis="y", alpha=0.3)

    # Right: Original benchmark latency
    sys_names2 = [s.replace("OPA ", "OPA\n") for s in ob["system"]]
    lats2 = ob["avg_latency_ms"]
    bars2 = ax2.bar(sys_names2, lats2, color=["#FF5722", "#2196F3", "#4CAF50"],
                     width=0.5, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars2, lats2):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"{val:.2f}ms", ha="center", va="bottom", fontsize=9)
    ax2.set_ylabel("Avg latency per action (ms)")
    ax2.set_title("Original Benchmark (24 cases)")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("VeriTool vs OPA: Latency Comparison", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    path = OUT / "latency_comparison.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig3_detection_rate(data):
    """Detection rate: safe OK and violations blocked."""
    ad = data["agentdojo_banking_3way"]
    ob = data["original_benchmark_3way"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

    # Left: AgentDojo banking
    x = np.arange(len(ad["system"]))
    w = 0.3
    safe_pct = [ok / ad["safe_total"] * 100 for ok in ad["safe_ok"]]
    viol_pct = [b / ad["violations_total"] * 100 for b in ad["violations_blocked"]]
    ax1.bar(x - w / 2, safe_pct, w, label="Safe OK", color="#4CAF50", edgecolor="white")
    ax1.bar(x + w / 2, viol_pct, w, label="Violations blocked", color="#FF5722", edgecolor="white")
    ax1.set_xticks(x)
    ax1.set_xticklabels(["VeriTool", "OPA\nstateless", "OPA\n+history"])
    ax1.set_ylabel("Percent (%)")
    ax1.set_title(f"AgentDojo Banking ({ad['safe_total']} safe, {ad['violations_total']} violations)")
    ax1.legend(frameon=True, fancybox=True)
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_ylim(0, 110)

    # Right: Original benchmark
    x2 = np.arange(len(ob["system"]))
    correct_pct = [c / ob["total"] * 100 for c in ob["correct"]]
    ax2.bar(x2, correct_pct, w * 1.5, color=["#FF5722", "#2196F3", "#4CAF50"],
            edgecolor="white")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(["OPA\nstateless", "OPA\n+history", "VeriTool"])
    ax2.set_ylabel("Correct rate (%)")
    ax2.set_title(f"Original Benchmark ({ob['total']} cases)")
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_ylim(0, 110)

    fig.suptitle("Detection Rate Comparison", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    path = OUT / "detection_rate.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig4_throughput(data):
    """Throughput by batch size."""
    tb = data["throughput_by_batch"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(tb["batch_size"], tb["actions_per_sec"], "o-", color="#2196F3",
            linewidth=2, markersize=6)
    ax.set_xscale("log")
    ax.set_xlabel("Batch size")
    ax.set_ylabel("Throughput (actions/sec)")
    ax.set_title("VeriTool Throughput vs Batch Size")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(tb["batch_size"])
    ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    for bs, tput in zip(tb["batch_size"], tb["actions_per_sec"]):
        ax.annotate(f"{tput:,}", (bs, tput), textcoords="offset points",
                     xytext=(0, 10), ha="center", fontsize=8)
    fig.tight_layout()
    path = OUT / "throughput.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig5_cross_domain(data):
    """Cross-domain throughput by suite."""
    cd = data["cross_domain_throughput"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

    # Left: traces per suite
    ax1.bar(cd["suites"], cd["n_traces"], color=["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"],
            width=0.5, edgecolor="white")
    ax1.set_ylabel("Number of traces")
    ax1.set_title("AgentDojo Traces by Suite")
    ax1.grid(axis="y", alpha=0.3)

    # Right: latency per suite
    ax2.bar(cd["suites"], [a * 1000 for a in cd["avg_ms"]],
            color=["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"],
            width=0.5, edgecolor="white")
    ax2.set_ylabel("Avg latency per tool call (μs)")
    ax2.set_title("Latency by Suite")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("Cross-Domain Benchmark (97 traces, 4 suites)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    path = OUT / "cross_domain.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig6_scalability_zoomed(data):
    """Sub-millisecond zoom: up to 100 entries."""
    sc = data["scalability"]
    fig, ax = plt.subplots(figsize=(8, 5))

    for i, (name, vals) in enumerate(sc.items()):
        sizes = vals["sizes"]
        means = vals["mean_us"]
        stdevs = vals["stdev_us"]
        color = COLORS.get(name, f"C{i}")
        ax.errorbar(sizes[:5], means[:5], yerr=stdevs[:5],
                     label=name, color=color, marker="o", capsize=3,
                     linestyle=LINESTYLES[i % len(LINESTYLES)],
                     markersize=5, linewidth=1.5)

    ax.set_xscale("log")
    ax.set_xlabel("Trace size (entries)")
    ax.set_ylabel("Latency (μs)")
    ax.set_title("Sub-millisecond Range: Trace Size 0–100")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(True, which="both", alpha=0.3)
    ax.axhline(y=1000, color="red", linestyle="--", alpha=0.4, label="1ms threshold")
    ax.set_ylim(0, 1200)
    fig.tight_layout()
    path = OUT / "scalability_zoomed.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig7_throughput_comparison(data):
    """VeriTool vs OPA throughput bar chart."""
    ad = data["agentdojo_banking_3way"]
    fig, ax = plt.subplots(figsize=(6, 4))
    sys_names = ["VeriTool", "OPA\nstateless", "OPA\n+history"]
    tputs = ad["throughput_actions_per_sec"]
    colors = ["#4CAF50", "#FF5722", "#2196F3"]
    bars = ax.bar(sys_names, tputs, color=colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, tputs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 50,
                f"{val:,}/s", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Actions per second")
    ax.set_title("Throughput Comparison")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "throughput_comparison.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig8_false_positives(data):
    """False positive rate comparison."""
    ad = data["agentdojo_banking_3way"]
    fig, ax = plt.subplots(figsize=(6, 4))
    sys_names = ["VeriTool", "OPA\nstateless", "OPA\n+history"]
    fp_ct = ad["false_positives"]
    fp_pct = [c / ad["safe_total"] * 100 for c in fp_ct]
    colors = ["#4CAF50", "#FF5722", "#2196F3"]
    bars = ax.bar(sys_names, fp_pct, color=colors, width=0.5, edgecolor="white")
    for bar, val, ct in zip(bars, fp_pct, fp_ct):
        label = f"{val:.0f}% ({ct}/{ad['safe_total']})"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                label, ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("False positive rate (%)")
    ax.set_title("Safe Traces Falsely Blocked")
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, 100)
    fig.tight_layout()
    path = OUT / "false_positives.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig9_taubench_detection(data):
    """TAU-bench 3-way detection for all 4 invariants."""
    td = data["taubench_detection"]
    inv_names = td["invariants"]
    sys_names = td["systems"]

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    colors = ["#4CAF50", "#FF5722", "#2196F3"]
    markers = ["o", "s", "D"]
    x = np.arange(len(sys_names))
    w = 0.25

    for idx, inv in enumerate(inv_names):
        ax = axes[idx // 2][idx % 2]
        safe_pct = [ok / td["safe_total"][idx] * 100 for ok in td["safe_ok"][idx]]
        viol_pct = [b / td["violations_total"][idx] * 100 for b in td["violations_blocked"][idx]]
        fp_pct = [fp / td["safe_total"][idx] * 100 for fp in td["false_positives"][idx]]

        ax.bar(x - w, safe_pct, w, label="Safe OK", color="#4CAF50", alpha=0.8, edgecolor="white")
        ax.bar(x, viol_pct, w, label="Viol blocked", color="#2196F3", alpha=0.8, edgecolor="white")
        ax.bar(x + w, fp_pct, w, label="False pos", color="#FF5722", alpha=0.8, edgecolor="white")

        ax.set_xticks(x)
        ax.set_xticklabels(["VeriTool", "OPA\nstateless", "OPA\n+history"], fontsize=8)
        ax.set_ylim(0, 110)
        ax.set_ylabel("Percent (%)")
        ax.set_title(f"{inv.title()}", fontsize=12)
        ax.grid(axis="y", alpha=0.3)
        if idx == 0:
            ax.legend(frameon=True, fancybox=True, fontsize=8)

    fig.suptitle("TAU-bench Detection: VeriTool vs OPA", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path = OUT / "taubench_detection.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig10_taubench_latency(data):
    """TAU-bench latency comparison bar chart."""
    td = data["taubench_detection"]
    inv_names = td["invariants"]
    sys_names = td["systems"]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(inv_names))
    w = 0.25
    colors = ["#4CAF50", "#FF5722", "#2196F3"]

    for i, sys_name in enumerate(sys_names):
        lats = [td["avg_latency_ms"][j][i] for j in range(len(inv_names))]
        offset = (i - 1) * w
        bars = ax.bar(x + offset, lats, w, label=sys_name, color=colors[i], alpha=0.8, edgecolor="white")
        for bar, val in zip(bars, lats):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels([n.title() for n in inv_names])
    ax.set_ylabel("Avg latency per action (ms)")
    ax.set_title("TAU-bench: Latency by Invariant Type")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "taubench_latency.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig11_taubench_throughput(data):
    """TAU-bench throughput bar chart."""
    tt = data["taubench_throughput"]
    inv_names = tt["invariants"]

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = ["#2196F3", "#FF5722", "#4CAF50", "#9C27B0"]
    x = np.arange(len(inv_names))

    bars = ax.bar(x, tt["throughput_actions_per_sec"], color=colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, tt["throughput_actions_per_sec"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                f"{val:,}/s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([n.title() for n in inv_names])
    ax.set_ylabel("Throughput (actions/sec)")
    ax.set_title("TAU-bench: Throughput by Invariant Type")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "taubench_throughput.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig12_ablation_incremental_vs_batch(data):
    """Ablation 1: Incremental vs batch encoding latency."""
    a1 = data["ablation1_incremental_vs_batch"]
    inv_names = list(a1.keys())

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(inv_names))
    w = 0.3

    inc_vals = [a1[i]["inc_total_us"] for i in inv_names]
    batch_vals = [a1[i]["batch_total_us"] for i in inv_names]

    ax.bar(x - w/2, inc_vals, w, label="Incremental (per-action)", color="#2196F3", alpha=0.8, edgecolor="white")
    ax.bar(x + w/2, batch_vals, w, label="Batch (one-shot)", color="#FF5722", alpha=0.8, edgecolor="white")

    for i, (iv, bv) in enumerate(zip(inc_vals, batch_vals)):
        speedup = bv / max(iv, 1)
        ax.text(i, max(iv, bv) + 20, f"{speedup:.1f}x", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([n.title() for n in inv_names])
    ax.set_ylabel("Avg latency per trace (μs)")
    ax.set_title("Ablation 1: Incremental vs Batch Encoding")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "ablation_incremental_vs_batch.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig13_ablation_solver_swap(data):
    """Ablation 2: Z3 vs CVC5 latency comparison."""
    a2 = data["ablation2_solver_swap"]
    inv_names = list(a2.keys())

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(inv_names))
    w = 0.3

    z3_vals = [a2[i]["z3_avg_us"] for i in inv_names]
    cvc5_vals = [a2[i]["cvc5_avg_us"] for i in inv_names]

    ax.bar(x - w/2, z3_vals, w, label="Z3", color="#4CAF50", alpha=0.8, edgecolor="white")
    ax.bar(x + w/2, cvc5_vals, w, label="CVC5", color="#9C27B0", alpha=0.8, edgecolor="white")

    for i, (z, c) in enumerate(zip(z3_vals, cvc5_vals)):
        ratio = c / max(z, 1)
        ax.text(i, max(z, c) + 30, f"{ratio:.1f}x", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([n.title() for n in inv_names])
    ax.set_ylabel("Avg latency per trace (μs)")
    ax.set_title("Ablation 2: Z3 vs CVC5 Solver")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(axis="y", alpha=0.3)

    # Add a text box noting ratio
    ratios = [f"{n}: {cvc5_vals[i]/max(z3_vals[i],1):.1f}x slower" for i, n in enumerate(inv_names)]
    ax.text(0.98, 0.95, "\n".join(ratios), transform=ax.transAxes, fontsize=8,
            verticalalignment="top", horizontalalignment="right",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5})

    fig.tight_layout()
    path = OUT / "ablation_solver_swap.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig14_ablation_cross_invariant(data):
    """Ablation 3: Individual vs combined overhead."""
    a3 = data["ablation3_cross_invariant"]
    inv_names = list(a3["individual"].keys())

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(inv_names))
    w = 0.3

    ind_vals = [a3["individual"][i]["avg_us"] for i in inv_names]
    comb_vals = [a3["combined"][i]["avg_us"] for i in inv_names]

    ax.bar(x - w/2, ind_vals, w, label="Individual", color="#2196F3", alpha=0.8, edgecolor="white")
    ax.bar(x + w/2, comb_vals, w, label="All 4 combined", color="#FF9800", alpha=0.8, edgecolor="white")

    for i, (ind, comb) in enumerate(zip(ind_vals, comb_vals)):
        ov = comb / max(ind, 1)
        ax.text(i, max(ind, comb) + 20, f"{ov:.1f}x", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([n.title() for n in inv_names])
    ax.set_ylabel("Avg latency per trace (μs)")
    ax.set_title("Ablation 3: Cross-Invariant Overhead")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "ablation_cross_invariant.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def fig15_ablation_trace_depth(data):
    """Ablation 4: Trace depth saturation curves."""
    a4 = data["ablation4_trace_depth"]
    colors = {"ordering": "#2196F3", "exclusive_access": "#FF5722", "approval": "#4CAF50", "monotonic": "#9C27B0"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    linestyles = ["-", "--", "-.", ":"]

    # Left: full range (log-log)
    for i, (inv, v) in enumerate(a4.items()):
        ax1.plot(v["sizes"], v["mean_us"], label=inv.title(),
                 color=colors.get(inv, f"C{i}"), marker="o", markersize=4,
                 linestyle=linestyles[i], linewidth=1.5)
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("Trace size (entries)")
    ax1.set_ylabel("Latency (μs)")
    ax1.set_title("Trace Depth Saturation (log-log)")
    ax1.legend(frameon=True, fancybox=True, fontsize=8)
    ax1.grid(True, which="both", alpha=0.3)

    # Right: zoomed to sub-100 entries
    for i, (inv, v) in enumerate(a4.items()):
        idx = [j for j, s in enumerate(v["sizes"]) if s <= 64]
        ax2.plot([v["sizes"][j] for j in idx], [v["mean_us"][j] for j in idx],
                label=inv.title(), color=colors.get(inv, f"C{i}"), marker="o", markersize=4,
                linestyle=linestyles[i], linewidth=1.5)
    ax2.set_xlabel("Trace size (entries)")
    ax2.set_ylabel("Latency (μs)")
    ax2.set_title("Trace Depth Saturation (≤64 entries)")
    ax2.legend(frameon=True, fancybox=True, fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=1000, color="red", linestyle="--", alpha=0.4, label="1ms")
    ax2.axhline(y=100, color="orange", linestyle="--", alpha=0.4, label="100μs")
    ax2.legend(frameon=True, fancybox=True, fontsize=8)

    fig.suptitle("Ablation 4: Latency vs Trace Depth", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    path = OUT / "ablation_trace_depth.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def main():
    data = load()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Generating graphs...")
    fig1_scalability(data)
    fig2_latency_comparison(data)
    fig3_detection_rate(data)
    fig4_throughput(data)
    fig5_cross_domain(data)
    fig6_scalability_zoomed(data)
    fig7_throughput_comparison(data)
    fig8_false_positives(data)
    fig9_taubench_detection(data)
    fig10_taubench_latency(data)
    fig11_taubench_throughput(data)
    fig12_ablation_incremental_vs_batch(data)
    fig13_ablation_solver_swap(data)
    fig14_ablation_cross_invariant(data)
    fig15_ablation_trace_depth(data)
    print(f"\nAll graphs saved to {OUT.resolve()}/")
    print("Generated:")
    for p in sorted(OUT.glob("*.png")):
        print(f"  {p.name}")

if __name__ == "__main__":
    main()
