"""AI 模拟面试引擎（不依赖 Streamlit，纯逻辑可单测）。

核心循环：每轮一次 LLM 调用，一次完成
  ① 判定考生上一题回答（verdict/comment/weak_nodes，内部笔记）
  ② 基于候选知识点原文出下一题（next_question/next_nodes）
收束条件：达到目标轮数 / 候选知识点用尽 / LLM 主动收束 / 用户手动结束。
每轮立即落盘 SQLite，刷新后可 resume 重建状态。

报告为纯本地聚合（统计 + 逐题 + 薄弱清单 + 评级），不额外消耗 LLM。

注意：引擎通过 set_nodes() 拿到知识库节点（只读），app 启动时注入一次。
"""
import json
import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

import config
import prompts_interview as pi
import prompts_reviewer as pr
from db import get_conn

VERDICTS = ("correct", "partial", "wrong", "unanswered", "offtopic")
WEAK_VERDICTS = ("wrong", "unanswered", "offtopic")
_CONTENT_TYPES = ("core", "leaf")
_CAND_PER_ROUND = 3          # 每轮注入的候选知识点个数
_PER_NODE_CAP = 1600         # 每个候选节点正文截断上限（提速：控制每轮注入量）
_NOTE_PER_MSG = 60           # 面试官笔记单行截断

_nodes: Dict[str, object] = {}          # app 注入的知识库节点（只读）
_children: Dict[str, List[str]] = {}


def set_nodes(nodes, children):
    """app 启动时注入知识库（引擎只读，不写回 nodes/）。"""
    global _nodes, _children
    _nodes = nodes
    _children = children


def _now():
    return datetime.now().isoformat(timespec="seconds")


class LLMNotConfigured(Exception):
    pass


# ---------------- LLM 底层 ----------------

def _client():
    cfg = config.get_llm_config()
    if not cfg:
        raise LLMNotConfigured("未配置 LLM API key：请在页面左侧「🔑 API 配置」粘贴保存，或编辑 review/.env 后重启")
    from openai import OpenAI

    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=120), cfg["model"]


def _extract_json(text: str):
    """容错提取 JSON 对象：容忍 markdown 围栏与前后缀文字。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _llm_json(system: str, user: str, temperature: float = 0.4) -> dict:
    client, model = _client()
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=2000,  # 防个别轮生成超长文本拖慢；正常一轮输出仅 ~100 tokens
    )
    return _extract_json(r.choices[0].message.content)


# ---------------- 会话 CRUD ----------------

def new_session(scope_root: str, scope_title: str, cfg: dict) -> str:
    """cfg: {depth, target_rounds, review_mode}"""
    sid = uuid.uuid4().hex[:12]
    with get_conn() as c:
        c.execute(
            "INSERT INTO interview_sessions(session_id, scope_root, scope_title, config_json, status, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (sid, scope_root, scope_title, json.dumps(cfg, ensure_ascii=False), "active", _now()),
        )
    return sid


def get_session(sid: str) -> Optional[dict]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM interview_sessions WHERE session_id=?", (sid,)).fetchone()
    return dict(row) if row else None


def get_turns(sid: str) -> List[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM interview_turns WHERE session_id=? ORDER BY round_no", (sid,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_sessions() -> List[dict]:
    """全部会话（含题数/已答数统计），按创建时间倒序。"""
    with get_conn() as c:
        rows = c.execute(
            """
            SELECT s.*,
                   COUNT(t.round_no) AS n_turns,
                   SUM(CASE WHEN t.user_answer IS NOT NULL THEN 1 ELSE 0 END) AS n_answered
            FROM interview_sessions s
            LEFT JOIN interview_turns t ON t.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _save_turn(sid, round_no, question, node_ids, user_answer=None, judgment=None):
    with get_conn() as c:
        c.execute(
            "INSERT INTO interview_turns(session_id, round_no, question, node_ids, user_answer, judgment, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                sid,
                round_no,
                question,
                json.dumps(node_ids, ensure_ascii=False),
                user_answer,
                json.dumps(judgment, ensure_ascii=False) if judgment else None,
                _now(),
            ),
        )


def _update_turn(sid, round_no, user_answer, judgment):
    with get_conn() as c:
        c.execute(
            "UPDATE interview_turns SET user_answer=?, judgment=? WHERE session_id=? AND round_no=?",
            (user_answer, json.dumps(judgment, ensure_ascii=False), sid, round_no),
        )


