#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多轮追问 benchmark 评测（检索层，不评端到端回答）。

对比两种检索方式，唯一变量 = 追问记忆插件：
  baseline  （无插件）：每轮独立「TF-IDF 初筛 → gate 精挑」，不看历史
  followup （有插件）：追问判定 → 历史节点并入候选池 → gate 带上一轮上下文

指标（分 dependency 档位）：
  recall@3     注入节点 ∩ expected 非空 / 该档轮数（追问档 D1~D4 重点看）
  漏检率       gate 判 NONE(不注入) 的追问轮占比
  新话题误用率 D5 轮错误复用上一轮历史节点的占比
  闲聊误检率   chitchat 轮错误触发注入的占比

用法：
  python tools/eval_followup.py --limit 12          # 前 12 组快速验证
  python tools/eval_followup.py --mode followup     # 只跑插件
  python tools/eval_followup.py --no-gate           # 纯 TF-IDF 预筛，0 LLM 调用（sanity）
  python tools/eval_followup.py --model deepseek-chat
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from math import sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kb_benchmark as kb  # 复用 _tokenize / _tfidf_similarity / _load_node_meta / load_env

BASE = kb.BASE
QUESTIONS_PATH = os.path.join(BASE, "benchmark", "multiturn_questions.json")
RESULT_DIR = os.path.join(BASE, "benchmark", "results")

# ── 可调旋钮（追问插件的超参，集中暴露，评测调参改这里）──────────────
SIM_THRESHOLD = 0.15    # 追问判定：当前问题 vs 上一轮问题的 TF-IDF 余弦阈值
REF_BOOST_SIM = 0.03    # 含指代词/连接词时，相似度门槛放宽到该值
SHORT_LEN = 15          # 短追问字数阈值（≤此字数+指代词 → 强判追问）
HIST_WINDOW = 1         # 历史节点窗口（v1 只取上一轮注入节点）
CAND_CAP = 10           # 候选池封顶（TF-IDF top + 历史节点合并后）
FLOOR_WEIGHT = 0.1      # 历史节点并入时的保底权重（不压制 TF-IDF 强命中）
TFIDF_TOP = 5           # TF-IDF 初筛取前 K（历史节点在其上补齐）

REF_WORDS = ("那", "它", "他", "她", "这个", "这样", "这些", "那些", "但", "但是",
             "为什么", "怎么", "再", "还有", "然后", "所以", "反过来", "往下", "继续", "呢")

# 强指代/省略信号：命中才触发"带历史"（区别于广义追问信号，避免 D2/D3 被历史干扰）
STRONG_REF = ("那", "它", "他", "她", "这个", "这样", "这些", "那些", "反过来", "往下", "继续", "还有呢", "然后呢")

# 语气词/无意义字（相似度计算时剔除，避免"呢/啊/的"污染 TF 余弦）
PARTICLES = "呢啊呀吧吗嘛哈哦啦唉哟哇咦嘿嗯么的了"
# 复合方法：need_history 信号命中后，与上轮余弦 > 该值才算"真追问"（拦"那LTE帧结构"这类换话题误触发）
COS_CONFIRM = 0.10

# gate 支持的模型（复用 kb 的 MODELS）
GATE_MODELS = {m["name"]: m for m in kb.MODELS}

# 闲聊前置过滤用的技术词表（模拟线上 _is_short_chat 的增强版）
TECH_RE = re.compile(
    r"(FFT|DFT|DTFT|卷积|滤波|采样|混叠|频谱|信号|噪声|带宽|信噪比|衰落|多普勒|瑞利|莱斯|信道|编码|OFDM|调频|FM|AM|DSB|SSB|相位|频域|时域|功率|能量|香农|交织|循环码|频率|调制|解调|正交|MIMO|天线|电磁|傅里叶|拉普拉斯|Z变换|冲激|窗函数|吉布斯|奈奎斯特|抽取|内插|上采样|下采样|采样率|分辨率|线性|因果|稳定|极点|零点|反馈|双线性|预畸变|群时延|码间串扰|幅度|相位失真|FIR|IIR|切比雪夫|巴特沃斯|高斯|随机|包络|相干|多径|直射|反射|路径损耗|生成多项式|纠错|检错|冗余|频谱泄露|栅栏效应|加窗|主瓣|旁瓣|过渡带|计算机网络|OSI|TCP|IP|HTTP|LTE|均衡器|智能体|模型|GPU|显存|量化|复习|面试|保研)")


