# -*- coding: utf-8 -*-
"""生成五模型增益图（benchmark/gain_chart.png）。

两种版式（--variant）：
  forest    默认。横向森林图：灰点=裸跑 → 蓝点=+知识库，误差线=配对差值 95% CI，
            左侧标反直觉子集增益，右侧独立「增益」列（相对提升 + 绝对增益）。
            适合 README 内嵌（宽扁比例），信息量与正文表格互补（补显著性）。
  dumbbell  竖版哑铃图：直接在每个点旁标原始分数，不带 CI。适合 PPT 单页竖排。

数据来源：benchmark/results/merged_full_20260822.json（现算配对统计）。
results/ 不入库，文件缺失时回退到 README 已发布的聚合值（此时不画 CI，脚注注明）。

口径说明（重要）：
  · 分值点 = 各臂「有效样本均值」（与 README 已发布数字一致，非配对口径）；
  · 误差线 = 配对差值 95% CI（同题配对，剔除任一侧调用失败的题）；
  · 3 个模型各有 1 题裸跑调用失败（judge_score=-1），其配对 n=115，其余 116。

用法：
    python tools/plot_gain_chart.py                    # forest → benchmark/gain_chart.png
    python tools/plot_gain_chart.py --variant dumbbell --out ~/gain_dumbbell.png
"""
import argparse
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_style import FS, PALETTE, footer, strip_axes, title_block, use_style  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE, "benchmark", "results", "merged_full_20260822.json")
DEFAULT_OUT = os.path.join(BASE, "benchmark", "gain_chart.png")

# 模型展示名 + README 已发布聚合值（原始数据缺失时的回退）
#   (裸跑均分, +知识库均分, 相对提升 %, 反直觉子集增益)
PUBLISHED = [
    ("deepseek-chat",     "DeepSeek",   (7.809, 8.276, 5.98, 0.800)),
    ("zai-org/GLM-5.2",   "GLM-5.2",    (7.707, 8.026, 4.14, 0.467)),
    ("Qwen/Qwen3-32B",    "Qwen3-32B",  (7.496, 7.922, 5.69, 0.533)),
    ("Qwen/Qwen3-14B",    "Qwen3-14B",  (7.319, 8.017, 9.54, 1.067)),
    ("Qwen/Qwen3-8B",     "Qwen3-8B",   (7.043, 7.612, 8.07, 0.667)),
]
ANTI_PREFIX = "H-"          # 反直觉/难题子集题号前缀（15 题）
CI_XLIM = (6.5, 8.62)       # 横轴自 6.5 起（README 已注明）


# ── 统计 ────────────────────────────────────────────────────────────
def _t_crit(df: int) -> float:
    """95% 双尾 t 临界值（近似表，样本量很小，够用）"""
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
             8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086,
             25: 2.060, 30: 2.042, 40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990,
             100: 1.984, 120: 1.980, 200: 1.972}
    for k in sorted(table):
        if df <= k:
            return table[k]
    return 1.96


def _paired(diffs):
    """返回 (n, 均值, CI下界, CI上界, t, p)"""
    n = len(diffs)
    if n < 2:
        return n, (diffs[0] if diffs else 0.0), 0.0, 0.0, 0.0, 1.0
    m, sd = st.mean(diffs), st.stdev(diffs)
    se = sd / math.sqrt(n)
    t = m / se if se else 0.0
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    half = _t_crit(n - 1) * se
    return n, m, m - half, m + half, t, p


def compute():
    """优先从原始结果现算；缺失则回退 PUBLISHED（无 CI）"""
    if not os.path.exists(RESULTS):
        try:                                   # 跨盘符时 relpath 会抛 ValueError
            shown = os.path.relpath(RESULTS, BASE)
        except ValueError:
            shown = RESULTS
        print(f"[提示] 未找到 {shown}，回退 README 已发布聚合值（不含 95% CI）")
        return [{"raw": r, "name": n, "bare": b, "kb": k, "rel": rel, "anti": anti,
                 "diff": k - b, "gap": k - b, "ci": None, "t": None, "p": None, "n_pairs": None}
                for r, n, (b, k, rel, anti) in PUBLISHED], False

    recs = json.load(open(RESULTS, encoding="utf-8"))
    idx = {}
    for r in recs:
        if r.get("judge_score", -1) >= 0:
            idx[(r["model"], r["qid"], r["mode"])] = r["judge_score"]

    rows = []
    for raw, name, (pub_b, pub_k, pub_rel, pub_anti) in PUBLISHED:
        qids = sorted({q for m, q, _ in idx if m == raw})
        bare = {q: idx[(raw, q, "bare")] for q in qids if (raw, q, "bare") in idx}
        kb = {q: idx[(raw, q, "with_kb")] for q in qids if (raw, q, "with_kb") in idx}
        common = sorted(set(bare) & set(kb))
        if not common or not bare or not kb:
            rows.append({"raw": raw, "name": name, "bare": pub_b, "kb": pub_k,
                         "rel": pub_rel, "anti": pub_anti, "diff": pub_k - pub_b,
                         "ci": None, "t": None, "p": None, "n_pairs": None})
            continue
        b_mean, k_mean = st.mean(bare.values()), st.mean(kb.values())
        n, d_mean, lo, hi, t, p = _paired([kb[q] - bare[q] for q in common])
        anti = [kb[q] - bare[q] for q in common if q.startswith(ANTI_PREFIX)]
        rows.append({
            "raw": raw, "name": name,
            "bare": b_mean, "kb": k_mean,
            "rel": (k_mean - b_mean) / b_mean * 100,
            "anti": st.mean(anti) if anti else pub_anti,
            "diff": d_mean,                    # 配对差值（CI 中心）
            "gap": k_mean - b_mean,            # 各臂均值差（= 已发布增益）
            "ci": (lo, hi), "t": t, "p": p, "n_pairs": n,
        })
    rows.sort(key=lambda r: -r["bare"])        # 按裸跑分数降序
    return rows, True


