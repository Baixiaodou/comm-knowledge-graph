# -*- coding: utf-8 -*-
"""README 配图的统一视觉风格（单源）。

风格约定（2026-09-10 第二次重做，对齐 Apple-design 模板 00002）：
  · 色彩只用一个蓝（Action Blue #0066cc）+ 一个中性灰阶，绝不引入第二个彩色；
  · 字体栈优先 Inter（模板指定的 SF Pro 替代），退化到 Segoe UI / 微软雅黑；
  · 字号按 Apple 阶梯缩放：标题 12 / 行名 10.5 / 数值 9.5 / 注释 8；
    正文与行名的对比靠字重（400 / 600），不靠继续放大字号；
  · 极简：无网格、无边框、无图例框，唯一的分隔手段是留白与极浅参考线；
  · 图形元素用白描边压住穿过的线，形成干净的堆叠层次。

两个绘图脚本（plot_gain_chart / plot_scoring_rules）都从这里取色、字号与字体。
"""

import matplotlib

matplotlib.use("Agg")

# ── Apple-design 取色：单一 Action Blue + 中性灰阶 ──────────────────
BLUE = "#0066cc"          # Action Blue —— 全域唯一强调色
INK = "#1d1d1f"           # 近黑（正文 / 标题）
GRAY = "#86868b"          # 次要文字
GRAY_LIGHT = "#d2d2d7"    # 极浅（点 / 参考线）
PAPER = "#f5f5f7"         # Parchment（若需底色块）
BASE_FILL = "#e8e8ed"     # 低饱和填充（起止档）

PALETTE = {
    "title": INK,
    "sub": GRAY,
    "body": INK,
    "muted": GRAY,
    "kb": BLUE,
    "baseline-base": BASE_FILL,
    "strip": PAPER,
    "axis": GRAY_LIGHT,
    "rowline": PAPER,
}

# Apple 字号阶梯的等比缩放（模板基准 17px 正文 → 图上 9.5pt）
FS = {
    "title": 12.0,
    "sub": 8.0,
    "row": 10.5,
    "value": 9.5,
    "gain": 10.5,
    "note": 8.0,
    "footer": 7.0,
}

# Inter 是 Apple 模板点名的 SF Pro 开源替代；缺失时退化到中文字体。
# ⚠️ Segoe UI 不能放进这个栈：它没有 CJK 字形，一旦命中会把所有中文渲染成方框
#    （matplotlib 逐字形回退不可靠），本地实测过这个坑，故直接从栈里剔除。
FONT_STACK = ["Inter", "Microsoft YaHei", "SimHei", "DejaVu Sans"]


def use_style():
    """设置 rcParams 并返回 pyplot（调用方仍需自己 import pyplot 画图）"""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.sans-serif": FONT_STACK,
        "font.family": "sans-serif",
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
    fig.text(x, y, title, fontsize=FS["title"], color=PALETTE["title"], weight="bold",
             va="top", ha="left")
    fig.text(x, y - gap, subtitle, fontsize=FS["sub"], color=PALETTE["sub"], va="top",
             ha="left")


def footer(fig, lines, x=0.045, y=0.095, gap=0.032):
    """底部脚注（方法论 / 口径 / 局限）"""
    for i, line in enumerate(lines):
        fig.text(x, y - i * gap, line, fontsize=FS["footer"], color=PALETTE["muted"],
                 va="top", ha="left")
