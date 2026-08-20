# -*- coding: utf-8 -*-
"""分析 need_history(带历史判定) 与 题库 D1 标注 的重叠度
回答：我们现在是不是只对 D1 带历史？
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base\benchmark\results\followup_raw_20260821_002138.json"
d = json.load(open(RAW, encoding="utf-8"))

# followup 结果里有 is_followup(实际=need_history) 和 dependency(题库标注)
fol = d["followup"]
n_d1 = sum(1 for r in fol if r["dependency"] == "D1")
n_d2 = sum(1 for r in fol if r["dependency"] == "D2")
n_d3 = sum(1 for r in fol if r["dependency"] == "D3")
n_d4 = sum(1 for r in fol if r["dependency"] == "D4")

# 1. D1 中多少被触发带历史（召回）
d1_fu = [r for r in fol if r["dependency"] == "D1" and r.get("is_followup")]
print(f"=== D1 标注轮次: {n_d1} 条，其中 need_history 触发(带历史) {len(d1_fu)} 条 = {len(d1_fu)/n_d1:.1%}")
for r in d1_fu:
    print(f"  ✓ {r['q']}")

d1_nofu = [r for r in fol if r["dependency"] == "D1" and not r.get("is_followup")]
print(f"\n=== D1 标注但 need_history 没触发（漏判）: {len(d1_nofu)} 条")
for r in d1_nofu:
    print(f"  ✗ {r['q']}")

# 2. need_history 触发的轮次里，各档占比（精确率）
fu_all = [r for r in fol if r.get("is_followup")]
print(f"\n=== need_history 触发总数: {len(fu_all)} 条，按题库档位分布 ===")
from collections import Counter
c = Counter(r["dependency"] for r in fu_all)
for dep, n in c.most_common():
    print(f"  {dep}: {n} 条")

# 3. 触发在非 D1 上的具体轮次（可能的误触发）
print("\n=== need_history 触发在非 D1 档的轮次（看是否合理）===")
for r in fu_all:
    if r["dependency"] not in ("D1", "first"):
        print(f"  [{r['dependency']}] {r['q']}  → 注入 {r['injected']}  expected {r['expected']}")
