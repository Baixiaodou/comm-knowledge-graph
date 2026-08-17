"""调用外部 LLM（OpenAI 兼容接口）出题 / 生成解析。"""
import json
import re

from openai import OpenAI

import config
import prompts


class LLMNotConfigured(Exception):
    pass


def _client():
    cfg = config.get_llm_config()
    if not cfg:
        raise LLMNotConfigured(
            "未配置 LLM API key。请在 review/.env 或 tools/.env 中填写 DEEPSEEK_API_KEY 或 SILICONFLOW_API_KEY。"
        )
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=120)
    return client, cfg["model"]


def _chat(client, model, system, user, temperature=0.7):
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    return r.choices[0].message.content


def _extract_json(text: str):
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1).strip()
    start = text.find("[")
    if start == -1:
        start = text.find("{")
    end = text.rfind("]")
    if end == -1:
        end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def generate_questions(node_ids, node_contexts, n=5, types=None):
    """让 LLM 基于节点原文出一批题，返回 list[dict]（每项含 source_nodes）。"""
    client, model = _client()
    types = types or config.ALL_TYPES
    user = prompts.gen_user(node_contexts, node_ids, n, types)
    content = _chat(client, model, prompts.GEN_SYSTEM, user)
    data = _extract_json(content)
    if isinstance(data, dict):
        data = data.get("questions") or [data]

    node_set = set(node_ids)
    out = []
    for it in data:
        if not isinstance(it, dict):
            continue
        it["type"] = it.get("type", "short_answer")
        if it["type"] not in config.ALL_TYPES:
            it["type"] = "short_answer"
        it["stem"] = (it.get("stem") or "").strip()
        it["answer"] = (it.get("answer") or "").strip()
        it["analysis"] = (it.get("analysis") or "").strip()
        if not it["stem"]:
            continue
        # 解析每道题绑定的节点；AI 没给准就回退到所选主节点
        raw_nodes = it.get("nodes") or []
        if isinstance(raw_nodes, str):
            raw_nodes = [raw_nodes]
        valid = [x for x in raw_nodes if x in node_set]
        it["source_nodes"] = valid or ([node_ids[0]] if node_ids else [])
        out.append(it)
    return out


def generate_analysis(stem, answer, node_contexts):
    """基于节点原文生成某道题的解析。"""
    client, model = _client()
    user = prompts.ana_user(node_contexts, stem, answer)
    return _chat(client, model, prompts.ANA_SYSTEM, user, temperature=0.3).strip()
