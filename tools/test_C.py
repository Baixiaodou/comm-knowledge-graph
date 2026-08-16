import sys, json, time
sys.path.insert(0, 'tools')
import kb_benchmark as kb
kb.load_env()
tree_index = kb.load_tree_index()
qs = json.load(open('benchmark/questions_v5.json', encoding='utf-8'))['questions']
ds = {'name': 'deepseek-chat', 'base_url': 'https://api.deepseek.com', 'key': kb.DEEPSEEK_KEY}

th = te = exact = one = 0
bad = []
for q in qs:
    try:
        nids = kb.select_nodes_c(ds, q['question'], tree_index)
    except Exception:
        nids = []
    exp = set(q['expected_nodes']); sel = set(nids)
    hit = exp & sel
    th += len(hit); te += len(exp)
    if hit and len(hit) == len(exp):
        exact += 1
    if hit:
        one += 1
    else:
        bad.append(q['id'])
    time.sleep(0.3)

out = f"方案C DeepSeek: 召回{th}/{te}={th/te*100:.0f}% | 至少1个 {one}/{len(qs)} | 完全命中 {exact}/{len(qs)}"
print(out, flush=True)
print("未命中题:", bad, flush=True)
with open('benchmark/results/selection_recall_C.txt', 'w', encoding='utf-8') as f:
    f.write(out + "\n未命中题: " + str(bad) + "\n")