def mark_finished(sid: str):
    with get_conn() as c:
        c.execute(
            "UPDATE interview_sessions SET status='finished', finished_at=? WHERE session_id=?",
            (_now(), sid),
        )


def set_excluded(sid: str, excluded: bool):
    """excluded=1 的场次不参与图谱掌握度统计（可随时切回）。"""
    with get_conn() as c:
        c.execute("UPDATE interview_sessions SET excluded=? WHERE session_id=?", (1 if excluded else 0, sid))


def delete_session(sid: str):
    with get_conn() as c:
        c.execute("DELETE FROM interview_turns WHERE session_id=?", (sid,))
        c.execute("DELETE FROM interview_reviews WHERE session_id=?", (sid,))
        c.execute("DELETE FROM interview_sessions WHERE session_id=?", (sid,))


# ---------------- 判定校准官（评审官） ----------------

def get_review(sid: str) -> Optional[dict]:
    """已生成的评审结果；未生成返回 None。"""
    with get_conn() as c:
        row = c.execute(
            "SELECT review_json FROM interview_reviews WHERE session_id=?", (sid,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["review_json"])
    except (TypeError, ValueError):
        return None


def save_review(sid: str, review: dict):
    with get_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO interview_reviews(session_id, review_json, created_at) VALUES(?,?,?)",
            (sid, json.dumps(review, ensure_ascii=False), _now()),
        )


def _review_materials(sid: str) -> dict:
    """组装评审官复审材料：逐题记录文本 + 涉及节点原文。"""
    session = get_session(sid)
    turns = get_turns(sid)
    cfg = json.loads(session["config_json"])
    lines, node_ids = [], []
    for t in turns:
        try:
            j = json.loads(t["judgment"]) if t["judgment"] else {}
        except (TypeError, ValueError):
            j = {}
        nids = json.loads(t["node_ids"] or "[]")
        node_ids.extend(nids)
        node_ids.extend(j.get("weak_nodes") or [])
        verdict = j.get("verdict", "?")
        lines.append(
            f"Q{t['round_no']}（考察节点: {', '.join(nids) or '—'}）\n"
            f"  问题：{t['question']}\n"
            f"  考生回答：{(t['user_answer'] or '（未作答/跳过）')[:400]}\n"
            f"  面试官判定：{pr._fmt_verdict(verdict)}\n"
            f"  面试官点评：{j.get('comment', '')[:200]}\n"
        )
    blocks = []
    for nid in dict.fromkeys(node_ids):  # 去重保序
        n = _nodes.get(nid)
        if not n:
            continue
        body = (n.body or "")[:_PER_NODE_CAP]
        if len(n.body or "") > _PER_NODE_CAP:
            body += "\n……（正文过长已截断）"
        blocks.append(f"[节点 {nid}「{n.title}」]\n摘要：{n.summary}\n{body}")
    return {
        "turns_text": "\n".join(lines),
        "nodes_text": "\n\n".join(blocks),
        "cfg": cfg,
    }


def build_review(sid: str) -> dict:
    """生成（或返回已生成的）判定校准与诊断。

    评审官为独立 LLM 角色：复核逐题判定 + 产出画像/复习计划。
    仅 finished 场次可评审；已生成过则直接返回（不重复消耗 LLM）。
    失败抛异常由 UI 提示，不影响主流程与图谱（图谱仍以面试官判定为准）。
    """
    existing = get_review(sid)
    if existing:
        return existing
    session = get_session(sid)
    if not session:
        raise ValueError("场次不存在")
    if session["status"] != "finished":
        raise ValueError("面试未结束，暂不能生成评审")
    cfg = json.loads(session["config_json"])
    mats = _review_materials(sid)
    if not mats["turns_text"].strip():
        raise ValueError("本场没有可评审的答题记录")
    system = pr.system_message()
    user = pr.user_message(
        session["scope_title"], cfg.get("depth", ""), cfg.get("style", ""),
        mats["turns_text"], mats["nodes_text"],
    )
    data = _llm_json(system, user, temperature=0.2)

    # ---- 规整输出 ----
    vr = []
    for item in data.get("verdict_review") or []:
        if not isinstance(item, dict):
            continue
        orig, sugg = item.get("original"), item.get("suggested")
        if orig not in VERDICTS or sugg not in VERDICTS:
            continue
        vr.append(
            {
                "round_no": int(item.get("round_no") or 0),
                "original": orig,
                "suggested": sugg,
                "reason": str(item.get("reason") or "")[:300],
            }
        )
    plan = []
    for item in (data.get("plan") or [])[:5]:
        if not isinstance(item, dict):
            continue
        nid = item.get("node_id")
        if nid not in _nodes:
            continue
        plan.append(
            {
                "node_id": nid,
                "title": _nodes[nid].title,
                "why": str(item.get("why") or "")[:200],
                "how": str(item.get("how") or "")[:300],
            }
        )
    review = {
        "verdict_review": vr,
        "portrait": str(data.get("portrait") or "").strip(),
        "plan": plan,
        "next_suggestion": str(data.get("next_suggestion") or "").strip(),
    }
    save_review(sid, review)
    return review


