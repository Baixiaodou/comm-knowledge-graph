# -*- coding: utf-8 -*-
"""生成五模型增益图（benchmark/gain_chart.png）。

版式（--variant）：
  forest    默认。横向森林图，供 README 内嵌：每行一条极浅参考线，
            起始段用浅灰粗线连到结果点（哑铃），点=各臂均分，
            蓝色细线加端帽=配对差值 95% CI，右侧一列相对提升。
            图内不放标题与长脚注——标题与口径写进 README 图注。
  dumbbell  竖版哑铃图，供 PPT 单页使用：在每个点旁直标原始分数，带图内标题。

视觉（2026-09-10 第二次重做，对齐 Apple-design 模板 00002）：
  · 单一 Action Blue #0066cc 承载全部强调，其余一律中性灰；
  · 起始段用「浅灰粗连接条」表现 裸跑 → 加知识库 的迁移，替代旧版两个孤立圆点；
  · 行名与数值拉开层级靠字重（600 / 400）与留白，不再靠放大字号；
  · 去掉隔行底色、网格、边框，只留极浅参考线与底部轴线。

数据来源：benchmark/results/merged_full_20260822.json（现算配对统计）。
results/ 不入库，缺失时回退到 README 已发布的聚合值（此时不画 CI，并在终端提示）。

口径（与正文图注一致）：
  · 分值点 = 各臂有效样本均值；
  · 误差线 = 同题配对差值 95% CI（配对 t 检验）；
  · 3 个模型各有 1 题裸跑调用失败（judge_score=-1），其配对 n=115，其余 116。

用法：
    python tools/plot_gain_chart.py                      # forest → benchmark/gain_chart.png
    python tools/plot_gain_chart.py --variant dumbbell --out <path>.png
"""
import argparse
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_style import FS, PALETTE, footer, strip_axes, use_style  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE, "benchmark", "results", "merged_full_20260822.json")
DEFAULT_OUT = os.path.join(BASE, "benchmark", "gain_chart.png")

# 模型展示名 + README 已发布聚合值（原始数据缺失时的回退）
#   (裸跑均分, 加知识库均分, 相对提升 %, 反直觉子集增益)
PUBLISHED = [
    ("deepseek-chat",     "DeepSeek",   (7.809, 8.276, 5.98, 0.800)),
    ("zai-org/GLM-5.2",   "GLM-5.2",    (7.707, 8.026, 4.14, 0.467)),
    ("Qwen/Qwen3-32B",    "Qwen3-32B",  (7.496, 7.922, 5.69, 0.533)),
    ("Qwen/Qwen3-14B",    "Qwen3-14B",  (7.319, 8.017, 9.54, 1.067)),
    ("Qwen/Qwen3-8B",     "Qwen3-8B",   (7.043, 7.612, 8.07, 0.667)),
]
ANTI_PREFIX = "H-"          # 反直觉/难题子集题号前缀（15 题）
# 横轴范围：起点略低于最小值给点留白，终点留出端点帽与右侧增益列的空间。
XLIM = (6.90, 8.55)


# ── 统计 ────────────────────────────────────────────────────────────
def _t_crit(df: int) -> float:
    """95% 双尾 t 临界值（近似表；样本量小，够用）"""
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
             8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086,
             25: 2.060, 30: 2.042, 40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990,
             100: 1.984, 120: 1.980, 200: 1.972}
    for k in sorted(table):
        if df <= k:
            return table[k]
    return 1.96


def _paired(diffs):
    """返回 (n, 均值, CI 下界, CI 上界, t, p)"""
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
    """优先从原始结果现算；缺失则回退已发布聚合值（无 CI）"""
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
                         "gap": pub_k - pub_b, "ci": None, "t": None, "p": None, "n_pairs": None})
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
def _row_lines(ax, n):
    """每行一条极浅参考线（比轴线更弱，只做视线引导）"""
    for i in range(n):
        ax.axhline(n - 1 - i, color=PALETTE["rowline"], lw=1.1, zorder=0, xmax=0.985)


