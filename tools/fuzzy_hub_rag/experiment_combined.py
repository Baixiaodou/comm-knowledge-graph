#!/usr/bin/env python3
"""补充实验：LLM 判大小问题 + TF-IDF 粗筛 top-k hub 候选 + LLM 从候选选 1-2 个。

动机：k=2-12 扫描发现含 root 时 TF-IDF 候选召回 k=6 即 100%——TF-IDF 排序够格做
粗筛（S4 的失败在「TF-IDF 分流」前置环节，不在排序本身）。本实验验证：
把分流换成 LLM（97.5% 准），粗筛交给 TF-IDF top-k，选点仍由 LLM 从候选里做，
是否能以更短的输入（候选 6 行 vs 全量 19 行）追平 S5 全量选点的命中率。

用法：../../../../.venv/Scripts/python experiment_combined.py [k1,k2,...]
"""
import json
import os
import re
import sys
import time

from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "strategies"))
from kb import kb
from prompts import ROUTE_SYSTEM, RULE_BLOCK

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # = tools/（.env 所在）
env_path = os.path.join(BASE, ".env")
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
client = OpenAI(api_key=KEY, base_url="https://api.deepseek.com")

kb.load()
qs = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "benchmark", "questions_fuzzy.json"), encoding="utf-8"))["questions"]


def parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def route_with_candidates(q: str, k: int) -> tuple[str, list[str]]:
    cands = [h for h, _ in kb.rank(q, kb.hubs)][:k]
    lines = []
    for h in cands:
        s = f"- {h['id']}: {h['title']}"
        if h.get("summary"):
            s += f"（{h['summary']}）"
        lines.append(s)
    menu = "\n".join(lines)
    user = (
        f"用户问题：{q}\n\n"
        f"{RULE_BLOCK}"
        f"候选主题域（hub）清单（从这些里选）：\n{menu}\n\n"
        '输出 JSON：{"path": "HUB"或"LEAF", "hubs": ["id1", "id2"（最多2个，无则空数组）], "reason": "一句话理由"}'
    )
    reply = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": ROUTE_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.1, max_tokens=200,
    ).choices[0].message.content or ""
    data = parse_json(reply)
    valid = {h["id"] for h in cands}
    hubs = [i for i in data.get("hubs", []) if i in valid][:2]
    path = "hub" if str(data.get("path", "")).upper() == "HUB" and hubs else "leaf"
    return path, hubs


def main():
    ks = [int(x) for x in (sys.argv[1:] or ["4", "6"])]
    results = {}
    for k in ks:
        a_ok = h1 = h2 = h1d = h2d = decided = 0
        details = []
        for q in qs:
            path, picked = route_with_candidates(q["question"], k)
            exp = set(q["expected_hubs"])
            correct = path == "hub" and bool(exp)
            a_ok += 1 if correct else 0
            q_hit1 = q_hit2 = False
            if correct:
                decided += 1
                if picked and picked[0] in exp:
                    h1 += 1; h1d += 1; q_hit1 = True
                if any(p in exp for p in picked):
                    h2 += 1; h2d += 1; q_hit2 = True
            details.append({"id": q["id"], "path": path, "picked": picked, "hit1": q_hit1, "hit2": q_hit2})
        results[k] = {
            "a_acc": a_ok / len(qs), "b_hit1": h1 / len(qs), "b_hit2": h2 / len(qs),
            "b_hit1_decided": h1d / decided if decided else 0,
            "b_hit2_decided": h2d / decided if decided else 0,
            "decided": decided, "llm_calls": len(qs),
        }
        print(f"k={k}: 分类A={a_ok}/20={a_ok/20:.0%}  hit@1={h1}/20={h1/20:.0%}  hit@2={h2}/20={h2/20:.0%}  (判对{decided}题内 hit@2={h2d/decided:.0%})")
    print("\nS5 全量 hub 对照（2026-08-25 快照结论，随库更新会漂移）: A=97.5% hit@1=85% hit@2=90%")
    out = os.path.join(HERE, "results", f"combined_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ks": ks, "results": results}, f, ensure_ascii=False, indent=2)
    print("落盘:", out)


if __name__ == "__main__":
    main()
