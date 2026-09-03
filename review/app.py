"""AI 模拟面试 · Streamlit 入口（v2：RAG 知识树 + LLM 模拟面试官）。

定位（2026-09 重构）：不再用 benchmark 题库刷题，而是依托 knowledge-v2
树形知识库的节点原文，由 LLM 扮演面试官做专业课问答训练：
  - 选科目范围（知识树子树）→ 设时长/追问深度/点评时机 → 开场
  - 每轮一次 LLM 调用：判定上一答（内部笔记）+ 出下一题
  - 结束出结业报告（逐题判定/薄弱知识点清单/评级），本地聚合不耗 LLM
  - 图谱着色 = f(面试历史)：薄弱红 / 基本黄 / 完全绿 / 未面灰

运行：streamlit run review/app.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from streamlit.components.v1 import html as components_html

import config
import db
import graph_viz
import interview
import knowledge
import records

st.set_page_config(page_title="AI 模拟面试 · 专业课", page_icon="🎤", layout="wide")

db.init_db()

MIN_OF_ROUNDS = {v: k for k, v in config.DURATION_ROUNDS.items()}


@st.cache_data(show_spinner=False)
def load_kb():
    ns = knowledge.load_nodes()
    return ns, knowledge.build_tree(ns)


nodes, children = load_kb()
interview.set_nodes(nodes, children)
llm_ready = config.get_llm_config() is not None

# 判定 → 徽章色
VERDICT_BG = {
    "correct": "#2f9e44",
    "partial": "#e67700",
    "wrong": "#c92a2a",
    "unanswered": "#c92a2a",
    "offtopic": "#c92a2a",
}


# ---------------- 树顺序 / 节点选择 ----------------
def flatten_tree(nodes, children):
    order, seen = [], set()

    def dfs(nid, depth):
        if nid in seen:
            return
        seen.add(nid)
        order.append((nid, depth))
        for c in sorted(children.get(nid, [])):
            dfs(c, depth + 1)

    roots = [n for n in nodes if n == "root"] or [
        n for n in nodes.values() if not n.parent or n.parent not in nodes
    ]
    for r in roots:
        if r in nodes:
            dfs(r, 0)
    for nid in nodes:
        if nid not in seen:
            order.append((nid, 0))
    return order


order = flatten_tree(nodes, children)
order_ids = [nid for nid, _ in order]
DEPTH = {nid: d for nid, d in order}


def node_label(nid):
    return f"{'　' * DEPTH.get(nid, 0)}{nodes[nid].title}"


# ---------------- 会话状态助手 ----------------
def active_session_id():
    """返回当前应展示的场次 id：优先 session_state（active=继续答，
    finished=展示刚结束/上次查看的场次报告）；否则捡库里任意 active 场次。

    自动回收"孤儿场"：开场 LLM 调用期间刷新/中断会留下 0 轮的 active 场次，
    既无题可答又会锁死开始按钮——此类场次直接删除，避免 UI 死锁。
    """
    sid = st.session_state.get("iv_sid")
    s = interview.get_session(sid) if sid else None
    if s:
        return sid
    for row in interview.list_sessions():
        if row["status"] == "active":
            if row["n_turns"] == 0:
                interview.delete_session(row["session_id"])  # 开场中断的孤儿场
                continue
            st.session_state["iv_sid"] = row["session_id"]
            return row["session_id"]
    st.session_state.pop("iv_sid", None)
    return None


def current_turn(sid):
    for t in reversed(interview.get_turns(sid)):
        if t["user_answer"] is None:
            return t
    return None


def verdict_badge(v):
    if not v:
        return ""
    bg = VERDICT_BG.get(v, "#868e96")
    return (
        f'<span style="background:{bg};color:#fff;padding:1px 9px;'
        f'border-radius:10px;font-size:12px;font-weight:600">'
        f'{config.VERDICT_CN.get(v, v)}</span>'
    )


def show_comment_enabled(cfg):
    return cfg.get("review_mode", "结束后一起看") != "只判分不点评"


def render_review(review):
    """展示评审官诊断结果。"""
    st.markdown("### 🔎 评审官诊断与判定校准")
    st.caption(
        "独立评审角色在面试结束后复核（不参与过程）：校准可疑判定 + 整体画像 + 按优先级复习计划。"
    )
    if review.get("portrait"):
        st.markdown(f"**整体画像**：{review['portrait']}")
    vrs = review.get("verdict_review") or []
    if vrs:
        st.markdown("**可疑判定复核**（建议仅供参考；图谱掌握度仍以面试官判定为准）")
        rows = [
            {
                "题号": f"Q{v.get('round_no', '?')}",
                "原判定": config.VERDICT_CN.get(v.get("original"), v.get("original")),
                "校准建议": config.VERDICT_CN.get(v.get("suggested"), v.get("suggested")),
                "理由": v.get("reason", ""),
            }
            for v in vrs
        ]
        st.table(rows)
    else:
        st.success("评审官复核：逐题判定公允，无需要改判的题。")
    plan = review.get("plan") or []
    if plan:
        st.markdown("**复习计划（按优先级）**")
        for p in plan:
            st.markdown(
                f"- **{p.get('title', p.get('node_id'))}** [{p.get('node_id')}]："
                f"{p.get('why', '')} → *{p.get('how', '')}*"
            )
    if review.get("next_suggestion"):
        st.caption(f"**下次面试建议**：{review['next_suggestion']}")


def _render_review_block(sid):
    """报告页评审区：已有评审直接展示；否则给生成按钮（约 1 次调用，失败不阻塞）。"""
    review = interview.get_review(sid)
    if review:
        render_review(review)
        return
    if st.button(
        "🔎 生成评审官诊断（校准判定 + 复习计划）",
        key=f"gen_rev_{sid}",
        help="由独立评审角色复核逐题判定（挑判松/判严），并给出整体画像与按优先级排的复习计划。约 1 次调用。",
    ):
        with st.spinner("评审官复核中…"):
            try:
                interview.build_review(sid)
                st.rerun()
            except interview.LLMNotConfigured as e:
                st.error(str(e))
            except Exception as e:  # noqa: BLE001
                st.error(f"评审生成失败：{e}")


# ---------------- 报告渲染（Tab1 结束后 / Tab3 历史共用） ----------------
def render_report(rpt):
    vc = rpt["verdict_cnt"]
    cfg = rpt["cfg"]
    mins = MIN_OF_ROUNDS.get(cfg.get("target_rounds"))
    st.subheader(f"结业报告 · {rpt['scope_title']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总题数", rpt["n_turns"])
    c2.metric("得分", f"{rpt['score_pct']}%")
    c3.metric("评级", rpt["grade"])
    c4.metric("覆盖节点", f"{rpt['coverage']['asked']}/{rpt['coverage']['total']}")
    st.caption(
        f"深度「{cfg.get('depth')}」· 风格「{cfg.get('style') or '默认'}」· 目标 ~{cfg.get('target_rounds')} 题"
        + (f"（约 {mins} 分钟）" if mins else "")
        + f" · 答对 {vc['correct']} / 部分 {vc['partial']} / "
        f"答错 {vc['wrong']} / 未答上 {vc['unanswered']} / 跑题 {vc['offtopic']}"
    )
    st.markdown(f"**{rpt['grade_cn']}**")

    # —— 判定校准官评审区（仅已结束场次；报告与历史 Tab 共用本函数故两处都出现）——
    if rpt["session"]["status"] == "finished":
        _render_review_block(rpt["session"]["session_id"])

    if rpt["weak_nodes"]:
        st.markdown("#### 🔴 薄弱知识点（建议先补这些节点原文）")
        for w in rpt["weak_nodes"]:
            with st.expander(f"{w['title']} [{w['node_id']}] · 命中 {w['times']} 次"):
                st.markdown(f"**摘要**：{w['summary'] or '（无）'}")
                st.text(w["body"] or "（节点无正文）")
    else:
        st.success("本场无薄弱知识点，知识结构扎实！")

    st.markdown("#### 逐题记录")
    for a in rpt["answered"]:
        with st.expander(f"Q{a['round_no']} · {a['question'][:48]}"):
            st.markdown(f"{verdict_badge(a['verdict'])}　**问题**：{a['question']}")
            if a["user_answer"]:
                st.markdown(f"**你的回答**：\n\n{a['user_answer']}")
            else:
                st.markdown("**你的回答**：（未作答）")
            if a["comment"] and show_comment_enabled(cfg):
                st.markdown(f"**点评**：{a['comment']}")
            if a["node_ids"]:
                st.caption("考察节点：" + "、".join(f"{nid}({nodes[nid].title})" for nid in a["node_ids"] if nid in nodes))


# ---------------- Tab1：模拟面试 ----------------
def render_setup(disabled):
    st.markdown("### 开始一场新面试")
    st.caption(
        "面试官沿所选科目的知识点逐个设问，依据**节点原文**判定并自适应追问（答对才往深追，"
        "答错下探查基础）；过程不泄露对错，结束后出结业报告并给图谱着色。"
    )
    with st.form("iv_setup_form"):
        cur = st.session_state.get("iv_scope_root", "root")
        idx = order_ids.index(cur) if cur in order_ids else 0
        subject_id = st.selectbox(
            "科目范围（含其全部子节点）", order_ids, index=idx, format_func=node_label, key="iv_scope_root"
        )
        c1, c2, c3, c4 = st.columns([1, 1.2, 1.2, 1.4])
        duration = c1.selectbox(
            "面试时长", config.DURATION_CHOICES, index=1,
            format_func=lambda d: f"{d} 分钟", key="iv_dur",
        )
        depth = c2.selectbox(
            "追问深度", config.INTERVIEW_DEPTHS, index=1, key="iv_depth"
        )
        style = c3.selectbox(
            "面试官风格", config.INTERVIEW_STYLES, index=0, key="iv_style"
        )
        review_mode = c4.selectbox(
            "点评时机", config.REVIEW_MODES, index=0, key="iv_rm"
        )
        st.caption(f"**{depth}**：{config.DEPTH_DESC.get(depth, '')}")
        st.caption(f"**{style}**：{config.STYLE_DESC.get(style, '')}")
        weak_first = st.checkbox(
            "优先复测上次面试答错的知识点（跨场次记忆）", value=True, key="iv_weak",
            help="开新场时自动读历史场次，把答错/没答上的知识点排到最前优先复测，形成复习闭环。",
        )
        st.caption(f"目标题数：约 {config.DURATION_ROUNDS[duration]} 题 · 建议每题作答 ≤ 2 分钟 · "
                   f"「{review_mode}」模式")
        submitted = st.form_submit_button("🎬 开始面试", type="primary", disabled=disabled)
    if disabled:
        st.caption("上方有进行中的面试，可先「结束本场」或直接继续作答。")
    if submitted and llm_ready:
        cfg = {
            "depth": depth,
            "style": style,
            "target_rounds": config.DURATION_ROUNDS[duration],
            "review_mode": review_mode,
            "weak_first": bool(weak_first),
        }
        sid = interview.new_session(subject_id, nodes[subject_id].title, cfg)
        st.session_state["iv_sid"] = sid
        st.session_state.pop("iv_feedback", None)
        try:
            with st.spinner("面试官正在准备第 1 题…"):
                interview.ask_first(sid)
            st.rerun()
        except interview.LLMNotConfigured as e:
            st.error(str(e))
            interview.delete_session(sid)
        except Exception as e:  # noqa: BLE001
            st.error(f"开场失败（已撤销本场）：{e}")
            interview.delete_session(sid)


def render_answer_panel(sid, s):
    cfg = json.loads(s["config_json"])
    target = cfg["target_rounds"]
    t = current_turn(sid)
    if not t:
        return
    turns = interview.get_turns(sid)
    answered_before = len([x for x in turns if x["user_answer"] is not None])

    st.subheader(f"面试进行中 · {s['scope_title']}")
    st.caption(f"深度「{cfg.get('depth')}」· 风格「{cfg.get('style') or '默认'}」· 目标 ~{target} 题 · 点评「{cfg.get('review_mode')}」")
    if target > 0:
        st.progress(min(1.0, answered_before / target))
    st.markdown("---")

    # 即时反馈（上轮判定，仅非「结束后一起看」模式展示）
    fb = st.session_state.get("iv_feedback")
    if fb and cfg.get("review_mode") != "结束后一起看":
        r = fb.get("round_no") or 0
        if r < t["round_no"]:
            comment = fb.get("comment", "") if show_comment_enabled(cfg) else ""
            st.markdown(f"**上一题** {verdict_badge(fb.get('verdict'))}　{comment}", unsafe_allow_html=True)

    st.markdown(f"**第 {t['round_no']} 题 / ~{target} 题**")
    st.markdown(f"> {t['question']}")
    if cfg.get("review_mode") == "结束后一起看":
        st.caption("（真实面试不点评——安心答，结束一起看判定）")

    st.text_area(
        "你的回答",
        height=160,
        placeholder="在此输入你的回答（可换行、可写推导）。答不上就点下方「没答上/跳过」。",
        key="iv_ans_input",
    )
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        do_submit = st.button("提交回答", type="primary", use_container_width=True)
    with b2:
        do_skip = st.button("没答上 / 跳过", use_container_width=True)
    with b3:
        do_end = st.button("提前结束面试", use_container_width=True)

    if do_end:
        interview.manual_finish(sid)
        st.session_state.pop("iv_feedback", None)
        st.rerun()

    answer = st.session_state.get("iv_ans_input", "").strip()
    if do_submit and not answer:
        st.warning("回答为空——若确实没答上，请点「没答上 / 跳过」。")
        return
    if do_submit or do_skip:
        st.session_state.pop("iv_ans_input", None)
        try:
            with st.spinner("面试官判定中…"):
                out = interview.submit_answer(sid, answer if do_submit else "")
        except interview.LLMNotConfigured as e:
            st.error(str(e))
            return
        except Exception as e:  # noqa: BLE001
            st.error(f"本轮推进失败：{e}（可直接「提前结束面试」保住已答记录）")
            return
        if out.get("finished"):
            st.session_state.pop("iv_feedback", None)
            st.rerun()
        if out.get("judged"):
            st.session_state["iv_feedback"] = {
                "round_no": t["round_no"],
                "verdict": out["judged"].get("verdict"),
                "comment": out["judged"].get("comment", ""),
            }
        st.rerun()


def render_tab_live():
    st.header("🎤 模拟面试")
    if not llm_ready:
        st.warning(
            "未配置 LLM API key。请在 `review/.env` 或知识库 `tools/.env` 中填写 "
            "`DEEPSEEK_API_KEY` 后重启。"
        )
        return

    sid = active_session_id()
    if sid:
        s = interview.get_session(sid)
        if s["status"] == "active":
            render_answer_panel(sid, s)
            st.markdown("---")
            render_setup(disabled=True)
            return
        # 刚结束 / 上次看到的已完成场次 → 展示报告
        try:
            render_report(interview.build_report(sid))
        except Exception as e:  # noqa: BLE001
            st.error(f"报告生成失败：{e}")
        ex = bool(s["excluded"])
        want_ex = st.checkbox(
            "本场不计入知识图谱掌握度统计",
            value=ex,
            key=f"ex_toggle_{sid}",
            help="勾选后此场的对错不影响图谱节点颜色，可随时改回。",
        )
        if want_ex != ex:
            interview.set_excluded(sid, want_ex)
            st.rerun()
        st.markdown("---")
        render_setup(disabled=False)
    else:
        render_setup(disabled=False)


# ---------------- Tab2：面试驱动知识图谱 ----------------
def render_tab_graph():
    st.header("🗺 知识图谱 · 面试驱动着色")
    st.caption(
        "颜色来源 = 已结束场次的判定：**红=薄弱难点**（答错/未答上/跑题，一票否决）；"
        "橙/黄/绿=多次判定均值；灰=还没面到。tooltip 里的数字 = 被问次数。"
    )
    mastery = records.interview_mastery()
    stats = records.total_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("已结束场次", stats["sessions"])
    c2.metric("有效答题", stats["turns"])
    c3.metric("薄弱节点", stats["weak_nodes"])

    legend = [
        ("未面试", records.GREY),
        ("薄弱难点", records.RED),
        ("基本/完全掌握", "#48bb78"),
    ]
    chips = "".join(
        f'<span style="display:inline-block;width:11px;height:11px;background:{c};'
        f'border-radius:50%;margin:0 6px 0 14px;vertical-align:middle"></span>{n}'
        for n, c in legend
    )
    st.markdown(chips, unsafe_allow_html=True)

    hl_sel = st.selectbox(
        "高亮某个子树（方便定位科目范围）", ["__none__"] + order_ids,
        format_func=lambda x: "（不高亮）" if x == "__none__" else node_label(x),
        key="graph_hl",
    )
    if hl_sel != "__none__":
        highlight = knowledge.subtree_ids(nodes, children, hl_sel)
    else:
        highlight = None

    opt = graph_viz.build_option(nodes, children, mastery, highlight_ids=highlight)
    components_html(graph_viz.graph_html(opt, 620), height=680)


# ---------------- Tab3：历史与薄弱 ----------------
def render_tab_hist():
    st.header("📋 面试历史与薄弱清单")
    stats = records.total_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("已结束场次", stats["sessions"])
    c2.metric("有效答题", stats["turns"])
    c3.metric("薄弱节点", stats["weak_nodes"])
    st.markdown("---")

    sessions = interview.list_sessions()
    if not sessions:
        st.info("还没有任何面试记录，去「🎤 模拟面试」开一场吧。")
        return

    st.markdown("#### 全部场次")
    for row in sessions:
        try:
            cfg = json.loads(row["config_json"] or "{}")
        except (TypeError, ValueError):
            cfg = {}
        mins = MIN_OF_ROUNDS.get(cfg.get("target_rounds"))
        n_ans = row["n_answered"] or 0
        status_cn = "⏳ 进行中" if row["status"] == "active" else "✅ 已结束"
        ex_cn = " · 不计入图谱" if row.get("excluded") else ""
        head = (
            f"{status_cn} **{row['scope_title']}** — {row['created_at'][:16]}"
            f" · 深度「{cfg.get('depth', '?')}」"
            f"{('(约' + str(mins) + '分钟)') if mins else ''} · 已答 {n_ans}/{row['n_turns']} 题{ex_cn}"
        )
        st.markdown(head)
        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            if st.button("查看报告", key=f"hist_report_{row['session_id']}"):
                st.session_state["iv_view"] = row["session_id"]
                st.rerun()
        with b2:
            if row["status"] == "active":
                if st.button("继续面试", key=f"hist_resume_{row['session_id']}"):
                    st.session_state["iv_sid"] = row["session_id"]
                    st.rerun()
        with b3:
            confirm = st.session_state.get("del_confirm") == row["session_id"]
            if not confirm:
                if st.button("删除", key=f"hist_del_{row['session_id']}"):
                    st.session_state["del_confirm"] = row["session_id"]
                    st.rerun()
            else:
                if st.button("⚠️ 确认删除？", key=f"hist_del2_{row['session_id']}"):
                    interview.delete_session(row["session_id"])
                    st.session_state.pop("del_confirm", None)
                    st.session_state.pop("iv_view", None)
                    st.rerun()
        st.markdown("---")

    # 查看某场报告
    view_sid = st.session_state.get("iv_view")
    if view_sid:
        s = interview.get_session(view_sid)
        if s:
            st.markdown("#### 场次报告")
            try:
                render_report(interview.build_report(view_sid))
            except Exception as e:  # noqa: BLE001
                st.error(f"报告生成失败：{e}")
            if st.button("收起报告", key="close_view"):
                st.session_state.pop("iv_view", None)
                st.rerun()
            st.markdown("---")

    # 跨场次聚合薄弱清单
    st.markdown("#### 🔴 薄弱知识点聚合（全部场次）")
    weak = sorted(
        ((nid, e) for nid, e in records.interview_mastery().items() if e["weak"]),
        key=lambda x: (-x[1]["count"], x[0]),
    )
    if not weak:
        st.success("目前没有薄弱节点——继续保持！")
    else:
        st.caption("出现在多场、多次答错的节点排前面。红色即图谱上的红点。")
        for nid, e in weak[:30]:
            nd = nodes.get(nid)
            if not nd:
                continue
            with st.expander(f"{nd.title} [{nid}] · 命中 {e['count']} 次"):
                st.markdown(f"**摘要**：{nd.summary or '（无）'}")
                st.text((nd.body or "")[:800] or "（节点无正文）")


tab_live, tab_graph, tab_hist = st.tabs(["🎤 模拟面试", "🗺 知识图谱", "📋 历史与薄弱"])
with tab_live:
    render_tab_live()
with tab_graph:
    render_tab_graph()
with tab_hist:
    render_tab_hist()