def _dot(ax, x, y, color, size):
    """圆点：白描边，压住穿过的连接条与 CI 线，形成干净堆叠"""
    ax.scatter([x], [y], s=size, color=color, zorder=4,
               edgecolor="white", linewidth=1.1)


def draw_forest(rows, out_path, has_data):
    """README 内嵌版：无图内标题、无长脚注（口径写在 README 图注里）

    2026-09-10 第二次重做：
      · 起始段改为浅灰粗连接条 —— 一眼看出「从哪升到哪」；
      · 单一 Action Blue 承载全部强调，其余中性灰；
      · 右侧增益列改单行（相对提升），行名与数值靠字重分层。
    """
    plt = use_style()
    n = len(rows)
    fig = plt.figure(figsize=(7.2, 2.45), dpi=300)
    #         [left, bottom, width, height]
    ax = fig.add_axes([0.135, 0.215, 0.645, 0.740])

    _row_lines(ax, n)
    for i, r in enumerate(rows):
        y = n - 1 - i
        # ① 连接条：裸跑 → 加知识库（浅灰，圆头，给点径留出视觉呼吸）
        if abs(r["kb"] - r["bare"]) > 0.02:
            ax.plot([r["bare"], r["kb"]], [y, y], color=PALETTE["baseline-base"],
                    lw=6.0, solid_capstyle="round", zorder=2)
        # ② CI：配对差值区间，细线 + 端帽，位于同一行
        if r.get("ci"):
            c = r["bare"] + r["diff"]
            lo, hi = r["ci"]
            ax.errorbar([c], [y], xerr=[[c - (r["bare"] + lo)], [(r["bare"] + hi) - c]],
                        fmt="none", ecolor=PALETTE["kb"], elinewidth=1.0,
                        capsize=2.6, capthick=1.0, alpha=0.85, zorder=3)
        # ③ 两个点：起点中性灰、终点 Action Blue
        _dot(ax, r["bare"], y, PALETTE["axis"], 34)
        _dot(ax, r["kb"], y, PALETTE["kb"], 46)
        # ④ 右侧增益列：单行，Action Blue 加粗
        ax.text(1.035, y, f"+{r['rel']:.1f}%", transform=ax.get_yaxis_transform(),
                fontsize=FS["gain"], color=PALETTE["kb"], weight="bold",
                va="center", ha="left")

    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([r["name"] for r in rows], fontsize=FS["row"],
                       color=PALETTE["body"], weight="600")
    ax.set_xlim(*XLIM)
    ax.set_ylim(-0.62, n - 0.38)
    ax.set_xticks([7.0, 7.5, 8.0, 8.5])
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=2.6, pad=4)
    ax.tick_params(axis="y", length=0, pad=8)
    strip_axes(ax)

    # 轴标题放绘图区左下，替代「裁判均分」这句在正文图注里的话
    ax.text(0.0, -0.235, "裁判均分（qwen-max，0–10）", transform=ax.transAxes,
            fontsize=FS["note"], color=PALETTE["sub"], va="center", ha="left")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", ls="none", color=PALETTE["axis"],
               markersize=5.0, markeredgecolor="white", markeredgewidth=0.8, label="裸跑"),
        Line2D([], [], marker="o", ls="none", color=PALETTE["kb"],
               markersize=5.8, markeredgecolor="white", markeredgewidth=0.8, label="加知识库"),
        Line2D([], [], color=PALETTE["kb"], lw=1.0, alpha=0.85,
               label="95% CI（配对差值）"),
    ]
    leg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.133, 0.145),
                     ncol=3, frameon=False, fontsize=FS["note"], handletextpad=0.4,
                     columnspacing=1.8, borderpad=0)
    for t in leg.get_texts():
        t.set_color(PALETTE["sub"])

    if not has_data:
        footer(fig, ["未找到原始评测结果，本图未绘制 95% CI（可跑 tools/kb_benchmark.py 复现）"],
               x=0.133, y=0.055, gap=0.04)

    fig.savefig(out_path, dpi=300, facecolor="white")
    print("saved:", out_path)


