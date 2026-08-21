"""对比 links 三种注入层次对答题分数的影响（5 道题 × DeepSeek）

① 关系描述（现状）：选中节点 content + links 关系描述
② 邻居摘要：① + links 邻居的 summary（一句话本质）
③ 邻居全文：① + links 邻居的完整 content
"""
import sys, json, time
sys.path.insert(0, 'tools')
import kb_benchmark as kb
kb.load_env()

tree_index = kb.load_tree_index()
all_qs = json.load(open('benchmark/questions_v5.json', encoding='utf-8'))['questions']
meta = kb._load_node_meta()
ds = {'name': 'deepseek-chat', 'base_url': 'https://api.deepseek.com', 'key': kb.DEEPSEEK_KEY}

def is_knowledge(nid):
    return meta.get(nid, {}).get('type') in ('core', 'leaf')

def neighbors_of(nids):
    nb = []
    for nid in nids:
        for l in meta.get(nid, {}).get('links', []):
            if is_knowledge(l) and l not in nids and l not in nb:
                nb.append(l)
    return nb

# 选 5 道 links 关联最丰富的跨学科题
test_qids = ['L4-cross-01', 'L4-cross-05', 'L4-cross-08', 'L4-cross-09', 'L4-cross-16']
qs = [q for q in all_qs if q['id'] in test_qids]

BASE = "你是通信工程专业的学生，请基于下面的知识回答问题。\n\n"

print(f"=== links 三种注入层次对比（5 题 × DeepSeek，裁判 qwen-max）===\n", flush=True)
results = {}
for q in qs:
    nids = kb.select_nodes_d(ds, q['question'], tree_index)
    nb = neighbors_of(nids)
    base = kb.load_nodes_by_ids(nids)  # ① 含 links 关系描述

    # ② 邻居摘要
    nb_summary = "\n### 关联知识点（一句话本质）\n" + "\n".join(
        f"- {meta.get(n,'{}').get('title')}：{meta.get(n,'{}').get('summary','')}" for n in nb
    )
    inject2 = base + nb_summary

    # ③ 邻居全文
    inject3 = base + "\n\n" + kb.load_nodes_by_ids(nb)

    print(f"【{q['id']}】{q['question'][:30]}... 选中 {nids}，邻居 {nb}", flush=True)
    for name, inject in [('①关系描述', base), ('②邻居摘要', inject2), ('③邻居全文', inject3)]:
        ans = kb.ask_model(ds, BASE + inject, q['question'])
        j = kb.judge_answer(q['question'], q['answer'], 'deepseek', ans)
        score = j.get('score', -1)
        comment = j.get('comment', '')
        print(f"  {name}: 分={score} | 注入{len(inject)}字 | {comment[:50]}", flush=True)
        results.setdefault(q['id'], {})[name] = score
        time.sleep(0.3)

print("\n=== 汇总 ===", flush=True)
for name in ['①关系描述', '②邻居摘要', '③邻居全文']:
    scores = [results[q][name] for q in test_qids]
    avg = sum(scores) / len(scores)
    print(f"{name}: {' '.join(str(s) for s in scores)} → 平均 {avg:.1f}", flush=True)