def is_chitchat(q: str, prev_q: str, variant: str = "current") -> bool:
    """闲聊前置过滤（模拟线上 _is_short_chat + 增强）：
    短句 + 无技术词 + 非裸指代追问 → 视为闲聊，不触发检索（注入 []）。
    """
    q = q.strip()
    if not q or len(q) > 15:
        return False  # 长句不拦（可能有信息量）
    if TECH_RE.search(q):
        return False  # 含技术词不拦
    if need_history(q, prev_q, variant):
        return False  # 裸指代/省略式追问（"补零呢"）不拦，走追问逻辑
    return True


# ── 文本相似度（两句话 TF 余弦）──────────────────────────────────────
def _cos_between(a: str, b: str) -> float:
    ta, tb = defaultdict(int), defaultdict(int)
    for t in kb._tokenize(a):
        ta[t] += 1
    for t in kb._tokenize(b):
        tb[t] += 1
    common = set(ta) & set(tb)
    dot = sum(ta[t] * tb[t] for t in common)
    na = sqrt(sum(v * v for v in ta.values())) or 1.0
    nb = sqrt(sum(v * v for v in tb.values())) or 1.0
    return dot / (na * nb)


def strip_particles(text: str) -> str:
    """剔除语气词与常用标点，用于相似度计算的干净文本"""
    return re.sub(f"[{PARTICLES}？?。！!，,、～~…·《》【】\"']", "", text)


def _cos_clean(a: str, b: str) -> float:
    """去语气词后的 TF 余弦（更准，不被"呢/啊/的"污染）"""
    return _cos_between(strip_particles(a), strip_particles(b))


def is_followup(cur_q: str, prev_q: str) -> bool:
    """v1 追问判定：指代词信号 + TF-IDF 相似度。无上一轮 → False"""
    if not prev_q:
        return False
    sim = _cos_between(cur_q, prev_q)
    has_ref = any(w in cur_q for w in REF_WORDS)
    short = len(cur_q) <= SHORT_LEN
    if has_ref and (sim > REF_BOOST_SIM or short):
        return True
    return sim > SIM_THRESHOLD


def need_history(cur_q: str, prev_q: str, variant: str = "current") -> bool:
    """是否需要带历史（比 is_followup 更严格，只对强指代/省略式追问为 True）。

    关键设计：D1 裸指代/省略式追问（"那反过来呢""补零呢"）TF-IDF 不可靠，历史才是答案；
    D2/D3 短追问（"频谱泄露根源是什么"）本身信息完整，带历史反而被上一轮节点带偏。
    故只对强指代 + 短 / 呢结尾 / 强指代+高相似 触发带历史。

    variant:
      current        原逻辑（信号命中即带历史）
      compound       信号命中 + 与上轮余弦 > COS_CONFIRM（拦"那LTE帧结构"换话题误触发）
      clean_compound 同 compound，但余弦用去语气词后的文本（更准）
    """
    if not prev_q:
        return False
    q = cur_q.strip()
    has_strong = any(w in cur_q for w in STRONG_REF)
    ends_ne = q.endswith("呢") or q.endswith("呢？") or q.endswith("呢。")
    short = len(q) <= SHORT_LEN
    # 省略式追问（"补零呢？"）或 强指代短追问（"那混叠呢"）
    if ends_ne or (has_strong and short):
        signal = True
    # 强指代 + 较高相似（"那反过来不做周期延拓会怎样" 这类中等长度）
    elif has_strong and _cos_between(cur_q, prev_q) > REF_BOOST_SIM:
        signal = True
    else:
        signal = False
    if not signal:
        return False
    # 复合确认：与上轮余弦 > COS_CONFIRM，否则视为换话题（拒绝带历史）
    if variant in ("compound", "clean_compound"):
        sim = _cos_clean(cur_q, prev_q) if variant == "clean_compound" else _cos_between(cur_q, prev_q)
        if sim <= COS_CONFIRM:
            return False
    return True


