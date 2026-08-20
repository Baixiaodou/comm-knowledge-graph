#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多轮追问记忆插件（v1.4 定稿 · current 版）。

从 benchmark 评测验证出的最优逻辑抽取（44 组题库实测：追问档净增益 +9.8%，
闲聊误检率 0，D1 裸指代增益 +29%）。设计为**纯判定/合并逻辑**，TF-IDF 与
LLM gate 由调用方注入，因此可直接对接线上 node_retriever，不依赖本项目其他模块。

三件事（对应三个公开方法）：
  1. should_skip(q, prev_q)    闲聊前置过滤 —— 短句+无技术词+非追问 → True（不检索）
  2. need_history(q, prev_q)   追问判定     —— 强指代/省略式追问 → True（带历史）
  3. build_candidates(...)     候选池合并   —— 追问时历史节点优先（D1 裸指代
     + build_context(...)                     TF-IDF 不可靠，历史才是答案）

用法（线上对接示例）：
    plugin = FollowupRAG(tech_re=..., tokenize_fn=...)
    # 每用户每轮：
    if plugin.should_skip(q, prev_q):
        injected = []                      # 闲聊，不检索
    else:
        tfidf_ids = tfidf_fn(q)            # 调用方 TF-IDF 初筛（排除 hub/root）
        if plugin.need_history(q, prev_q):
            cands = plugin.merge_history(tfidf_ids, prev_ids, history_first=True)
            ctx = plugin.build_context(prev_q, prev_ids, title_fn)
        else:
            cands, ctx = tfidf_ids, None
        injected = gate_fn(q, cands, ctx)  # 调用方 LLM 精挑
    prev_q, prev_ids = q, injected         # 每用户状态（线上存内存 dict/SQLite）

