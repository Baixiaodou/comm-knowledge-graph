#!/usr/bin/env python3
"""从 knowledge-v2/nodes/*.md 的 frontmatter 自动生成 tree.json。

用法：
    python tools/build_tree.py

tree.json 是只读索引，永远不手动编辑，改节点后跑这个脚本重新生成。
"""
import json
import glob
import os
import re
import sys

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")
TREE_PATH = os.path.join(BASE, "knowledge-v2", "_meta", "tree.json")


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception as e:
        print(f"[warn] yaml 解析失败: {e}", file=sys.stderr)
        return {}


def build_tree():
    nodes = {}
    for f in sorted(glob.glob(os.path.join(NODES_DIR, "*.md"))):
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        fm = parse_frontmatter(text)
        nid = fm.get("id")
        if not nid:
            print(f"[warn] {os.path.basename(f)} 缺少 id，跳过", file=sys.stderr)
            continue
        nodes[nid] = {
            "title": fm.get("title", nid),
            "parent": fm.get("parent", ""),
            "depth": fm.get("depth", 0),
            "type": fm.get("type", "leaf"),
            "link_count": len(fm.get("links") or []),
            "has_cot": bool(fm.get("cot")),
            "children": [],
        }

    for nid, node in nodes.items():
        p = node.get("parent", "")
        if p and p in nodes:
            nodes[p]["children"].append(nid)

    tree = {
        "_note": "自动生成，不手动编辑。由 tools/build_tree.py 从 nodes/*.md frontmatter 构建。",
        "nodes": nodes,
    }
    with open(TREE_PATH, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, ensure_ascii=False, indent=2)

    # 统计
    n = len(nodes)
    leaves = sum(1 for x in nodes.values() if not x["children"])
    cores = sum(1 for x in nodes.values() if x["has_cot"])
    links = sum(x["link_count"] for x in nodes.values())
    print(f"tree.json 已生成：{n} 节点 | 叶子 {leaves} | core {cores} | links {links}")


if __name__ == "__main__":
    build_tree()
