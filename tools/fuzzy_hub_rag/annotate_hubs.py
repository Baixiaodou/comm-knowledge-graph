#!/usr/bin/env python3
"""fuzzy_hub_rag 题库标注：DeepSeek 3 轮独立选 hub + 一致性核对。

用法：
    python annotate_hubs.py            # 全量 20 题 × 3 轮标注
    python annotate_hubs.py --ids F05  # 只标指定题（--limit 1 等价）
    python annotate_hubs.py --draft    # 用已有标注草稿重新核对（不调 API）

输出：results/annotation_draft.json（每轮选择+理由+一致性），打印核对表。
人工复核流程：看 draft 核对表 → 对不一致/可疑的题复核 → 把最终 expected_hubs
写回 questions_fuzzy.json（_meta.annotation.status 改 finalized）。
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import kb  # noqa: E402
from openai import OpenAI  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(HERE, "questions_fuzzy.json")
RESULT = os.path.join(HERE, "results", "annotation_draft.json")

ROUNDS = 3
TEMPERATURE = 0.7


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


ANNOTATE_SYSTEM = (
    "你是知识库结构标注员。知识库是层级树：hub=枝干/大主题模块（一个主题域的总体、"
    "类型、构成、概览），core/leaf=具体知识点。用户问题若是在问「某个主题域里有哪些"
    "内容/类型/方向/工具/关键技术/组成」，它就是一个模糊大问题，应该落到 hub 上。"
    "请为每个问题选出最相关的 1-2 个 hub（覆盖回答该问题最应介绍的主题模块）。"
    "只输出 JSON，不要任何其他文字。"
)

PROMPT_TMPL = (
    "问题：{question}\n\n"
    "知识库 hub 菜单（id 标题：摘要）：\n{menu}\n\n"
    "要求：\n"
    "1. 选出最相关的 1-2 个 hub（用方括号里的 id）；如果问题问的是整个知识体系/全部课程/"
    "学习顺序/没有对应枝干的大范围问题，选 root。\n"
    "2. 跨树问题可以选 2 个不同树的 hub。\n"
    "3. 输出格式：{{\"hubs\": [\"id1\", \"id2\"], \"reason\": \"一句话理由\"}}"
)


def one_round(client, question: str, menu: str) -> dict:
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": ANNOTATE_SYSTEM},
            {"role": "user", "content": PROMPT_TMPL.format(question=question, menu=menu)},
        ],
        temperature=TEMPERATURE,
        max_tokens=200,
    )
    text = (resp.choices[0].message.content or "").strip()
    text = text.strip("```json").strip("```").strip()
    data = json.loads(text)
    hubs = [h for h in data.get("hubs", []) if h]
    if not hubs:
        raise ValueError("empty hubs")
    return {"hubs": hubs, "reason": data.get("reason", "")}


def annotate(ids=None, use_draft=False):
    kb.load()
    menu = kb.hub_menu()
    with open(QUESTIONS, encoding="utf-8") as fh:
        qdata = json.load(fh)
    questions = [q for q in qdata["questions"] if not ids or q["id"] in ids]

    draft = {}
    if use_draft and os.path.exists(RESULT):
        draft = json.load(open(RESULT, encoding="utf-8"))

    if use_draft:
        questions = [q for q in questions if q["id"] in draft.get("rounds", {})]
    else:
        key = load_env()
        if not key:
            print("错误：未找到 DEEPSEEK_API_KEY（tools/.env）")
            sys.exit(1)
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    summary = []
    for q in questions:
        qid = q["id"]
        if not use_draft:
            rounds = []
            for i in range(ROUNDS):
                for attempt in range(3):
                    try:
                        rounds.append(one_round(client, q["question"], menu))
                        break
                    except Exception as e:
                        print(f"  {qid} 第{i + 1}轮失败({attempt + 1}/3): {e}")
                        time.sleep(2)
                else:
                    rounds.append({"hubs": [], "reason": "标注失败"})
                time.sleep(0.5)
            draft.setdefault("rounds", {})[qid] = rounds
            json.dump(draft, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rounds = draft["rounds"][qid]

        # 一致性：多数派
        counter = {}
        for r in rounds:
            key = tuple(r["hubs"])
            counter[key] = counter.get(key, 0) + 1
        best_key, best_n = max(counter.items(), key=lambda kv: kv[1])
        consensus = {
            "hubs": list(best_key),
            "agreement": f"{best_n}/{len(rounds)}",
            "full_agree": best_n == len(rounds),
        }
        summary.append({
            "id": qid,
            "question": q["question"],
            "rounds": [{"hubs": r["hubs"], "reason": r["reason"]} for r in rounds],
            "consensus": consensus,
        })
        flag = "✔" if consensus["full_agree"] else ("◐" if best_n >= 2 else "✘")
        print(f"{flag} {qid} {q['question']}")
        print(f"    轮次: " + " | ".join(f"{','.join(r['hubs'])}" for r in rounds))
        print(f"    多数: {','.join(consensus['hubs'])} ({consensus['agreement']})")
        for r in rounds:
            if tuple(r["hubs"]) != best_key:
                print(f"    异见: {','.join(r['hubs'])} — {r['reason']}")

    draft["summary"] = summary
    json.dump(draft, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n标注草稿已写入 results/annotation_draft.json（{len(summary)} 题）")
    print("下一步：人工复核 → 把定稿 expected_hubs 写回 questions_fuzzy.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", help="只标注指定题（逗号分隔）")
    ap.add_argument("--draft", action="store_true", help="用已有草稿重新核对，不调 API")
    args = ap.parse_args()
    ids = set(args.ids.split(",")) if args.ids else None
    annotate(ids=ids, use_draft=args.draft)
