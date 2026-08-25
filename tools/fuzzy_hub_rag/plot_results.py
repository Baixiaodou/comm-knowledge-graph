#!/usr/bin/env python3
"""把 experiment_*.json 画成直观对比图（results/experiment_overview.png）。

4 面板：
(a) 5 策略最优配置对比（Part A 准确率 / 大问题召回 / hit@1 / hit@2 + LLM 调用数）
(b) S1 纯 TF-IDF 双池分流的阈值网格热力图（floor × margin → 准确率）
(c) S5 20 道模糊题逐题选点命中（hit1 / 仅 hit2 / miss / 判为 leaf）
(d) S5 大小点分类混淆矩阵（20 模糊 + 20 对照组）
"""
import json
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(HERE, "results")
latest = sorted(glob.glob(os.path.join(RESULT_DIR, "experiment_2*.json")))[-1]
with open(latest, encoding="utf-8") as f:
    exp = json.load(f)
best = exp["best"]
s5 = [r for r in exp["runs"] if r["strategy"] == "S5"][0]

STRATS = ["S1", "S2", "S3", "S4", "S5"]
NAMES = {"S1": "纯 TF-IDF 分流\n（0 次 LLM）", "S2": "TF-IDF + 临界\nLLM 确认",
         "S3": "同左 + 全量\nhub 选点", "S4": "同左 + top-5\n候选选点", "S5": "全 LLM 判定\n（胜出）"}
BAR_COLORS = {"a_acc": "#2E86AB", "b_hub_recall": "#F6AE2D", "b_hit1": "#7FB8D8", "b_hit2": "#9BC53D"}
METRIC_LABEL = {"a_acc": "大小点分类准确率", "b_hub_recall": "大问题召回", "b_hit1": "选点 hit@1", "b_hit2": "选点 hit@2"}

fig = plt.figure(figsize=(17, 11))
fig.suptitle(f"fuzzy_hub_rag 专项 benchmark 结果总览 · S5 全 LLM 判定胜出（{os.path.basename(latest)}）",
             fontsize=16, fontweight="bold")

# ── (a) 5 策略最优配置对比 ──────────────────────────────────────────
ax1 = fig.add_subplot(2, 2, 1)
x = np.arange(len(STRATS))
width = 0.19
for i, m in enumerate(METRIC_LABEL):
    vals = [best[s][m] * 100 for s in STRATS]
    ax1.bar(x + (i - 1.5) * width, vals, width, label=METRIC_LABEL[m],
            color=BAR_COLORS[m], edgecolor="white", zorder=3)
    for xi, v in zip(x + (i - 1.5) * width, vals):
        ax1.text(xi, v + 1.2, f"{v:.0f}", ha="center", fontsize=8, color="#333")
