# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base\benchmark\results\followup_raw_20260820_233238.json"
d = json.load(open(RAW, encoding="utf-8"))
bi = {(r["did"], r["turn"]): r for r in d["baseline"]}

def hit(r):
    return bool(r["expected"]) and any(n in r["expected"] for n in r["injected"])

print("=== v1.1 负增益轮次 (baseline命中 但 followup未命中) ===")
for r in d["followup"]:
    key = (r["did"], r["turn"])
    b = bi.get(key)
    if not b:
        continue
    if hit(b) and not hit(r):
        print(f"[{r['did']}] t{r['turn']} dep={r['dependency']} fu={r.get('is_followup')}")
        print(f"  q: {r['q']}")
        print(f"  base={b['injected']}  fol={r['injected']}  exp={r['expected']}")
        print()

print("=== v1.1 正增益轮次 ===")
for r in d["followup"]:
    key = (r["did"], r["turn"])
    b = bi.get(key)
    if not b:
        continue
    if not hit(b) and hit(r):
        print(f"[{r['did']}] t{r['turn']} dep={r['dependency']} fu={r.get('is_followup')}")
        print(f"  q: {r['q']}")
        print(f"  base={b['injected']}  fol={r['injected']}  exp={r['expected']}")
        print()