# ---------------- 节点规划 ----------------

def _children_of(nodes):
    ch: Dict[str, List[str]] = {nid: [] for nid in nodes}
    for nid, n in nodes.items():
        if n.parent and n.parent in nodes:
            ch[n.parent].append(nid)
    return ch


def content_nodes(root_id: str) -> List[str]:
    """所选子树内适合出题的内容节点（core/leaf），BFS 稳定顺序。"""
    if root_id not in _nodes:
        return []
    ids: List[str] = []
    queue = [root_id]
    while queue:
        cur = queue.pop(0)
        if cur in _nodes:
            ids.append(cur)
        queue.extend(_children.get(cur, []))
    return [nid for nid in ids if _nodes[nid].type in _CONTENT_TYPES]


def weak_priorities(scope_root: str) -> List[tuple]:
    """跨场次薄弱聚合：该子树范围内、全部已结束(excluded=0)场次中被判定
    答错/未答上/跑题的节点，按命中次数倒序返回 [(node_id, count), ...]。

    这是"记忆驱动复习闭环"的数据底座：开新场时把历史薄弱点排到候选最前复测。
    """
    content = set(content_nodes(scope_root))
    if not content:
        return []
    cnt: Counter = Counter()
    with get_conn() as c:
        sids = [
            r[0]
            for r in c.execute(
                "SELECT session_id FROM interview_sessions WHERE status='finished' AND excluded=0"
            ).fetchall()
        ]
    for sid in sids:
        for t in get_turns(sid):
            try:
                j = json.loads(t["judgment"]) if t["judgment"] else {}
            except (TypeError, ValueError):
                continue
            if j.get("verdict") in WEAK_VERDICTS:
                for nid in json.loads(t["node_ids"] or "[]"):
                    if nid in content:
                        cnt[nid] += 1
                for w in j.get("weak_nodes") or []:
                    if w in content:
                        cnt[w] += 1
    return cnt.most_common()


def _scope_content(scope_root: str, weak_first: bool = True) -> List[str]:
    """范围内容节点，weak_first=True 时把历史薄弱节点提到最前（优先复测）。"""
    content = content_nodes(scope_root)
    if weak_first:
        weak_set = {nid for nid, _ in weak_priorities(scope_root)}
        if weak_set:
            content = [n for n in content if n in weak_set] + [n for n in content if n not in weak_set]
    return content


def _weak_text(scope_root: str) -> str:
    """把历史薄弱点格式化为给面试官的提示文本（最多列 8 条）。"""
    lines = []
    for nid, cnt in weak_priorities(scope_root)[:8]:
        nd = _nodes.get(nid)
        if nd:
            lines.append(f"- 「{nd.title}」[{nid}]：历史答错 {cnt} 次")
    return "\n".join(lines)


def _candidates(content: List[str], used: set, k: int = _CAND_PER_ROUND) -> List[str]:
    return [nid for nid in content if nid not in used][:k]


def _candidates_text(nids: List[str]) -> str:
    blocks = []
    for i, nid in enumerate(nids, 1):
        n = _nodes.get(nid)
        if not n:
            continue
        body = (n.body or "")[:_PER_NODE_CAP]
        if len(n.body or "") > _PER_NODE_CAP:
            body += "\n……（正文过长已截断）"
        links = [lk.get("title") or lk.get("id") or "" for lk in n.links]
        parts = [f"[候选{i}] 节点 {nid}「{n.title}」", f"摘要：{n.summary}"]
        if n.cot:
            parts.append(f"思维链：{n.cot.get('origin', '')} → {n.cot.get('conclusion', '')}")
        if links:
            parts.append(f"相关连接：{', '.join(links[:6])}")
        parts.append(body)
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def _note_text(turns: List[dict]) -> str:
    lines = []
    for t in turns:
        try:
            j = json.loads(t["judgment"]) if t["judgment"] else {}
        except (TypeError, ValueError):
            continue
        v = j.get("verdict")
        if not v:
            continue
        vcn = config.VERDICT_CN.get(v, v)
        weak = ",".join(j.get("weak_nodes") or [])
        q = (t["question"] or "").replace("\n", " ")[:_NOTE_PER_MSG]
        lines.append(f"Q{t['round_no']}「{q}」→ {vcn}" + (f" | 弱:{weak}" if weak else ""))
    return "\n".join(lines)


