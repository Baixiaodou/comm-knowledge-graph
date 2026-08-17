"""知识库复习出题插件 · Streamlit 入口。

运行：streamlit run review/app.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import config
import db
import knowledge
import question_bank
import generator
import records
import graph_viz

st.set_page_config(page_title="知识库复习出题", page_icon="📚", layout="wide")

# ---------- 初始化 ----------
db.init_db()
question_bank.import_benchmark()


@st.cache_data(show_spinner=False)
def load_kb():
    nodes = knowledge.load_nodes()
    children = knowledge.build_tree(nodes)
    return nodes, children


nodes, children = load_kb()
llm_ready = config.get_llm_config() is not None

SELF_ASSESS = ["完全掌握", "基本掌握", "初步掌握", "薄弱难点"]


# ---------- 侧边栏：选节点 + 图例 ----------
def flatten_tree(nodes, children):
    order = []

    def dfs(nid, depth):
        order.append((nid, depth))
        for c in sorted(children.get(nid, [])):
            dfs(c, depth + 1)

    roots = [n for n in nodes if n == "root"] or [
        n for n in nodes.values() if not n.parent or n.parent not in nodes
    ]
    for r in roots:
        if r in nodes:
            dfs(r, 0)
    done = {nid for nid, _ in order}
    for nid in nodes:
        if nid not in done:
            order.append((nid, 0))
    return order


order = flatten_tree(nodes, children)
order_ids = [nid for nid, _ in order]
_depth = {nid: d for nid, d in order}


def node_label(nid):
    return f"{'　' * _depth.get(nid, 0)}{nodes[nid].title}"


with st.sidebar:
    st.title("📚 复习出题")
    st.caption("依附树形知识库，只读不修改")

    if "selected_node" not in st.session_state:
        st.session_state.selected_node = "root"
    cur = st.session_state.selected_node
    idx = order_ids.index(cur) if cur in order_ids else 0
    sel = st.selectbox("选择学习节点（含其所有子节点）", order_ids, index=idx, format_func=node_label)
    st.session_state.selected_node = sel

    scope = knowledge.subtree_ids(nodes, children, sel)
    st.caption(f"学习范围：{len(scope)} 个节点")

    st.markdown("**掌握度图例**")
    legend = [
        ("未复习", "#9aa5b1"),
        ("初步掌握", "#f6ad55"),
        ("基本掌握", "#f6e05e"),
        ("完全掌握", "#48bb78"),
        ("薄弱难点", "#e53e3e"),
    ]
    for name, color in legend:
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;background:{color};'
            f'border-radius:50%;margin-right:6px;vertical-align:middle"></span>{name}',
            unsafe_allow_html=True,
        )

    if not llm_ready:
        st.warning("未配置 LLM API key，AI 出题/解析不可用（benchmark 题仍可刷）。")


# ---------- 主区域 ----------
mastery_map = records.nodes_mastery()
reviewed = records.reviewed_question_ids()
scope_qids = question_bank.question_ids_for_nodes(scope)
answered_cnt = len([q for q in scope_qids if q in reviewed])

tab_learn, tab_bank, tab_progress = st.tabs(["📖 学习出题", "🗂 题库管理", "📊 学习进度"])


# ================= Tab 1：学习出题 =================
with tab_learn:
    st.subheader("知识图谱")
    st.caption("节点颜色 = 掌握度；当前所选节点及其子树已高亮描边")
    opt = graph_viz.build_option(nodes, children, mastery_map, highlight_ids=scope)
    st.html(graph_viz.graph_html(opt, 620), unsafe_allow_javascript=True)

    st.markdown("---")
    node = nodes[sel]
    st.subheader(f"当前节点：{node.title}（{sel}）")
    st.markdown(f"**摘要**：{node.summary}")
    if node.cot:
        st.markdown(f"**思维链起点**：{node.cot.get('origin', '')}")
    with st.expander("查看节点原文"):
        st.text(node.body)

    st.markdown("---")
    st.subheader(f"本范围题目（{answered_cnt}/{len(scope_qids)} 已作答）")

    if not scope_qids:
        st.info("该范围暂无题目。可在下方「AI 生成题目」生成。")

    questions = question_bank.get_questions(scope_qids)
    questions.sort(key=lambda q: (0 if q["question_id"] in reviewed else 1, q["question_id"]))

    for q in questions:
        qid = q["question_id"]
        qnodes = question_bank.question_nodes(qid)
        done = qid in reviewed
        type_cn = config.QUESTION_TYPE_CN.get(q["type"], q["type"])
        src = "benchmark" if q["source"] == "benchmark" else "AI"
        title = f"{'✅' if done else '⬜'} [{type_cn}] {q['stem'][:56]}"
        with st.expander(title):
            st.caption(f"节点：{', '.join(qnodes)} · 来源：{src} · 题目ID：{qid}")
            st.markdown(q["stem"])

            if st.button("显示答案与解析", key=f"showbtn_{qid}"):
                st.session_state[f"show_{qid}"] = True

            if st.session_state.get(f"show_{qid}"):
                st.markdown("**参考答案**")
                st.write(q["answer"] or "（无参考答案）")

                analysis = q.get("analysis")
                if not analysis:
                    if llm_ready:
                        with st.spinner("生成解析中…"):
                            try:
                                ctx = knowledge.nodes_context(nodes, qnodes)
                                analysis = generator.generate_analysis(q["stem"], q["answer"] or "", ctx)
                                question_bank.set_analysis(qid, analysis)
                            except Exception as e:  # noqa: BLE001
                                analysis = f"（解析生成失败：{e}）"
                    else:
                        analysis = "（未配置 LLM，无法生成解析）"
                st.markdown("**解析**")
                st.write(analysis)

                st.markdown("**本次掌握程度**")
                cur_m = st.session_state.get(f"m_{qid}", "基本掌握")
                m = st.radio(
                    "掌握程度",
                    SELF_ASSESS,
                    index=SELF_ASSESS.index(cur_m) if cur_m in SELF_ASSESS else 1,
                    key=f"m_{qid}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                if st.button("记录掌握程度", key=f"recbtn_{qid}"):
                    records.record_review(qid, qnodes, m)
                    st.session_state.pop(f"show_{qid}", None)
                    st.rerun()

    st.markdown("---")
    st.subheader("AI 生成题目")
    if not llm_ready:
        st.warning("未配置 LLM API key。请在 review/.env 或 tools/.env 中填写 DEEPSEEK_API_KEY。")
    else:
        all_done = len(scope_qids) > 0 and answered_cnt == len(scope_qids)
        if all_done:
            st.success("本范围所有题库题已做完，可以生成新题了！")

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            n_gen = st.slider("题目数量", 1, 10, 5)
        with c2:
            types_gen = st.multiselect(
                "题型",
                config.ALL_TYPES,
                default=config.ALL_TYPES,
                format_func=lambda t: config.QUESTION_TYPE_CN[t],
            )
        with c3:
            st.write("")
            gen_clicked = st.button("生成并加入题库", type="primary")

        if gen_clicked:
            if not types_gen:
                st.warning("请至少选一种题型")
            else:
                with st.spinner("AI 出题中…"):
                    try:
                        ctx = knowledge.nodes_context(nodes, scope)
                        items = generator.generate_questions(scope, ctx, n=n_gen, types=types_gen)
                        added = 0
                        for it in items:
                            qid = f"ai-{uuid.uuid4().hex[:12]}"
                            question_bank.add_question(
                                {
                                    "question_id": qid,
                                    "type": it["type"],
                                    "stem": it["stem"],
                                    "answer": it["answer"],
                                    "analysis": it.get("analysis"),
                                    "source_nodes": it["source_nodes"],
                                }
                            )
                            added += 1
                        st.success(f"已生成 {added} 道题。")
                        st.rerun()
                    except generator.LLMNotConfigured as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001
                        st.error(f"出题失败：{e}")


# ================= Tab 2：题库管理 =================
with tab_bank:
    st.subheader("题库管理")
    st.caption("按节点查看题目，可删除单题或让 AI 重新生成。")

    bank_node = st.selectbox("选择节点", order_ids, index=order_ids.index(sel) if sel in order_ids else 0, format_func=node_label)
    bank_qids = question_bank.question_ids_for_nodes([bank_node])
    st.caption(f"该节点下共 {len(bank_qids)} 道题")

    for q in question_bank.get_questions(bank_qids):
        qid = q["question_id"]
        qnodes = question_bank.question_nodes(qid)
        type_cn = config.QUESTION_TYPE_CN.get(q["type"], q["type"])
        src = "benchmark" if q["source"] == "benchmark" else "AI"
        with st.expander(f"[{type_cn}] {q['stem'][:56]}"):
            st.caption(f"节点：{', '.join(qnodes)} · 来源：{src} · 题目ID：{qid}")
            st.markdown(q["stem"])
            if st.button("删除此题", key=f"delbtn_{qid}"):
                question_bank.delete_question(qid)
                st.rerun()

    st.markdown("---")
    if llm_ready:
        if st.button("为该节点（及子树）AI 生成一批题", type="primary"):
            with st.spinner("AI 出题中…"):
                try:
                    sub = knowledge.subtree_ids(nodes, children, bank_node)
                    ctx = knowledge.nodes_context(nodes, sub)
                    items = generator.generate_questions(sub, ctx, n=5, types=config.ALL_TYPES)
                    added = 0
                    for it in items:
                        qid = f"ai-{uuid.uuid4().hex[:12]}"
                        question_bank.add_question(
                            {
                                "question_id": qid,
                                "type": it["type"],
                                "stem": it["stem"],
                                "answer": it["answer"],
                                "analysis": it.get("analysis"),
                                "source_nodes": it["source_nodes"],
                            }
                        )
                        added += 1
                    st.success(f"已生成 {added} 道题。")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"出题失败：{e}")
    else:
        st.warning("未配置 LLM API key，无法 AI 生成。")


# ================= Tab 3：学习进度 =================
with tab_progress:
    st.subheader("学习进度总览")

    total_questions = question_bank.get_questions(question_bank.question_ids_for_nodes(list(nodes.keys())))
    total_q = len(total_questions)
    total_r = len(reviewed)

    c1, c2, c3 = st.columns(3)
    c1.metric("知识节点", len(nodes))
    c2.metric("题库题目", total_q)
    c3.metric("已作答题目", total_r)

    st.markdown("---")

    # 每个节点一行：颜色点 + 标题 + 状态 + 做题数 + 最近复习
    rows = []
    for nid, d in order:
        n = nodes[nid]
        entry = mastery_map.get(nid)
        color = records.mastery_color(entry)
        label = records.mastery_label(entry)
        cnt = entry["count"] if entry else 0
        last = ""
        if entry:
            recs = records.node_records(nid)
            last = recs[0]["last_review_time"][:16] if recs else ""
        rows.append((nid, n.title, color, label, cnt, last))

    st.markdown("**节点掌握情况**（颜色见侧边栏图例）")
    for nid, title, color, label, cnt, last in rows:
        if cnt == 0 and label == "未复习":
            continue  # 只显示已开始复习的节点，避免表格过长
    # 上面过滤后重列
    shown = [r for r in rows if r[4] > 0]
    if not shown:
        st.info("还没有任何学习记录。去「学习出题」做几道题吧。")
    else:
        import pandas as pd

        df = pd.DataFrame(
            [(r[1], r[3], r[4], r[5]) for r in shown],
            columns=["节点", "掌握度", "做题数", "最近复习"],
        )
        st.dataframe(df, width="stretch")

    st.markdown("---")
    st.subheader("指定节点历史")
    hist_node = st.selectbox("查看节点", order_ids, index=order_ids.index(sel) if sel in order_ids else 0, format_func=node_label, key="hist_sel")
    recs = records.node_records(hist_node)
    if not recs:
        st.info("该节点暂无学习记录。")
    else:
        import pandas as pd

        hist_df = pd.DataFrame(
            [
                (r["question_id"], r["user_mastery"], r["last_review_time"][:16], r["review_count"])
                for r in recs
            ],
            columns=["题目ID", "掌握度", "最后复习", "复习次数"],
        )
        st.dataframe(hist_df, width="stretch")