# ── 检索核心 ──────────────────────────────────────────────────────────
class Retriever:
    """一次加载知识库节点文本 + meta，提供 TF-IDF 初筛 + gate 精挑"""

    def __init__(self, model_cfg):
        self.model = model_cfg
        self.doc_texts = kb._all_node_texts()
        self.meta = kb._load_node_meta()

    def tfidf_candidates(self, q: str, top_k: int = TFIDF_TOP) -> list:
        """TF-IDF 初筛：排除 root/hub，只留 core/leaf，返回 [nid...]（按分数降序）"""
        scores = kb._tfidf_similarity(q, self.doc_texts)
        return [
            nid for nid, _ in sorted(scores.items(), key=lambda x: -x[1])
            if self.meta.get(nid, {}).get("type") in ("core", "leaf") and nid != "root"
        ][:top_k]

    @staticmethod
    def merge_history(tfidf_ids: list, history_ids: list, cap: int = CAND_CAP, history_first: bool = False) -> list:
        """历史节点并入候选池：去重、封顶。

        history_first=False（默认）：TF-IDF 命中优先，历史垫底（D2/D3 独立追问场景，历史仅兜底）
        history_first=True：历史优先（D1 裸指代场景，TF-IDF 不可靠，历史才是答案）
        """
        if not history_ids:
            return tfidf_ids[:cap]
        merged = []
        seen = set()
        if history_first:
            for nid in history_ids:
                if nid != "root" and nid not in seen:
                    merged.append(nid)
                    seen.add(nid)
            for nid in tfidf_ids:
                if nid not in seen:
                    merged.append(nid)
                    seen.add(nid)
        else:
            for nid in tfidf_ids:
                if nid not in seen:
                    merged.append(nid)
                    seen.add(nid)
            for nid in history_ids:
                if nid not in seen and nid != "root":
                    merged.append(nid)
                    seen.add(nid)
        return merged[:cap]

    def gate_select(self, q: str, cands: list, context: dict | None = None) -> list:
        """LLM 精挑：从候选里选相关节点，返回 [nid...]；全不相关返回 []（NONE）"""
        if not cands:
            return []
        cand_lines = []
        for nid in cands:
            m = self.meta.get(nid, {})
            cand_lines.append(f"- {m.get('title', nid)} ({nid}): {m.get('summary', '')[:60]}")
        cand_index = "\n".join(cand_lines)

        if context:
            ctx_block = (
                f"上一轮问题：{context['q']}\n"
                f"上一轮已用知识点：{', '.join(context['titles']) or '(无)'}\n\n"
                f"注意：当前问题可能是对上一轮的追问，可能口语化、省略主语、用代词指代上一轮的概念。"
                f"请结合上一轮上下文理解，不要因为口语化/省略/指代就判定不相关。\n"
            )
        else:
            ctx_block = ""

        prompt = f"""你是通信工程专业的学生。下面是程序预筛选出的候选知识点（已按相关度排序）：

{cand_index}

现在要回答一个问题。请从候选中选出与当前问题相关的知识点（选 1-3 个），只输出节点 id 列表，格式如 ["dsp-dft"]；如果候选中没有相关的，只输出 NONE，不要输出任何其他内容。

{ctx_block}
当前问题：{q}"""

        extra = {}
        if re.search(r"qwen3|GLM-5|MiniMax|Kimi-K2", self.model["name"], re.I):
            extra["extra_body"] = {"enable_thinking": False}
        client = kb.OpenAI(api_key=self.model["key"], base_url=self.model["base_url"], timeout=90)
        for attempt in range(2):
            try:
                r = client.chat.completions.create(
                    model=self.model["name"],
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0,
                    **extra,
                )
                text = r.choices[0].message.content.strip()
                if "NONE" in text.upper() and "[" not in text:
                    return []
                m = re.search(r"\[.*?\]", text, re.DOTALL)
                if m:
                    try:
                        ids = json.loads(m.group(0))
                        result = [i for i in ids if isinstance(i, str) and i in cands][:3]
                        if result:
                            return result
                    except Exception:
                        pass
                found = [i for i in re.findall(r"((?:comm|dsp|mob|rsp|emf|net)-[\w-]+)", text) if i in cands]
                if found:
                    return found[:3]
                return []
            except Exception:
                if attempt == 1:
                    return []
                time.sleep(1)
        return []


