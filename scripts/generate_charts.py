import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Set publication style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300

output_dir = Path("/home/wes/projects/Capstone/visualizations")
output_dir.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# FIGURE 1: Token Consumption Comparison across 5-Stage Gauntlet
# -------------------------------------------------------------
stages = [
    "1. Structural\nNavigation",
    "2. Linear\nBlast Radius",
    "3. Divergent\nFan-Out",
    "4. Dynamic\nLens (Blind Spot)",
    "5. Fault\nTriangulation",
]

baseline_tokens = [6478, 6000, 7064, 4500, 14500]
substrate_tokens = [184.2, 1086, 942.5, 980, 26.8]
reduction_pcts = [97.2, 81.9, 86.7, 78.2, 99.8]

x = np.arange(len(stages))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 5.5))
rects1 = ax.bar(x - width/2, baseline_tokens, width, label='Baseline (Linear Scan / Full Context)', color='#ef4444', alpha=0.88, edgecolor='#b91c1c')
rects2 = ax.bar(x + width/2, substrate_tokens, width, label='Relational Substrate (B-Tree CTE)', color='#10b981', alpha=0.92, edgecolor='#047857')

ax.set_ylabel('Context Window Consumption (Tokens, Log Scale)', fontsize=11, fontweight='bold')
ax.set_title('Token Ingestion Comparison: Baseline vs. Relational Substrate (5-Stage Gauntlet)', fontsize=13, fontweight='bold', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(stages, fontsize=10)
ax.legend(frameon=True, facecolor='white', framealpha=0.95, loc='upper right')
ax.set_yscale('log')
ax.set_ylim(10, 40000)

# Add annotations
for i in range(len(stages)):
    # Percentage badge above green bar
    ax.annotate(f'-{reduction_pcts[i]:.1f}%\nTokens',
                xy=(x[i] + width/2, substrate_tokens[i]),
                xytext=(0, 8),
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=9, fontweight='bold', color='#065f46')

plt.tight_layout()
fig1_path = output_dir / "figure1_token_reduction_gauntlet.png"
plt.savefig(fig1_path)
plt.close()
print(f"Generated: {fig1_path}")

# -------------------------------------------------------------
# FIGURE 2: Execution Latency (Speedup Multipliers)
# -------------------------------------------------------------
benchmarks = [
    "Structural Path\nResolution",
    "Dynamic Lens\nReconciliation",
    "Fault Triangulation\n(24 Failing Tests)",
    "Fog-of-War Query\n(TTRPG Substrate)",
    "Prerequisite Feasibility\n(SQL EXCEPT)",
]

baseline_latencies_ms = [8.86, 4500.0, 30000.0, 2500.0, 2000.0]
substrate_latencies_ms = [0.171, 0.420, 7.251, 0.039, 0.015]
speedups = [f"{b/s:,.0f}x" for b, s in zip(baseline_latencies_ms, substrate_latencies_ms)]

y = np.arange(len(benchmarks))
height = 0.35

fig, ax = plt.subplots(figsize=(10, 5.5))
rects1 = ax.barh(y + height/2, baseline_latencies_ms, height, label='Baseline (Grep / LLM Inference)', color='#f59e0b', alpha=0.85, edgecolor='#d97706')
rects2 = ax.barh(y - height/2, substrate_latencies_ms, height, label='Relational Substrate (SQLite WAL CTE)', color='#3b82f6', alpha=0.9, edgecolor='#1d4ed8')

ax.set_xlabel('Execution Latency in Milliseconds (Log Scale)', fontsize=11, fontweight='bold')
ax.set_title('Query & Resolution Latency: Baseline vs. Relational Substrate', fontsize=13, fontweight='bold', pad=15)
ax.set_yticks(y)
ax.set_yticklabels(benchmarks, fontsize=10)
ax.set_xscale('log')
ax.set_xlim(0.005, 100000)
ax.legend(frameon=True, facecolor='white', framealpha=0.95, loc='lower right')

for i in range(len(benchmarks)):
    ax.annotate(f" {speedups[i]} faster",
                xy=(substrate_latencies_ms[i], y[i] - height/2),
                xytext=(6, -3),
                textcoords="offset points",
                ha='left', va='center',
                fontsize=9.5, fontweight='bold', color='#1e3a8a')

plt.tight_layout()
fig2_path = output_dir / "figure2_latency_speedup_comparison.png"
plt.savefig(fig2_path)
plt.close()
print(f"Generated: {fig2_path}")

# -------------------------------------------------------------
# FIGURE 3: Progressive Disclosure Breakdown (Exp 1 Incident Tree)
# -------------------------------------------------------------
labels = ['Hop 1:\nRoot Outage\n& Previews', 'Hop 2:\nSubsystem\n& Previews', 'Hop 3:\nTarget Culprit\nBody Ingested']
hop_tokens = [285, 310, 582]
cumulative_tokens = [285, 595, 1177]
baseline_flat_tokens = 15340

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={'width_ratios': [1.2, 1]})

# Stacked progression
ax1.bar(labels, hop_tokens, color=['#60a5fa', '#3b82f6', '#1d4ed8'], edgecolor='#1e3a8a', width=0.55)
ax1.set_ylabel('Tokens Ingested per Hop', fontsize=10, fontweight='bold')
ax1.set_title('Hyper-Web Progressive Traversal (Exp 1)', fontsize=11, fontweight='bold')
ax1.set_ylim(0, 800)

for idx, (t, c) in enumerate(zip(hop_tokens, cumulative_tokens)):
    ax1.annotate(f'{t} tokens\n(Cumul: {c})',
                 xy=(idx, t),
                 xytext=(0, 5),
                 textcoords="offset points",
                 ha='center', va='bottom', fontsize=8.5, fontweight='bold')

# Comparison donut / bar
categories = ['Substrate\n(3 Hops)', 'Baseline\n(Full Dump)']
totals = [1177, 15340]
bar_colors = ['#10b981', '#ef4444']
bars = ax2.bar(categories, totals, color=bar_colors, edgecolor=['#047857', '#b91c1c'], width=0.45)
ax2.set_ylabel('Total Tokens Consumed', fontsize=10, fontweight='bold')
ax2.set_title('Total Context Overhead (92.3% Reduction)', fontsize=11, fontweight='bold')

for bar in bars:
    height = bar.get_height()
    ax2.annotate(f'{height:,} tokens',
                 xy=(bar.get_x() + bar.get_width() / 2, height),
                 xytext=(0, 5),
                 textcoords="offset points",
                 ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
fig3_path = output_dir / "figure3_progressive_disclosure_exp1.png"
plt.savefig(fig3_path)
plt.close()
print(f"Generated: {fig3_path}")
