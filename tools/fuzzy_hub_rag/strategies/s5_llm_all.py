"""S5：全 LLM 判定路由 + 全量选点（准确率上界对照）

每问必调 1 次 LLM（40 次），不依赖 TF-IDF 分流。作为准确率上界参考，
衡量「双池 TF-IDF 分流」本身在多大程度上损失了分类能力。
"""

from .base import BaseStrategy, parse_json_reply
from .prompts import ROUTE_SYSTEM, build_route_user


class S5(BaseStrategy):
    name = "S5"
    desc = "全 LLM 判定路由 + 全量 19 hub 选 1-2 个（上界对照，每问 1 次调用）"

    def route(self, query: str):
        selection = (
            "若是大问题，从下列 hub 中选出最相关的 1-2 个（覆盖回答该问题最应介绍的主题模块；"
            "问整个知识体系/全部课程/学习顺序/没有对应枝干的大范围问题选 root）：\n"
            f"{self.kb.hub_menu()}"
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