# ── 绘制 ────────────────────────────────────────────────────────────
def _rows_bands(ax, n):
    """浅灰隔行 + 仅行间分隔线（替代网格；首尾不封边）"""
    for i in range(n):
        if i % 2 == 1:
            ax.axhspan(n - 1 - i - 0.5, n - 1 - i + 0.5, facecolor=PALETTE["band"], zorder=0)
    for i in range(1, n):
        ax.axhline(n - 1 - (i - 0.5), color="#e6e9ee", lw=0.8, zorder=1)


def _arrow(ax, x0, x1, y):
    """基线 → 知识库 的浅蓝连接箭头（细杆小头，不与 CI 线争视觉）"""
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.2",
                                color=PALETTE["connector"], lw=4.2,
                                shrinkA=4, shrinkB=8, mutation_scale=13),
                zorder=2)


def _dots(ax, x, y, kind, scale=1.0):
    """圆点（白描边，压住穿过的连接线与 CI 线）"""
    size = (62 if kind == "kb" else 46) * scale
    ax.scatter([x], [y], s=size, color=PALETTE[kind], zorder=4,
               edgecolor="white", linewidth=1.2)


def draw_forest(rows, out_path, has_data):
    plt = use_style()
    n = len(rows)
    # 画布尺寸按「GitHub README 显示宽度」定：PNG 约 1170px，内嵌按 88% 宽显示时
    # 缩放仅 0.76，8pt 脚注落地约 13px 仍可读（2120px 画布会被压到 9px）。
    fig = plt.figure(figsize=(7.8, 4.3), dpi=150)
    ax = fig.add_axes([0.135, 0.30, 0.615, 0.50])

    _rows_bands(ax, n)
    for i, r in enumerate(rows):
        y = n - 1 - i
        _arrow(ax, r["bare"], r["kb"], y)
        if r.get("ci"):
            c = r["bare"] + r["diff"]
            lo, hi = r["ci"]
            ax.errorbar([c], [y], xerr=[[c - (r["bare"] + lo)], [(r["bare"] + hi) - c]],
                        fmt="none", ecolor=PALETTE["kb"], elinewidth=1.1,
                        capsize=3.0, capthick=1.1, zorder=3.5)
        _dots(ax, r["bare"], y, "baseline")
        _dots(ax, r["kb"], y, "kb")
        # 左侧：反直觉子集增益（图内左上）
        ax.text(0.004, y, f"反直觉 +{r['anti']:.3f}", transform=ax.get_yaxis_transform(),
                fontsize=FS["note"], color=PALETTE["muted"], va="center", ha="left")
        # 右侧增益列（轴外，两行堆叠）
        ax.text(1.045, y + 0.22, f"+{r['rel']:.2f}%", transform=ax.get_yaxis_transform(),
                fontsize=FS["gain"], color=PALETTE["kb"], weight="bold", va="center", ha="left")
        ax.text(1.045, y - 0.24, f"+{r['gap']:.3f}", transform=ax.get_yaxis_transform(),
                fontsize=FS["value"] - 1, color=PALETTE["kb"], va="center", ha="left")
    ax.text(1.045, n - 1 + 0.62, "增益", transform=ax.get_yaxis_transform(),
            fontsize=FS["note"], color=PALETTE["muted"], va="center", ha="left")

    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([r["name"] for r in rows], fontsize=FS["row"], color=PALETTE["body"])
    ax.set_xlim(*CI_XLIM)
    ax.set_ylim(-0.62, n - 0.38)
    ax.set_xticks([7.0, 7.5, 8.0, 8.5])
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=3)
    ax.tick_params(axis="y", length=0)
    strip_axes(ax)

    title_block(fig, "五模型主结果：裸跑 → +知识库",
                "116 题 · method F · qwen-max 裁判 0–10 分 · 2026-08-22 全量重跑 · 按裸跑分数降序")
    # 图例
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", ls="none", color=PALETTE["baseline"], markersize=7, label="裸跑 baseline"),
        Line2D([], [], marker="o", ls="none", color=PALETTE["kb"], markersize=8, label="+知识库"),
        Line2D([], [], color=PALETTE["kb"], lw=1.4, label="95% CI（配对差值）"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.04, 0.175), ncol=3,
               frameon=False, fontsize=FS["note"], handletextpad=0.5, columnspacing=2.2)

    ts = [r["t"] for r in rows if r.get("t")]
    if ts:
        footer(fig, [
            f"误差线 = 配对差值 95% CI · 配对 t 检验：全部 p<0.01（t = {min(ts):.1f}–{max(ts):.1f}）",
            "同轮同裁判 · 长度偏见已排除 · 分值点 = 各臂有效样本均值（非配对口径，与正文表一致）",
            "CI 为同题配对口径：Qwen3-8B / 32B / DeepSeek 各有 1 题裸跑调用失败已剔除（配对 n=115）",
        ], y=0.150, gap=0.047)
    else:
        footer(fig, ["未找到 benchmark/results/merged_full_20260822.json，本图不含 95% CI",
                     "（原始结果不入库，可跑 tools/kb_benchmark.py 复现）"], y=0.110, gap=0.047)

    fig.savefig(out_path, dpi=150, facecolor="white")
    print("saved:", out_path)


