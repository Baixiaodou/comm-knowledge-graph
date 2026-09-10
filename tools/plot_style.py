# -*- coding: utf-8 -*-
"""README 配图的统一视觉风格（单源）。

风格约定（2026-09-10 重做）：
  · 配色只有三档：中性灰（基线）+ 深蓝（知识库）+ 浅蓝（连接）；
  · 不用网格、不用图例框、不用彩色边框——行分隔用极浅细线；
  · 数值直接标在元素旁，不靠图例/坐标轴反查；
  · 标题 + 灰色副标题在左上，方法论与口径放在底部脚注；
  · 只保留底部轴线，其余 spine 一律隐藏；
  · 字号收敛（正文 9 / 行名 10 / 标题 12.5），靠字重与留白分层，
    不靠放大字号——旧版字号整体偏大，观感笨重。

两个绘图脚本（plot_gain_chart / plot_scoring_rules）都从这里取色与字号。
"""

import matplotlib

matplotlib.use("Agg")

PALETTE = {
    "title": "#1b1f24",      # 主标题
    "sub": "#8a9099",        # 副标题 / 口径说明
    "body": "#2d3339",       # 正文数值
    "muted": "#9aa0a6",      # 次要标注
    "baseline": "#b8bdc6",   # 裸跑（基线）
    "kb": "#1f4e79",         # 加知识库
    "connector": "#cfe0f0",  # 基线→知识库 连接
    "band": "#f7f9fb",       # 隔行底色
    "axis": "#d8dce2",       # 轴线 / 分隔线
    "rowline": "#f0f2f5",    # 行参考线（比轴线更浅）
    "warm": "#c08a3e",       # 少量强调（反直觉等）
}

FS = {
    "title": 12.5,
    "sub": 8.5,
    "row": 10.0,
    "value": 9.0,
    "gain": 10.0,
    "note": 7.5,
    "footer": 7.0,
}


def use_style():
    """设置 rcParams 并返回 pyplot（调用方仍需自己 import pyplot 画图）"""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": None,
    })
    return plt


def strip_axes(ax, keep_bottom=True):
    """去掉所有边框，只留底部轴线（细、浅灰）"""
    for name, spine in ax.spines.items():
        spine.set_visible(keep_bottom and name == "bottom")
    if keep_bottom:
        ax.spines["bottom"].set_color(PALETTE["axis"])
        ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(False)


def title_block(fig, title, subtitle, x=0.045, y=0.945, gap=0.055):
    """左上角标题 + 灰色副标题"""
    fig.text(x, y, title, fontsize=FS["title"], color=PALETTE["title"], weight="bold", va="top")
    fig.text(x, y - gap, subtitle, fontsize=FS["sub"], color=PALETTE["sub"], va="top")


def footer(fig, lines, x=0.045, y=0.095, gap=0.032):
    """底部脚注（方法论 / 口径 / 局限）"""
    for i, line in enumerate(lines):
        fig.text(x, y - i * gap, line, fontsize=FS["footer"], color=PALETTE["muted"], va="top")