calls = [best[s]["llm_calls"] for s in STRATS]
for xi, c in zip(x, calls):
    ax1.text(xi, 106, f"{c} 次 LLM\n调用", ha="center", fontsize=8.5, color="#B03A2E",
             fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels([NAMES[s] for s in STRATS], fontsize=10)
ax1.set_ylim(0, 118)
ax1.set_ylabel("准确率 / 命中率 (%)")
ax1.set_title("(a) 5 策略最优配置对比（40 题 · 每策略取最佳阈值）", fontsize=12, fontweight="bold")
ax1.legend(loc="lower right", fontsize=8.5, framealpha=0.9)
ax1.grid(axis="y", alpha=0.3, zorder=0)
ax1.axvspan(3.5, 4.5, color="#F5B041", alpha=0.12)

# ── (b) S1 阈值网格热力图 ───────────────────────────────────────────
ax2 = fig.add_subplot(2, 2, 2)
s1_runs = [r for r in exp["runs"] if r["strategy"] == "S1"]
floor_vals = sorted({r["floor"] for r in s1_runs})
margin_vals = sorted({r["margin"] for r in s1_runs})
grid = np.zeros((len(floor_vals), len(margin_vals)))
for r in s1_runs:
    i = floor_vals.index(r["floor"])
    j = margin_vals.index(r["margin"])
    grid[i, j] = r["a_acc"] * 100
im = ax2.imshow(grid, cmap="YlOrRd", vmin=50, vmax=80)
ax2.set_xticks(range(len(margin_vals)))
ax2.set_xticklabels([f"{m:.2f}" for m in margin_vals])
ax2.set_yticks(range(len(floor_vals)))
ax2.set_yticklabels([f"{fl:.2f}" for fl in floor_vals])
ax2.set_xlabel("margin（hub 领先 leaf 的最小分差）")
ax2.set_ylabel("floor（hub 池最低分门槛）")
for i in range(len(floor_vals)):
    for j in range(len(margin_vals)):
        ax2.text(j, i, f"{grid[i, j]:.0f}%", ha="center", va="center",
                 fontsize=13, fontweight="bold",
                 color="white" if grid[i, j] < 68 else "#333")
ax2.set_title("(b) S1 纯 TF-IDF 双池分流：阈值怎么调都救不回来（最优 78%）",
              fontsize=12, fontweight="bold")
fig.colorbar(im, ax=ax2, shrink=0.85, label="Part A 准确率")

# ── (c) S5 逐题选点命中 ─────────────────────────────────────────────
ax3 = fig.add_subplot(2, 2, 3)
f_items = [it for it in s5["details"] if it["id"].startswith("F")]
f_items = list(reversed(f_items))  # F20 在顶部
colors, labels = [], []
for it in f_items:
    if it.get("hit1"):
        colors.append("#2E9E4F"); labels.append("hit@1")
    elif it.get("hit2"):
        colors.append("#A8D5A2"); labels.append("仅 hit@2")
    elif it.get("hit1") is None:
        colors.append("#B0B0B0"); labels.append("判为小问题")
    else:
        colors.append("#D64545"); labels.append("miss")
ax3.barh(range(len(f_items)), [1] * len(f_items), color=colors, height=0.72,
         edgecolor="white")
for i, it in enumerate(f_items):
    picked = "、".join(it.get("picked") or []) or "—"
    ax3.text(0.008, i, f"{it['id']}  {it['question'][:16]}…", va="center", fontsize=8.5,
             color="white", fontweight="bold")
    ax3.text(1.008, i, f"期望 {','.join(it['expected'])} → 选中 {picked}",
             va="center", fontsize=7.5, color="#444")
ax3.set_yticks([])
ax3.set_xlim(0, 2.2)
ax3.set_xticks([])
ax3.set_title("(c) S5 20 道模糊题逐题选点（深绿=首个即中 17 题，灰=误判小问题 1 题，红=完全跑偏 1 题）",
              fontsize=12, fontweight="bold")
from matplotlib.patches import Patch
ax3.legend(handles=[Patch(color="#2E9E4F", label="hit@1（17）"), Patch(color="#A8D5A2", label="仅 hit@2（1）"),
                    Patch(color="#B0B0B0", label="误判为小问题（1）"), Patch(color="#D64545", label="miss（1）")],
           loc="lower right", fontsize=8.5, framealpha=0.9)

# ── (d) S5 混淆矩阵 ─────────────────────────────────────────────────
ax4 = fig.add_subplot(2, 2, 4)
c = s5["confusion"]
mat = np.array([[c["hub_hub"], c["hub_leaf"]], [c["leaf_hub"], c["leaf_leaf"]]])
total = mat.sum()
acc = (c["hub_hub"] + c["leaf_leaf"]) / total
im2 = ax4.imshow(mat, cmap="YlGn", vmin=0, vmax=20)
ax4.set_xticks([0, 1])
ax4.set_xticklabels(["判为 HUB\n（大问题）", "判为 LEAF\n（小问题）"])
ax4.set_yticks([0, 1])
ax4.set_yticklabels(["真实：模糊大问题\n（20 题）", "真实：对照组具体题\n（20 题）"])
for i in range(2):
    for j in range(2):
        color = "white" if mat[i, j] > 12 else "#333"
        ax4.text(j, i, f"{mat[i, j]} 题", ha="center", va="center", fontsize=20,
                 fontweight="bold", color=color)
ax4.set_title(f"(d) S5 大小点分类混淆矩阵 · 准确率 {acc:.1%}（39/40，唯一错误 = F16 被判小问题）",
              fontsize=12, fontweight="bold")
fig.colorbar(im2, ax=ax4, shrink=0.85)

fig.tight_layout(rect=[0, 0, 1, 0.955])
out = os.path.join(RESULT_DIR, "experiment_overview.png")
fig.savefig(out, dpi=150, facecolor="white")
print("已输出:", out)
