"""fuzzy_hub_rag benchmark 共享核心：节点/tree 加载 + TF-IDF。

与线上 src/plugins/ai_chat/node_retriever.py 同口径（tokenize/idf/rank 逻辑一致），
改动任一方必须同步并重跑 benchmark 回归。
"""

import math
import os
import re
from collections import Counter

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")
TREE_PATH = os.path.join(BASE, "knowledge-v2", "_meta", "tree.json")
QUESTIONS_FULL = os.path.join(BASE, "benchmark", "questions_full.json")


def _tokenize(text: str) -> list[str]:
    """中文双字 bigram + 英文单词 + 数字（与线上 node_retriever 完全一致）"""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    tokens += re.findall(r"\d+", text)
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            tokens.append(seg[i] + seg[i + 1])
    return tokens


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                return (yaml.safe_load(parts[1]) or {}), parts[2].strip()
            except yaml.YAMLError:
                pass
    return {}, text.strip()


class KB:
    """一次加载，供 benchmark/annotate/strategies 共享"""

    def __init__(self):
        # 数量不写死：随 knowledge-v2/nodes 更新自动变化（2026-09-04 实况：90 = 20 hub + 70 core/leaf）
        self.nodes: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.title_map: dict[str, str] = {}
        self.hubs: list[dict] = []           # type == hub（含 root；数量随知识库，勿依赖写死值）
        self.leaves: list[dict] = []         # type in (core, leaf)，正常检索池
        self.children: dict[str, list[str]] = {}  # hub_id -> 直接子节点 id 列表
        self.idf: dict[str, float] = {}
        self.loaded = False

    def load(self) -> None:
        for f in sorted(os.listdir(NODES_DIR)):
            if not f.endswith(".md"):
                continue
            with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
                meta, content = _parse_frontmatter(fh.read())
            nid = meta.get("id", "")
            if not nid:
                continue
            node = {
                "id": nid,
                "title": meta.get("title", nid),
                "type": meta.get("type", "leaf"),
                "summary": meta.get("summary", ""),
                "content": content,
                "links": meta.get("links") or [],
            }
            self.nodes.append(node)
            self.by_id[nid] = node
            self.title_map[nid] = node["title"]
            if node["type"] == "hub":
                self.hubs.append(node)
            else:
                self.leaves.append(node)
        # children 映射（tree.json 的 children 即 hub 的直接子节点，全部 core/leaf）
        with open(TREE_PATH, encoding="utf-8") as fh:
            tree = json_load(TREE_PATH)["nodes"]
        for nid, info in tree.items():
            self.children[nid] = list(info.get("children") or [])
        self._build_idf()
        self.loaded = True

    def _build_idf(self):
        n = len(self.nodes)
        df: Counter = Counter()
        for node in self.nodes:
            text = node["title"] + " " + node["summary"] + " " + node["content"]
            for t in set(_tokenize(text)):
                df[t] += 1
        self.idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}

    # -- 检索 ---------------------------------------------------------
    def _node_vec(self, node: dict) -> dict[str, float]:
        """节点词向量（idf 加权 TF，惰性缓存）"""
        cache = getattr(node, "_vec", None)
        if cache is None:
            tf = Counter(_tokenize(node["title"] + " " + node["summary"] + " " + node["content"]))
            cache = {t: c * self.idf[t] for t, c in tf.items() if t in self.idf}
            node["_vec"] = cache
        return cache

    def rank(self, query: str, pool: list[dict] | None = None) -> list[tuple[dict, float]]:
        """TF-IDF cosine 排序（与线上 _rank 一致），pool 默认全部节点"""
        q_tf = Counter(_tokenize(query))
        q_vec = {t: tf * self.idf[t] for t, tf in q_tf.items() if t in self.idf}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        pool = pool if pool is not None else self.nodes
        scored = []
        for node in pool:
            vec = self._node_vec(node)
            dot = sum(w * q_vec.get(t, 0.0) for t, w in vec.items())
            d_norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
            scored.append((node, dot / (q_norm * d_norm)))
        scored.sort(key=lambda x: -x[1])
        return scored

    # -- hub 相关 ------------------------------------------------------
    def hub_brief(self, node: dict) -> str:
        """标注/选点用的 hub 一行简介：id + 标题 + summary"""
        return f"[{node['id']}] {node['title']}：{node['summary']}"

    def descendant_leaves(self, hub_id: str) -> list[str]:
        """hub 统领的子节点标题（直接子节点 + 孙节点标题），用于注入和 last_ids"""
        out: list[str] = []
        for cid in self.children.get(hub_id, []):
            c = self.by_id.get(cid)
            if not c:
                continue
            out.append(c["id"])
            out.extend(self.children.get(cid, []))
        return out

    def hub_menu(self) -> str:
        """hub 菜单文本（标注 prompt 用；运行时取自 self.hubs，全量随知识库更新）"""
        return "\n".join(self.hub_brief(h) for h in self.hubs)


def json_load(path: str):
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# 全局单例（benchmark / annotate / strategies 共用）
kb = KB()
