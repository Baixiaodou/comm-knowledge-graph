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
BENCHMARK_FILE = KB_ROOT / "benchmark" / "questions_full.json"

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

# ---------- 掌握度 ----------
MASTERY_LEVELS = ["未复习", "初步掌握", "基本掌握", "完全掌握", "薄弱难点"]

MASTERY_VALUE = {
    "未复习": 0,
    "薄弱难点": 1,
    "初步掌握": 2,
    "基本掌握": 3,
    "完全掌握": 4,
}

# ---------- 题型 ----------
QUESTION_TYPE_CN = {
    "short_answer": "简答题",
    "judge": "判断题",
    "fill_blank": "填空题",
}
ALL_TYPES = list(QUESTION_TYPE_CN.keys())


# ---------- LLM ----------
def get_llm_config():
    """返回 (api_key, base_url, model)；未配置任何 key 时返回 None。"""
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
