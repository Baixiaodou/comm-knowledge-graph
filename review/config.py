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
    """按优先级加载 .env：review/.env（页面显式保存，最高）→ 知识库 tools/.env → 上一级 tools/.env（共享兜底，不覆盖已有值）。

    review/.env 用 override=True：它是本应用内显式保存的配置（页面「API 配置」面板写入），
    应覆盖系统环境残留；tools/.env 是共享文件（benchmark 等其他工具在用），只做兜底，绝不覆盖。
    """
    own = REVIEW_DIR / ".env"
    if own.exists():
        load_dotenv(own, override=True)
    for p in (KB_ROOT / "tools" / ".env", KB_ROOT.parent / "tools" / ".env"):
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

# ---------- 模拟面试：面试官风格（与深度档正交：风格管"怎么问"，深度管"问到哪层"） ----------
INTERVIEW_STYLES = ["温和引导", "学院派严谨", "压力测试"]

STYLE_DESC = {
    "温和引导": "像本校老师摸底：语气温和，答错给台阶、换角度提示，帮考生进入状态。",
    "学院派严谨": "像复试委员会：术语要精确、定义要完整，抓表述漏洞并要求澄清，追问逻辑链条。",
    "压力测试": "像最刁钻的导师：揪住漏洞反诘、逼问边界与反例，考应变与诚实（承认不知道的姿势）。",
}

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


# ---------- LLM：页面配置（安全落盘） ----------
def mask_key(key: str) -> str:
    """掩码显示 key：sk-1234****5678。绝不显示完整 key。"""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 10:
        return key[:3] + "****"
    return key[:6] + "…" + key[-4:]


def save_llm_config(api_key: str = "", base_url: str = "", model: str = "", env_file=None) -> bool:
    """把 LLM 配置保存到 review/.env（已被 .gitignore 排除，不会提交 GitHub）。

    - 只写入非空字段，保留文件里其他键（如 SILICONFLOW_API_KEY）。
    - 写文件同时立即更新本进程 os.environ，key 当场生效，无需重启。
    - env_file 仅供测试注入临时路径；默认写 REVIEW_DIR/.env。
    """
    api_key = (api_key or "").strip()
    base_url = (base_url or "").strip()
    model = (model or "").strip()
    if not (api_key or base_url or model):
        raise ValueError("至少填写一项（API key 或高级选项）")

    from dotenv import set_key

    env_file = Path(env_file) if env_file else (REVIEW_DIR / ".env")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.touch(exist_ok=True)

    if api_key:
        set_key(env_file, "DEEPSEEK_API_KEY", api_key)
        os.environ["DEEPSEEK_API_KEY"] = api_key
    if base_url:
        set_key(env_file, "REVIEW_BASE_URL", base_url)
        os.environ["REVIEW_BASE_URL"] = base_url
    if model:
        set_key(env_file, "REVIEW_MODEL", model)
        os.environ["REVIEW_MODEL"] = model
    return True


def api_key_status() -> dict:
    """供 UI 展示的脱敏状态：configured / provider / masked / model / base_url。"""
    cfg = get_llm_config()
    if not cfg:
        return {"configured": False}
    bu = cfg["base_url"]
    if "deepseek" in bu:
        provider = "DeepSeek"
    elif "siliconflow" in bu:
        provider = "SiliconFlow"
    else:
        provider = bu
    return {
        "configured": True,
        "provider": provider,
        "masked": mask_key(cfg["api_key"]),
        "model": cfg["model"],
        "base_url": bu,
    }
