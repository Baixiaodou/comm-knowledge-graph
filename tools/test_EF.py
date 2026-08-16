"""对比方案 E vs F 的选节点召回率（35题，DeepSeek 精挑）

方案 E = TF-IDF top-10 排除hub + 精挑
方案 F = TF-IDF top-8 排除hub + links扩展 + 按TF-IDF截断回10 + 精挑
"""
import sys, json, time, yaml, os, re
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

def gen_E(q, top_k=10):
    """方案E候选：TF-IDF top-10 排除hub"""
    scores = kb._tfidf_similarity(q, texts)
    ranked = [nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1]) if is_knowledge(nid)]
    return ranked[:top_k]

def gen_F(q, top_k=8, cap=10):
    """方案F候选：top-8排除hub + links扩展 + 按TF-IDF截断回cap"""
    scores = kb._tfidf_similarity(q, texts)
    ranked = [nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1]) if is_knowledge(nid)][:top_k]
    cand = list(ranked)
    for nid in ranked:
        for nb in meta.get(nid, {}).get('links', []):
            if is_knowledge(nb) and nb not in cand:
                cand.append(nb)
    # 按 TF-IDF 分重新排序，截断到 cap
    cand = sorted(cand, key=lambda nid: scores.get(nid, 0), reverse=True)[:cap]
    return cand

def pick_from_candidates(q, cand_ids):
    """DeepSeek 精挑：从候选里选 2-3 个"""
    cand_lines = []
    for nid in cand_ids:
        m = meta.get(nid, {})
        cand_lines.append(f"- {m.get('title')} ({nid}): {m.get('summary', '')[:60]}")
    cand_index = "\n".join(cand_lines)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{q}"""
    extra = {}
    for attempt in range(2):
        try:
            r = client.chat.completions.create(
                model=ds['name'],
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=200, temperature=0, **extra,
            )
            text = r.choices[0].message.content.strip()
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            if m:
                try:
                    ids = json.loads(m.group(0))
                    result = [i for i in ids if isinstance(i, str) and i in cand_ids][:3]
                    if result:
                        return result
                except Exception:
                    pass
            found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in cand_ids]
            if found:
                return found[:3]
            return cand_ids[:3]
        except Exception:
            if attempt == 1:
                return cand_ids[:3]
            time.sleep(1)
    return cand_ids[:3]

def eval_method(name, gen, do_pick):
    th = te = exact = one = 0
    bad = []
    for q in qs:
        cand = gen(q['question'])
        nids = pick_from_candidates(q['question'], cand) if do_pick else cand
        exp = set(q['expected_nodes']); sel = set(nids)
        hit = exp & sel
        th += len(hit); te += len(exp)
        if hit and len(hit) == len(exp): exact += 1
        if hit: one += 1
        else: bad.append(q['id'])
        time.sleep(0.2)
    print(f"{name}: 召回 {th}/{te}={th/te*100:.0f}% | 至少1个 {one}/35 | 完全命中 {exact}/35 | 未命中 {bad}", flush=True)

# 候选覆盖率（纯程序）
print("=== 候选覆盖率（纯程序）===", flush=True)
for name, gen in [('E 候选(top-10排除hub)', gen_E), ('F 候选(links扩展截断回10)', gen_F)]:
    th = te = one = 0
    for q in qs:
        cand = gen(q['question'])
        exp = set(q['expected_nodes']); sel = set(cand)
        hit = exp & sel
        th += len(hit); te += len(exp)
        if hit: one += 1
    avg = sum(len(gen(q['question'])) for q in qs) / len(qs)
    print(f"  {name}: 召回 {th}/{te}={th/te*100:.0f}% | 至少1个 {one}/35 | 平均候选 {avg:.1f}个", flush=True)

# 精挑后召回率
print("\n=== 精挑后召回率（DeepSeek）===", flush=True)
eval_method('方案E(top-10排除hub+精挑)', gen_E, True)
eval_method('方案F(links扩展截断回10+精挑)', gen_F, True)
