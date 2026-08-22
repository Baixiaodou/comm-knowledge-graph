#!/usr/bin/env python3
"""知识库 benchmark 评测（任务 #13）。

对比：多个模型「裸跑 vs +知识库」回答题库问题，用 Qwen-Max 裁判打分。

用法：
    python tools/kb_benchmark.py            # 全量跑
    python tools/kb_benchmark.py --limit 3  # 先跑前 3 题测试
    python tools/kb_benchmark.py --models deepseek-chat Qwen/Qwen2.5-7B-Instruct  # 指定模型
"""
import argparse
import json
import os
import re
import sys
import time

from openai import OpenAI

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(BASE, "benchmark", "questions.json")
NODES_DIR = os.path.join(BASE, "knowledge-v2", "nodes")
TREE_PATH = os.path.join(BASE, "knowledge-v2", "_meta", "tree.json")
RESULT_DIR = os.path.join(BASE, "benchmark", "results")

# ── API 配置（从环境变量或 tools/.env 读）────────────────────────────
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
SILICON_KEY = os.environ.get("SILICONFLOW_API_KEY", "")

# 默认考生模型（裸跑 vs +知识库）。Qwen3.5-4B 在硅基流动上 180s 超时不可用，已剔除
MODELS = [
    {"name": "deepseek-chat", "base_url": "https://api.deepseek.com", "key": DEEPSEEK_KEY},
    {"name": "Qwen/Qwen3.5-9B", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
    {"name": "Qwen/Qwen3-8B", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
    {"name": "Qwen/Qwen3-14B", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
    {"name": "Qwen/Qwen3-32B", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
    {"name": "THUDM/GLM-4-32B-0414", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
    {"name": "zai-org/GLM-5.2", "base_url": "https://api.siliconflow.cn/v1", "key": SILICON_KEY},
]
# 裁判模型
JUDGE = {"name": "qwen-max", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "key": DASHSCOPE_KEY}


def load_env():
    """从 tools/.env 读取 key（如果环境变量没设置）"""
    global DEEPSEEK_KEY, DASHSCOPE_KEY, SILICON_KEY
    env_path = os.path.join(BASE, "tools", ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
    SILICON_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
    for m in MODELS:
        if "siliconflow" in m["base_url"]:
            m["key"] = SILICON_KEY
        elif "deepseek" in m["base_url"]:
            m["key"] = DEEPSEEK_KEY
        else:
            m["key"] = DASHSCOPE_KEY
    JUDGE["key"] = DASHSCOPE_KEY


# ── 知识库加载 ───────────────────────────────────────────────────────
def load_knowledge_base() -> str:
    """把 knowledge-v2 的节点组装成结构化 context 文本"""
    import yaml

    # 1. 树骨架
    tree_text = ""
    if os.path.exists(TREE_PATH):
        with open(TREE_PATH, encoding="utf-8") as f:
            tree = json.load(f)["nodes"]
        tree_text = "## 知识树结构（层级关系）\n"
        def walk(nid, depth=0):
            lines = []
            n = tree.get(nid, {})
            lines.append("  " * depth + f"- {n.get('title', nid)} [{n.get('type','')}]")
            for c in sorted(n.get("children", [])):
                lines.extend(walk(c, depth + 1))
            return lines
        tree_text += "\n".join(walk("root"))

    # 2. 节点内容 + links + cot
    node_blocks = []
    links_block = ["\n## 知识关联（links）"]
    cot_blocks = ["\n## 核心概念思维链（cot）"]
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        content = m.group(2).strip()
        nid = fm.get("id", "")
        title = fm.get("title", nid)
        node_blocks.append(f"### {title}（{nid}）\n{fm.get('summary','')}\n{content}")
        for link in fm.get("links") or []:
            if isinstance(link, dict):
                links_block.append(f"- {nid} ↔ {link.get('id')}: {link.get('relation','')}")
        cot = fm.get("cot")
        if cot and isinstance(cot, dict):
            cot_blocks.append(f"### {title}\n问题：{cot.get('origin','')}\n推导：{cot.get('reasoning','')}\n结论：{cot.get('conclusion','')}")

    kb = "\n".join([
        "你是一位通信工程专业的学生，下面是你精心整理的结构化知识库，包含树状层级、知识关联和核心概念思维链。请基于这些知识回答问题。",
        tree_text,
        "\n## 各节点内容",
        "\n\n".join(node_blocks),
        "\n".join(links_block),
        "\n".join(cot_blocks),
    ])
    return kb


def load_questions(path=None):
    with open(path or QUESTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def load_tree_index() -> str:
    """返回树目录（每个节点的 id + title + summary），供模型第一轮定位用"""
    import yaml
    nodes = []
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        nodes.append({
            "id": fm.get("id", ""),
            "title": fm.get("title", ""),
            "summary": fm.get("summary", ""),
            "parent": fm.get("parent", ""),
        })
    by_parent = {}
    for n in nodes:
        by_parent.setdefault(n["parent"], []).append(n)

    def render(nid, depth=0):
        lines = []
        for n in sorted(by_parent.get(nid, []), key=lambda x: x["title"]):
            lines.append("  " * depth + f"- {n['title']} ({n['id']}): {n['summary'][:60]}")
            lines.extend(render(n["id"], depth + 1))
        return lines
    return "\n".join(render(""))


def load_nodes_by_ids(nids) -> str:
    """返回指定节点的完整内容（content + links + cot）"""
    import yaml
    blocks = []
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        if fm.get("id") in nids:
            content = m.group(2).strip()
            links = ""
            for link in fm.get("links") or []:
                if isinstance(link, dict):
                    links += f"- {fm.get('id')} ↔ {link.get('id')}: {link.get('relation', '')}\n"
            cot = ""
            c = fm.get("cot")
            if c and isinstance(c, dict):
                cot = f"\n思维链：\n问题：{c.get('origin', '')}\n推导：{c.get('reasoning', '')}\n结论：{c.get('conclusion', '')}\n"
            blocks.append(f"### {fm.get('title')}（{fm.get('id')}）\n{fm.get('summary', '')}\n{content}\n{links}{cot}")
    return "\n\n".join(blocks)


def select_nodes(model_cfg, question, tree_index, max_retries=2):
    """第一轮：让模型从树目录里选出 2-3 个相关节点 id"""
    client = OpenAI(api_key=model_cfg["key"], base_url=model_cfg["base_url"], timeout=180)
    prompt = f"""你是通信工程专业的学生。下面是你的知识库目录（树结构 + 每个知识点的摘要）：

{tree_index}

现在要回答一个问题。请判断需要调用知识库中的哪些知识点（选 2-3 个最相关的节点），只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{question}"""
    extra = {}
    if re.search(r"qwen3|GLM-[45]|MiniMax|Kimi-K2", model_cfg["name"], re.I):
        extra["extra_body"] = {"enable_thinking": False}
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model_cfg["name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                **extra,
            )
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i, str)][:3]
                    if result:
                        return result
                except Exception:
                    pass
            # 兜底：即使 JSON 被截断/格式异常，也从文本里提取目录中存在的节点 id
            known = set(re.findall(r"\(((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)\)", tree_index))
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in known]
            if found:
                return found[:3]
            return []
        except Exception:
            if attempt == max_retries - 1:
                return []
            time.sleep(1)
    return []


# ── 方案 B/C：程序预筛（TF-IDF 字符 n-gram 相似度）────────────────────
def _tokenize(text):
    """中文按字符 2-gram，英文/数字按小写词，用于无分词的 TF-IDF"""
    tokens = []
    for seg in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower()):
        if re.match(r"[\u4e00-\u9fff]", seg):
            if len(seg) >= 2:
                tokens += [seg[i:i+2] for i in range(len(seg)-1)]
            else:
                tokens.append(seg)
        else:
            tokens.append(seg)
    return tokens


def _all_node_texts():
    """返回 {id: (title+summary+content)}，供程序预筛用"""
    import yaml
    texts = {}
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        texts[fm.get("id", "")] = (fm.get("title", "") + " " + fm.get("summary", "") + " " + m.group(2))
    return texts


def _tfidf_similarity(query, doc_texts):
    """字符 2-gram TF-IDF 余弦相似度，返回 {id: score}"""
    from math import log, sqrt
    N = len(doc_texts)
    q_tokens = _tokenize(query)
    # 文档频率
    df = {}
    doc_tokens = {}
    for nid, txt in doc_texts.items():
        toks = _tokenize(txt)
        doc_tokens[nid] = toks
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    # 查询向量（TF-IDF）
    q_tf = {}
    for t in q_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1
    q_vec = {}
    for t, tf in q_tf.items():
        idf = log((N + 1) / (df.get(t, 0) + 1)) + 1
        q_vec[t] = tf * idf
    q_norm = sqrt(sum(v*v for v in q_vec.values())) or 1
    scores = {}
    for nid, toks in doc_tokens.items():
        d_tf = {}
        for t in toks:
            d_tf[t] = d_tf.get(t, 0) + 1
        dot = 0
        d_norm = 0
        for t, tf in d_tf.items():
            idf = log((N + 1) / (df.get(t, 0) + 1)) + 1
            w = tf * idf
            d_norm += w * w
            if t in q_vec:
                dot += q_vec[t] * w
        d_norm = sqrt(d_norm) or 1
        scores[nid] = dot / (q_norm * d_norm)
    return scores


def select_nodes_b(question, tree_index, top_k=3):
    """方案 B：纯程序预筛（TF-IDF 相似度），不调用模型"""
    doc_texts = _all_node_texts()
    scores = _tfidf_similarity(question, doc_texts)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    # 过滤掉 root（不是具体知识点）
    result = [nid for nid, _ in ranked if nid != "root"][:top_k]
    return result


def select_nodes_c(model_cfg, question, tree_index, top_k=10, max_retries=2):
    """方案 C：混合——程序先筛 top_k 候选，模型再从候选中精挑 2-3 个"""
    doc_texts = _all_node_texts()
    scores = _tfidf_similarity(question, doc_texts)
    ranked = [nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1]) if nid != "root"][:top_k]
    # 构建候选目录（只含 top_k 候选）
    import yaml
    cand_lines = []
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        if fm.get("id") in ranked:
            cand_lines.append(f"- {fm.get('title')} ({fm.get('id')}): {fm.get('summary', '')[:60]}")
    cand_index = "\n".join(cand_lines)
    client = OpenAI(api_key=model_cfg["key"], base_url=model_cfg["base_url"], timeout=180)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{question}"""
    extra = {}
    if re.search(r"qwen3|GLM-[45]|MiniMax|Kimi-K2", model_cfg["name"], re.I):
        extra["extra_body"] = {"enable_thinking": False}
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model_cfg["name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                **extra,
            )
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i, str) and i in ranked][:3]
                    if result:
                        return result
                except Exception:
                    pass
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in ranked]
            if found:
                return found[:3]
            return ranked[:3]
        except Exception:
            if attempt == max_retries - 1:
                return ranked[:3]
            time.sleep(1)
    return ranked[:3]


def _load_node_meta():
    """返回 {id: {'type','title','summary','links'}}，供树+Wiki检索用（一次读完所有节点元信息）"""
    import yaml
    meta = {}
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        meta[fm.get("id", "")] = {
            "type": fm.get("type", "leaf"),
            "title": fm.get("title", ""),
            "summary": fm.get("summary", ""),
            "links": [l["id"] for l in (fm.get("links") or []) if isinstance(l, dict)],
        }
    return meta


def select_nodes_d(model_cfg, question, tree_index, top_k=10, max_retries=2):
    """检索方案 D（历史方案）：程序初筛（排除 hub/root）+ 模型精挑。

    1. TF-IDF 初筛：排除 hub（分类文件夹）/root，只留 core/leaf（真正知识点），取 top-K
    2. 模型精挑：从候选中选 2-3 个节点
    （注：这是方案演进中的中间方案，已由 select_nodes_final 取代——最终方案是
    top-3 + links 扩展 + 精挑，见 README「检索方案研究」；保留本函数供历史复现）
    """
    import yaml
    doc_texts = _all_node_texts()
    meta = _load_node_meta()

    # 1. TF-IDF 初筛，排除 root/hub，只留 core/leaf
    scores = _tfidf_similarity(question, doc_texts)
    cand = [
        nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1])
        if meta.get(nid, {}).get("type") in ("core", "leaf")
    ][:top_k]

    # 3. 构建候选目录（只含 cand）
    cand_lines = []
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        if fm.get("id") in cand:
            cand_lines.append(f"- {fm.get('title')} ({fm.get('id')}): {fm.get('summary', '')[:60]}")
    cand_index = "\n".join(cand_lines)

    # 4. 模型精挑 2-3 个
    client = OpenAI(api_key=model_cfg["key"], base_url=model_cfg["base_url"], timeout=180)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：
 
{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{question}"""
    extra = {}
    if re.search(r"qwen3|GLM-[45]|MiniMax|Kimi-K2", model_cfg["name"], re.I):
        extra["extra_body"] = {"enable_thinking": False}
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model_cfg["name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                **extra,
            )
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i, str) and i in cand][:3]
                    if result:
                        return result
                except Exception:
                    pass
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in cand]
            if found:
                return found[:3]
            return cand[:3]
        except Exception:
            if attempt == max_retries - 1:
                return cand[:3]
            time.sleep(1)
    return cand[:3]


