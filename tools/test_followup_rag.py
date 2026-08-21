# -*- coding: utf-8 -*-
"""followup_rag.py 插件冒烟测试（独立，不依赖 eval_followup）。

验证 need_history / should_skip 在关键样本上的判定是否符合 benchmark 结论：
- D1 裸指代（"补零呢""那反过来呢"）→ 需要带历史
- D2/D3 完整短追问（"频谱泄露根源是什么"）→ 不带历史
- 闲聊（"安慰我""好呀"）→ should_skip 拦截
- 换话题（"那 LTE 帧结构是多少毫秒？"）→ 含"那"触发（宽松版特性，由 gate 分辨）
"""
import json
import sys
import io
import os
import re
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiturn_rag.followup_rag import FollowupRAG

# 技术词表（模拟线上 _is_short_chat 的技术词，should_skip 用它区分"技术短句"与"闲聊"）
TECH_RE = re.compile(
    r"(FFT|DFT|DTFT|卷积|滤波|采样|混叠|频谱|信号|噪声|带宽|信噪比|衰落|多普勒|瑞利|莱斯|信道|编码|OFDM|调频|FM|AM|DSB|SSB|相位|频域|时域|功率|能量|香农|交织|循环码|频率|调制|解调|正交|MIMO|天线|电磁|傅里叶|拉普拉斯|Z变换|冲激|窗函数|吉布斯|奈奎斯特|抽取|内插|上采样|下采样|采样率|分辨率|线性|因果|稳定|极点|零点|反馈|双线性|预畸变|群时延|码间串扰|幅度|相位失真|FIR|IIR|切比雪夫|巴特沃斯|高斯|随机|包络|相干|多径|直射|反射|路径损耗|生成多项式|纠错|检错|冗余|频谱泄露|栅栏效应|加窗|主瓣|旁瓣|过渡带|LTE|均衡器|模型|GPU|显存|量化)")

plugin = FollowupRAG(tech_re=TECH_RE)

cases = [
    # (当前句, 上一轮, 期望 need_history, 期望 should_skip)
    ("补零呢？", "观测时间不变，单纯末尾补零效果是什么？", True, False),
    ("补零呢", "观测时间不变，单纯末尾补零效果是什么？", True, False),
    ("那反过来呢", "周期延拓什么条件下会发生混叠？", True, False),
    ("频谱泄露根源是什么？", "频谱泄露、栅栏效应、加窗，是不是DFT的三大问题？", False, False),
    ("为什么相位失真会产生码间串扰？", "什么是线性相位，群时延物理意义？", False, False),
    ("安慰我", "多普勒带宽来自多径还是多普勒效应？", False, True),
    ("好呀", "香农公式怎么理解？", False, True),
]

print("=== need_history / should_skip 判定样例 ===")
ok = True
for q, prev, exp_nh, exp_skip in cases:
    nh = plugin.need_history(q, prev)
    sk = plugin.should_skip(q, prev)
    mark = "PASS" if (nh == exp_nh and sk == exp_skip) else "FAIL"
    if nh != exp_nh or sk != exp_skip:
        ok = False
    print(f"  [{mark}] {q!r} -> need_history={nh}(期望{exp_nh}) should_skip={sk}(期望{exp_skip})")

# 全题库判定分布 sanity（有题库时）
qs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmark", "multiturn_questions.json")
if os.path.exists(qs_path):
    data = json.load(open(qs_path, encoding="utf-8"))
    c = Counter()
    prev_q = None
    for d in data["dialogues"]:
        for t in d["turns"]:
            q = t["q"]
            if plugin.should_skip(q, prev_q):
                c["skip(闲聊)"] += 1
            elif plugin.need_history(q, prev_q):
                c["need_history(带历史)"] += 1
            else:
                c["独立检索"] += 1
            prev_q = q
    print(f"\n全题库判定分布: {dict(c)}")

print("\n结论:", "✅ 全部通过" if ok else "❌ 有 FAIL，需检查")
