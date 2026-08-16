import sys, json, time
sys.path.insert(0, 'tools')
import kb_benchmark as kb
kb.load_env()
tree_index = kb.load_tree_index()
qs = json.load(open('benchmark/questions_v6_node_test.json', encoding='utf-8'))['questions']
ds = {'name': 'deepseek-chat', 'base_url': 'https://api.deepseek.com', 'key': kb.DEEPSEEK_KEY}

def eval_picker(name, picker):
    th = te = exact = one = 0
    bad = []
    for q in qs:
        try:
            nids = picker(q['question'])
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
        time.sleep(0.25)
    n = len(qs)
    line = f"{name}: 召回{th}/{te}={th/te*100:.0f}% | 至少1个 {one}/{n} | 完全命中 {exact}/{n}"
    print(line, flush=True)
    if bad:
        print(f"  未命中: {bad}", flush=True)
    return line

results = []
results.append(eval_picker("方案B 程序预筛", lambda q: kb.select_nodes_b(q, tree_index)))
results.append(eval_picker("方案A DeepSeek", lambda q: kb.select_nodes(ds, q, tree_index)))
results.append(eval_picker("方案C DeepSeek", lambda q: kb.select_nodes_c(ds, q, tree_index)))

with open('benchmark/results/selection_recall_v6.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(results) + "\n")
print("\n已保存到 selection_recall_v6.txt", flush=True)
