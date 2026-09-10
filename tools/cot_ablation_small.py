#!/usr/bin/env python3
"""CoT 消融小实验（P10 结构页实验背书用）。

设计：
- 复用 2026-08-22 全量评测（merged_full_20260822.json, method F）的 selected_nodes——不重新选点，
  每个模型用自己的 8/22 选点记录，消融变量唯一 = 注入是否含思维链（cot 字段）。
- 只抽「选点含 core 节点」的题（CoT 只挂在 core 上；不含 core 的题剥不剥注入内容相同，跑了白跑）。
- L3/L4 分层各抽 15 题（固定种子可复现），共 30 题 × 2 配置 = 60 组答题 + 60 次裁判 / 模型。
- 同题同选点同轮同裁判：with_kb_cot 与 with_kb_no_cot 严格配对。
- 双模型对照（小 vs 大）：Qwen/Qwen3-8B（硅基流动）+ deepseek-chat（官方），验证「CoT 对小模型更有效」。

用法：
    python cot_ablation_small.py --limit 2   # 试跑
    python cot_ablation_small.py             # 全量 30 题 × 2 模型
    python cot_ablation_small.py --analyze   # 只分析已有结果（不调用 API）
"""
import argparse
import json
import os
import random
import re
import time
from collections import defaultdict

from kb_benchmark import JUDGE, load_env, load_nodes_by_ids, load_questions, ask_model, judge_answer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")
MERGED = os.path.join(BASE, "benchmark", "results", "merged_full_20260822.json")
OUT = os.path.join(BASE, "benchmark", "results", "cot_ablation_30.jsonl")

MODEL_CFGS = {
    "Qwen/Qwen3-8B": {"name": "Qwen/Qwen3-8B", "base_url": "https://api.siliconflow.cn/v1", "key_env": "SILICONFLOW_API_KEY"},
    "deepseek-chat": {"name": "deepseek-chat", "base_url": "https://api.deepseek.com", "key_env": "DEEPSEEK_API_KEY"},
}
N_PER_LEVEL = 15
SEED = 42


def core_node_ids():
    import yaml
    ids = set()
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        text = open(os.path.join(NODES_DIR, f), encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        if fm.get("type") == "core":
            ids.add(fm.get("id"))
    return ids


def pick_questions(n_per_level=N_PER_LEVEL, seed=SEED):
    """从 merged_full 取 method F 选点（按模型），筛含 core 的题，L3/L4 分层抽样（题集对所有模型一致）"""
    merged = json.load(open(MERGED, encoding="utf-8"))
    cores = core_node_ids()
    sel = defaultdict(dict)   # sel[model][qid] = selected_nodes
    for r in merged:
        if r.get("method") == "F" and r.get("selected_nodes"):
            sel[r["model"]][r["qid"]] = r["selected_nodes"]

    questions = {q["id"]: q for q in load_questions(
        os.path.join(BASE, "benchmark", "questions_full.json"))}

    # 题集以 8B 的选点为基准抽（两模型用同一批题，便于跨模型对照）
    by_level = defaultdict(list)
    for qid, nids in sel["Qwen/Qwen3-8B"].items():
        if qid in questions and cores & set(nids):
            by_level[questions[qid]["level"]].append(qid)

    rng = random.Random(seed)
    picked = []
    for lv in sorted(by_level):
        pool = sorted(by_level[lv])
        rng.shuffle(pool)
        picked += pool[:n_per_level]
    return [questions[qid] for qid in picked], sel


def analyze(path=OUT):
    """配对分析：no_cot - with_cot 逐题差值（按模型分组）"""
    if not os.path.exists(path):
        print("结果文件不存在:", path)
        return
    idx = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("judge_score", -1) >= 0:
            idx[(r["model"], r["qid"], r["mode"])] = r["judge_score"]
    import statistics as st
    from math import erf
    for model in sorted(set(m for m, _, _ in idx)):
        qids = sorted(set(q for m, q, _ in idx if m == model))
        diffs = []
        for q in qids:
            a = idx.get((model, q, "with_kb_cot"))
            b = idx.get((model, q, "with_kb_no_cot"))
            if a is not None and b is not None:
                diffs.append((q, a, b, b - a))
        if not diffs:
            continue
        vals = [d for _, _, _, d in diffs]
        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        m_, sd, n = st.mean(vals), st.stdev(vals), len(vals)
        if sd == 0:
            print(f"\n[{model}] 配对数 {n}: 配对差全为 0（无效应）")
            continue
        t = m_ / (sd / n ** 0.5)
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / 2 ** 0.5)))
        print(f"\n[{model}] 配对数 {n}")
        print(f"  含CoT {st.mean([a for _, a, _, _ in diffs]):.3f} | 无CoT {st.mean([b for _, _, b, _ in diffs]):.3f}")
        print(f"  配对差(无-含) {m_:+.3f}  median {st.median(vals):+.1f}  sd {sd:.2f}")
        print(f"  去掉CoT变好 {pos} / 变差 {neg} / 持平 {n-pos-neg}")
        print(f"  配对 t = {t:.3f}  p ~= {p:.4f}")


