# -*- coding: utf-8 -*-
"""精确统计 knowledge-v2 当前状态（README 示意图数据源）"""
import json
import re
import sys
import io
import os
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NODES_DIR = os.path.join(KB, "knowledge-v2", "nodes")
TREE_PATH = os.path.join(KB, "knowledge-v2", "_meta", "tree.json")

import yaml

nodes = []
for f in sorted(glob.glob(os.path.join(NODES_DIR, "*.md"))):
    text = open(f, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        continue
    fm = yaml.safe_load(m.group(1)) or {}
    nodes.append({
        "id": fm.get("id", ""),
        "title": fm.get("title", ""),
        "parent": fm.get("parent", ""),
        "type": fm.get("type", "leaf"),
        "cot": fm.get("cot"),
        "links": fm.get("links") or [],
    })

print(f"总节点: {len(nodes)}")
from collections import Counter
tc = Counter(n["type"] for n in nodes)
print(f"类型: core={tc['core']} hub={tc['hub']} leaf={tc['leaf']}")
cot_count = sum(1 for n in nodes if n.get("cot"))
print(f"思维链(cot): {cot_count}")

total_links = sum(len(n["links"]) for n in nodes)
# 跨树 links：link id 前缀 != 当前节点前缀
cross = 0
for n in nodes:
    pre = n["id"].split("-")[0]
    for lk in n["links"]:
        target = lk.get("id") if isinstance(lk, dict) else lk
        if target and target.split("-")[0] != pre:
            cross += 1
print(f"links: {total_links} 条，跨树 {cross} 条")

# 各学科子树（含学科根节点）：parent 链回溯到 depth1
by_id = {n["id"]: n for n in nodes}
root_name = {"comm": "通信原理", "dsp": "信号与系统+DSP", "emf": "电磁场",
             "mob": "移动通信", "net": "计算机网络", "rsp": "随机信号处理"}

def subtree_size(nid):
    n = by_id.get(nid)
    if not n:
        return 0
    return 1 + sum(subtree_size(c["id"]) for c in nodes if c["parent"] == nid)

for pre, name in root_name.items():
    # 找该学科根（id 前缀匹配且 parent 是 root）
    roots = [n for n in nodes if n["id"].startswith(pre + "-") and n["parent"] == "root"]
    if not roots:
        # 电磁场可能没有子节点，根自己 depth1
        roots = [n for n in nodes if n["id"] == pre + "-principles" and n["parent"] == "root"]
    size = sum(subtree_size(r["id"]) for r in roots)
    print(f"  {name}: {size} 个 (根: {[r['id'] for r in roots]})")
