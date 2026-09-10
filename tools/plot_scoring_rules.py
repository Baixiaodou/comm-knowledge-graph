# -*- coding: utf-8 -*-
"""生成裁判评分档位图（benchmark/scoring_rules.png）。

学术化版式：单一蓝色阶（浅→深）表示档位递进，无彩虹配色、无网格、无边框，
图内不放标题与维度说明——标题、评分三维度（正确度 / 完整度 / 逻辑性）与口径
写在 README 的图注里，图本身只承载「分数 → 档位」这一条信息。

窄档（9–10，占全宽 1/10）标签置于带外，避免文字被裁切（旧版即在此溢出画布）。

用法：
    python tools/plot_scoring_rules.py [--out <path>.png]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_style import FS, PALETTE, strip_axes, use_style  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(BASE, "benchmark", "scoring_rules.png")

# (下界, 上界, 底色, 档位标签, 门槛文案, 标签色)  —— 单色阶：浅灰蓝 → 深蓝
BANDS = [
    (0, 2, "#dde5ec", "编造内容", "≤ 2 分", "#1f2937"),
    (2, 4, "#c5d4e1", "概念 / 原理错误", "≤ 4 分", "#1f2937"),
    (4, 6, "#a9bfd3", "只答表面规律", "≤ 6 分", "#1f2937"),
    (6, 9, "#6f9bc0", "完整但未达深层", "6–9 分", "#ffffff"),
    (9, 10, "#1f4e79", "完整 + 深层机制", "9–10 分", "#ffffff"),
]
NARROW = 1.6      # 带宽小于此值（数据单位）时，标签移到带外


def draw(out_path):
    plt = use_style()
    # 画布按 README 显示宽度定，dpi 300 保证放大/高分屏下不糊
    fig = plt.figure(figsize=(6.8, 1.85), dpi=300)
    ax = fig.add_axes([0.045, 0.36, 0.915, 0.46])
    ax.set_ylim(0.18, 1.02)

    y, h = 0.60, 0.40
    for lo, hi, color, label, thr, tc in BANDS:
        ax.barh(y, hi - lo, left=lo, height=h, color=color, zorder=3,
                edgecolor="white", linewidth=1.0)
        cx = (lo + hi) / 2
        if hi - lo < NARROW:
            ax.text(cx, y + h / 2 + 0.04, label, ha="center", va="bottom",
                    fontsize=FS["note"], color=PALETTE["kb"])
        else:
            ax.text(cx, y, label, ha="center", va="center",
                    fontsize=FS["note"], color=tc, zorder=4)
        ax.text(cx, y - h / 2 - 0.04, thr, ha="center", va="top",
                fontsize=FS["note"] - 0.5, color=PALETTE["muted"])

    ax.set_xlim(0, 10)
    ax.set_yticks([])
    ax.set_xticks(range(0, 11))
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=3)
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
