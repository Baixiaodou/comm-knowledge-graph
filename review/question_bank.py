"""题库读写：benchmark 导入 + 题目增删查 + 解析缓存回写。"""
import json
from datetime import datetime

import config
from db import get_conn


def _now():
    return datetime.now().isoformat(timespec="seconds")


def import_benchmark(force=False):
    """把 benchmark/questions_full.json 导入题库（source='benchmark'）。

    每道题绑定 expected_nodes（可为多节点）。返回导入条数。
    """
    if not config.BENCHMARK_FILE.exists():
        return 0
    with get_conn() as c:
        cnt = c.execute("SELECT COUNT(*) FROM questions WHERE source='benchmark'").fetchone()[0]
        if cnt > 0 and not force:
            return 0
        data = json.loads(config.BENCHMARK_FILE.read_text(encoding="utf-8"))
        questions = data.get("questions", [])
        n = 0
        for q in questions:
            qid = (q.get("id") or "").strip()
            if not qid:
                continue
            c.execute(
                "INSERT OR IGNORE INTO questions(question_id, type, stem, answer, analysis, source, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (qid, "short_answer", q.get("question", ""), q.get("answer", ""), None, "benchmark", _now()),
            )
            for nid in q.get("expected_nodes", []):
                c.execute(
                    "INSERT OR IGNORE INTO question_nodes(question_id, node_id) VALUES(?, ?)", (qid, nid)
                )
            n += 1
        return n


def question_ids_for_nodes(node_ids):
    """返回覆盖这些节点（任一）的题目 id（去重）。"""
    if not node_ids:
        return []
    ph = ",".join("?" for _ in node_ids)
    with get_conn() as c:
        rows = c.execute(
            f"SELECT DISTINCT question_id FROM question_nodes WHERE node_id IN ({ph})", list(node_ids)
        ).fetchall()
    return [r["question_id"] for r in rows]


def get_questions(qids):
    if not qids:
        return []
    ph = ",".join("?" for _ in qids)
    with get_conn() as c:
        rows = c.execute(f"SELECT * FROM questions WHERE question_id IN ({ph})", list(qids)).fetchall()
    return [dict(r) for r in rows]


def get_question(qid):
    with get_conn() as c:
        row = c.execute("SELECT * FROM questions WHERE question_id=?", (qid,)).fetchone()
    return dict(row) if row else None


def question_nodes(qid):
    with get_conn() as c:
        rows = c.execute("SELECT node_id FROM question_nodes WHERE question_id=?", (qid,)).fetchall()
    return [r["node_id"] for r in rows]


def add_question(question):
    """question: {question_id, type, stem, answer, analysis, source_nodes:[..]}"""
    with get_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO questions(question_id, type, stem, answer, analysis, source, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                question["question_id"],
                question["type"],
                question["stem"],
                question.get("answer"),
                question.get("analysis"),
                "ai",
                _now(),
            ),
        )
        for nid in question.get("source_nodes", []):
            c.execute(
                "INSERT OR IGNORE INTO question_nodes(question_id, node_id) VALUES(?, ?)",
                (question["question_id"], nid),
            )


def set_analysis(qid, analysis):
    with get_conn() as c:
        c.execute("UPDATE questions SET analysis=? WHERE question_id=?", (analysis, qid))


def delete_question(qid):
    with get_conn() as c:
        c.execute("DELETE FROM questions WHERE question_id=?", (qid,))
        c.execute("DELETE FROM question_nodes WHERE question_id=?", (qid,))
        c.execute("DELETE FROM review_records WHERE question_id=?", (qid,))


def count_questions_for_nodes(node_ids):
    if not node_ids:
        return 0
    ph = ",".join("?" for _ in node_ids)
    with get_conn() as c:
        row = c.execute(
            f"SELECT COUNT(DISTINCT question_id) AS n FROM question_nodes WHERE node_id IN ({ph})",
            list(node_ids),
        ).fetchone()
    return row["n"]


def all_questions_for_node(node_id):
    qids = question_ids_for_nodes([node_id])
    return get_questions(qids)
