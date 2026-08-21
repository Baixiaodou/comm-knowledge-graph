"""对比测试：top5+links+LLM精挑 vs 直接top10+LLM精挑（DeepSeek，50题）

方案 A（新）：TF-IDF 初筛 top-5（排除 hub）+ links 扩展（不截断）+ LLM 精挑 2-3
方案 B（当前）：TF-IDF 初筛 top-10（排除 hub）+ LLM 精挑 2-3（= select_nodes_d）
"""
import sys, json, os, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb_benchmark as kb

kb.load_env()
tree_index = kb.load_tree_index()
meta = kb._load_node_meta()
doc_texts = kb._all_node_texts()

qs = json.load(open(os.path.join(os.path.dirname(__file__), "..", "benchmark", "questions_node_test.json"), encoding="utf-8"))["questions"]
DS = {"name": "deepseek-chat", "base_url": "https://api.deepseek.com", "key": kb.DEEPSEEK_KEY}


def _build_cand_index(cand_ids):
    """根据候选 id 列表，构建候选目录（title + summary）"""
    lines = []
    for f in sorted(os.listdir(kb.NODES_DIR)):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(kb.NODES_DIR, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        import yaml
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        if fm.get("id") in cand_ids:
            lines.append(f"- {fm.get('title')} ({fm.get('id')}): {fm.get('summary', '')[:60]}")
    return "\n".join(lines)


def _llm_pick(cand_ids, question):
    """LLM 从候选里精挑 2-3 个（复用 kb 的 client 逻辑）"""
    from openai import OpenAI
    cand_index = _build_cand_index(cand_ids)
    client = OpenAI(api_key=DS["key"], base_url=DS["base_url"], timeout=90)
    prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选 2-3 个最相关的节点，只输出节点 id 列表，格式如 ["comm-am","comm-rf-mod"]，不要输出任何其他内容。

问题：{question}"""
    for attempt in range(2):
        try:
            r = client.chat.completions.create(
                model=DS["name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
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


def method_A(question):
    """top-5 + links 扩展（不截断）+ LLM 精挑"""
    scores = kb._tfidf_similarity(question, doc_texts)
    ranked = [nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1])
              if meta.get(nid, {}).get("type") in ("core", "leaf")]
    top5 = ranked[:5]
    cand = list(top5)
    for nid in top5:
        for nb in meta.get(nid, {}).get("links", []):
            if meta.get(nb, {}).get("type") in ("core", "leaf") and nb not in cand:
                cand.append(nb)
    return _llm_pick(cand, question), len(cand)


def method_B(question):
    """top-10 排除 hub + LLM 精挑（= select_nodes_d）"""
    nids = kb.select_nodes_d(DS, question, tree_index)
    return nids, 10


def evaluate(name, fn):
    th = te = exact = one = 0
    avg_cand = 0
    for q in qs:
        try:
            nids, n_cand = fn(q["question"])
        except Exception as e:
            nids, n_cand = [], 0
        avg_cand += n_cand
        exp = set(q["expected_nodes"])
        sel = set(nids)
        hit = exp & sel
        th += len(hit)
        te += len(exp)
        if hit and len(hit) == len(exp):
            exact += 1
        if hit:
            one += 1
        time.sleep(0.15)
    n = len(qs)
    print(f"[{name}]")
    print(f"  召回 {th}/{te} = {th/te*100:.1f}% | 完全命中 {exact}/{n} | 至少命中1个 {one}/{n} | 平均候选 {avg_cand/n:.1f}")
    print()
    return th, te, exact, one


if __name__ == "__main__":
    print(f"=== 方案对比：top5+links+LLM vs top10+LLM（DeepSeek，{len(qs)} 题，expected {sum(len(q['expected_nodes']) for q in qs)} 个）===\n")
    print("先跑方案 B（当前）...", flush=True)
    evaluate("方案B 直接top10+LLM精挑", method_B)
    print("再跑方案 A（新）...", flush=True)
    evaluate("方案A top5+links+LLM精挑", method_A)
    print("done", flush=True)
