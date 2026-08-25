"""S1：纯 TF-IDF 双池分流 + TF-IDF 选点（0 LLM 调用，成本基线）"""

from .base import BaseStrategy


class S1(BaseStrategy):
    name = "S1"
    desc = "纯 TF-IDF 双池分流（floor/margin）+ TF-IDF top-2 选点，0 次 LLM"

    def route(self, query: str):
        hubs, leaves = self._dual_pool(query)
        is_hub, _h, _l = self._decide(hubs, leaves)
        if is_hub:
            return "hub", [n["id"] for n, _s in hubs[:2]]
        return "leaf", []
