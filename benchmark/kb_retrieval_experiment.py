#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索层对照实验（论文核心表）

复现 src/plugins/ai_chat/node_retriever.py 的检索层，去掉 LLM gate，
只评「必要证据是否进入候选池」——这是 RAG 的召回上限，纯 CPU，零 API 成本。

流程（与线上一致）：
    TF-IDF cosine（title+summary+content，中文 bigram）
        -> 排除 root/hub，只留 core/leaf
        -> top-K 候选
        -> links 一层扩展（邻居 type 必须 core/leaf）

四组对照：
    A  无图        top-K，不扩展                   候选 = K
    B  随机图      top-K + 随机重连 links 扩展      候选 = K + 邻居
    C  真实图      top-K + 真实 links 扩展          候选 = K + 邻居
    D  等预算无图  top-K'，不扩展                   候选 ≈ B/C 的候选数
    ↑ D 回答审稿人必问的「你只是多看了几个节点而已」

随机图构造：保持每个节点的出度不变，只把边随机重连到其他 core/leaf 节点。
这样 B 与 C 的唯一差异是「边连到谁」，是干净的控制变量。

指标：
    recall      必要证据召回率 = |gold ∩ 候选池| / |gold|
    all_found   必要证据全找齐率（gold ⊆ 候选池）
    pool_size   候选池大小（成本口径）

用法：
    python kb_retrieval_experiment.py                    # 默认 K=3，20 个随机种子
    python kb_retrieval_experiment.py --k 5 --seeds 30
    python kb_retrieval_experiment.py --min-score 0.05   # 复现线上的低分拦截