作者：小洛洛多轮追问改造（2026-08-21）
"""
import re
from math import sqrt


class FollowupRAG:
    # 强指代/省略信号：命中才触发"带历史"（区别于广义追问信号，避免 D2/D3 被历史干扰）
    STRONG_REF = ("那", "它", "他", "她", "这个", "这样", "这些", "那些",
                  "反过来", "往下", "继续", "还有呢", "然后呢")

    # 语气词/无意义字（相似度计算时剔除，避免"呢/啊/的"污染余弦）
    PARTICLES = "呢啊呀吧吗嘛哈哦啦唉哟哇咦嘿嗯么的了"

    def __init__(self, tech_re=None, tokenize_fn=None, short_len=15, ref_boost_sim=0.03):
        """
        tech_re: 技术词正则（编译好的 re.Pattern）。用于闲聊过滤——含技术词不拦。
                 线上可直接传 node_retriever 的关键词模式；没有则传 None（视为全不拦）。
        tokenize_fn: 中文分词/切词函数（用于 TF 余弦）。缺省用字符 2-gram（与项目 TF-IDF 一致）。
        short_len: 短追问字数阈值（≤此字数 + 指代 → 强判追问）。
        ref_boost_sim: 含强指代时相似度门槛放宽到该值。
        """
        self.tech_re = tech_re
        self._tokenize = tokenize_fn or self._default_tokenize
        self.short_len = short_len
        self.ref_boost_sim = ref_boost_sim

    # ── 分词与相似度 ─────────────────────────────────────────────────
    @staticmethod
    def _default_tokenize(text):
        """中文按字符 2-gram，英文/数字按小写词（与项目 TF-IDF 一致）"""
        tokens = []
        for seg in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower()):
            if re.match(r"[\u4e00-\u9fff]", seg):
                if len(seg) >= 2:
                    tokens += [seg[i:i + 2] for i in range(len(seg) - 1)]
                else:
                    tokens.append(seg)
            else:
                tokens.append(seg)
        return tokens

    def strip_particles(self, text):
        return re.sub(f"[{self.PARTICLES}？?。！!，,、～~…·《》【】\"']", "", text)

    def _cos(self, a, b, clean=False):
        ta, tb = {}, {}
        if clean:
            a, b = self.strip_particles(a), self.strip_particles(b)
        for t in self._tokenize(a):
            ta[t] = ta.get(t, 0) + 1
        for t in self._tokenize(b):
            tb[t] = tb.get(t, 0) + 1
        common = set(ta) & set(tb)
        dot = sum(ta[t] * tb[t] for t in common)
        na = sqrt(sum(v * v for v in ta.values())) or 1.0
        nb = sqrt(sum(v * v for v in tb.values())) or 1.0
        return dot / (na * nb)

    # ── ① 闲聊前置过滤（模拟线上 _is_short_chat 的增强版）──────────
    def should_skip(self, q, prev_q):
        """短句 + 无技术词 + 非裸指代追问 → 视为闲聊，不触发检索"""
        q = q.strip()
        if not q or len(q) > 15:
            return False                      # 长句不拦（可能有信息量）
        if self.tech_re and self.tech_re.search(q):
            return False                      # 含技术词不拦
        if self.need_history(q, prev_q):
            return False                      # 裸指代/省略式追问不拦
        return True

    # ── ② 追问判定（是否带历史）────────────────────────────────────
    def need_history(self, cur_q, prev_q):
        """强指代/省略式追问才带历史。

        D1 裸指代（"那反过来呢""补零呢"）TF-IDF 不可靠，历史才是答案；
        D2/D3 短追问（"频谱泄露根源是什么"）本身信息完整，不带历史（避免被带偏）。
        注意：不做"与上轮余弦确认"——实测（benchmark v1.4）余弦确认会把 D1 裸指代
        误杀（裸指代与上轮词面本就不重合），净增益从 +9.8% 掉到 +2.0%。
        """
        if not prev_q:
            return False
        q = cur_q.strip()
        has_strong = any(w in cur_q for w in self.STRONG_REF)
        ends_ne = q.endswith("呢") or q.endswith("呢？") or q.endswith("呢。")
        short = len(q) <= self.short_len
        if ends_ne or (has_strong and short):
            return True
        if has_strong and self._cos(cur_q, prev_q) > self.ref_boost_sim:
            return True
        return False

    # ── ③ 候选池合并 + 上下文构建 ──────────────────────────────────
    @staticmethod
    def merge_history(tfidf_ids, history_ids, cap=10, history_first=True):
        """历史节点并入候选池：去重、封顶。

        history_first=True（追问默认）：历史优先——D1 裸指代 TF-IDF 不可靠，历史才是答案。
        history_first=False：TF-IDF 命中优先，历史垫底（独立追问兜底场景）。
        """
        if not history_ids:
            return tfidf_ids[:cap]
        merged, seen = [], set()
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

    @staticmethod
    def build_context(prev_q, prev_ids, title_fn=None):
        """构建 gate 的上一轮上下文（追问时传给 gate 消歧）"""
        titles = []
        if title_fn:
            titles = [title_fn(n) for n in prev_ids if title_fn(n)]
        return {
            "q": prev_q,
            "titles": titles,
            "nodes": prev_ids,
        }


class Session:
    """每用户追问会话状态（内存版；线上可换 SQLite 持久化）。

    一行对接线上：
        sessions = {}                      # {user_openid: Session}
        s = sessions.setdefault(uid, Session(plugin))
        injected = s.process(q, tfidf_fn, gate_fn, title_fn)

    返回本轮应注入的知识节点 id 列表（闲聊返回 []）。
    """

    def __init__(self, plugin=None):
        self.plugin = plugin or FollowupRAG()
        self.prev_q = None
        self.prev_ids = []

    def process(self, q, tfidf_fn, gate_fn, title_fn=None):
        """一轮完整处理：闲聊过滤 → 追问判定 → 候选合并 → gate 精挑 → 更新状态"""
        if self.plugin.should_skip(q, self.prev_q):
            injected = []
        else:
            tfidf_ids = tfidf_fn(q)
            if self.plugin.need_history(q, self.prev_q):
                cands = self.plugin.merge_history(tfidf_ids, self.prev_ids, history_first=True)
                ctx = self.plugin.build_context(self.prev_q, self.prev_ids, title_fn)
            else:
                cands, ctx = tfidf_ids, None
            injected = gate_fn(q, cands, ctx)
        self.prev_q = q
        self.prev_ids = injected
        return injected

    def reset(self):
        """新话题/换话题时清空状态"""
        self.prev_q = None
        self.prev_ids = []
