"""统一在干净题库（expected 全 core/leaf）上测 A/B/C/D/E/F 六方案召回率"""
import sys, json, time, re
sys.path.insert(0, 'tools')
import kb_benchmark as kb
kb.load_env()
from openai import OpenAI

tree_index = kb.load_tree_index()
qs = json.load(open('benchmark/questions_v5.json', encoding='utf-8'))['questions']
texts = kb._all_node_texts()
meta = kb._load_node_meta()
ds = {'name': 'deepseek-chat', 'base_url': 'https://api.deepseek.com', 'key': kb.DEEPSEEK_KEY}
client = OpenAI(api_key=ds['key'], base_url=ds['base_url'], timeout=90)

def is_knowledge(nid):
    return meta.get(nid, {}).get('type') in ('core', 'leaf')

def pick_from_candidates(q, cand_ids):
    cand_lines = []
    for nid in cand_ids:
        m = meta.get(nid, {})
        cand_lines.append(f"- {m.get('title')} ({nid}): {m.get('summary', '')[:60]}")
    cand_index = "\n".join(cand_lines)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{q}"""
    for attempt in range(2):
        try:
            r = client.chat.completions.create(model=ds['name'], messages=[{'role':'user','content':prompt}], max_tokens=200, temperature=0)
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i,str) and i in cand_ids][:3]
                    if result: return result
                except Exception: pass
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in cand_ids]
            if found: return found[:3]
            return cand_ids[:3]
        except Exception:
            if attempt == 1: return cand_ids[:3]
            time.sleep(1)
    return cand_ids[:3]

# 各方案选节点（返回最终选中的 2-3 个节点）
def m_A(q): return kb.select_nodes(ds, q, tree_index)                       # A: 模型看74目录自主选
def m_B(q): return kb.select_nodes_b(q, tree_index)                         # B: 纯TF-IDF top-3 含hub
def m_C(q): return kb.select_nodes_c(ds, q, tree_index)                     # C: top-10含hub+精挑
def m_D(q):                                                                 # D: 排除hub+links扩展不截断(候选~15-20)+精挑
    scores = kb._tfidf_similarity(q, texts)
    ranked = [n for n,_ in sorted(scores.items(), key=lambda x:-x[1]) if is_knowledge(n)][:8]
    cand = list(ranked)
    for nid in ranked:
        for nb in meta.get(nid,{}).get('links',[]):
            if is_knowledge(nb) and nb not in cand: cand.append(nb)
    return pick_from_candidates(q, cand[:15])
def m_E(q):                                                                 # E: top-10排除hub+精挑
    scores = kb._tfidf_similarity(q, texts)
    ranked = [n for n,_ in sorted(scores.items(), key=lambda x:-x[1]) if is_knowledge(n)][:10]
    return pick_from_candidates(q, ranked)
def m_F(q): return kb.select_nodes_d(ds, q, tree_index)                     # F: links扩展截断回10+精挑

for name, fn in [('A(模型看目录自主)', m_A), ('B(纯TF-IDF top-3)', m_B), ('C(top-10含hub+精挑)', m_C),
                 ('D(links扩展不截断+精挑)', m_D), ('E(top-10排除hub+精挑)', m_E), ('F(links扩展截断回10+精挑)', m_F)]:
    th = te = exact = one = 0
    bad = []
    for q in qs:
        try:
            nids = fn(q['question'])
        except Exception:
            nids = []
        exp = set(q['expected_nodes']); sel = set(nids)
        hit = exp & sel
        th += len(hit); te += len(exp)
        if hit and len(hit) == len(exp): exact += 1
        if hit: one += 1
        else: bad.append(q['id'])
        time.sleep(0.15)
    print(f"{name}: 召回 {th}/{te}={th/te*100:.0f}% | 至少1个 {one}/35 | 完全命中 {exact}/35 | 未命中 {bad}", flush=True)
