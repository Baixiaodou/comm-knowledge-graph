#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染 README 配图（只使用仓库内已公开的数据，无任何未发表实验结果）

产出：
    docs/img/kb_graph.png     知识图谱全景（90 节点 / 340 连接 / 7 棵主题树）
    benchmark/gain_chart.png  5 模型知识库增益对比（数据与 README 表格一致）

用法：
    python tools/render_readme_figures.py
依赖：matplotlib（系统 Python 需已安装；中文用微软雅黑）
"""

import json
import math
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE = json.load(open(os.path.join(BASE, "knowledge-v2", "_meta", "tree.json"), encoding="utf-8"))["nodes"]
IMG_DIR = os.path.join(BASE, "docs", "img")
ROOT = "root"
R_HUB, RING = 2.1, 1.62  # 顶部 hub 半径 / 层间半径步长

# 每个节点 .md 的 frontmatter 里 links 才是真正的边（tree.json 只有 link_count）
LINK_RE = re.compile(r"^\s*-\s*id:\s*(\S+)", re.M)


def load_edges():
    edges = set()
    for nid in TREE:
        fm = open(os.path.join(BASE, "knowledge-v2", "nodes", nid + ".md"), encoding="utf-8").read().split("---")[1]
        if "links:" not in fm:
            continue
        block = fm.split("links:", 1)[1]
        for target in LINK_RE.findall(block):
            if target in TREE:
                edges.add(frozenset((nid, target)))
    edges.discard(frozenset((nid,)))  # 防御：自环
    return [tuple(e) for e in edges if len(e) == 2]


_children = {}
for _nid, _meta in TREE.items():
    _children.setdefault(_meta.get("parent"), []).append(_nid)
TOPS = sorted(_children[ROOT], key=lambda n: -subtree_size(n)) if False else None  # subtree_size 定义在后，见 init()


def subtree_size(nid):
    return 1 + sum(subtree_size(c) for c in _children.get(nid, []))


def tree_of(nid):
    while TREE[nid].get("parent") != ROOT and TREE[nid].get("parent") in TREE:
        nid = TREE[nid]["parent"]
    return nid


# ── 知识图谱全景 ────────────────────────────────────────────────────
PALETTE = ["#3B82C4", "#E8763A", "#4C9F70", "#D65F5F", "#5FA8A3", "#9673B8", "#A08253"]


def short_title(title):
    return re.split(r"[（(]", title)[0].strip()


def polar(ang, r):
    return (r * math.cos(ang), r * math.sin(ang))


def render_graph():
    tops = sorted(_children[ROOT], key=lambda n: -subtree_size(n))
    tree_color = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(tops)}
    tree_name = {t: short_title(TREE[t]["title"]) for t in tops}
    sizes = {t: subtree_size(t) for t in tops}
    total = sum(sizes.values())
    edges = load_edges()

    pos = {}
    GAP = math.radians(5.0)
    raw = [2 * math.pi * sizes[t] / total - GAP for t in tops]
    MIN_SPAN = math.radians(30)
    raw = [max(r, MIN_SPAN) for r in raw]
    scale = (2 * math.pi - len(raw) * GAP) / sum(raw)
    acc = math.radians(90)
    for t, r in zip(tops, raw):
        span = r * scale
        place_tree(t, acc - span / 2, span, R_HUB, pos)
        acc += span + GAP
    relax(pos)

    fig, ax = plt.subplots(figsize=(20, 11.5), dpi=150)
    ax.set_xlim(-10.6, 10.6)
    ax.set_ylim(-7.05, 6.15)
    ax.set_aspect("equal")
    ax.axis("off")

    # 跨树 links：先画（最底层），细弧线 + 低透明度
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        if tree_of(a) != tree_of(b):
            x1, y1 = pos[a]
            x2, y2 = pos[b]
            dist = math.hypot(x2 - x1, y2 - y1)
            sag = min(0.42, dist * 0.10)
            rad = sag / max(dist, 1e-6) * side_of(x1, y1, x2, y2)
            ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                         connectionstyle=f"arc3,rad={rad}", arrowstyle="-",
                         color=tree_color[tree_of(a)], alpha=0.20, lw=0.75, zorder=1))

    # 树内父子边
    for nid, meta in TREE.items():
        p = meta.get("parent")
        if p in TREE and p != ROOT:
            x1, y1 = pos[p]
            x2, y2 = pos[nid]
            ax.plot([x1, x2], [y1, y2], color=tree_color[tree_of(nid)], lw=1.1, alpha=0.30, zorder=2)

    # 节点 + 标签
    for nid, (x, y) in pos.items():
        meta = TREE[nid]
        c = tree_color[tree_of(nid)]
        typ = meta["type"]
        r = {"hub": 0.17, "core": 0.125, "leaf": 0.095}[typ]
        if typ == "hub":
            ax.add_patch(Circle((x, y), r, facecolor="white", edgecolor=c, lw=2.8, zorder=4))
        else:
            ax.add_patch(Circle((x, y), r, facecolor=c, edgecolor="white", lw=1.2, alpha=0.95, zorder=4))
        if meta.get("has_cot"):
            ax.add_patch(Circle((x, y), r + 0.05, facecolor="none", edgecolor=c, lw=1.1, alpha=0.5, zorder=3))
        label = short_title(meta["title"])
        if typ == "hub":
            ax.text(x, y - r - 0.13, label, ha="center", va="top", fontsize=11,
                    fontweight="bold", color="#1A202C", zorder=6)
        else:
            k = 1 if x >= 0 else -1
            ax.text(x + k * (r + 0.06), y, label, ha="left" if k > 0 else "right",
                    va="center", fontsize=8.4, color="#425261", zorder=6)

    # 中心徽标
    ax.text(0, 0.14, "通信工程\n知识库 v2", ha="center", va="center", fontsize=17.5,
            fontweight="bold", color="#2D3748", linespacing=1.55, zorder=6)
    ax.text(0, -0.92, "90 节点 · 340 连接 · 7 棵主题树", ha="center", va="center",
            fontsize=9.5, color="#718096", zorder=6)

    # 标题 + 图例
    ax.text(-10.3, 6.02, "知识图谱全景", fontsize=21, fontweight="bold", color="#1A202C", va="top")
    ax.text(-10.3, 5.47, "树层级管「在哪」，Wiki 连接管「和谁相关」——弧线为跨树连接 · 空心圆 = 分类枢纽 · 圆环 = 带思维链的节点",
            fontsize=11, color="#718096", va="top")
    handles = [plt.Line2D([], [], marker="o", ls="", ms=9, mfc=tree_color[t], mec="none") for t in tops]
    ax.legend(handles, [f"{tree_name[t]}（{sizes[t]}）" for t in tops], loc="upper center", ncol=4,
              frameon=False, fontsize=11, bbox_to_anchor=(0.5, 0.055),
              handletextpad=0.25, columnspacing=1.6)

    os.makedirs(IMG_DIR, exist_ok=True)
    out = os.path.join(IMG_DIR, "kb_graph.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white", pad_inches=0.25)
    print("saved", out)


def relax(pos, iters=820):
    """标签防重叠：靠太近的节点互相推开，弱弹簧拉回原布局。"""
    half = {n: (0.062 * len(short_title(TREE[n]["title"])) + 0.26) *
               (1.75 if TREE[n]["type"] == "hub" else 1.0) for n in pos}
    orig = dict(pos)
    nodes = list(pos)
    for _ in range(iters):
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dx = pos[b][0] - pos[a][0]
                dy = (pos[b][1] - pos[a][1]) * 2.6
                d = math.hypot(dx, dy) or 1e-6
                dmin = half[a] + half[b]
                if d < dmin:
                    f = (dmin - d) / d * 0.30
                    px, py = dx * f, dy * f / 2.6
                    pos[a] = (pos[a][0] - px, pos[a][1] - py)
                    pos[b] = (pos[b][0] + px, pos[b][1] + py)
        for n in nodes:
            k = 0.06 if TREE[n]["type"] == "hub" else 0.014
            nx = pos[n][0] + (orig[n][0] - pos[n][0]) * k
            ny = pos[n][1] + (orig[n][1] - pos[n][1]) * k
            pos[n] = (max(-10.1, min(10.1, nx)), max(-5.75, min(4.9, ny)))


def place_tree(t, a0, span, radius, pos):
    """扇形布局：角度按「局部」子树规模递归分配，越深越靠外。"""
    pos[t] = polar(a0 + span / 2, radius)
    def place(nid, center, sp, r):
        kids = [k for k in _children.get(nid, []) if k not in pos]
        if not kids:
            return
        total = sum(subtree_size(k) for k in kids)
        acc = center - sp / 2
        for k in kids:
            ks = sp * subtree_size(k) / total
            pos[k] = polar(acc + ks / 2, r + RING)
            place(k, acc + ks / 2, ks, r + RING)
            acc += ks
    place(t, a0 + span / 2, span * 0.97, radius)


def side_of(x1, y1, x2, y2):
    """让弧线朝远离圆心的方向弯，减少穿过中心区域。"""
    cross = x1 * y2 - y1 * x2
    return 1 if cross > 0 else -1


# ── 5 模型增益图（数据 = README「核心结果」表格，2026-08-22 全量重跑） ──
GAINS = [  # (模型, 规模, 整体增益, 反直觉子集增益, 相对提升)
    ("Qwen3-14B", "14B", 0.698, 1.067, "+9.54%"),
    ("Qwen3-8B", "8B", 0.569, 0.667, "+8.07%"),
    ("DeepSeek", "大模型", 0.467, 0.800, "+5.98%"),
    ("Qwen3-32B", "32B", 0.427, 0.533, "+5.69%"),
    ("GLM-5.2", "大模型", 0.319, 0.467, "+4.14%"),
]


def render_gain():
    fig, ax = plt.subplots(figsize=(12.5, 6.2), dpi=150)
    names = [f"{m}\n{v}" for m, v, *_ in GAINS][::-1]
    overall = [g[2] for g in GAINS][::-1]
    tricky = [g[3] for g in GAINS][::-1]
    rel = [g[4] for g in GAINS][::-1]
    y = range(len(names))
    h = 0.36
    ax.barh([i + h / 2 + 0.02 for i in y], overall, height=h, color="#2B6CB0", label="整体增益")
    ax.barh([i - h / 2 - 0.02 for i in y], tricky, height=h, color="#90C2E7", label="反直觉难题子集增益")
    for i, (o, t, r) in enumerate(zip(overall, tricky, rel)):
        ax.text(o + 0.015, i + h / 2 + 0.02, f"+{o:.3f}（{r}）", va="center", fontsize=10.5,
                color="#1A365D", fontweight="bold")
        ax.text(t + 0.015, i - h / 2 - 0.02, f"+{t:.3f}", va="center", fontsize=10, color="#4A6B8A")
    ax.set_yticks(list(y), names, fontsize=10.5)
    ax.set_xlim(0, 1.28)
    ax.xaxis.set_visible(False)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#CBD5E0")
    ax.legend(loc="lower right", frameon=False, fontsize=11)
    ax.set_title("知识库增益：全部 5 个模型均为正增益（116 题 · method F）",
                 fontsize=14.5, fontweight="bold", color="#1A202C", loc="left", pad=14)
    fig.tight_layout()
    out = os.path.join(BASE, "benchmark", "gain_chart.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out)


if __name__ == "__main__":
    render_graph()
    render_gain()
