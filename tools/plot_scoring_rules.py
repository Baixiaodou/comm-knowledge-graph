# -*- coding: utf-8 -*-
"""生成裁判评分机制图（benchmark/scoring_rules.png）。

与 plot_gain_chart 共用 plot_style 的视觉规范：无网格、无边框、克制配色、
标题+副标题在左上、口径说明放底部脚注。

内容：0–10 分五档评分带 + 三个评分维度（正确度兜底 / 完整度累计 / 逻辑性突破上限）。
窄档（9–10）标签放带外，避免文字溢出——旧版正是这里被裁切。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_style import FS, PALETTE, footer, strip_axes, use_style  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(BASE, "benchmark", "scoring_rules.png")

# (下界, 上界, 底色, 标签, 门槛文案, 标签色)
BANDS = [
    (0, 2, "#a8443f", "编造内容", "≤ 2 分", "#ffffff"),
    (2, 4, "#c07a5e", "概念 / 原理错误", "≤ 4 分", "#ffffff"),
    (4, 6, "#cf9f4a", "只答表面规律", "≤ 6 分", "#3a2c10"),
    (6, 9, "#8fae8b", "完整但未达深层", "6–9 分", "#1f3320"),
    (9, 10, "#2f6b4f", "完整 + 深层机制", "9–10 分", "#ffffff"),
]
# 三个维度（脚注）：色条 + 说明
DIMENSIONS = [
    ("#a8443f", "正确度（兜底下限）：编造内容 ≤ 2 分；概念 / 结论 / 原理错误 ≤ 4 分"),
    ("#cf9f4a", "完整度（逐点累计）：在正确度基础上，每漏一个核心要点扣 2 分"),
    ("#2f6b4f", "逻辑性（突破上限）：只答表面规律 ≤ 6 分；答出深层机制（why）9–10 分"),
]


def draw(out_path):
    plt = use_style()
    # 画布按 GitHub README 显示宽度定（见 plot_gain_chart 注释）
    fig = plt.figure(figsize=(7.8, 2.75), dpi=150)
    ax = fig.add_axes([0.055, 0.33, 0.905, 0.36])
    ax.set_ylim(0.30, 1.0)

    y, h = 0.70, 0.34
    for lo, hi, color, label, thr, tc in BANDS:
        ax.barh(y, hi - lo, left=lo, height=h, color=color, zorder=3,
                edgecolor="white", linewidth=1.2)
        cx = (lo + hi) / 2
        width = hi - lo
        # 窄档标签上移，避免像旧版那样在带内被裁切
        if width < 1.6:
            ax.text(cx, y + h / 2 + 0.03, label, ha="center", va="bottom",
                    fontsize=FS["note"], color="#2f6b4f")
        else:
            ax.text(cx, y, label, ha="center", va="center",
                    fontsize=FS["note"] + 0.5, color=tc, zorder=4)
        ax.text(cx, y - h / 2 - 0.03, thr, ha="center", va="top",
                fontsize=FS["note"] - 0.5, color=PALETTE["muted"])

    ax.set_xlim(0, 10)
    ax.set_yticks([])
    ax.set_xticks(range(0, 11))
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=3)
    strip_axes(ax)

    fig.text(0.055, 0.97, "裁判评分机制：正确度 / 完整度 / 逻辑性",
             fontsize=FS["title"], color=PALETTE["title"], weight="bold", va="top")
    fig.text(0.055, 0.895, "qwen-max 裁判 · 温度 0 · 0–10 分严格分档",
             fontsize=FS["sub"], color=PALETTE["sub"], va="top")

    # 三维度脚注（色条 + 说明）
    x0, y0, gap = 0.055, 0.225, 0.055
    for i, (color, text) in enumerate(DIMENSIONS):
        yy = y0 - i * gap
        fig.patches.append(plt.Rectangle((x0, yy - 0.005), 0.012, 0.010,
                                         transform=fig.transFigure, color=color,
                                         figure=fig, zorder=5))
        fig.text(x0 + 0.021, yy, text, fontsize=FS["note"] - 0.5,
                 color=PALETTE["body"], va="center")

    footer(fig, ["分数 = 正确度打底 → 完整度逐点累计 → 逻辑性决定能否突破 6 分上限；"
                 "同轮评测内裸跑与 +知识库由同一裁判同口径打分"], y=0.045, gap=0.038)

    fig.savefig(out_path, dpi=150, facecolor="white")
    print("saved:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="输出路径（默认 benchmark/scoring_rules.png）")
    args = ap.parse_args()
    draw(args.out or DEFAULT_OUT)


if __name__ == "__main__":
    main()
