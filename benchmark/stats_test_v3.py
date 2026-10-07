#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索层统计检验（v3 修正 gold 口径，零成本）

对主表口径（top-3 池）与严格等预算口径做配对检验：
    C−A  真实图 vs 纯词面
    C−D  真实图 vs 等预算词面 top-8（回答「只是多看了节点」）
    C−B  真实图 vs 随机图（回答「边的语义质量」）
    严格等预算 N=5/8/10/12/15 的 C−A（k=1/2/3，逐题重算，与主实验同种子同配置）

方法（无 scipy 依赖，全部可复算）：
    1) 配对 bootstrap（10000 次）95% CI
    2) 符号翻转置换检验（10000 次 Monte Carlo）双侧 p
    3) Wilcoxon 符号秩（正态近似 + 结校正）双侧 p
B 组取每题 50 种子的均值后再配对（与主表口径一致）。

用法：.venv/Scripts/python.exe stats_test_v3.py
输出：v3/统计检验结果_required口径.md
"""

import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kb_retrieval_experiment import (  # noqa: E402
    load_kb, rank, expand_pad, build_random_graph, KB_NODES, Q_FILE_V3, KEEP_TYPES, q_gold)

V3 = os.path.join(HERE, "v3")
N_BOOT = 10000
N_PERM = 10000
SEED = 42
SEEDS = 50
STRICT_NS = (5, 8, 10, 12, 15)
STRICT_KS = (1, 2, 3)


def boot_ci(diffs, rng):
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(N_BOOT))
    return means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT)]


def perm_p(diffs, rng):
    """符号翻转置换：H0 = 配对差分布关于 0 对称"""
    obs = abs(statistics.mean(diffs))
    n = len(diffs)
    hit = 0
    for _ in range(N_PERM):
        s = sum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(s / n) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (N_PERM + 1)


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilcoxon_p(diffs):
    """Wilcoxon 符号秩，双侧，正态近似 + 结校正（零差剔除）"""
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n < 5:
        return None, n
    ranked = sorted((abs(x), i) for i, x in enumerate(d))
    ranks = [0.0] * n
    i = 0
    tie_terms = []
    while i < n:
        j = i
        while j < n and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + j - 1) / 2 + 1
        tie_terms.append((j - i) ** 3 - (j - i))
        for k in range(i, j):
            ranks[ranked[k][1]] = avg
        i = j
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(tie_terms) / 48
    if var <= 0:
        return None, n
    z = (w_plus - mean) / math.sqrt(var)
    return 2 * norm_sf(abs(z)), n


def fmt(name, diffs, rng):
    lo, hi = boot_ci(diffs, rng)
    p_perm = perm_p(diffs, rng)
    p_w, n_eff = wilcoxon_p(diffs)
    pos = sum(1 for x in diffs if x > 0)
    neg = sum(1 for x in diffs if x < 0)
    tie = len(diffs) - pos - neg
    sig = "✅ 显著为正" if (p_perm < 0.05 and lo > 0) else (
        "❌ 显著为负" if (p_perm < 0.05 and hi < 0) else "➖ 不显著")
    pw = f"{p_w:.4f}" if p_w is not None else "—"
    return (f"| {name} | {statistics.mean(diffs)*100:+.1f} | [{lo*100:+.1f}, {hi*100:+.1f}] | "
            f"{p_perm:.4f} | {pw} (n′={n_eff}) | +{pos}/−{neg}/={tie} | {sig} |")


def strict_rows(questions, nodes, by_id, idf, real_graph):
    """重算严格等预算的逐题 C−A（与 kb_retrieval_experiment 同配置同种子）"""
    rand_graphs = [build_random_graph(by_id, s) for s in range(SEEDS)]
    out = {N: {k: [] for k in STRICT_KS} for N in STRICT_NS}
    for q in questions:
        gset = set(g for g in q_gold(q, "required") if g in by_id)
        if not gset:
            continue
        scored = rank(q["question"], nodes, idf)
        knowledge = [n["id"] for n, _ in scored if n["type"] in KEEP_TYPES]
        for N in STRICT_NS:
            pa = knowledge[:N]
            a = len(gset & set(pa)) / len(gset)
            for k in STRICT_KS:
                pc = expand_pad(knowledge[:k], real_graph, by_id, knowledge, N)
                out[N][k].append(len(gset & set(pc)) / len(gset) - a)
    return out


def main():
    raw = json.load(open(os.path.join(V3, "检索层实验_raw.json"), encoding="utf-8"))
    rows = raw["rows"]
    assert raw["config"]["gold_field"] == "required" and raw["config"]["seeds"] == SEEDS

    nodes, by_id, idf = load_kb(KB_NODES)
    d = json.load(open(Q_FILE_V3, encoding="utf-8"))
    questions = [q for q in d["questions"] if any(g in by_id for g in q_gold(q, "required"))]
    real_graph = {n["id"]: [l["id"] for l in n["links"] if l["id"]] for n in nodes}

    rng = random.Random(SEED)
    L = ["# 检索层统计检验（v3.2 修正 gold，162 题）", "",
         f"- 方法：配对 bootstrap {N_BOOT} 次 95% CI ＋ 符号翻转置换 {N_PERM} 次（双侧 p）",
         "  ＋ Wilcoxon 符号秩（正态近似+结校正；零差剔除后记 n′）",
         "- 数据：`检索层实验_raw.json`（池口径）＋ strict 逐题差按同种子同配置重算",
         "- random.seed=42，全部可复算", "",
         "## 主表口径（池大小不强制相等）", "",
         "| 对照 | 平均差(pp) | bootstrap 95% CI | 置换 p | Wilcoxon p | 正/负/平 | 判定 |",
         "|---|---|---|---|---|---|---|"]
    ca = [r["C"]["recall"] - r["A"]["recall"] for r in rows]
    cd = [r["C"]["recall"] - r["D"]["recall"] for r in rows]
    cb = [r["C"]["recall"] - statistics.mean(r["B_agg"]["recall"]) for r in rows]
    L.append(fmt("C − A（真实图 vs 词面 top-3）", ca, rng))
    L.append(fmt("C − D（真实图 vs 等预算词面 top-8）", cd, rng))
    L.append(fmt("C − B（真实图 vs 随机图）", cb, rng))
    L.append("")
    L.append("## 严格等预算口径（候选数硬相等，C−A）")
    L.append("")
    L.append("| N | k | 平均差(pp) | bootstrap 95% CI | 置换 p | Wilcoxon p | 正/负/平 | 判定 |")
    L.append("|---|---|---|---|---|---|---|---|")
    st = strict_rows(questions, nodes, by_id, idf, real_graph)
    for N in STRICT_NS:
        for k in STRICT_KS:
            L.append(fmt(f"N={N}", st[N][k], rng).replace("| N=" + str(N) + " |",
                                                         f"| N={N} | k={k} |", 1))
    L += ["", "> 主表 C−D 的零差题占比高（预算对齐后多数题两组都满分），Wilcoxon 的 n′ 小、",
          "> p 值偏保守；以 bootstrap CI 与置换 p 为主要判据，Wilcoxon 作参考。"]
    out = "\n".join(L)
    print(out)
    path = os.path.join(V3, "统计检验结果_required口径.md")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"\n[已写入] {path}")


if __name__ == "__main__":
    main()
