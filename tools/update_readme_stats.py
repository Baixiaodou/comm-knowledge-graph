#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动更新 README 里的知识库统计（节点数 / 类型分布 / 思维链 / 链接 / 学科树）。

用法（每次更新 knowledge-v2 后跑一次）：
    python tools/update_readme_stats.py

原理：实时统计 knowledge-v2/nodes/*.md 的 frontmatter，替换 README.md 中
硬编码的统计位置（badge、三类节点图、六棵主题树、links 描述、项目结构）。
数字没变时输出"无变化"（幂等）。
"""
import json
import os
import re
import sys
import glob

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")
README = os.path.join(BASE, "README.md")

SUBJECT = [
    ("comm", "通信原理"),
    ("dsp", "信号与系统 + DSP"),
    ("emf", "电磁场"),
    ("mob", "移动通信"),
    ("net", "计算机网络"),
    ("rsp", "随机信号处理"),
]


def load_nodes():
    nodes = []
    for f in sorted(glob.glob(os.path.join(NODES_DIR, "*.md"))):
        text = open(f, encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        nodes.append({
            "id": fm.get("id", ""),
            "type": fm.get("type", "leaf"),
            "parent": fm.get("parent", ""),
            "cot": fm.get("cot"),
            "links": fm.get("links") or [],
        })
    return nodes


def compute(nodes):
    from collections import Counter
    tc = Counter(n["type"] for n in nodes)
    by_id = {n["id"]: n for n in nodes}

    def subtree_size(nid):
        n = by_id.get(nid)
        if not n:
            return 0
        return 1 + sum(subtree_size(c["id"]) for c in nodes if c["parent"] == nid)

    subject_sizes = {}
    for pre, _name in SUBJECT:
        roots = [n for n in nodes if n["id"].startswith(pre + "-") and n["parent"] == "root"]
        subject_sizes[pre] = sum(subtree_size(r["id"]) for r in roots)

    total_links = sum(len(n["links"]) for n in nodes)
    cross = sum(
        1 for n in nodes
        for lk in n["links"]
        if (lk.get("id") if isinstance(lk, dict) else lk) and
           (lk.get("id") if isinstance(lk, dict) else lk).split("-")[0] != n["id"].split("-")[0]
    )
    return {
        "total": len(nodes),
        "core": tc.get("core", 0),
        "hub": tc.get("hub", 0),
        "leaf": tc.get("leaf", 0),
        "cot": sum(1 for n in nodes if n.get("cot")),
        "links": total_links,
        "cross_links": cross,
        "subjects": subject_sizes,
    }


def update_readme(s):
    """按顺序替换 README 中的统计位置，返回改动列表"""
    text = open(README, encoding="utf-8").read()
    changes = []

    def sub(pattern, repl, desc, flags=0):
        nonlocal text
        new, n = re.subn(pattern, repl, text, count=1, flags=flags)
        if n:
            changes.append(desc)
            text = new

    # 1. badge（节点 / 思维链 / 连接）
    sub(r"节点-(\d+)-", f"节点-{s['total']}-", "badge 节点数")
    sub(r"思维链-(\d+)-", f"思维链-{s['cot']}-", "badge 思维链数")
    sub(r"连接-(\d+)-", f"连接-{s['links']}-", "badge 连接数")

    # 2. 三类节点 mermaid 图（core/hub/leaf）
    sub(r"核心概念（\d+）", f"核心概念（{s['core']}）", "三类节点图 core")
    sub(r"枢纽（\d+）", f"枢纽（{s['hub']}）", "三类节点图 hub")
    sub(r"叶子（\d+）", f"叶子（{s['leaf']}）", "三类节点图 leaf")

    # 3. 三类节点表格（| `core` | 核心概念 | 带思维链... | 31 |）
    sub(r"(\| `core` \| 核心概念 \| 带思维链[^\n]*\| )\d+ \|", rf"\g<1>{s['core']} |",
        "三类节点表 core")
    sub(r"(\| `hub` \| 分类文件夹 \| 统领子节点[^\n]*\| )\d+ \|", rf"\g<1>{s['hub']} |",
        "三类节点表 hub")
    sub(r"(\| `leaf` \| 叶子知识点 \| 具体知识点[^\n]*\| )\d+ \|", rf"\g<1>{s['leaf']} |",
        "三类节点表 leaf")

    # 4. 六棵主题树 mermaid（学科名（N），全角括号）
    for pre, name in SUBJECT:
        n = s["subjects"].get(pre, 0)
        sub(rf"({re.escape(name)}（)\d+）", rf"\g<1>{n}）", f"学科树 {name}")

    # 5. links 描述：全库共 **271 条连接，其中 76 条跨树连接**
    sub(r"全库共 \*\*\d+ 条连接，其中 \d+ 条跨树连接\*\*",
        f"全库共 **{s['links']} 条连接，其中 {s['cross_links']} 条跨树连接**",
        "links 描述")

    # 6. 项目结构：74 个 .md 节点（注意用全角 │）
    sub(r"(│   ├── nodes/\s*# )\d+( 个 \.md 节点)",
        rf"\g<1>{s['total']}\g<2>", "项目结构 nodes 数")

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    return changes


def main():
    nodes = load_nodes()
    s = compute(nodes)
    print(f"当前统计: 总 {s['total']} | core {s['core']} / hub {s['hub']} / leaf {s['leaf']} "
          f"| 思维链 {s['cot']} | 链接 {s['links']}（跨树 {s['cross_links']}）")
    print(f"学科分布: { {k: s['subjects'][k] for k, _ in SUBJECT} }")
    changes = update_readme(s)
    if changes:
        print(f"\n已更新 README: {len(changes)} 处 -> {changes}")
    else:
        print("\nREADME 统计与知识库一致，无变化（幂等 ✓）")


if __name__ == "__main__":
    main()