"""

import os
import re
import sys
import json
import math
import glob
import random
import argparse
import statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# 项目根：兼容两种布局——GitHub 仓库（benchmark/ 在仓库根）与主工作区（知识库研究/benchmark/）
PROJ = os.path.dirname(HERE)
if not os.path.isdir(os.path.join(PROJ, "knowledge-v2", "nodes")):
    PROJ = os.path.dirname(os.path.dirname(HERE))
KB_NODES = os.path.join(PROJ, "knowledge-v2", "nodes")
Q_FILE_V3 = os.path.join(HERE, "v3", "questions_v3_unified.json")  # v3.1 统一题库（162 题）
OUT_DIR = os.path.join(HERE, "v3")
KEEP_TYPES = ("core", "leaf")  # 检索排除 hub/root（与线上一致）


def q_gold(q, gold_field):
    """按口径取 gold 节点集。

    required：gold_required（必要证据，论文正式口径，须人工标注）。
    related ：gold_related ∪ suggested_nodes（相关参考集，预实验口径——
              数字只看相对趋势，不能进论文主表）。
    """
    if gold_field == "required":
        return q.get("gold_required") or []
    return list(dict.fromkeys((q.get("gold_related") or []) + (q.get("suggested_nodes") or [])))


# ---------------- 与线上 node_retriever 完全一致的检索原语 ----------------

def tokenize(text: str) -> list:
    """中文双字 bigram + 英文单词 + 数字（照抄线上实现）"""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    tokens += re.findall(r"\d+", text)
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            tokens.append(seg[i] + seg[i + 1])
    return tokens


def parse_frontmatter(text: str):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return {}, text
    try:
        import yaml
        return (yaml.safe_load(m.group(1)) or {}), text[m.end():]
    except Exception:
        return {}, text


def load_kb(nodes_dir: str):
    """加载节点：返回 (nodes, by_id, idf)"""
    import yaml  # noqa: F401
    nodes = []
    for f in sorted(glob.glob(os.path.join(nodes_dir, "*.md"))):
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        meta, content = parse_frontmatter(text)
        nid = meta.get("id", "")
        if not nid:
            continue
        links = []
        for lk in (meta.get("links") or []):
            if isinstance(lk, dict):
                links.append({"id": lk.get("id", ""), "relation": lk.get("relation", "")})
            else:
                links.append({"id": str(lk), "relation": ""})
        nodes.append({
            "id": nid,
            "title": meta.get("title", nid),
            "type": meta.get("type", "leaf"),
            "summary": meta.get("summary", ""),
            "content": content,
            "links": links,
        })
    by_id = {n["id"]: n for n in nodes}
    # IDF（与线上 _build_idf 一致）
    n = len(nodes)
    df = Counter()
    for node in nodes:
        text = node["title"] + " " + node["summary"] + " " + node["content"]
        for t in set(tokenize(text)):
            df[t] += 1
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}
    # 预计算每个节点的词频与模长（避免每次检索重复分词，提速 ~50x）
    for node in nodes:
        d_tf = Counter(tokenize(node["title"] + " " + node["summary"] + " " + node["content"]))
        node["tf"] = d_tf
        node["tf_norm"] = math.sqrt(
            sum((tf * idf.get(t, 0.0)) ** 2 for t, tf in d_tf.items())
        ) or 1.0
    return nodes, by_id, idf


def rank(query: str, nodes: list, idf: dict):
    """TF-IDF cosine 排序（与线上 _rank 数学等价，用预计算 tf 加速）"""
    q_tf = Counter(tokenize(query))
    q_vec = {t: tf * idf[t] for t, tf in q_tf.items() if t in idf}
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
    scored = []
    for node in nodes:
        dot = 0.0
        for t, tf in node["tf"].items():
            qw = q_vec.get(t)
            if qw:
                dot += qw * tf * idf.get(t, 0.0)
        scored.append((node, dot / (q_norm * node["tf_norm"])))
    scored.sort(key=lambda x: -x[1])
    return scored


# ---------------- 随机图构造（保持出度分布） ----------------

def build_random_graph(by_id: dict, seed: int) -> dict:
    """把每条边随机重连到其他 core/leaf 节点，保持每个节点的出度不变。

    返回 {node_id: [neighbor_id, ...]}，边数与原图相同。
    """
    rnd = random.Random(seed)
    pool = [nid for nid, n in by_id.items() if n["type"] in KEEP_TYPES]
    rand_links = {}
    for nid, node in by_id.items():
        out_deg = len(node["links"])
        if out_deg == 0:
            rand_links[nid] = []
            continue
        # 与真实图一致：只连 core/leaf，排除自身
        cand = [x for x in pool if x != nid]
        if len(cand) <= out_deg:
            rand_links[nid] = cand
        else:
            rand_links[nid] = rnd.sample(cand, out_deg)
    return rand_links


# ---------------- 检索（四组） ----------------

def expand(base, expand_map, by_id):
    """一层 links 扩展（邻居 type 必须 core/leaf），与线上逻辑一致"""
    out = list(base)
    seen = set(base)
    for nid in base:
        for nb in (expand_map or {}).get(nid, []):
            if nb and nb not in seen and nb in by_id and by_id[nb]["type"] in KEEP_TYPES:
                out.append(nb)
                seen.add(nb)
    return out


def retrieve_pool(query, nodes, by_id, idf, k, expand_map=None, min_score=0.0):
    """返回 (候选池 id 列表, top1分数, 是否被低分拦截)"""
    scored = rank(query, nodes, idf)
    knowledge = [(n, s) for n, s in scored if n["type"] in KEEP_TYPES]
    if not knowledge:
        return [], 0.0, True
    top1 = knowledge[0][1]
    if top1 < min_score:
        return [], top1, True
    base = [n["id"] for n, _ in knowledge[:k]]
    return expand(base, expand_map, by_id), top1, False


def expand_pad(base, expand_map, by_id, knowledge, N):
    """一层 links 扩展 + 词面补足到 N（A2 修复：预算公平）。

    图扩展优先，不足 N 时按全局词面排名补足（跳过已在池中的），
    保证候选池恰好 N 个（只要词面排名够长）。B/C 组同样处理，
    唯一差异仍是「边连向谁」。
    """
    out = expand(base, expand_map, by_id)
    if len(out) >= N:
        return out[:N]
    in_pool = set(out)
    for nid in knowledge:
        if nid not in in_pool:
            out.append(nid)
            in_pool.add(nid)
            if len(out) >= N:
                break
    return out


def evaluate(questions, nodes, by_id, idf, real_graph, k, seeds, min_score, d_fixed, gold_field):
    """跑四组对照，返回逐题结果。

    D 组 = 词面 top-d_fixed（固定 N'，A3 修复：不再用 C 组实际池大小
    反推 K'——那是「上帝视角」，审稿人必挑）。
    """
    rand_graphs = [build_random_graph(by_id, s) for s in range(seeds)]

    rows = []
    for q in questions:
        gold = [g for g in q_gold(q, gold_field) if g in by_id]
        if not gold:
            continue
        gset = set(gold)
        rec = {"id": q["id"], "uid": q.get("uid"), "level": q.get("level"), "type": q.get("type"),
               "subject_group": q.get("subject_group"), "n_gold": len(gset)}

        # A 无图
        pa, t1, blocked = retrieve_pool(q["question"], nodes, by_id, idf, k, None, min_score)
        rec["A"] = {"pool": pa, "top1": t1, "blocked": blocked}
        # C 真实图
        pc, _, _ = retrieve_pool(q["question"], nodes, by_id, idf, k, real_graph, min_score)
        rec["C"] = {"pool": pc}
        # D 固定 N' 无图
        pd, _, _ = retrieve_pool(q["question"], nodes, by_id, idf, d_fixed, None, min_score)
        rec["D"] = {"pool": pd}
        # B 随机图（多种子）
        rec["B"] = []
        for rg in rand_graphs:
            pb, _, _ = retrieve_pool(q["question"], nodes, by_id, idf, k, rg, min_score)
            rec["B"].append(pb)

        for grp in ("A", "C", "D"):
            p = rec[grp]["pool"]
            rec[grp]["recall"] = len(gset & set(p)) / len(gset)
            rec[grp]["all_found"] = 1.0 if gset <= set(p) else 0.0
            rec[grp]["pool_size"] = len(p)
        rec["B_agg"] = {"recall": [], "all_found": [], "pool_size": []}
        for p in rec["B"]:
            rec["B_agg"]["recall"].append(len(gset & set(p)) / len(gset))
            rec["B_agg"]["all_found"].append(1.0 if gset <= set(p) else 0.0)
            rec["B_agg"]["pool_size"].append(len(p))
        rows.append(rec)
    return rows, d_fixed


def agg(rows, key):
    """聚合某组指标"""
    if key == "B":
        r = [statistics.mean(x["B_agg"]["recall"]) for x in rows]
        a = [statistics.mean(x["B_agg"]["all_found"]) for x in rows]
        p = [statistics.mean(x["B_agg"]["pool_size"]) for x in rows]
    else:
        r = [x[key]["recall"] for x in rows]
        a = [x[key]["all_found"] for x in rows]
        p = [x[key]["pool_size"] for x in rows]
    return {
        "recall": statistics.mean(r) if r else 0,
        "recall_sd": statistics.pstdev(r) if len(r) > 1 else 0,
        "all_found": statistics.mean(a) if a else 0,
        "pool": statistics.mean(p) if p else 0,
    }


def scan(questions, nodes, by_id, idf, real_graph, k_max, seeds, gold_field):
    """预算扫描：K=1..k_max，看「达到相同召回率所需候选预算」。

    这是论文最有说服力的对比——若图扩展有真实效率优势，
    它应该在更小的候选预算下达到相同召回率。
    性能：每题只做一次 rank，所有 K 值复用排序结果。
    """
    rand_graphs = [build_random_graph(by_id, s) for s in range(seeds)]
    acc = {k: {"A": [], "B": [], "C": [], "pA": [], "pB": [], "pC": []}
           for k in range(1, k_max + 1)}
    for q in questions:
        gset = set(g for g in q_gold(q, gold_field) if g in by_id)
        if not gset:
            continue
        scored = rank(q["question"], nodes, idf)
        knowledge = [n["id"] for n, _ in scored if n["type"] in KEEP_TYPES]
        for k in range(1, k_max + 1):
            base = knowledge[:k]
            # A 无图
            acc[k]["A"].append(len(gset & set(base)) / len(gset))
            acc[k]["pA"].append(len(base))
            # C 真实图
            pc = expand(base, real_graph, by_id)
            acc[k]["C"].append(len(gset & set(pc)) / len(gset))
            acc[k]["pC"].append(len(pc))
            # B 随机图（种子均值）
            r_, p_ = [], []
            for rg in rand_graphs:
                pb = expand(base, rg, by_id)
                r_.append(len(gset & set(pb)) / len(gset))
                p_.append(len(pb))
            acc[k]["B"].append(statistics.mean(r_))
            acc[k]["pB"].append(statistics.mean(p_))
    return [{"k": k,
             "A": {"recall": statistics.mean(acc[k]["A"]), "pool": statistics.mean(acc[k]["pA"])},
             "B": {"recall": statistics.mean(acc[k]["B"]), "pool": statistics.mean(acc[k]["pB"])},
             "C": {"recall": statistics.mean(acc[k]["C"]), "pool": statistics.mean(acc[k]["pC"])}}
            for k in range(1, k_max + 1)]


def budget_for(scan_rows, key, target):
    """达到 target 召回率所需的最小候选预算（线性插值）"""
    prev = None
    for r in scan_rows:
        if r[key]["recall"] >= target:
            if prev is None:
                return r["k"], r[key]["pool"], r[key]["recall"]
            # 在 prev 与 r 之间插值
            r0, r1 = prev[key]["recall"], r[key]["recall"]
            p0, p1 = prev[key]["pool"], r[key]["pool"]
            w = (target - r0) / (r1 - r0) if r1 > r0 else 0
            return None, p0 + w * (p1 - p0), target
        prev = r
    return None, None, None


def strict_budget(questions, nodes, by_id, idf, real_graph, budgets, ks, seeds, gold_field):
    """严格等预算对照：所有组的候选数完全相同（硬 N + 词面补足）。

    这是回答审稿人「你只是多看了几个节点」的最严格设计——
    候选数一眼可查，唯一差异是这 N 个候选怎么选出来。
    A2 修复：C/B 组图扩展不足 N 时用词面补足（expand_pad），预算公平。
    每题只做一次 rank，所有 (N, k) 组合复用。
    """
    rand_graphs = [build_random_graph(by_id, s) for s in range(seeds)]
    table = []
    for N in budgets:
        ks_ok = [k for k in sorted(ks) if k <= N]
        recA, poolA = [], []
        recC = {k: [] for k in ks_ok}
        recB = {k: [] for k in ks_ok}
        poolC = {k: [] for k in ks_ok}
        for q in questions:
            gset = set(g for g in q_gold(q, gold_field) if g in by_id)
            if not gset:
                continue
            scored = rank(q["question"], nodes, idf)
            knowledge = [n["id"] for n, _ in scored if n["type"] in KEEP_TYPES]
            pa = knowledge[:N]
            recA.append(len(gset & set(pa)) / len(gset))
            poolA.append(len(pa))
            for k in ks_ok:
                base = knowledge[:k]
                pc = expand_pad(base, real_graph, by_id, knowledge, N)
                recC[k].append(len(gset & set(pc)) / len(gset))
                poolC[k].append(len(pc))
                rb = []
                for rg in rand_graphs:
                    pb = expand_pad(base, rg, by_id, knowledge, N)
                    rb.append(len(gset & set(pb)) / len(gset))
                recB[k].append(statistics.mean(rb))
        table.append({
            "N": N,
            "A": statistics.mean(recA) if recA else 0,
            "A_pool": statistics.mean(poolA) if poolA else 0,
            "C": {k: statistics.mean(v) for k, v in recC.items()},
            "B": {k: statistics.mean(v) for k, v in recB.items()},
            "C_pool": {k: statistics.mean(v) for k, v in poolC.items()},
        })
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3, help="TF-IDF 初筛 top-K（线上 node_candidate_k=3）")
    ap.add_argument("--seeds", type=int, default=20, help="随机图种子数")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="初筛下限（线上 0.05；默认 0 不拦截，聚焦扩展效果）")
    ap.add_argument("--scan", type=int, default=0, help="预算扫描的最大 K（如 15），0=不扫描")
    ap.add_argument("--strict", default="5,8,10,12,15",
                    help="严格等预算的候选数 N 列表（逗号分隔），空串则跳过")
    ap.add_argument("--strict-ks", default="1,2,3", help="严格等预算的起始种子数 k 列表")
    ap.add_argument("--d-fixed", type=int, default=8,
                    help="主表 D 组固定 N'（词面 top-N'，A3：不再插值）")
    ap.add_argument("--gold-field", choices=["required", "related"], default="required",
                    help="gold 口径：required=必要证据（正式）；related=相关参考集（预实验，趋势参考）")
    ap.add_argument("--md", default=None, help="输出 Markdown 报告路径")
    args = ap.parse_args()

    nodes, by_id, idf = load_kb(KB_NODES)
    n_keep = sum(1 for n in nodes if n["type"] in KEEP_TYPES)

    d = json.load(open(Q_FILE_V3, encoding="utf-8"))
    questions = d["questions"] if isinstance(d, dict) else d
    all_q = len(questions)
    questions = [q for q in questions if any(g in by_id for g in q_gold(q, args.gold_field))]
    gold_tag = ("必要证据 gold_required（正式口径）" if args.gold_field == "required"
                else "gold_related ∪ suggested_nodes（预实验口径，仅看趋势）")
    if not questions:
        raise SystemExit(
            f"[错误] 0 道题可用（gold 口径={args.gold_field}）。"
            + ("gold_required 尚未人工标注，请用 --gold-field related 先跑预实验。" 
               if args.gold_field == "required" else "请检查题库文件。"))

    real_graph = {n["id"]: [l["id"] for l in n["links"] if l["id"]] for n in nodes}

    rows, d_fixed = evaluate(questions, nodes, by_id, idf, real_graph, args.k, args.seeds,
                             args.min_score, args.d_fixed, args.gold_field)

    A, B, C, D = (agg(rows, g) for g in ("A", "B", "C", "D"))
    n = len(rows)
    blocked = sum(1 for x in rows if x["A"]["blocked"])

    L = []
    P = L.append
    P("# 检索层对照实验结果")
    P("")
    P(f"- 知识库：{len(nodes)} 节点（可检索 core/leaf {n_keep} 个，hub/root 已排除）")
    P(f"- 题目：{n} / {all_q} 道（v3.1 统一题库；gold 口径：{gold_tag}）")
    P(f"- 参数：top-K = {args.k}；D 组固定 N' = {d_fixed}；随机图种子 = {args.seeds}")
    if args.gold_field == "related":
        P("- **【预实验】**本表用相关参考集当 gold，召回率系统性偏高，只用于看组间相对趋势；")
        P("  正式主表须等 gold_required 人工标注完成后用 `--gold-field required` 重跑。")
    P(f"- 初筛下限 min_score = {args.min_score}"
      + ("（复现线上拦截）" if args.min_score > 0 else "（不拦截，聚焦扩展效果）"))
    if blocked:
        P(f"- 【注意】有 {blocked} 道题因 top-1 分数低于下限而整体跳过注入")
    P("")
    P("## 主表")
    P("")
    P("| 组 | 检索方式 | 候选池大小 | 必要证据召回率 | 全找齐率 |")
    P("|---|---|---|---|---|")
    P(f"| A | TF-IDF top-{args.k}，无扩展 | {A['pool']:.1f} | {A['recall']:.1%} | {A['all_found']:.1%} |")
    P(f"| B | top-{args.k} + **随机图**扩展（{args.seeds} 种子均值） | {B['pool']:.1f} | {B['recall']:.1%} | {B['all_found']:.1%} |")
    P(f"| C | top-{args.k} + **真实图**扩展 | {C['pool']:.1f} | {C['recall']:.1%} | {C['all_found']:.1%} |")
    P(f"| D | TF-IDF top-{d_fixed}（固定 N'），无扩展 | {D['pool']:.1f} | {D['recall']:.1%} | {D['all_found']:.1%} |")
    P("")
    P("**关键对比**：")
    P(f"- 真实图 vs 随机图：{C['recall'] - B['recall']:+.1%}（同样多的边，只差「连向谁」）")
    P(f"- 真实图 vs 无图：{C['recall'] - A['recall']:+.1%}")
    P(f"- 真实图 vs 等预算无图：{C['recall'] - D['recall']:+.1%}（回答「只是多看了几个节点」）")
    P("")

    # 分层
    for dim, label in (("level", "难度"), ("type", "题型")):
        P(f"## 按{label}分层（召回率）")
        P("")
        groups = defaultdict(list)
        for x in rows:
            groups[x[dim]].append(x)
        P(f"| {label} | 题数 | A 无图 | B 随机图 | C 真实图 | D 等预算 | C-B |")
        P("|---|---|---|---|---|---|---|")
        for kk in sorted(groups, key=lambda z: (str(type(z)), z)):
            g = groups[kk]
            a_, b_, c_, d_ = (agg(g, x) for x in ("A", "B", "C", "D"))
            P(f"| {kk} | {len(g)} | {a_['recall']:.1%} | {b_['recall']:.1%} | "
              f"{c_['recall']:.1%} | {d_['recall']:.1%} | {c_['recall'] - b_['recall']:+.1%} |")
        P("")

    # 跨学科 vs 单学科
    P("## 按是否跨学科分层（召回率）")
    P("")
    P("| 类别 | 题数 | A 无图 | B 随机图 | C 真实图 | D 等预算 | C-B |")
    P("|---|---|---|---|---|---|---|")
    P("")
    cross, single = [], []
    for x in rows:
        subj = x.get("subject_group") or ""
        (cross if x.get("type") == "relation" or subj == "cross" else single).append(x)
    P("| 类别 | 题数 | A 无图 | B 随机图 | C 真实图 | D 等预算 | C-B |")
    P("|---|---|---|---|---|---|---|")
    for nm, g in (("跨学科(cross/relation)", cross), ("单学科", single)):
        if not g:
            continue
        a_, b_, c_, d_ = (agg(g, x) for x in ("A", "B", "C", "D"))
        P(f"| {nm} | {len(g)} | {a_['recall']:.1%} | {b_['recall']:.1%} | "
          f"{c_['recall']:.1%} | {d_['recall']:.1%} | {c_['recall'] - b_['recall']:+.1%} |")
    P("")

    # 失败案例
    P("## 真实图未命中案例（gold 完全不在候选池）")
    P("")
    fails = [x for x in rows if x["C"]["recall"] == 0]
    P(f"共 {len(fails)} 道（占 {len(fails)/max(n,1):.0%}）：")
    P("")
    for x in fails[:15]:
        P(f"- `{x['id']}` (L{x['level']}/{x['type']}, gold={x['n_gold']})")
    if len(fails) > 15:
        P(f"- ...另 {len(fails) - 15} 道")
    P("")

    # 预算扫描
    scan_rows = []
    if args.scan and args.scan > 1:
        scan_rows = scan(questions, nodes, by_id, idf, real_graph, args.scan, args.seeds, args.gold_field)
        P(f"## 预算扫描（K = 1..{args.scan}）")
        P("")
        P("「候选预算」= 交给下游精选的候选节点数。若图扩展有真实效率优势，")
        P("它应在**更小的候选预算**下达到相同召回率。")
        P("")
        P("| K | A 无图 候选/召回 | B 随机图 候选/召回 | C 真实图 候选/召回 |")
        P("|---|---|---|---|")
        for r in scan_rows:
            P(f"| {r['k']} | {r['A']['pool']:.1f} / {r['A']['recall']:.1%} | "
              f"{r['B']['pool']:.1f} / {r['B']['recall']:.1%} | "
              f"{r['C']['pool']:.1f} / {r['C']['recall']:.1%} |")
        P("")
        P("### 达到目标召回率所需的候选预算")
        P("")
        P("| 目标召回率 | A 无图 | B 随机图 | C 真实图 | D 等预算无图 |")
        P("|---|---|---|---|---|")
        scanD = [{"k": r["k"], "D": {"recall": r["A"]["recall"], "pool": r["k"]}} for r in scan_rows]
        for tgt in (0.80, 0.85, 0.90, 0.92):
            cells = []
            for key, src in (("A", scan_rows), ("B", scan_rows), ("C", scan_rows), ("D", scanD)):
                _, pool, _ = budget_for(src, key, tgt)
                cells.append("未达到" if pool is None else f"{pool:.1f}")
            P(f"| {tgt:.0%} | " + " | ".join(cells) + " |")
        P("")
        P("> 阅读方式：若「C 真实图」列的数字明显小于「D 等预算无图」列，")
        P("> 说明图扩展能用更少的候选预算达到同样召回率（真实效率优势）；")
        P("> 若两列接近，说明在小规模知识库上图扩展无效率优势。")
        P("")

    # 严格等预算对照
    strict_rows = []
    if args.strict:
        budgets = [int(x) for x in args.strict.split(",") if x.strip()]
        sks = [int(x) for x in args.strict_ks.split(",") if x.strip()]
        strict_rows = strict_budget(questions, nodes, by_id, idf, real_graph, budgets, sks, args.seeds, args.gold_field)
        P("## 严格等预算对照（三组候选数完全相同）")
        P("")
        P("所有组硬截断到相同候选数 N，唯一差异是「这 N 个怎么选出来」。")
        P("这是回答「你只是多看了几个节点」的最直接证据。")
        P("")
        for r in strict_rows:
            ks_ok = sorted(r["C"].keys())
            hdr = "| 组 | " + " | ".join(f"k={k}" for k in ks_ok) + " |"
            P(f"**候选预算 N = {r['N']}**（A 组实际候选 {r['A_pool']:.0f}）")
            P("")
            P(hdr)
            P("|---" * (len(ks_ok) + 1) + "|")
            P("| A 无图（纯词面 top-N） | " + " | ".join([f"{r['A']:.1%}"] * len(ks_ok)) + " |")
            P("| C 真实图扩展 | " + " | ".join(f"{r['C'][k]:.1%}" for k in ks_ok) + " |")
            P("| B 随机图扩展 | " + " | ".join(f"{r['B'][k]:.1%}" for k in ks_ok) + " |")
            P("| *C − A* | " + " | ".join(f"{r['C'][k] - r['A']:+.1%}" for k in ks_ok) + " |")
            P("| *C − B* | " + " | ".join(f"{r['C'][k] - r['B'][k]:+.1%}" for k in ks_ok) + " |")
            P("")
        P("> 阅读方式：`C − A` 为正 = 同样 N 个候选，用图扩展选出来的更准；")
        P("> `C − B` 为正 = 收益来自边的语义质量，而非「多连了几条边」。")
        P("")

    out = "\n".join(L)
    print(out)
    md_path = args.md or os.path.join(OUT_DIR, "检索层实验结果.md")
    with open(md_path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"\n[已写入] {md_path}")

    raw_path = os.path.join(OUT_DIR, "检索层实验_raw.json")
    with open(raw_path, "w", encoding="utf-8", newline="") as f:
        json.dump({"config": vars(args), "summary":
                   {"A": A, "B": B, "C": C, "D": D},
                   "scan": scan_rows,
                   "strict": strict_rows,
                   "rows": rows},
                  f, ensure_ascii=False, indent=1)
    print(f"[已写入] {raw_path}")


if __name__ == "__main__":
    main()