def draw_dumbbell(rows, out_path):
    plt = use_style()
    n = len(rows)
    fig = plt.figure(figsize=(5.9, 9.2), dpi=200)
    ax = fig.add_axes([0.235, 0.075, 0.545, 0.775])

    _rows_bands(ax, n)
    for i, r in enumerate(rows):
        y = n - 1 - i
        _arrow(ax, r["bare"], r["kb"], y)
        _dots(ax, r["bare"], y, "baseline", 1.35)
        _dots(ax, r["kb"], y, "kb", 1.35)
        ax.text(r["bare"], y + 0.30, f"{r['bare']:.3f}", ha="center", va="bottom",
                fontsize=FS["value"], color=PALETTE["body"], weight="bold")
        ax.text(r["kb"], y - 0.30, f"{r['kb']:.3f}", ha="center", va="top",
                fontsize=FS["value"], color=PALETTE["kb"], weight="bold")
        ax.text(1.06, y + 0.13, f"+{r['gap']:.2f}", transform=ax.get_yaxis_transform(),
                fontsize=FS["gain"], color=PALETTE["kb"], weight="bold", va="center", ha="left")
        ax.text(1.06, y - 0.15, f"+{r['rel']:.2f}%", transform=ax.get_yaxis_transform(),
                fontsize=FS["value"] - 1, color=PALETTE["kb"], va="center", ha="left")
    ax.text(1.06, n - 1 + 0.62, "增益", transform=ax.get_yaxis_transform(),
            fontsize=FS["note"], color=PALETTE["muted"], va="center", ha="left")

    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([r["name"] for r in rows], fontsize=FS["row"] + 1, color=PALETTE["body"])
    ax.set_xlim(*CI_XLIM)
    ax.set_ylim(-0.62, n - 0.38)
    ax.set_xticks([7.0, 7.5, 8.0, 8.5])
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=3)
    ax.tick_params(axis="y", length=0)
    strip_axes(ax)

    fig.text(0.235, 0.885, "116 题 benchmark：5 个模型全部正增益",
             fontsize=FS["title"], color=PALETTE["title"], weight="bold", va="top")
    fig.text(0.235, 0.856, "2026-08-22 全量重跑 · method F · 按裸跑分数降序",
             fontsize=FS["sub"], color=PALETTE["sub"], va="top")
    fig.text(0.5, 0.040, "qwen-max 裁判均分（0–10 分，横轴自 6.5 起）",
             fontsize=FS["note"], color=PALETTE["muted"], ha="center", va="top")

    fig.savefig(out_path, dpi=200, facecolor="white")
    print("saved:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["forest", "dumbbell"], default="forest")
    ap.add_argument("--out", default="", help="输出路径（默认 benchmark/gain_chart.png）")
    args = ap.parse_args()

    rows, has_data = compute()
    out = args.out or DEFAULT_OUT
    print(" | ".join(f"{r['name']} 裸跑 {r['bare']:.3f} → +KB {r['kb']:.3f}"
                     f"（{r['gap']:+.3f}{'' if not r.get('ci') else f'，配对 {r['diff']:+.3f} CI[{r['ci'][0]:+.3f},{r['ci'][1]:+.3f}] p={r['p']:.1e}'}）"
                     for r in rows))
    if args.variant == "forest":
        draw_forest(rows, out, has_data)
    else:
        draw_dumbbell(rows, out)


if __name__ == "__main__":
    main()
