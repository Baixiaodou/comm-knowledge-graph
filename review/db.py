"""SQLite 本地存储：模拟面试会话 + 逐轮记录 + 节点掌握度聚合依据。

核心表（v2 模拟面试版）：
- interview_sessions  面试会话元信息（科目根节点 / 配置 / 状态 / 是否排除出图谱统计）
- interview_turns     逐轮记录（问题 / 用户回答 / 判定 JSON / 涉及节点）

旧版刷题表（questions / question_nodes / review_records）定义保留，
仅用于兼容历史 db 文件，新代码不再读写它们。
"""
import sqlite3
from contextlib import contextmanager

import config

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
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as c:
        c.executescript(SCHEMA)
