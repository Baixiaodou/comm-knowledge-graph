# -*- coding: utf-8 -*-
"""校验 multiturn_questions.json：expected_nodes 合法性 + 分档/长度分布"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from collections import Counter

KB = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base"
tree = json.load(open(KB + r"\knowledge-v2\_meta\tree.json", encoding="utf-8"))["nodes"]
data = json.load(open(KB + r"\benchmark\multiturn_questions.json", encoding="utf-8"))

bad = []
all_nodes = set()
for d in data["dialogues"]:
    for t in d["turns"]:
        for n in t["expected"]:
            all_nodes.add(n)
            if n not in tree:
                bad.append((d["id"], n, "NOT_IN_TREE"))
            elif tree[n]["type"] not in ("core", "leaf"):
                bad.append((d["id"], n, tree[n]["type"]))
print("用到的节点数:", len(all_nodes))
print("非法节点(hub/root/不存在):", bad if bad else "无 ✓")

print("\n=== D4 追问详情 ===")
for d in data["dialogues"]:
    for t in d["turns"]:
        if t["dependency"] == "D4":
            print(f"  {d['id']} ({len(t['q'])}字): {t['q']}")

print("\n=== 追问长度分布(不含 first/chitchat/D5) ===")
lens = Counter()
for d in data["dialogues"]:
    for t in d["turns"]:
        if t["dependency"] not in ("first", "chitchat", "D5"):
            if t["dependency"] == "D1":
                lens["D1(≤8字)"] += 1
            elif len(t["q"]) <= 15:
                lens["短(9-15字)"] += 1
            elif len(t["q"]) <= 25:
                lens["中(16-25字)"] += 1
            else:
                lens["长(>25字)"] += 1
print(dict(lens))

print("\n=== 每档样本数(dependency) ===")
dep = Counter(t["dependency"] for d in data["dialogues"] for t in d["turns"])
print(dict(dep))
