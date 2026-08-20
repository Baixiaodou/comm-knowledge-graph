# -*- coding: utf-8 -*-
"""专项分析：负例档(chitchat/D5)的误检/偏离详情"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base\benchmark\results\followup_raw_20260821_001635.json"
d = json.load(open(RAW, encoding="utf-8"))
bi = {(r["did"], r["turn"]): r for r in d["baseline"]}

def hit(r):
    return bool(r["expected"]) and any(n in r["expected"] for n in r["injected"])

print("=== 闲聊档(chitchat) 每轮详情 ===")
for r in d["followup"]:
    if r["dependency"] != "chitchat":
        continue
    b = bi.get((r["did"], r["turn"]), {})
    fu = "带历史" if r.get("is_followup") else "独立"
    status = "✅正确(未注入)" if not r["injected"] else "❌误检(注入了!)"
    print(f"[{r['did']}] t{r['turn']} 判定={fu} {status}")
    print(f"  q: {r['q']}")
    print(f"  followup注入: {r['injected']}  baseline注入: {b.get('injected', [])}")

print("\n=== 新话题档(D5) 每轮详情 ===")
for r in d["followup"]:
    if r["dependency"] != "D5":
        continue
    b = bi.get((r["did"], r["turn"]), {})
    ok = hit(r)
    print(f"[{r['did']}] t{r['turn']} {'✅独立命中' if ok else '❌偏离'} 判定={'带历史' if r.get('is_followup') else '独立'}")
    print(f"  q: {r['q']}")
    print(f"  expected: {r['expected']}")
    print(f"  followup注入: {r['injected']}  baseline注入: {b.get('injected', [])}")
