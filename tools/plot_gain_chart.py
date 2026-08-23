# -*- coding: utf-8 -*-
"""生成知识库增益柱状图（benchmark/gain_chart.png）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 数据（README 2026-08-22 全量重跑，method F）
models = ["Qwen3-14B", "Qwen3-8B", "DeepSeek", "Qwen3-32B", "GLM-5.2"]
gain = [0.698, 0.569, 0.467, 0.427, 0.319]          # 整体增益（绝对分）
gain_anti = [1.067, 0.667, 0.800, 0.533, 0.467]     # 反直觉子集增益
rel = [9.54, 8.07, 5.98, 5.69, 4.14]                # 相对提升 %

# 按整体增益降序排序（顶部最大）
order = np.argsort(gain)[::-1]
models = [models[i] for i in order]
gain = [gain[i] for i in order]
gain_anti = [gain_anti[i] for i in order]
rel = [rel[i] for i in order]

y = np.arange(len(models))
h = 0.34

fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=150)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

b1 = ax.barh(y + h/2, gain, height=h, color="#2b6cb0", label="整体增益", zorder=3)
b2 = ax.barh(y - h/2, gain_anti, height=h, color="#b7791f", label="反直觉子集增益", zorder=3)

# 柱外标注：整体增益+相对提升（蓝）、反直觉子集增益（橙）
for i, (g, ga, r) in enumerate(zip(gain, gain_anti, rel)):
    ax.text(g + 0.02, i + h/2, f"+{g:.3f}  (+{r:.2f}%)", va="center", ha="left", fontsize=10, color="#1a4a8a")
    ax.text(ga + 0.02, i - h/2, f"+{ga:.3f}", va="center", ha="left", fontsize=10, color="#8a5a10")

ax.set_yticks(y)
ax.set_yticklabels(models, fontsize=12)
ax.set_xlabel("增益（分数）", fontsize=12)
ax.set_title("知识库增益：5 模型对比（116 题 · method F）", fontsize=14, pad=12)
ax.legend(loc="upper right", fontsize=10, frameon=False)
ax.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)
ax.set_xlim(0, 1.35)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)

fig.tight_layout()
out = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base\benchmark\gain_chart.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print("saved:", out)
