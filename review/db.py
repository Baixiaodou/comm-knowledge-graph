"""SQLite 本地存储：模拟面试会话 + 逐轮记录 + 节点掌握度聚合依据。

核心表（v2 模拟面试版）：
- interview_sessions  面试会话元信息（科目根节点 / 配置 / 状态 / 是否排除出图谱统计）
- interview_turns     逐轮记录（问题 / 用户回答 / 判定 JSON / 涉及节点）

旧版刷题表（questions / question_nodes / review_records）定义保留，
仅用于兼容历史 db 文件，新代码不再读写它们。
"""
import json
import sqlite3
from contextlib import contextmanager

import config


def safe_json_loads(s: str, default=None):
    """容错解析 JSON 字符串。

    interview_turns.judgment / node_ids 等字段的历史数据可能缺失或脏（旧版本写入格式、
    手工编辑库），各模块统一走此函数解析，不再各自 try/except（曾重复 6+ 处且口径不一）。
    """
    if s is None:
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default

SCHEMA = """
-- ===== v2 模拟面试核心表 =====
CREATE TABLE IF NOT EXISTS interview_sessions (
    session_id   TEXT PRIMARY KEY,
    scope_root   TEXT NOT NULL,          -- 面试范围根节点 id
    scope_title  TEXT NOT NULL,          -- 根节点标题（展示用）
    config_json  TEXT NOT NULL,          -- {"depth","target_rounds","review_mode"}
    status       TEXT NOT NULL DEFAULT 'active',   -- active | finished
    excluded     INTEGER NOT NULL DEFAULT 0,       -- 1 = 不参与图谱掌握度统计
    created_at   TEXT,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS interview_turns (
    session_id   TEXT NOT NULL,
    round_no     INTEGER NOT NULL,
    question     TEXT NOT NULL,          -- 面试官问题
    node_ids     TEXT NOT NULL,          -- 提问涉及的节点 id（JSON 数组，已校验存在）
    user_answer  TEXT,                   -- 用户回答；NULL = 尚未作答
    judgment     TEXT,                   -- JSON: {verdict,comment,level}
    created_at   TEXT,
    PRIMARY KEY (session_id, round_no)
);

CREATE INDEX IF NOT EXISTS idx_it_session ON interview_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_is_status   ON interview_sessions(status);

-- ===== 判定校准官（评审官）结果：一场一条 =====
CREATE TABLE IF NOT EXISTS interview_reviews (
    session_id   TEXT PRIMARY KEY,
    review_json  TEXT NOT NULL,          -- JSON: {verdict_review,portrait,plan,next_suggestion}
    created_at   TEXT
);

-- ===== 旧版刷题表（兼容历史 db，不再使用）=====
CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    stem        TEXT NOT NULL,
    answer      TEXT,
    analysis    TEXT,
    source      TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS question_nodes (
    question_id TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    PRIMARY KEY (question_id, node_id)
);

CREATE TABLE IF NOT EXISTS review_records (
    node_id          TEXT NOT NULL,
    question_id      TEXT NOT NULL,
    user_mastery     TEXT NOT NULL,
    last_review_time TEXT NOT NULL,
    review_count     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (node_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_qn_node ON question_nodes(node_id);
CREATE INDEX IF NOT EXISTS idx_rr_node ON review_records(node_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL + busy_timeout：本应用读多写少但跨页签/多按钮并发（图谱查询 vs 逐轮落盘），
    # 无 WAL 时写入会与并发读互相阻塞报 database is locked。
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_turn_if_pending(sid: str, round_no: int, user_answer: str, judgment: str) -> bool:
    """乐观锁：仅当该轮仍未作答时才写入（防双击/多窗口并发重复提交）。

    返回 True = 本写入生效；False = 该轮已被他人抢先作答（调用方应丢弃本次 LLM 结果，
    避免覆盖已落盘的判定或撞 (session_id, round_no) 主键抛 IntegrityError）。
    """
    with get_conn() as c:
        cur = c.execute(
            "UPDATE interview_turns SET user_answer=?, judgment=? "
            "WHERE session_id=? AND round_no=? AND user_answer IS NULL",
            (user_answer, judgment, sid, round_no),
        )
        return cur.rowcount > 0


def init_db():
    with get_conn() as c:
        c.executescript(SCHEMA)
