#!/usr/bin/env python3
"""知识库结构校验（kb_lint 第一步：结构完整性）。

检查项：
1. 必填字段完整性（id/title/parent/depth/type/summary）
2. core 节点必须有 cot
3. parent / links 指向的节点必须存在（broken link 检测）
4. depth 与 parent 的一致性（子 = 父 + 1）
5. 孤立节点检测（无任何节点指向它）

用法：python tools/kb_lint.py
"""
import glob
import os
import re
import sys

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception as e:
        print(f"[warn] yaml 解析失败: {e}", file=sys.stderr)
        return {}


def check():
    nodes = {}
    errors = []
    warnings = []

    # 1. 读取所有节点
    for f in sorted(glob.glob(os.path.join(NODES_DIR, "*.md"))):
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        fm = parse_frontmatter(text)
        nid = fm.get("id")
        if not nid:
            errors.append(f"{os.path.basename(f)}: 缺少 id")
            continue
        if nid in nodes:
            errors.append(f"{nid}: id 重复")
        nodes[nid] = {"file": os.path.basename(f), "fm": fm}

    # 2. 必填字段 + core 必须有 cot
    for nid, node in nodes.items():
        fm = node["fm"]
        for field in ["title", "parent", "depth", "type", "summary"]:
            val = fm.get(field)
            if field == "parent" and nid == "root":
                continue
            if val is None or val == "":
                errors.append(f"{nid}: 缺少必填字段 {field}")
        if fm.get("type") == "core" and not fm.get("cot"):
            errors.append(f"{nid}: type=core 但缺少 cot")
        if fm.get("type") != "core" and fm.get("cot"):
            warnings.append(f"{nid}: 非 core 节点却写了 cot")

    # 3. parent / links 指向存在性
    for nid, node in nodes.items():
        fm = node["fm"]
        parent = fm.get("parent", "")
        if parent and parent not in nodes:
            errors.append(f"{nid}: parent '{parent}' 不存在")
        for link in (fm.get("links") or []):
            lid = link.get("id") if isinstance(link, dict) else link
            if lid not in nodes:
                errors.append(f"{nid}: link '{lid}' 不存在（broken link）")

    # 4. depth 一致性
    for nid, node in nodes.items():
        fm = node["fm"]
        parent = fm.get("parent", "")
        if parent in nodes:
            expected = nodes[parent]["fm"].get("depth", -1) + 1
            if fm.get("depth") != expected:
                errors.append(f"{nid}: depth 应为 {expected}，实际 {fm.get('depth')}")

    # 5. 孤立节点（有 parent 但无任何节点反向引用它）
    for nid, node in nodes.items():
        if nid == "root":
            continue
        is_referenced = any(
            n2["fm"].get("parent") == nid
            or any(
                (l.get("id") if isinstance(l, dict) else l) == nid
                for l in (n2["fm"].get("links") or [])
            )
            for n2 in nodes.values()
        )
        if not is_referenced:
            warnings.append(f"{nid}: 无任何节点反向引用（孤立）")

    # 6. 统计
    n = len(nodes)
    cores = sum(1 for x in nodes.values() if x["fm"].get("type") == "core")
    links = sum(len(x["fm"].get("links") or []) for x in nodes.values())
    print(f"节点 {n} | core {cores} | links {links}")

    if errors:
        print(f"\n[错误] {len(errors)} 处：")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n[OK] 结构完整，无错误")

    if warnings:
        print(f"\n[警告] {len(warnings)} 处：")
        for w in warnings:
            print(f"  - {w}")

    return len(errors) == 0


if __name__ == "__main__":
    sys.exit(0 if check() else 1)
