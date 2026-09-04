"""面试驱动的节点掌握度聚合（v2 模拟面试版）。

数据源：interview_turns（仅统计 status='finished' 且 excluded=0 的场次）。
判定映射：correct=4（绿） partial=3（黄） wrong/unanswered/offtopic=1（薄弱，一票否决红）。
图谱着色 = f(面试历史)，不再读写旧版 review_records 刷题表。
"""
import config
from collections import defaultdict

from db import get_conn, safe_json_loads

# 颜色
GREY = "#9aa5b1"   # 未复习
RED = "#e53e3e"    # 薄弱难点（一票否决）
COLOR_STOPS = [(2, "#f6ad55"), (3, "#f6e05e"), (4, "#48bb78")]  # 初步橙 / 基本黄 / 完全绿

VERDICT_VALUE = {"correct": 4, "partial": 3, "wrong": 1, "unanswered": 1, "offtopic": 1}


def interview_mastery():
    """返回 {node_id: {'mastery': float, 'count': int, 'weak': bool, 'levels': [...]}}。

    - count   = 该节点被问到的次数（跨场次）
    - weak    = 任一判定为 wrong/unanswered/offtopic → 一票否决
    - mastery = 无薄弱时按各次判定均值（2~4），供颜色插值
    """
    agg = defaultdict(list)
    weak_flag = defaultdict(bool)
    with get_conn() as c:
        rows = c.execute(
            """
            SELECT t.node_ids, t.judgment, s.excluded, s.status
            FROM interview_turns t
            JOIN interview_sessions s ON s.session_id = t.session_id
            WHERE s.status = 'finished' AND s.excluded = 0
              AND t.user_answer IS NOT NULL AND t.judgment IS NOT NULL
            """
        ).fetchall()

    for r in rows:
        j = safe_json_loads(r["judgment"]) or {}
        verdict = j.get("verdict")
        if verdict not in config.VERDICT_CN:
            continue
        node_ids = safe_json_loads(r["node_ids"], []) or []
        for nid in node_ids:
            agg[nid].append(verdict)
            if verdict in ("wrong", "unanswered", "offtopic"):
                weak_flag[nid] = True

    out = {}
    for nid, verdicts in agg.items():
        vals = [VERDICT_VALUE[v] for v in verdicts]
        out[nid] = {
            "mastery": (sum(vals) / len(vals)) if vals else 0.0,
            "count": len(verdicts),
            "weak": weak_flag.get(nid, False),
            "levels": verdicts,
        }
    return out


def total_stats():
    """全局统计：面试场次 / 总题数 / 薄弱节点数。供进度页展示。"""
    with get_conn() as c:
        n_sessions = c.execute("SELECT COUNT(*) AS n FROM interview_sessions WHERE status='finished'").fetchone()["n"]
        n_turns = c.execute(
            "SELECT COUNT(*) AS n FROM interview_turns t "
            "JOIN interview_sessions s ON s.session_id=t.session_id "
            "WHERE s.status='finished' AND s.excluded=0 AND t.user_answer IS NOT NULL AND t.judgment IS NOT NULL"
        ).fetchone()["n"]
    n_weak = sum(1 for e in interview_mastery().values() if e["weak"])
    return {"sessions": n_sessions, "turns": n_turns, "weak_nodes": n_weak}


# ---------- 颜色插值 ----------
def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def value_to_color(v):
    v = max(2.0, min(4.0, float(v)))
    stops = [(s, _hex_to_rgb(c)) for s, c in COLOR_STOPS]
    if v <= stops[0][0]:
        return COLOR_STOPS[0][1]
    if v >= stops[-1][0]:
        return COLOR_STOPS[-1][1]
    for i in range(len(stops) - 1):
        v0, c0 = stops[i]
        v1, c1 = stops[i + 1]
        if v0 <= v <= v1:
            t = (v - v0) / (v1 - v0)
            rgb = tuple(c0[j] + (c1[j] - c0[j]) * t for j in range(3))
            return _rgb_to_hex(rgb)
    return COLOR_STOPS[-1][1]


def mastery_color(entry):
    """节点掌握度 → 颜色。None/无记录=灰，有薄弱=红，否则按均值渐变。"""
    if not entry or entry["count"] == 0:
        return GREY
    if entry["weak"]:
        return RED
    return value_to_color(entry["mastery"])


def mastery_label(entry):
    if not entry or entry["count"] == 0:
        return "未复习"
    if entry["weak"]:
        return "薄弱难点"
    v = entry["mastery"]
    if v < 2.5:
        return "初步掌握"
    if v < 3.5:
        return "基本掌握"
    return "完全掌握"
