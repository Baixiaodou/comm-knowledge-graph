"""S3：TF-IDF 分流 + LLM 一次调用（兜底确认 HUB/LEAF + 从全量 hub 语义选点）

用户提议的合并方案：确认与选点一次调用完成，不信任 TF-IDF 对 hub 的排序，
选点基于全量 hub 的语义理解。
"""

from .base import BaseStrategy, parse_json_reply
from .prompts import ROUTE_SYSTEM, build_route_user


class S3(BaseStrategy):
    name = "S3"
    desc = "TF-IDF 分流 + LLM 一次调用（确认 HUB/LEAF + 从全量 hub 语义选 1-2 个）"

    def _route_llm(self, query: str, menu: str) -> tuple[str, list[str]]:
        selection = (
            "若是大问题，从下列 hub 中选出最相关的 1-2 个（覆盖回答该问题最应介绍的主题模块；"
            "问整个知识体系/全部课程/学习顺序/没有对应枝干的大范围问题选 root）：\n"
            f"{menu}"
        )
        reply = self._llm([
            {"role": "system", "content": ROUTE_SYSTEM},
            {"role": "user", "content": build_route_user(query, selection)},
        ], max_tokens=200, temperature=0.1)
        data = parse_json_reply(reply)
        path = str(data.get("path", "")).strip().upper()
        if path.startswith("HUB"):
            hubs = [h for h in data.get("hubs", []) if h in self.kb.by_id][:2]
            if hubs:
                return "hub", hubs
        return "leaf", []

    def route(self, query: str):
        hubs, leaves = self._dual_pool(query)
        is_hub, _h, _l = self._decide(hubs, leaves)
        if is_hub:
            return self._route_llm(query, self.kb.hub_menu())
        return "leaf", []