def _valid_nodes(raw, candidates: List[str]) -> List[str]:
    """校验 LLM 给的节点：必须 ⊆ 本轮候选且存在；否则回退候选[0]。"""
    if isinstance(raw, str):
        raw = [raw]
    valid = [x for x in (raw or []) if x in candidates and x in _nodes]
    return valid or ([candidates[0]] if candidates else [])


# ---------------- 引擎推进 ----------------

def ask_first(sid: str) -> dict:
    """开场：出第 1 题并落盘（未作答）。"""
    session = get_session(sid)
    cfg = json.loads(session["config_json"])
    weak_first = cfg.get("weak_first", True)
    content = _scope_content(session["scope_root"], weak_first)
    cands = _candidates(content, set())
    if not cands:
        raise ValueError("该范围没有可出题的内容节点（core/leaf）")
    system = pi.system_message(
        cfg["depth"], session["scope_title"], len(content), cfg["target_rounds"],
        style=cfg.get("style", ""),
        weak_hint=_weak_text(session["scope_root"]) if weak_first else "",
    )
    user = pi.user_message(round_no=1, is_first=True, note_text="", candidates_text=_candidates_text(cands))
    data = _llm_json(system, user)
    q = (data.get("next_question") or "").strip()
    if not q:
        raise ValueError("AI 未返回题目，请重试")
    nids = _valid_nodes(data.get("next_nodes"), cands)
    _save_turn(sid, 1, q, nids)
    return {"round_no": 1, "question": q, "node_ids": nids}


def submit_answer(sid: str, answer: str) -> dict:
    """提交当前题回答（空串 = 跳过/未作答）→ 判定上一答 + 推进下一题。

    返回 {"finished": bool, "reason": str, "judged": {...}|None, "next": {...}|None}
    """
    session = get_session(sid)
    if not session or session["status"] != "active":
        return {"finished": True, "reason": "会话不存在或已结束"}
    cfg = json.loads(session["config_json"])
    target = cfg["target_rounds"]

    turns = get_turns(sid)
    current = next((t for t in reversed(turns) if t["user_answer"] is None), None)
    if not current:
        mark_finished(sid)
        return {"finished": True, "reason": "没有待作答的题目，会话已结束"}

    answered_before = len([t for t in turns if t["user_answer"] is not None])
    cur_nodes = json.loads(current["node_ids"] or "[]")

    # used：其余轮次问过的节点 + 全部历史薄弱点；当前题节点允许被"追问/确认"再覆盖
    used: set = set()
    for t in turns:
        if t["round_no"] == current["round_no"]:
            continue
        used.update(json.loads(t["node_ids"] or "[]"))
        try:
            used.update(json.loads(t["judgment"]).get("weak_nodes") or [])
        except (TypeError, ValueError):
            pass
    if cur_nodes:
        used.discard(cur_nodes[0])

    content = _scope_content(session["scope_root"], cfg.get("weak_first", True))
    n_content = len(content)
    force_end = (answered_before + 1) >= target
    cands = [] if force_end else _candidates(content, used)
    if force_end or not cands:
        cands_text = "（本轮为最后一轮：判定完成后请 should_end=true，next_question 填空串）"
        cands = cur_nodes or ([content[0]] if content else [])
    else:
        cands_text = _candidates_text(cands)

    system = pi.system_message(
        cfg["depth"], session["scope_title"], n_content, target,
        style=cfg.get("style", ""),
    )
    user = pi.user_message(
        round_no=current["round_no"] + 1,
        is_first=False,
        note_text=_note_text(turns),
        candidates_text=cands_text,
        current_question=current["question"],
        user_answer=answer,
    )
    data = _llm_json(system, user)

    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        verdict = "partial"
    weak = [x for x in (data.get("weak_nodes") or []) if x in _nodes]
    judgment = {
        "verdict": verdict,
        "comment": (data.get("comment") or "").strip(),
        "reference": (data.get("reference") or "").strip(),  # 参考答案要点（判后展示对照）
        "weak_nodes": weak,
    }
    _update_turn(sid, current["round_no"], answer, judgment)

    answered_now = answered_before + 1
    should_end = bool(data.get("should_end")) or force_end or (answered_now >= target) or (not cands and cands_text.startswith("（本轮为最后一轮"))
    reason = (data.get("reason") or "").strip()
    if should_end:
        mark_finished(sid)
        return {"finished": True, "reason": reason or "已达到目标轮数，面试结束", "judged": judgment, "next": None}

    q = (data.get("next_question") or "").strip()
    if not q:
        mark_finished(sid)
        return {"finished": True, "reason": "AI 未给出下一题（已收束）", "judged": judgment, "next": None}

    nids = _valid_nodes(data.get("next_nodes"), cands)
    _save_turn(sid, current["round_no"] + 1, q, nids)
    return {
        "finished": False,
        "judged": judgment,
        "next": {"round_no": current["round_no"] + 1, "question": q, "node_ids": nids},
    }