# ── 两种检索流程 ─────────────────────────────────────────────────────
def run_baseline(dialogues, retr, no_gate=False):
    """无插件：每轮独立检索，不看历史；闲聊前置过滤拦截短闲聊"""
    results = []
    for d in dialogues:
        prev_q = None
        for i, t in enumerate(d["turns"]):
            q = t["q"]
            if is_chitchat(q, prev_q):
                injected = []
            else:
                cands = retr.tfidf_candidates(q)
                if no_gate:
                    injected = cands[:3]
                else:
                    injected = retr.gate_select(q, cands, context=None)
            results.append({
                "did": d["id"], "turn": i, "q": q,
                "dependency": t["dependency"], "expected": t["expected"],
                "injected": injected,
            })
            prev_q = q
    return results


def run_followup(dialogues, retr, no_gate=False, variant="current"):
    """有插件：强指代/省略式追问才带历史（历史优先），其余独立检索；闲聊前置过滤。
    variant: current / compound / clean_compound（见 need_history）
    """
    results = []
    for d in dialogues:
        prev_q = None
        prev_ids = []
        for i, t in enumerate(d["turns"]):
            q = t["q"]
            if is_chitchat(q, prev_q, variant):
                injected = []
                nh = False
            else:
                nh = need_history(q, prev_q, variant)
                tfidf_ids = retr.tfidf_candidates(q)
                if nh:
                    # 强指代/省略式追问：历史优先（TF-IDF 对裸指代不可靠）
                    cands = retr.merge_history(tfidf_ids, prev_ids, history_first=True)
                    context = {
                        "q": prev_q,
                        "titles": [retr.meta.get(n, {}).get("title", n) for n in prev_ids],
                    }
                else:
                    cands = tfidf_ids
                    context = None
                if no_gate:
                    injected = cands[:3]
                else:
                    injected = retr.gate_select(q, cands, context=context)
            results.append({
                "did": d["id"], "turn": i, "q": q,
                "dependency": t["dependency"], "expected": t["expected"],
                "injected": injected, "is_followup": nh,
            })
            prev_q = q
            prev_ids = injected
    return results


# ── 指标计算 ─────────────────────────────────────────────────────────
def hit(injected, expected):
    return bool(expected) and any(n in expected for n in injected)


def evaluate(results):
    """分档指标。返回 {档位: {n, recall, ...}}"""
    stat = defaultdict(lambda: {"n": 0, "hit": 0, "empty": 0, "reuse_prev": 0})
    for r in results:
        dep = r["dependency"]
        s = stat[dep]
        s["n"] += 1
        if hit(r["injected"], r["expected"]):
            s["hit"] += 1
        if not r["injected"]:
            s["empty"] += 1
        # 误用：注入节点全不在 expected（记作 off_target）
        if r["injected"] and not hit(r["injected"], r["expected"]):
            s["off_target"] = s.get("off_target", 0) + 1
    out = {}
    for dep, s in stat.items():
        n = s["n"]
        out[dep] = {
            "n": n,
            "recall": round(s["hit"] / n, 3) if n else 0,
            "miss_rate": round(s["empty"] / n, 3) if n else 0,  # 漏检(判NONE)
            "off_target": round(s.get("off_target", 0) / n, 3) if n else 0,  # 注入但没命中
        }
    return out


