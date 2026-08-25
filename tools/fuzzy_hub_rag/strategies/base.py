"""策略公共基类：双池 TF-IDF 分流 + LLM 客户端共享。

分流判定（所有 S1-S4 共用）：
    h = hub 池最高分，l = leaf 池最高分
    is_hub = h >= floor 且 (h - l) >= margin
floor/margin 是网格调优参数。S5 全 LLM 不用双池。
"""

import json
import re


def parse_json_reply(text: str) -> dict:
    """容错解析 LLM 输出（可能带 markdown 代码块/前后缀文字）"""
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class BaseStrategy:
    name = "base"
    desc = ""
    needs_client = False  # 该策略是否用 LLM

    def __init__(self, kb, client=None, floor=0.05, margin=0.02):
        self.kb = kb
        self.client = client
        self.floor = floor
        self.margin = margin
        self.llm_calls = 0  # 本轮 benchmark 累计额外调用次数

    # -- 双池 TF-IDF 分流 -------------------------------------------
    def _dual_pool(self, query: str):
        hubs = self.kb.rank(query, self.kb.hubs)
        leaves = self.kb.rank(query, self.kb.leaves)
        return hubs, leaves

    def _decide(self, hubs, leaves):
        """返回 (is_hub, h_score, l_score)"""
        h = hubs[0][1] if hubs else 0.0
        l = leaves[0][1] if leaves else 0.0
        return (h >= self.floor and (h - l) >= self.margin), h, l

    # -- LLM 调用 ----------------------------------------------------
    def _llm(self, messages, max_tokens=60, temperature=0.1) -> str:
        self.llm_calls += 1
        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    def route(self, query: str):
        """返回 ("hub"|"leaf", hub_ids)"""
        raise NotImplementedError

    def reset_stats(self):
        self.llm_calls = 0
