"""学习状态记录：写记录、按节点汇总掌握度 + 复习题数、映射颜色。"""
from collections import defaultdict
from datetime import datetime

import config
from db import get_conn

# 颜色
GREY = "#9aa5b1"   # 未复习
RED = "#e53e3e"    # 薄弱难点（一票否决）
COLOR_STOPS = [(2, "#f6ad55"), (3, "#f6e05e"), (4, "#48bb78")]  # 初步橙 / 基本黄 / 完全绿


def record_review(question_id, node_ids, mastery):
    """答完一道题后，为每个绑定节点各写一条记录（同题重复复习则计数 +1）。"""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as c:
        for nid in node_ids:
            c.execute(
                """
                INSERT INTO review_records(node_id, question_id, user_mastery, last_review_time, review_count)
                VALUES(?, ?, ?, ?, 1)
                ON CONFLICT(node_id, question_id) DO UPDATE SET
                    user_mastery = excluded.user_mastery,
                    last_review_time = excluded.last_review_time,
                    review_count = review_count + 1
                """,
                (nid, question_id, mastery, now),
            )


def node_records(node_id):
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM review_records WHERE node_id=? ORDER BY last_review_time DESC", (node_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def reviewed_question_ids():
    """返回所有已经做过（有记录）的题目 id 集合。"""
    with get_conn() as c:
        rows = c.execute("SELECT DISTINCT question_id FROM review_records").fetchall()
    return {r["question_id"] for r in rows}


def nodes_mastery():
    """返回 {node_id: {'mastery': float, 'count': int, 'weak': bool, 'levels': [...]}}。

    - count   = 该节点下已做题数（去重）
    - weak    = 是否有一题标了「薄弱难点」
    - mastery = 无薄弱时取各题掌握度均值（2~4），供颜色插值
    """
    agg = defaultdict(list)
    with get_conn() as c:
        rows = c.execute("SELECT node_id, user_mastery FROM review_records").fetchall()
    for r in rows:
        agg[r["node_id"]].append(r["user_mastery"])

    out = {}
    for nid, levels in agg.items():
        weak = any(m == "薄弱难点" for m in levels)
        vals = [config.MASTERY_VALUE.get(m, 0) for m in levels]
        out[nid] = {
            "mastery": (sum(vals) / len(vals)) if vals else 0.0,
            "count": len(levels),
            "weak": weak,
            "levels": levels,
        }
    return out


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