def manual_finish(sid: str):
    """用户主动结束：未答的当前题记 unanswered 后收束。"""
    turns = get_turns(sid)
    current = next((t for t in reversed(turns) if t["user_answer"] is None), None)
    if current:
        judgment = {
            "verdict": "unanswered",
            "comment": "面试被主动结束",
            "weak_nodes": json.loads(current["node_ids"] or "[]"),
        }
        _update_turn(sid, current["round_no"], "（未作答）", judgment)
    mark_finished(sid)


# ---------------- 报告（本地聚合，无 LLM） ----------------

def build_report(sid: str) -> dict:
    session = get_session(sid)
    turns = get_turns(sid)
    cfg = json.loads(session["config_json"])

    answered = []
    for t in turns:
        try:
            j = json.loads(t["judgment"]) if t["judgment"] else {}
        except (TypeError, ValueError):
            j = {}
        answered.append(
            {
                "round_no": t["round_no"],
                "question": t["question"],
                "node_ids": json.loads(t["node_ids"] or "[]"),
                "user_answer": t["user_answer"] or "",
                "verdict": j.get("verdict"),
                "comment": j.get("comment", ""),
                "reference": j.get("reference", ""),  # 参考答案要点（判后对照复习）
                "weak_nodes": j.get("weak_nodes", []),
            }
        )

    verdict_cnt = Counter(a["verdict"] for a in answered if a["verdict"])
    n = len(answered)
    correct = verdict_cnt.get("correct", 0)
    partial = verdict_cnt.get("partial", 0)

    score = (correct + 0.6 * partial) / n if n else 0.0
    grade, grade_cn = "D", config.GRADE_BANDS[-1][2]
    for thr, g, desc in config.GRADE_BANDS:
        if score >= thr:
            grade, grade_cn = g, desc
            break

    weak_counter: Counter = Counter()
    for a in answered:
        if a["verdict"] in WEAK_VERDICTS:
            weak_counter.update(a["node_ids"])
        for w in a["weak_nodes"]:
            weak_counter.update([w])
    weak_nodes = []
    for nid, times in weak_counter.most_common():
        nd = _nodes.get(nid)
        if nd:
            weak_nodes.append(
                {"node_id": nid, "title": nd.title, "summary": nd.summary, "times": times, "body": (nd.body or "")[:1200]}
            )

    content = content_nodes(session["scope_root"])
    asked_ids = set()
    for t in turns:
        asked_ids.update(json.loads(t["node_ids"] or "[]"))
    coverage_asked = len(asked_ids & set(content))

    return {
        "session": session,
        "cfg": cfg,
        "scope_title": session["scope_title"],
        "n_turns": n,
        "verdict_cnt": {
            "correct": correct,
            "partial": partial,
            "wrong": verdict_cnt.get("wrong", 0),
            "unanswered": verdict_cnt.get("unanswered", 0),
            "offtopic": verdict_cnt.get("offtopic", 0),
        },
        "score_pct": round(score * 100),
        "grade": grade,
        "grade_cn": grade_cn,
        "coverage": {"asked": coverage_asked, "total": len(content)},
        "answered": answered,
        "weak_nodes": weak_nodes,
    }
