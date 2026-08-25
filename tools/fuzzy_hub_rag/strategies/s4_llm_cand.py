"""S4：TF-IDF 分流 + LLM 从 TF-IDF top-5 候选 hub 里选点（验证候选池漏选担忧）

与 S3 同构（一次调用确认+选点），但选点范围限制为 TF-IDF 分数最高的 5 个 hub。
若结果显著差于 S3，说明「TF-IDF 对 hub 的排序不可靠、真 hub 会被漏出候选池」
的担忧成立，线上必须用全量语义选点。
"""

from .base import BaseStrategy, parse_json_reply
from .prompts import ROUTE_SYSTEM, build_route_user


class S4(BaseStrategy):
    name = "S4"
    desc = "TF-IDF 分流 + LLM 从 TF-IDF top-5 候选 hub 里选 1-2 个（验证漏选担忧）"
    candidate_k = 5

    def _route_llm(self, query: str, menu: str) -> tuple[str, list[str]]:
        selection = (
            "若是大问题，从下列候选 hub 中选出最相关的 1-2 个：\n"
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
            menu = "\n".join(f"- [{n['id']}] {n['title']}：{n['summary']}"
                             for n, _s in hubs[: self.candidate_k])
            return self._route_llm(query, menu)
        return "leaf", []