def print_report(baseline, followup, dialogues):
    print("\n" + "=" * 74)
    print("多轮追问 benchmark 检索层评测报告")
    print("=" * 74)
    eb = evaluate(baseline)
    ef = evaluate(followup)

    print("\n{:<12}{:>6}{:>16}{:>16}{:>14}".format(
        "dependency", "n", "baseline R@3", "followup R@3", "增益"))
    print("-" * 74)
    order = ["first", "D1", "D2", "D3", "D4", "D5", "chitchat"]
    for dep in order:
        if dep not in eb and dep not in ef:
            continue
        b = eb.get(dep, {"n": 0, "recall": 0})
        f = ef.get(dep, {"n": 0, "recall": 0})
        n = f.get("n", 0) or b.get("n", 0)
        gain = f["recall"] - b["recall"]
        print("{:<12}{:>6}{:>16}{:>16}{:>+13.3f}".format(
            dep, n, b["recall"], f["recall"], gain))

    # 追问档（D1~D4）汇总
    def agg(dep_stats, deps):
        n = sum(dep_stats.get(d, {"n": 0})["n"] for d in deps)
        hit = sum(dep_stats.get(d, {"n": 0})["n"] * dep_stats.get(d, {"recall": 0})["recall"] for d in deps)
        return (round(hit / n, 3) if n else 0, n)

    b_fu, n_fu = agg(eb, ["D1", "D2", "D3", "D4"])
    f_fu, _ = agg(ef, ["D1", "D2", "D3", "D4"])
    print("-" * 74)
    print(f"追问档(D1~D4) 汇总: baseline R@3={b_fu}  followup R@3={f_fu}  增益={f_fu - b_fu:+.3f}  (n={n_fu})")

    # 负例档（D5 新话题 / chitchat 闲聊）
    print("\n负例档:")
    for dep, label in [("D5", "新话题(应独立命中新话题节点,不吞历史)"), ("chitchat", "闲聊(应不触发注入)")]:
        f = ef.get(dep, {"n": 0, "recall": 0, "off_target": 0, "miss_rate": 0})
        if dep == "chitchat":
            false_pos = round(1 - f["miss_rate"], 3)  # 注入非空率 = 误检率（应=0）
            print(f"  {label}: n={f['n']}  误检率(注入非空)={false_pos}  注入偏离={f['off_target']}")
        else:
            print(f"  {label}: n={f['n']}  独立命中率={f['recall']}  注入偏离(未命中expected)={f['off_target']}")

    return eb, ef


def print_variant_compare(baseline, followup_map, dialogues):
    """多变体对比：并列显示各 variant 的分档 recall + 汇总 + 负例"""
    eb = evaluate(baseline)
    efs = {v: evaluate(fol) for v, fol in followup_map.items()}

    print("\n" + "=" * 74)
    print("多变体对比（baseline vs 各 variant 的 followup）")
    print("=" * 74)
    order = ["D1", "D2", "D3", "D4", "first", "D5", "chitchat"]
    header = "{:<10}{:>5}".format("dependency", "n")
    for v in followup_map:
        header += f"{v:>18}"
    print(header)
    print("-" * len(header))
    for dep in order:
        if dep not in eb and not any(dep in e for e in efs.values()):
            continue
        n = eb.get(dep, {"n": 0})["n"] or next(iter(efs.values())).get(dep, {"n": 0})["n"]
        row = f"{dep:<10}{n:>5}"
        for v in followup_map:
            f = efs[v].get(dep, {"n": 0, "recall": 0})
            row += f"{f['recall']:>18}"
        print(row)

    def agg(dep_stats, deps):
        n = sum(dep_stats.get(d, {"n": 0})["n"] for d in deps)
        hit = sum(dep_stats.get(d, {"n": 0})["n"] * dep_stats.get(d, {"recall": 0})["recall"] for d in deps)
        return (round(hit / n, 3) if n else 0, n)

    b_fu, n_fu = agg(eb, ["D1", "D2", "D3", "D4"])
    row = f"追问档汇总  {n_fu:>5}"
    for v in followup_map:
        f_fu, _ = agg(efs[v], ["D1", "D2", "D3", "D4"])
        row += f"{f_fu:>18}"
    print("-" * len(header))
    print(row)
    row = f"{'净增益':<10}{'':>5}"
    for v in followup_map:
        f_fu, _ = agg(efs[v], ["D1", "D2", "D3", "D4"])
        row += f"{f_fu - b_fu:>+18.3f}"
    print(row)

    print("\n负例档:")
    for dep, label in [("D5", "新话题(独立命中率↑好)"), ("chitchat", "闲聊(误检率↓好)")]:
        line = f"  {label}: "
        for v in followup_map:
            f = efs[v].get(dep, {"n": 0, "recall": 0, "miss_rate": 0})
            if dep == "chitchat":
                fp = round(1 - f["miss_rate"], 3)
                line += f"{v}={fp}(误检) "
            else:
                line += f"{v}={f['recall']}(命中) "
        print(line)

    return eb, efs