def draw_dumbbell(rows, out_path):
    """PPT 竖版：点旁直标原始分数，带图内标题"""
    plt = use_style()
    n = len(rows)
    fig = plt.figure(figsize=(6.0, 8.4), dpi=200)
    ax = fig.add_axes([0.245, 0.075, 0.520, 0.760])

    _row_lines(ax, n)
    for i, r in enumerate(rows):
        y = n - 1 - i
        ax.plot([r["bare"], r["kb"]], [y, y], color=PALETTE["baseline-base"], lw=6, zorder=2,
                solid_capstyle="round")
        _dot(ax, r["bare"], y, PALETTE["axis"], 46)
        _dot(ax, r["kb"], y, PALETTE["kb"], 62)
        ax.text(r["bare"], y + 0.28, f"{r['bare']:.3f}", ha="center", va="bottom",
                fontsize=FS["value"], color=PALETTE["body"], weight="bold")
        ax.text(r["kb"], y - 0.28, f"{r['kb']:.3f}", ha="center", va="top",
                fontsize=FS["value"], color=PALETTE["kb"], weight="bold")
        ax.text(1.06, y + 0.14, f"+{r['gap']:.2f}", transform=ax.get_yaxis_transform(),
                fontsize=FS["gain"], color=PALETTE["kb"], weight="bold", va="center", ha="left")
        ax.text(1.06, y - 0.16, f"+{r['rel']:.2f}%", transform=ax.get_yaxis_transform(),
                fontsize=FS["value"] - 1, color=PALETTE["kb"], va="center", ha="left")
    ax.text(1.06, n - 1 + 0.55, "增益", transform=ax.get_yaxis_transform(),
            fontsize=FS["note"], color=PALETTE["muted"], va="center", ha="left")

    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([r["name"] for r in rows], fontsize=FS["row"], color=PALETTE["body"],
                       weight="600")
    ax.set_xlim(*XLIM)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_xticks([7.0, 7.5, 8.0, 8.5])
    ax.tick_params(axis="x", labelsize=FS["note"], colors=PALETTE["sub"], length=3)
    ax.tick_params(axis="y", length=0)
    strip_axes(ax)

    fig.text(0.245, 0.935, "116 题 benchmark：五个模型全部正增益",
             fontsize=FS["title"], color=PALETTE["title"], weight="bold", va="top")
    fig.text(0.245, 0.905, "2026-08-22 全量重跑 · method F · 按裸跑分数降序",
             fontsize=FS["sub"], color=PALETTE["sub"], va="top")
    fig.text(0.245 + 0.520 / 2, 0.040, "裁判均分（qwen-max，0–10 分）",
             fontsize=FS["note"], color=PALETTE["muted"], ha="center", va="top")

    fig.savefig(out_path, dpi=200, facecolor="white")
    print("saved:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["forest", "dumbbell"], default="forest")
    ap.add_argument("--out", default="", help="输出路径（默认 benchmark/gain_chart.png）")
    args = ap.parse_args()

    rows, has_data = compute()
    for r in rows:
        ci = "" if not r.get("ci") else (f"，配对 {r['diff']:+.3f} "
                                         f"CI[{r['ci'][0]:+.3f},{r['ci'][1]:+.3f}] p={r['p']:.1e}")
        print(f"{r['name']:<11} 裸跑 {r['bare']:.3f} → 加知识库 {r['kb']:.3f}"
              f"（{r['gap']:+.3f}{ci}）")
    out = args.out or DEFAULT_OUT
    if args.variant == "forest":
        draw_forest(rows, out, has_data)
    else:
        draw_dumbbell(rows, out)


if __name__ == "__main__":
    main()
