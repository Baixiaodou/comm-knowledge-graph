"""E vs F 各重复 N 次，取平均召回率，消除精挑噪声"""
import sys, json, time, re, statistics
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

def cand_E(q):
    scores = kb._tfidf_similarity(q, texts)
    ranked = [n for n,_ in sorted(scores.items(), key=lambda x:-x[1]) if is_knowledge(n)][:10]
    return ranked

def cand_F(q):
    scores = kb._tfidf_similarity(q, texts)
    ranked = [n for n,_ in sorted(scores.items(), key=lambda x:-x[1]) if is_knowledge(n)][:8]
    cand = list(ranked)
    for nid in ranked:
        for nb in meta.get(nid,{}).get('links',[]):
            if is_knowledge(nb) and nb not in cand: cand.append(nb)
    return sorted(cand, key=lambda nid: scores.get(nid,0), reverse=True)[:10]

def run_once(gen):
    th = te = exact = one = 0
    for q in qs:
        nids = pick_from_candidates(q['question'], gen(q['question']))
        exp = set(q['expected_nodes']); sel = set(nids)
        hit = exp & sel
        th += len(hit); te += len(exp)
        if hit and len(hit) == len(exp): exact += 1
        if hit: one += 1
        time.sleep(0.15)
    return th/te*100, exact

N = 3
print(f"E vs F 各重复 {N} 次（每次 35 题精挑）", flush=True)
for name, gen in [('E(top-10排除hub)', cand_E), ('F(links扩展截断回10)', cand_F)]:
    recalls = []
    for i in range(N):
        r, exact = run_once(gen)
        recalls.append(r)
        print(f"  {name} 第{i+1}次: 召回 {r:.0f}% | 完全命中 {exact}/35", flush=True)
    avg = statistics.mean(recalls)
    stdev = statistics.stdev(recalls) if N > 1 else 0
    print(f"  → {name} 平均 {avg:.1f}% ± {stdev:.1f}", flush=True)
    print(flush=True)
