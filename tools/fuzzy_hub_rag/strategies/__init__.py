"""策略注册表：fuzzy_benchmark.py 从这里拿全部策略实例"""

from .s1_tfidf import S1
from .s2_llm_gate import S2
from .s3_llm_full import S3
from .s4_llm_cand import S4
from .s5_llm_all import S5

ALL = [S1, S2, S3, S4, S5]


def make_strategies(kb, client, floor=0.05, margin=0.02) -> list:
    return [cls(kb, client=client, floor=floor, margin=margin) for cls in ALL]
