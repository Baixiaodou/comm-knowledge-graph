#!/usr/bin/env python3
"""fuzzy_hub_rag 专项 benchmark：大小点分类 + hub 选点精准度 + LLM 成本。

Part A（40 题）：20 模糊大问题（期望 hub）+ 从 questions_full.json 固定 seed 抽 20 题（期望 leaf/core）
    → 混淆矩阵 + 分类准确率
Part B（仅 20 模糊题）：策略判 hub 时，选中的 hub 是否命中标注的 expected_hubs
    → hub_recall（敢不敢判 hub）/ hit@1 / hit@2
成本：40 题触发的 LLM 额外调用次数（S1=0 基线，S5=40 上界）

用法：
    python fuzzy_benchmark.py --once 0.06 0.03        # 指定 floor/margin 冒烟
    python fuzzy_benchmark.py --grid                   # 阈值网格调优（默认）
    python fuzzy_benchmark.py --strategies S1,S3 --grid
结果落盘 results/experiment_<ts>.json，控制台出对比表。
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import kb, json_load, QUESTIONS_FULL  # noqa: E402
from strategies import make_strategies  # noqa: E402
from openai import OpenAI  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FUZZY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "benchmark", "questions_fuzzy.json")
RESULT_DIR = os.path.join(HERE, "results")

GRID_FLOOR = [0.03, 0.06, 0.09]
GRID_MARGIN = [0.0, 0.03, 0.06]
CTRL_SEED = 42
CTRL_COUNT = 20


def load_env():
    env_path = os.path.join(BASE, "tools", ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    return os.environ.get("DEEPSEEK_API_KEY", "")


def build_questions():
    """40 题：20 模糊（expected path=hub）+ 20 对照组（expected path=leaf）"""
    fuzzy = json_load(QUESTIONS_FUZZY)["questions"]
    fuzzy_set = [{
        "id": q["id"], "question": q["question"],
        "path": "hub", "expected": q["expected_hubs"],
    } for q in fuzzy]
    full = json_load(QUESTIONS_FULL)["questions"]
    rng = random.Random(CTRL_SEED)
    ctrl = rng.sample(full, CTRL_COUNT)
    ctrl_set = [{
        "id": q["id"], "question": q["question"],
        "path": "leaf", "expected": [],
    } for q in ctrl]
    return fuzzy_set + ctrl_set


def eval_strategy(strategy, questions):
    """跑 40 题，返回指标。questions 每项 {"id","question","path","expected"}"""
    a = {"hub_hub": 0, "hub_leaf": 0, "leaf_hub": 0, "leaf_leaf": 0}
    b = {"hub_decided": 0, "hit1": 0, "hit2": 0, "details": []}
    for q in questions:
        path, hub_ids = strategy.route(q["question"])
        if q["path"] == "hub":
            if path == "hub":
                a["hub_hub"] += 1
                b["hub_decided"] += 1
                hit1 = bool(hub_ids) and hub_ids[0] in q["expected"]
                hit2 = bool(set(hub_ids) & set(q["expected"]))
                b["hit1"] += hit1
                b["hit2"] += hit2
                b["details"].append({
                    "id": q["id"], "question": q["question"],
                    "expected": q["expected"], "picked": hub_ids,
                    "hit1": hit1, "hit2": hit2,
                })
            else:
                a["hub_leaf"] += 1
                b["details"].append({
                    "id": q["id"], "question": q["question"],
                    "expected": q["expected"], "picked": [],
                    "note": "判为 leaf（Part A 错误，Part B 不计 hit）",
                })
        else:
            if path == "hub":
                a["leaf_hub"] += 1
                b["details"].append({
                    "id": q["id"], "question": q["question"],
                    "expected": [], "picked": hub_ids,
                    "note": "对照组误判为 hub（应走 leaf）",
                })
            else:
                a["leaf_leaf"] += 1
    total = sum(a.values())
    return {
        "confusion": a,
        "a_acc": (a["hub_hub"] + a["leaf_leaf"]) / total,
        "b_hub_recall": b["hub_decided"] / 20,
        "b_hit1": b["hit1"] / 20,          # 分母固定 20（未判 hub 的题算 miss）
        "b_hit2": b["hit2"] / 20,
        "b_hit1_decided": b["hit1"] / max(1, b["hub_decided"]),
        "b_hit2_decided": b["hit2"] / max(1, b["hub_decided"]),
        "llm_calls": strategy.llm_calls,
        "details": b["details"],
    }


def run_one(strategy_cls, questions, client, floor, margin, use_llm):
    strategy = strategy_cls(kb, client=client, floor=floor, margin=margin)
    metrics = eval_strategy(strategy, questions)
    metrics.update({"floor": floor, "margin": margin, "strategy": strategy.name})
    return strategy, metrics


def pick_best(results):
    """最优参数：Part A 准确率优先 → hit@2 其次 → 调用次数最少"""
    return max(results, key=lambda r: (r["a_acc"], r["b_hit2"], -r["llm_calls"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", nargs=2, type=float, metavar=("FLOOR", "MARGIN"),
                    help="只跑一组参数（冒烟）")
    ap.add_argument("--grid", action="store_true", help="阈值网格调优（默认）")
    ap.add_argument("--strategies", default="", help="逗号分隔，如 S1,S3（默认全部）")
    args = ap.parse_args()

    kb.load()
    questions = build_questions()
    names = [s.strip().upper() for s in args.strategies.split(",") if s.strip()]

    from strategies import ALL
    classes = [c for c in ALL if not names or c.name in names]
    grid = [(f, m) for f in GRID_FLOOR for m in GRID_MARGIN] if args.grid or not args.once \
        else [(args.once[0], args.once[1])]
    need_llm = any(c.name in ("S2", "S3", "S4", "S5") for c in classes)
    client = None
    if need_llm:
        key = load_env()
        if not key:
            print("错误：未找到 DEEPSEEK_API_KEY")
            sys.exit(1)
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    report = {"questions": build_questions_for_report(), "runs": [], "best": {}}
    rows = []
    for cls in classes:
        results = []
        # S5 全 LLM 判定与 floor/margin 无关，只跑一组（省调用）
        cls_grid = [(0.0, 0.0)] if cls.name == "S5" else grid
        for floor, margin in cls_grid:
            _s, metrics = run_one(cls, questions, client, floor, margin, need_llm)
            results.append(metrics)
            report["runs"].append(metrics)
            json.dump(report, open(os.path.join(RESULT_DIR, "experiment_latest.json"), "w",
                                   encoding="utf-8"), ensure_ascii=False, indent=2)
            c = metrics["confusion"]
            print(f"{cls.name} floor={floor:.2f} margin={margin:.2f} | "
                  f"A={metrics['a_acc']:.2%} ({c['hub_hub']}H→H/{c['hub_leaf']}H→L/"
                  f"{c['leaf_hub']}L→H/{c['leaf_leaf']}L→L) | "
                  f"B_recall={metrics['b_hub_recall']:.0%} hit1={metrics['b_hit1']:.0%} "
                  f"hit2={metrics['b_hit2']:.0%} | llm={metrics['llm_calls']}")
            time.sleep(0.3)
        best = pick_best(results)
        report["best"][cls.name] = best
        rows.append(best)
        print()

    # 对比表
    print("=" * 100)
    print(f"{'策略':6s} {'floor':>6s} {'margin':>7s} {'A准确率':>8s} {'hub误判':>7s} "
          f"{'leaf误判':>8s} {'B召回':>6s} {'hit@1':>6s} {'hit@2':>6s} {'LLM调用':>7s}")
    for r in sorted(rows, key=lambda x: -x["a_acc"]):
        c = r["confusion"]
        print(f"{r['strategy']:6s} {r['floor']:6.2f} {r['margin']:7.2f} "
              f"{r['a_acc']:8.2%} {c['hub_leaf']:7d} {c['leaf_hub']:8d} "
              f"{r['b_hub_recall']:6.0%} {r['b_hit1']:6.0%} {r['b_hit2']:6.0%} "
              f"{r['llm_calls']:7d}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULT_DIR, f"experiment_{ts}.json")
    json.dump(report, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n完整结果：{path}")
    print("（含每题选点明细 details，best 为每策略最优参数）")


def build_questions_for_report():
    return build_questions()


if __name__ == "__main__":
    main()