def _pick_node_ids(model_cfg, question, cand_ids, max_retries=2):
    """从候选节点 id 中 LLM 精挑 2-3 个（候选目录构建 + JSON/正则解析 + 兜底）。
    供 select_nodes_d / select_nodes_final 共用，避免精挑逻辑多处复制。
    """
    import yaml
    cand_lines = []
    for f in sorted(os.listdir(NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        if fm.get("id") in cand_ids:
            cand_lines.append(f"- {fm.get('title')} ({fm.get('id')}): {fm.get('summary', '')[:60]}")
    cand_index = "\n".join(cand_lines)
    client = OpenAI(api_key=model_cfg["key"], base_url=model_cfg["base_url"], timeout=180)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{question}"""
    extra = {}
    if re.search(r"qwen3|GLM-[45]|MiniMax|Kimi-K2", model_cfg["name"], re.I):
        extra["extra_body"] = {"enable_thinking": False}
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model_cfg["name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                **extra,
            )
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i, str) and i in cand_ids][:3]
                    if result:
                        return result
                except Exception:
                    pass
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in cand_ids]
            if found:
                return found[:3]
            return cand_ids[:3]
        except Exception:
            if attempt == max_retries - 1:
                return cand_ids[:3]
            time.sleep(1)
    return cand_ids[:3]


def select_nodes_final(model_cfg, question, top_k=3, max_retries=2):
    """最终检索方案（benchmark 验证：116 题召回 79.1%）：top-K + links 扩展 + LLM 精挑。

    1. TF-IDF 初筛（排除 root/hub，只留 core/leaf），取 top-K（默认 3）
    2. links 扩展：top-K 节点的 links 邻居（core/leaf）并入候选（不截断）
       ——补回"关键词不重合但语义相关"的节点，top-K 越窄 links 价值越大
    3. LLM 从完整候选精挑 2-3 个
    即 test_top34.py method_links 的正式实现（原实现仅存在于实验脚本）。
    """
    doc_texts = _all_node_texts()
    meta = _load_node_meta()
    scores = _tfidf_similarity(question, doc_texts)
    ranked = [nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1])
              if meta.get(nid, {}).get("type") in ("core", "leaf")]
    topk = ranked[:top_k]
    cand = list(topk)
    for nid in topk:
        for nb in meta.get(nid, {}).get("links", []):
            if meta.get(nb, {}).get("type") in ("core", "leaf") and nb not in cand:
                cand.append(nb)
    return _pick_node_ids(model_cfg, question, cand, max_retries)


# ── 模型调用 ─────────────────────────────────────────────────────────
def ask_model(model_cfg, system_prompt, question, max_retries=2):
    client = OpenAI(api_key=model_cfg["key"], base_url=model_cfg["base_url"], timeout=180)
    extra = {}
    # qwen3 系列需要 enable_thinking=false（非流式）
    if re.search(r"qwen3|GLM-[45]|MiniMax|Kimi-K2", model_cfg["name"], re.I):
        extra["extra_body"] = {"enable_thinking": False}
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model_cfg["name"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                max_tokens=400,
                temperature=0.3,
                **extra,
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                return f"[ERROR] {str(e)[:200]}"
            time.sleep(2 * (attempt + 1))
    return "[ERROR]"


def judge_answer(question, std_answer, model_name, answer):
    """Qwen-Max 裁判：基于标准答案打分 0-10，返回 (分数, 评语)"""
    client = OpenAI(api_key=JUDGE["key"], base_url=JUDGE["base_url"], timeout=180)
    prompt = f"""你是通信原理课程的资深面试官，请严格按标准答案给考生答案打分。评分必须拉开差距，宁严勿松，尤其对错误和不完整要重扣。

【题目】{question}

【标准答案】{std_answer}

【考生（{model_name}）答案】{answer}

严格评分规则：
1. 关键概念、结论、原理出现错误 → 直接扣到 4 分以下（错误是致命的）
2. 遗漏标准答案的核心要点 → 每漏一个扣 2 分
3. 只答出表面规律、没答出深层机制（why 层面的本质原因）→ 最多 6 分
4. 编造不存在的内容 → 直接 2 分以下
5. 完整、准确、深入（答出深层机制）→ 9-10 分

分档参考：
10 = 完全正确、覆盖所有要点、有深层理解
8-9 = 正确但有小遗漏或表述不够深
6-7 = 有明显遗漏，或只答表面没答深层机制
4-5 = 有关键错误，或遗漏大部分要点
1-3 = 严重错误或答非所问

输出格式（严格按此格式，只输出 JSON）：
{{"score": <0到10的整数>, "comment": "<一句话评语，指出具体错误或遗漏>"}}"""
    try:
        r = client.chat.completions.create(
            model=JUDGE["name"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        text = r.choices[0].message.content.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                # 类型校验：score 必须是 int/float，防裁判输出异常污染统计
                if isinstance(data, dict) and isinstance(data.get("score"), (int, float)):
                    return data
                return {"score": -1, "comment": "裁判输出 score 类型异常"}
            except Exception:
                return {"score": -1, "comment": "裁判输出 JSON 解析失败"}
        return {"score": -1, "comment": "裁判输出格式异常"}
    except Exception as e:
        return {"score": -1, "comment": f"裁判异常: {str(e)[:100]}"}


# ── 主流程 ───────────────────────────────────────────────────────────
def main():
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全部）")
    parser.add_argument("--start", type=int, default=0, help="从第 N 题开始（0=开头，配合 --limit 做分段并行）")
    parser.add_argument("--models", nargs="*", help="只跑指定模型名")
    parser.add_argument("--no-judge", action="store_true", help="只跑答案不打分")
    parser.add_argument("--questions", default="", help="指定题库 json 路径（默认 benchmark/questions.json）")
    parser.add_argument("--method", default="F",
                        help="选节点方式：A=模型自主 B=程序预筛 C=混合 D=树+Wiki(历史) F=最终方案(top3+links+精挑)")
    parser.add_argument("--modes", nargs="*", default=["bare", "with_kb"],
                        help="只跑指定模式（bare/with_kb），默认两个都跑（用于多 key 并行拆分）")
    args = parser.parse_args()

    os.makedirs(RESULT_DIR, exist_ok=True)
    questions = load_questions(args.questions or None)
    if args.start > 0:
        questions = questions[args.start:]
    if args.limit > 0:
        questions = questions[: args.limit]

    kb = load_knowledge_base()
    tree_index = load_tree_index()
    print(f"知识库加载完成：全量 {len(kb)} 字符 | 树目录 {len(tree_index)} 字符")
    print(f"题库：{len(questions)} 题")

    models = [m for m in MODELS if not args.models or m["name"] in args.models]
    print(f"模型：{len(models)} 个，共 {len(models)*2} 组（裸跑 + 知识库）")

    BASE_PROMPT = "你是通信工程专业的学生，请回答下面的问题。"
    # +知识库模式：两阶段，先让模型看目录选节点，再注入选中节点内容
    KB_PROMPT = BASE_PROMPT + "\n\n以下是你知识库中与问题相关的知识点：\n"

    results = []
    ts = time.strftime("%Y%m%d_%H%M%S")
    # 实时保存：每答完一题就 append 到 jsonl，中途崩溃也不丢
    raw_path = os.path.join(RESULT_DIR, f"raw_{ts}.jsonl")
    for mi, model in enumerate(models):
        if not model["key"]:
            print(f"[跳过] {model['name']}: 无 API key", flush=True)
            continue
        for mode in args.modes:
            label = f"{model['name']} [{mode}]"
            print(f"\n=== {label} ===", flush=True)
            for qi, q in enumerate(questions):
                if mode == "with_kb":
                    # 第一轮：选相关节点（A 模型自主 / B 程序预筛 / C 混合 / D 树+Wiki / F final）
                    if args.method == "B":
                        nids = select_nodes_b(q["question"], tree_index)
                    elif args.method == "C":
                        nids = select_nodes_c(model, q["question"], tree_index)
                    elif args.method == "D":
                        nids = select_nodes_d(model, q["question"], tree_index)
                    elif args.method == "F":
                        nids = select_nodes_final(model, q["question"])
                    else:
                        nids = select_nodes(model, q["question"], tree_index)
                    # 第二轮：注入选中节点内容回答
                    nodes_content = load_nodes_by_ids(nids)
                    sys_prompt = KB_PROMPT + nodes_content if nodes_content else BASE_PROMPT
                    ans = ask_model(model, sys_prompt, q["question"])
                else:
                    ans = ask_model(model, BASE_PROMPT, q["question"])
                    nids = []
                record = {
                    "model": model["name"],
                    "mode": mode,
                    "qid": q["id"],
                    "level": q["level"],
                    "question": q["question"],
                    "answer": ans,
                    "method": args.method,
                    "selected_nodes": nids,
                    "expected_nodes": q.get("expected_nodes", []),
                }
                # 测量卫生：选节点失败/无内容 → 标记降级（裸跑成绩不得冒充 +知识库）
                if mode == "with_kb" and not nodes_content:
                    record["degraded"] = True
                # 测量卫生：调用失败（[ERROR] 占位）→ 不送裁判打分（记 -1 由汇总剔除）
                call_failed = ans.startswith("[ERROR]")
                if not args.no_judge and not call_failed:
                    j = judge_answer(q["question"], q["answer"], model["name"], ans)
                    record["judge_score"] = j.get("score", -1)
                    record["judge_comment"] = j.get("comment", "")
                    print(f"  [{q['id']}] L{q['level']} 分={record['judge_score']}", flush=True)
                else:
                    if call_failed:
                        record["judge_score"] = -1
                        record["judge_comment"] = "调用失败(未打分)"
                        print(f"  [{q['id']}] L{q['level']} 调用失败，跳过打分", flush=True)
                    else:
                        print(f"  [{q['id']}] L{q['level']} 已答", flush=True)
                results.append(record)
                # 实时 append 到文件
                with open(raw_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                time.sleep(0.3)  # 避免限流

    print(f"\n原始结果已保存: {raw_path}", flush=True)

    # 汇总
    if not args.no_judge:
        summary = summarize(results)
        sum_path = os.path.join(RESULT_DIR, f"summary_{ts}.json")
        with open(sum_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"汇总已保存: {sum_path}")
        print_summary(summary)


def summarize(results):
    """按模型×模式×层级汇总平均分"""
    from collections import defaultdict
    stat = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.get("judge_score", -1) < 0:
            continue
        key = (r["model"], r["mode"])
        stat[key]["all"].append(r["judge_score"])
        stat[key][f"L{r['level']}"].append(r["judge_score"])

    summary = {}
    for (model, mode), levels in stat.items():
        entry = {"model": model, "mode": mode}
        for lv, scores in levels.items():
            entry[lv] = round(sum(scores) / len(scores), 2)
        summary[f"{model}|{mode}"] = entry
    return summary


def print_summary(summary):
    print("\n" + "=" * 60)
    print("评测汇总（平均分，满分 10）")
    print("=" * 60)
    # 按模型分组，对比裸跑 vs 知识库
    models = sorted(set(k.split("|")[0] for k in summary))
    for m in models:
        bare = summary.get(f"{m}|bare", {})
        kb = summary.get(f"{m}|with_kb", {})
        bare_all = bare.get("all", 0)
        kb_all = kb.get("all", 0)
        diff = kb_all - bare_all
        print(f"\n{m}")
        print(f"  裸跑:     {bare_all}")
        print(f"  +知识库:  {kb_all}  (增益 {diff:+.2f})")
        for lv in ["L3", "L4"]:
            b = bare.get(lv, 0)
            k = kb.get(lv, 0)
            print(f"    {lv}: 裸跑 {b} → +KB {k}  ({k-b:+.2f})")


if __name__ == "__main__":
    main()
