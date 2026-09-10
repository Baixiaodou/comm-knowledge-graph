# -*- coding: utf-8 -*-
"""生成裁判评分机制分数带图（benchmark/scoring_rules.png）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(10.5, 3.6), dpi=150)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# 分数带分段：0-2 编造 / 2-4 概念错误 / 4-6 表面规律 / 6-9 完整浅层 / 9-10 深层机制
bands = [
    (0, 2, "#e24b4a", "编造内容", "≤ 2 分", "#fff"),
    (2, 4, "#f09595", "概念/结论/原理错误", "≤ 4 分", "#501313"),
    (4, 6, "#ef9f27", "只答表面规律", "≤ 6 分", "#412402"),
    (6, 9, "#c0dd97", "完整但未达深层", "6-9 分", "#173404"),
    (9, 10, "#2f855a", "完整 + 深层机制", "9-10 分", "#fff"),
]

y = 0.22
for lo, hi, color, label, score, tc in bands:
    rect = FancyBboxPatch((lo, y), hi - lo, 0.55, boxstyle="round,pad=0.01,rounding_size=0.02",
                          facecolor=color, edgecolor="none", zorder=3)
    ax.add_patch(rect)
    cx = (lo + hi) / 2
    ax.text(cx, y + 0.275, label, ha="center", va="center", fontsize=10, color=tc, zorder=4)
    ax.text(cx, y - 0.02, score, ha="center", va="top", fontsize=9, color="#333", zorder=4)

ax.set_xlim(0, 10)
ax.set_ylim(0, 1.55)
ax.set_xticks(range(0, 11))
ax.set_yticks([])
ax.set_xlabel("分数（0-10）", fontsize=12)
ax.set_title("裁判评分机制：正确度 / 完整度 / 逻辑性（qwen-max · 温度 0）", fontsize=13, pad=10)
ax.grid(axis="x", linestyle="--", alpha=0.3, zorder=0)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)

# 下方三维度说明
notes = [
    "正确度（兜底下限）：编造内容 ≤2 分；概念/结论/原理错误 ≤4 分",
    "完整度（逐点累计）：在正确度基础上，每漏一个核心要点扣 2 分",
    "逻辑性（突破上限）：只答表面规律 ≤6 分；答出深层机制（why）9-10 分",
]
colors = ["#a32d2d", "#854f0b", "#2f855a"]
for i, (note, c) in enumerate(zip(notes, colors)):
    ax.plot([0.15, 0.45], [1.28 - i * 0.17, 1.28 - i * 0.17], color=c, lw=3, solid_capstyle="round")
    ax.text(0.55, 1.28 - i * 0.17, note, fontsize=9.5, va="center", color="#222")

fig.tight_layout()
out = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base\benchmark\scoring_rules.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print("saved:", out)
