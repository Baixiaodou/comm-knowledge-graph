# -*- coding: utf-8 -*-
"""自测：followup_rag.py 插件 与 eval_followup.py 内联 current 逻辑 判定一致性"""
import json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import eval_followup as ef
from multiturn_rag.followup_rag import FollowupRAG

plugin = FollowupRAG(tech_re=ef.TECH_RE)

with open(ef.QUESTIONS_PATH, encoding="utf-8") as f:
    data = json.load(f)

diff_nh = diff_skip = 0
total = 0
for d in data["dialogues"]:
    prev_q = None
    for t in d["turns"]:
        q = t["q"]
        total += 1
        # need_history 一致性
        a = ef.need_history(q, prev_q, "current")
        b = plugin.need_history(q, prev_q)
        if a != b:
            diff_nh += 1
            print(f"[need_history 不一致] {d['id']} t:{t['dependency']} q={q}  内联={a} 插件={b}")
        # should_skip 一致性
        a2 = ef.is_chitchat(q, prev_q, "current")
        b2 = plugin.should_skip(q, prev_q)
        if a2 != b2:
            diff_skip += 1
            print(f"[should_skip 不一致] {d['id']} t:{t['dependency']} q={q}  内联={a2} 插件={b2}")
        prev_q = q

print(f"\n总轮次: {total}")
print(f"need_history 不一致: {diff_nh}  (应=0)")
print(f"should_skip 不一致: {diff_skip}  (应=0)")
print("结论:", "✅ 插件与评测内联逻辑完全一致" if diff_nh == 0 and diff_skip == 0 else "❌ 有差异，需修复")

# 附：插件独立跑一遍判定统计（不调 gate，纯判定 sanity）
from collections import Counter
c = Counter()
prev_q = None
for d in data["dialogues"]:
    for t in d["turns"]:
        q = t["q"]
        if plugin.should_skip(q, prev_q):
            c["skip(闲聊)"] += 1
        elif plugin.need_history(q, prev_q):
            c["need_history(带历史)"] += 1
        else:
            c["独立检索"] += 1
        prev_q = q
print("\n插件判定分布(全题库):", dict(c))
