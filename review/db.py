"""SQLite 本地存储：题库 + 题目-节点绑定 + 学习记录。

三张表：
- questions      题库（题目本体，含 type/stem/answer/analysis/source）
- question_nodes 题目 ↔ 节点 多对多（综合题绑定多个节点）
- review_records 学习记录（节点 + 题目 + 掌握度 + 时间 + 复习次数）
"""
import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
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
