"""S2：TF-IDF 分流 + hub 在局时 LLM 兜底确认 HUB/LEAF + TF-IDF 选点

hub 在局（双池判定为 hub）才调 1 次 LLM 做二分类确认；
确认后选点仍用 TF-IDF top-2（不信任 LLM 排序的对照组）。
"""

from .base import BaseStrategy
from .prompts import ROUTE_SYSTEM, build_confirm_user


class S2(BaseStrategy):
    name = "S2"
    desc = "TF-IDF 分流 + hub 在局时 LLM 确认 HUB/LEAF + TF-IDF top-2 选点"

    def _confirm(self, query: str, hub_candidates) -> str:
        cand = "\n".join(f"- [{n['id']}] {n['title']}：{n['summary']}" for n, _s in hub_candidates[:3])
        reply = self._llm([
            {"role": "system", "content": ROUTE_SYSTEM},
            {"role": "user", "content": build_confirm_user(query, cand)},
        ], max_tokens=10, temperature=0.1)
        return reply.strip().upper()[:8]

    def route(self, query: str):
        hubs, leaves = self._dual_pool(query)
        is_hub, _h, _l = self._decide(hubs, leaves)
        if is_hub:
            ans = self._confirm(query, hubs)
            if ans.startswith("HUB"):
                return "hub", [n["id"] for n, _s in hubs[:2]]
            return "leaf", []
        return "leaf", []
