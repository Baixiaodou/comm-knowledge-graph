"""路径与常量配置（全部用相对路径，兼容 Windows / Linux / 中文路径）。

本文件所在目录即 review/，其上一级是知识库根目录 knowledge-base/。
"""
from pathlib import Path
import os

from dotenv import load_dotenv

# ---------- 路径 ----------
REVIEW_DIR = Path(__file__).resolve().parent
KB_ROOT = REVIEW_DIR.parent
NODES_DIR = KB_ROOT / "knowledge-v2" / "nodes"
# 旧版刷题已移除，benchmark 不再作为题目来源（路径仅保留兼容引用）

DATA_DIR = REVIEW_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "review.db"


def _load_env():
    """按优先级加载 .env：review/.env → 知识库 tools/.env → 上一级 tools/.env（兼容旧布局）。"""
    candidates = [
        REVIEW_DIR / ".env",
        KB_ROOT / "tools" / ".env",
        KB_ROOT.parent / "tools" / ".env",
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)


_load_env()

# ---------- 模拟面试：深度档位 ----------
# 每档对应面试官 SYSTEM prompt 里的一段"追问指令"，控制最多追到哪一层。
INTERVIEW_DEPTHS = ["温和", "标准", "深挖", "压力测试"]

DEPTH_DESC = {
    "温和": "以概念理解为主（是什么、为什么需要）；答对即可换题，不做深度追问，适合第一轮摸底。",
    "标准": "理解 + 机制（怎么工作、关键权衡、易混点区分）；答对可在同一主题上追问一层 why，不要求现场推导。",
    "深挖": "机制 + 定量（数量级、关键公式、参数影响）；答对会要求手推简单公式或给出数量级估计。",
    "压力测试": "深挖 + 反诘 + 边界（为什么不用别的方案、这个结论在什么条件下失效、承认不知道的姿势）；会揪住答错的点反复追问，考应变与诚实。",
}

# ---------- 模拟面试：时长档 → 目标题数 ----------
DURATION_CHOICES = [5, 10, 15, 20]           # 分钟
DURATION_ROUNDS = {5: 6, 10: 10, 15: 14, 20: 18}   # 分钟 → 预估题目数

# ---------- 模拟面试：点评显示时机 ----------
REVIEW_MODES = ["结束后一起看", "每题立即看", "只判分不点评"]
# 判定五档（英文键，前端展示映射）
VERDICT_CN = {
    "correct": "答对",
    "partial": "部分正确",
    "wrong": "答错",
    "unanswered": "未答上",
    "offtopic": "跑题",
}


# ---------- LLM ----------
def get_llm_config():
    """返回 (api_key, base_url, model)；未配置任何 key 时返回 None。

    默认模型 deepseek-chat：官方别名，指向 v4-flash 非思考模式，JSON 输出稳定。
    ⚠️ 若改配 deepseek-v4-flash，必须额外禁用 thinking（extra_body），
    否则 high-effort thinking 会破坏结构化 JSON 出题/判定。
    """
    ds = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    sf = os.environ.get("SILICONFLOW_API_KEY", "").strip()

    if ds:
        return {
            "api_key": ds,
            "base_url": os.environ.get("REVIEW_BASE_URL", "https://api.deepseek.com"),
            "model": os.environ.get("REVIEW_MODEL", "deepseek-chat"),
        }
    if sf:
        return {
            "api_key": sf,
            "base_url": os.environ.get("REVIEW_BASE_URL", "https://api.siliconflow.cn/v1"),
            "model": os.environ.get("REVIEW_MODEL", "Qwen/Qwen3-32B"),
        }
    return None