def main():
    load_env()
    for cfg in MODEL_CFGS.values():
        cfg["key"] = os.environ.get(cfg["key_env"], "")

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（试跑）")
    ap.add_argument("--analyze", action="store_true", help="只分析已有结果")
    ap.add_argument("--n", type=int, default=N_PER_LEVEL, help="每层抽题数")
    ap.add_argument("--models", nargs="*", default=list(MODEL_CFGS), help="只跑指定模型")
    args = ap.parse_args()

    if args.analyze:
        analyze()
        return

    questions, sel = pick_questions(args.n)
    print(f"抽出 {len(questions)} 题（8B 选点含 core）: "
          f"L3={sum(1 for q in questions if q['level']==3)} "
          f"L4={sum(1 for q in questions if q['level']==4)}")
    if args.limit:
        questions = questions[: args.limit]

    done = set()
    if os.path.exists(OUT):  # 断点续跑
        for line in open(OUT, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["model"], r["qid"], r["mode"]))
        print(f"已有 {len(done)} 条记录，续跑")

    with open(OUT, "a", encoding="utf-8") as fout:
        for model_name in args.models:
            cfg = MODEL_CFGS[model_name]
            if not cfg.get("key"):
                print(f"[跳过] {model_name}: 无 {cfg['key_env']}")
                continue
            print(f"\n===== {model_name} =====", flush=True)
            for qi, q in enumerate(questions):
                nids = sel[model_name].get(q["id"])
                if not nids:
                    print(f"[{qi+1}] {q['id']} 该模型无选点记录，跳过")
                    continue
                full = load_nodes_by_ids(nids, include_cot=True)
                nocot = load_nodes_by_ids(nids, include_cot=False)
                pre = "你是通信工程专业的学生，请回答下面的问题。\n\n以下是你知识库中与问题相关的知识点：\n"
                for mode, sp in (("with_kb_cot", pre + full), ("with_kb_no_cot", pre + nocot)):
                    if (model_name, q["id"], mode) in done:
                        continue
                    ans = ask_model(cfg, sp, q["question"])
                    rec = {"model": model_name, "mode": mode, "qid": q["id"],
                           "level": q["level"], "question": q["question"],
                           "answer": ans, "selected_nodes": nids,
                           "expected_nodes": q.get("expected_nodes", [])}
                    if ans.startswith("[ERROR]"):
                        rec["judge_score"] = -1
                        rec["judge_comment"] = "调用失败(未打分)"
                    else:
                        j = judge_answer(q["question"], q["answer"], model_name, ans)
                        rec["judge_score"] = j.get("score", -1)
                        rec["judge_comment"] = j.get("comment", "")
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()
                    print(f"[{qi+1}/{len(questions)}] {q['id']} {mode.split('_')[-1]} 分={rec['judge_score']}", flush=True)
                    time.sleep(0.3)

    print("\n=== 汇总 ===")
    analyze()


if __name__ == "__main__":
    main()