# ── 主流程 ───────────────────────────────────────────────────────────
def main():
    kb.load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 组（0=全部）")
    parser.add_argument("--mode", default="both", choices=["baseline", "followup", "both"])
    parser.add_argument("--model", default="deepseek-chat", help="gate 模型")
    parser.add_argument("--no-gate", action="store_true", help="纯 TF-IDF 预筛，0 LLM 调用（sanity check）")
    parser.add_argument("--variant", default="current",
                        help="followup 变体，逗号分隔可多值: current / compound / clean_compound（默认 current）")
    args = parser.parse_args()

    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    dialogues = data["dialogues"]
    if args.limit > 0:
        dialogues = dialogues[: args.limit]

    model_cfg = GATE_MODELS.get(args.model)
    if not model_cfg:
        print(f"[错误] 模型 {args.model} 不在可用列表。可用: {list(GATE_MODELS)}", flush=True)
        sys.exit(1)
    if not args.no_gate and not model_cfg.get("key"):
        print(f"[错误] 模型 {args.model} 无 API key（tools/.env 未配置）。no-gate 模式无需 key，可加 --no-gate。", flush=True)
        sys.exit(1)

    variants = [v.strip() for v in args.variant.split(",") if v.strip()]
    retr = Retriever(model_cfg)
    print(f"题库: {len(dialogues)} 组 | gate 模型: {args.model} | no_gate={args.no_gate} | variants={variants}", flush=True)
    print(f"旋钮: sim_threshold={SIM_THRESHOLD} ref_boost={REF_BOOST_SIM} short_len={SHORT_LEN} "
          f"cand_cap={CAND_CAP} floor={FLOOR_WEIGHT} tfidf_top={TFIDF_TOP} cos_confirm={COS_CONFIRM}", flush=True)

    baseline, followup_map = [], {}
    if args.mode in ("baseline", "both"):
        print("\n[1/2] 跑 baseline（无插件，逐轮独立检索）...", flush=True)
        baseline = run_baseline(dialogues, retr, args.no_gate)
    if args.mode in ("followup", "both"):
        for v in variants:
            print(f"\n[2/2] 跑 followup variant={v}...", flush=True)
            followup_map[v] = run_followup(dialogues, retr, args.no_gate, variant=v)

    # 保存原始结果
    os.makedirs(RESULT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(RESULT_DIR, f"followup_raw_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"baseline": baseline, "followup_map": followup_map}, f, ensure_ascii=False, indent=1)
    print(f"\n原始结果已保存: {raw_path}", flush=True)

    if baseline and followup_map:
        print_variant_compare(baseline, followup_map, dialogues)
    elif baseline:
        print("\n=== baseline 分档指标 ===")
        print(json.dumps(evaluate(baseline), ensure_ascii=False, indent=2))
    elif followup_map:
        for v, fol in followup_map.items():
            print(f"\n=== followup[{v}] 分档指标 ===")
            print(json.dumps(evaluate(fol), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
