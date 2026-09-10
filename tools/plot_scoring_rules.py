# -*- coding: utf-8 -*-
"""生成裁判评分档位图（benchmark/scoring_rules.png）。

视觉（2026-09-10 第二次重做，对齐 Apple-design 模板 00002）：
  · 单一蓝色阶（浅灰 → Action Blue），无彩虹配色、无网格、无边框；
  · 每档只在带内标一个短语，分数门槛用极小的字标在带下方 —— 信息不重复两次；
  · 图形元素只有一条带，靠色阶递进表达「分数 → 档位」这一件事；
  · 输出尺寸按 2 倍图给足分辨率，README 里缩放后文字仍然锐利。

标题、评分三维度（正确度 / 完整度 / 逻辑性）与口径写在 README 图注里，图本身不承载。

窄档（9–10，占全宽 1/10）标签置于带上方外部，避免文字被裁切（旧版即在此溢出画布）。

用法：
    python tools/plot_scoring_rules.py [--out <path>.png]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_style import BLUE, FS, PALETTE, strip_axes, use_style  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(BASE, "benchmark", "scoring_rules.png")

# (下界, 上界, 底色, 档位标签, 门槛文案, 标签色)
# 单色阶：#efeff2 → #9dc0e6 → Action Blue，深浅即分数高低
BANDS = [
    (0, 2, "#eeeff1", "编造内容",         "≤ 2",   "#1d1d1f"),
    (2, 4, "#d9e3ef", "概念 / 原理错误",  "≤ 4",   "#1d1d1f"),
    (4, 6, "#b6cde4", "只答表面规律",     "≤ 6",   "#1d1d1f"),
    (6, 9, "#7ba9d8", "完整但未达深层",   "6–9",   "#ffffff"),
    (9, 10, "#0066cc", "完整 + 深层机制", "9–10",  "#ffffff"),
]
NARROW = 1.6      # 带宽小于此值（数据单位）时，标签移到带外


def draw(out_path):
    plt = use_style()
    # 画布按 README 显示宽度定，dpi 300 保证放大/高分屏下不糊
    fig = plt.figure(figsize=(7.2, 1.95), dpi=300)
    ax = fig.add_axes([0.040, 0.330, 0.925, 0.430])
    ax.set_ylim(0.20, 1.00)

    y, h = 0.62, 0.38
    for lo, hi, color, label, thr, tc in BANDS:
        ax.barh(y, hi - lo, left=lo, height=h, color=color, zorder=3,
                edgecolor="white", linewidth=1.6)
        cx = (lo + hi) / 2
        if hi - lo < NARROW:
            ax.text(cx, y + h / 2 + 0.06, label, ha="center", va="bottom",
                    fontsize=FS["note"], color=BLUE, weight="bold")
        else:
            ax.text(cx, y, label, ha="center", va="center",
                    fontsize=FS["note"] + 0.5, color=tc, zorder=4)
        ax.text(cx, y - h / 2 - 0.07, thr, ha="center", va="top",
                fontsize=FS["note"] - 0.5, color=PALETTE["muted"])

    ax.set_xlim(0, 10)
    ax.set_yticks([])
    ax.set_xticks(range(0, 11))
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=2.6, pad=4)
    strip_axes(ax)

    fig.savefig(out_path, dpi=300, facecolor="white")
    print("saved:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="输出路径（默认 benchmark/scoring_rules.png）")
    args = ap.parse_args()
    draw(args.out or DEFAULT_OUT)


if __name__ == "__main__":
    main()
