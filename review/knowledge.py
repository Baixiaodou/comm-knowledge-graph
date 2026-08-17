"""读取树形知识库：解析节点 frontmatter、构建树、取子树、生成 AI 上下文。

只读知识库，绝不写回 nodes/。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

import config


@dataclass
class Node:
    id: str
    title: str
    parent: str
    depth: int
    type: str
    summary: str
    links: list = field(default_factory=list)
    cot: Optional[dict] = None
    body: str = ""
    path: Path = None
    created: str = ""
    updated: str = ""


def parse_frontmatter(text: str):
    """把 markdown 按 --- 拆成 (frontmatter_dict, body)。"""
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm = yaml.safe_load(parts[1]) or {}
    return fm, parts[2]


def load_nodes() -> Dict[str, Node]:
    nodes: Dict[str, Node] = {}
    for p in sorted(config.NODES_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        nid = (fm.get("id") or p.stem).strip()
        nodes[nid] = Node(
            id=nid,
            title=fm.get("title", nid),
            parent=(fm.get("parent") or "").strip(),
            depth=int(fm.get("depth", 0) or 0),
            type=fm.get("type", "leaf"),
            summary=fm.get("summary", "") or "",
            links=[lk for lk in (fm.get("links") or []) if isinstance(lk, dict)],
            cot=fm.get("cot") if isinstance(fm.get("cot"), dict) else None,
            body=body.strip(),
            path=p,
            created=str(fm.get("created", "") or ""),
            updated=str(fm.get("updated", "") or ""),
        )
    return nodes


def build_tree(nodes: Dict[str, Node]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {nid: [] for nid in nodes}
    for nid, n in nodes.items():
        if n.parent and n.parent in nodes:
            children[n.parent].append(nid)
    return children


def subtree_ids(nodes: Dict[str, Node], children: Dict[str, List[str]], root_id: str) -> List[str]:
    """返回 root_id 及其所有后代 id（含自身）。"""
    if root_id not in nodes:
        return []
    ids: List[str] = []
    stack = [root_id]
    while stack:
        cur = stack.pop()
        if cur in nodes and cur not in ids:
            ids.append(cur)
            stack.extend(children.get(cur, []))
    return ids


def node_context(nodes: Dict[str, Node], nid: str, max_chars: int = 4000) -> str:
    """生成给 AI 的节点原文上下文（摘要 + 思维链 + 正文）。"""
    n = nodes.get(nid)
    if not n:
        return ""
    parts = [
        f"# 节点 [{n.id}] {n.title}",
        f"摘要：{n.summary}",
    ]
    if n.cot:
        parts.append(f"思维链·问题起点：{n.cot.get('origin', '')}")
        parts.append(f"思维链·结论：{n.cot.get('conclusion', '')}")
    parts.append("节点正文：")
    body = n.body
    if len(body) > max_chars:
        body = body[:max_chars] + "\n……（正文过长已截断）"
    parts.append(body)
    return "\n".join(parts)


def nodes_context(nodes: Dict[str, Node], node_ids: List[str], total_cap: int = 24000) -> str:
    """拼接多个节点上下文，控制总长度。"""
    blocks = []
    used = 0
    for nid in node_ids:
        ctx = node_context(nodes, nid)
        if used + len(ctx) > total_cap:
            ctx = ctx[: max(0, total_cap - used)] + "\n……（总上下文超长，其余节点略）"
        blocks.append(ctx)
        used += len(ctx)
        if used >= total_cap:
            break
    return "\n\n".join(blocks)
