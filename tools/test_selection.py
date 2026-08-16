import sys, json, time
sys.path.insert(0, 'tools')
import kb_benchmark as kb
kb.load_env()
tree_index = kb.load_tree_index()
data = json.load(open('benchmark/questions_v5.json', encoding='utf-8'))
qs = data['questions']
ds = {'name': 'deepseek-chat', 'base_url': 'https://api.deepseek.com', 'key': kb.DEEPSEEK_KEY}
q8 = {'name': 'Qwen/Qwen3-8B', 'base_url': 'https://api.siliconflow.cn/v1', 'key': kb.SILICON_KEY}

def eval_picker(picker):
    th = te = exact = one = 0
    for q in qs:
        try:
            nids = picker(q['question'])
        except Exception as e:
            nids = []
        exp = set(q['expected_nodes']); sel = set(nids)
        hit = exp & sel
        th += len(hit); te += len(exp)
        if hit and len(hit) == len(exp):
            exact += 1
        if hit:
            one += 1
        time.sleep(0.3)
    n = len(qs)
    return f"召回{th}/{te}={th/te*100:.0f}% | 至少1个 {one}/{n} | 完全命中 {exact}/{n}"

results = []
results.append(("方案 A DeepSeek", eval_picker(lambda q: kb.select_nodes(ds, q, tree_index))))
results.append(("方案 A Qwen3-8B", eval_picker(lambda q: kb.select_nodes(q8, q, tree_index))))
results.append(("方案 C DeepSeek", eval_picker(lambda q: kb.select_nodes_c(ds, q, tree_index))))
results.append(("方案 C Qwen3-8B", eval_picker(lambda q: kb.select_nodes_c(q8, q, tree_index))))

with open('benchmark/results/selection_recall.txt', 'w', encoding='utf-8') as f:
    for name, r in results:
        f.write(f"{name}: {r}\n")
        print(f"{name}: {r}", flush=True)
