# -*- coding: utf-8 -*-
"""生成多轮追问 benchmark 题库：benchmark/multiturn_questions.json

数据来源：
  A 部分（正例 30 组）：source_raw_data/个人对话常用.txt 的「主问题+追问1+追问2」
      + 每组末尾补一条 D1 裸指代追问（制造"短追问/强依赖"梯度）
  B 部分（真实口语化追问 4 条）：洛洛真实对话日志（conversation_summaries + journalctl）
  C 部分（负例 5 条）：新话题误检 + 闲聊误检

dependency 档位：
  first    首问（独立检索）
  D1       裸指代 / 短追问（≤8字或纯指代，强依赖历史）
  D2       短追问（≤15字）
  D3       中等追问（16~25字）
  D4       长自包含追问（>25字，弱依赖）
  D5       新话题（负例，不应复用历史）
  chitchat 闲聊（负例，不应触发检索）

expected_nodes：该轮最终注入应命中的知识节点 id（core/leaf，来自 knowledge-v2/tree.json）
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(HERE)  # knowledge-base 根
SRC_TXT = os.path.join(KB, "..", "..", "source_raw_data", "个人对话常用.txt")
OUT = os.path.join(KB, "benchmark", "multiturn_questions.json")

# ── 1. 解析 个人对话常用.txt ───────────────────────────────────────────
def parse_txt(path):
    """返回 {编号: {main, f1, f2}}"""
    groups = {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # 每个条目：N. 问题：xxx \n 追问1：yyy \n 追问2：zzz
    entries = re.split(r"\n(?=\d+\.\s*问题：)", text)
    for e in entries:
        m = re.search(r"^(\d+)\.\s*问题：(.+)", e, re.M)
        if not m:
            continue
        num = int(m.group(1))
        main = m.group(2).strip()
        f1 = re.search(r"^追问1：(.+)", e, re.M)
        f2 = re.search(r"^追问2：(.+)", e, re.M)
        groups[num] = {
            "main": main,
            "f1": f1.group(1).strip() if f1 else "",
            "f2": f2.group(1).strip() if f2 else "",
        }
    return groups


# ── 2. 人工标注：30 组 expected_nodes + D1 补充追问 ──────────────────────
# exp: {"main": [...], "f1": [...], "f2": [...], "d1": [...]}
# d1_q: 每组末尾补的裸指代追问
ANNOT = {
    1: {"topic": "频域采样与周期延拓", "exp": {"main": ["dsp-dft", "dsp-sampling-theorem"], "f1": ["dsp-dft", "dsp-sampling-theorem"], "f2": ["dsp-sampling-theorem", "dsp-dft"], "d1": ["dsp-dft"], "d4": ["dsp-dft", "dsp-sampling-theorem"]}, "d1_q": "那反过来，不做周期延拓会怎样？", "d4_q": "既然时域采样满足奈奎斯特条件时频域才采 N 点做周期延拓，那么当频域采样点数 N 不够大时，周期延拓会在什么条件下发生混叠？"},
    2: {"topic": "DTFT 与 DFT", "exp": {"main": ["dsp-fourier-family", "dsp-dft"], "f1": ["dsp-fourier-family", "dsp-dft"], "f2": ["dsp-dft"], "d1": ["dsp-fourier-family", "dsp-dft"]}, "d1_q": "本质区别呢？"},
    3: {"topic": "DFT 循环卷积混叠", "exp": {"main": ["dsp-dft", "dsp-fft"], "f1": ["dsp-dft"], "f2": ["dsp-dft"], "d1": ["dsp-dft"], "d4": ["dsp-dft"]}, "d1_q": "关键参数呢？", "d4_q": "既然循环卷积会带来混叠但系统还能正常计算，那么在已知信道 H 的前提下，通过什么样的运算可以还原出原始输入序列？"},
    4: {"topic": "DFT 补点与线性卷积", "exp": {"main": ["dsp-dft", "dsp-fft"], "f1": ["dsp-dft"], "f2": ["mob-ofdm", "dsp-dft"], "d1": ["dsp-dft"]}, "d1_q": "那 M 的条件呢？"},
    5: {"topic": "FFT 功能与性质", "exp": {"main": ["dsp-fft"], "f1": ["dsp-fft"], "f2": ["dsp-fft", "dsp-spectrum"], "d1": ["dsp-fft"]}, "d1_q": "那它还是线性的吗？"},
    6: {"topic": "FFT 卷积与混叠", "exp": {"main": ["dsp-fft", "dsp-dft"], "f1": ["dsp-dft"], "f2": ["dsp-dft", "dsp-sampling-theorem"], "d1": ["dsp-dft"]}, "d1_q": "允许混叠的场景呢？"},
    7: {"topic": "FFT 复杂度", "exp": {"main": ["dsp-fft"], "f1": ["dsp-fft"], "f2": ["dsp-fft"], "d1": ["dsp-fft"]}, "d1_q": "补零呢？"},
    8: {"topic": "FFT 补零与分辨率", "exp": {"main": ["dsp-fft", "dsp-dft"], "f1": ["mob-ofdm", "dsp-fft"], "f2": ["dsp-spectrum", "dsp-fft"], "d1": ["dsp-spectrum"], "d4": ["mob-ofdm", "dsp-fft"]}, "d1_q": "那频率分辨率呢？", "d4_q": "既然 FFT 做卷积需要补零来避免混叠，那 OFDM 系统里的 IFFT 和 FFT 运算是否也需要补零，补零和不补零对结果有什么影响？"},
    9: {"topic": "DFT 三大问题", "exp": {"main": ["dsp-spectrum", "dsp-dft"], "f1": ["dsp-spectrum"], "f2": ["dsp-spectrum"], "d1": ["dsp-spectrum"]}, "d1_q": "泄露根源呢？"},
    10: {"topic": "频谱泄露与吉布斯", "exp": {"main": ["dsp-spectrum"], "f1": ["dsp-spectrum"], "f2": ["dsp-spectrum"], "d1": ["dsp-spectrum"]}, "d1_q": "那吉布斯现象呢？"},
    11: {"topic": "栅栏效应与分辨率", "exp": {"main": ["dsp-spectrum"], "f1": ["dsp-spectrum"], "f2": ["dsp-spectrum"], "d1": ["dsp-spectrum"], "d4": ["dsp-spectrum"]}, "d1_q": "那真正靠什么提？", "d4_q": "既然补零只能增加频点密度而不能提升物理频率分辨率，那么真正提升频率分辨率需要依靠什么，频点间隔和物理分辨率又有什么区别？"},
    12: {"topic": "观测时间与分辨精度", "exp": {"main": ["dsp-spectrum", "dsp-fourier-family"], "f1": ["dsp-spectrum"], "f2": ["dsp-spectrum"], "d1": ["dsp-spectrum"]}, "d1_q": "补零呢？"},
    13: {"topic": "窗函数参数", "exp": {"main": ["dsp-spectrum", "dsp-fir"], "f1": ["dsp-spectrum"], "f2": ["dsp-spectrum"], "d1": ["dsp-spectrum"]}, "d1_q": "主瓣宽度呢？"},
    14: {"topic": "H(s) 与 H(z)", "exp": {"main": ["dsp-laplace-z"], "f1": ["dsp-laplace-z", "dsp-fourier-family"], "f2": ["dsp-laplace-z"], "d1": ["dsp-laplace-z"]}, "d1_q": "收敛域呢？"},
    15: {"topic": "H(s) 时域与稳定性", "exp": {"main": ["dsp-laplace-z"], "f1": ["dsp-laplace-z", "dsp-fourier-family"], "f2": ["dsp-laplace-z"], "d1": ["dsp-laplace-z"]}, "d1_q": "极点要求呢？"},
    16: {"topic": "冲激响应不变法", "exp": {"main": ["dsp-iir"], "f1": ["dsp-iir"], "f2": ["dsp-iir"], "d1": ["dsp-iir"]}, "d1_q": "最大缺陷呢？"},
    17: {"topic": "双线性变换", "exp": {"main": ["dsp-iir"], "f1": ["dsp-iir"], "f2": ["dsp-iir"], "d1": ["dsp-iir"]}, "d1_q": "预畸变做在哪一步？"},
    18: {"topic": "线性相位与群时延", "exp": {"main": ["dsp-fir", "dsp-min-phase"], "f1": ["comm-isi", "dsp-fir"], "f2": ["dsp-iir", "dsp-min-phase"], "d1": ["dsp-iir", "dsp-min-phase"], "d4": ["dsp-iir", "dsp-min-phase"]}, "d1_q": "那 IIR 呢？", "d4_q": "既然相位失真会产生码间串扰而幅度失真不会，那么为什么因果稳定的 IIR 滤波器不能实现严格的线性相位？"},
    19: {"topic": "上采样插零与补零", "exp": {"main": ["dsp-reconstruction"], "f1": ["dsp-reconstruction"], "f2": ["dsp-reconstruction", "dsp-spectrum"], "d1": ["dsp-reconstruction"]}, "d1_q": "插零之后频谱呢？"},
    20: {"topic": "抽取与混叠", "exp": {"main": ["dsp-reconstruction"], "f1": ["dsp-reconstruction", "dsp-sampling-theorem"], "f2": ["dsp-reconstruction", "dsp-sampling-theorem"], "d1": ["dsp-reconstruction"]}, "d1_q": "混叠条件呢？"},
    21: {"topic": "切比雪夫 FIR/IIR", "exp": {"main": ["dsp-iir"], "f1": ["dsp-fir", "dsp-iir"], "f2": ["dsp-iir"], "d1": ["dsp-fir", "dsp-iir"]}, "d1_q": "怎么快速区分？"},
    22: {"topic": "切比雪夫 I/II 型", "exp": {"main": ["dsp-iir"], "f1": ["dsp-iir"], "f2": ["dsp-iir"], "d1": ["dsp-iir"]}, "d1_q": "波纹出现在哪？"},
    23: {"topic": "FIR/IIR 设计方法", "exp": {"main": ["dsp-fir", "dsp-iir"], "f1": ["dsp-fir"], "f2": ["dsp-fir", "dsp-min-phase"], "d1": ["dsp-fir"]}, "d1_q": "窗函数法呢？"},
    24: {"topic": "能量与功率信号", "exp": {"main": ["rsp-definition", "rsp-statistics"], "f1": ["rsp-definition"], "f2": ["rsp-definition"], "d1": ["rsp-definition"]}, "d1_q": "那随机信号呢？"},
    25: {"topic": "瑞利与莱斯分布", "exp": {"main": ["rsp-white-noise", "mob-small-scale"], "f1": ["rsp-white-noise", "mob-small-scale"], "f2": ["mob-small-scale", "rsp-white-noise"], "d1": ["rsp-white-noise", "mob-small-scale"], "d4": ["rsp-white-noise", "mob-small-scale"]}, "d1_q": "前提条件呢？", "d4_q": "既然窄带信号的包络服从瑞利或莱斯分布，那么这两种分布各自的前提条件是什么，有直射分量的时候对应哪一种？"},
    26: {"topic": "多普勒与相干", "exp": {"main": ["mob-small-scale"], "f1": ["mob-small-scale"], "f2": ["mob-small-scale"], "d1": ["mob-small-scale"], "d4": ["mob-small-scale"]}, "d1_q": "相干带宽呢？", "d4_q": "既然多普勒带宽和相干时间、相干带宽之间存在对应关系，那么相干带宽具体由什么物理量决定，它和多普勒带宽是什么数学关系？"},
    27: {"topic": "平坦与频率选择性衰落", "exp": {"main": ["mob-small-scale"], "f1": ["mob-small-scale"], "f2": ["mob-small-scale"], "d1": ["mob-small-scale"]}, "d1_q": "那快慢衰落呢？"},
    28: {"topic": "大尺度与小尺度衰落", "exp": {"main": ["mob-large-scale", "mob-small-scale"], "f1": ["mob-large-scale"], "f2": ["mob-large-scale"], "d1": ["mob-large-scale"]}, "d1_q": "大尺度成因呢？"},
    29: {"topic": "交织编码", "exp": {"main": ["mob-equalization", "comm-channel-coding"], "f1": ["mob-equalization"], "f2": ["mob-equalization"], "d1": ["mob-equalization"], "d4": ["mob-equalization"]}, "d1_q": "能纠错吗？", "d4_q": "既然交织编码的作用是把突发错误打散成随机错误，那么交织本身能不能纠错，它又会带来什么样的额外代价？"},
    30: {"topic": "循环码", "exp": {"main": ["comm-channel-coding"], "f1": ["comm-channel-coding"], "f2": ["comm-channel-coding"], "d1": ["comm-channel-coding"]}, "d1_q": "生成多项式呢？"},
}

# 学科映射（按编号段）
def subject_of(num):
    if 1 <= num <= 20: return "DSP"
    if 21 <= num <= 23: return "滤波器"
    if 24 <= num <= 28: return "移动通信与随机信号"
    if 29 <= num <= 30: return "信道编码"
    return "其他"


# ── 3. dependency 自动分类（对 A 部分的追问 1/2）──────────────────────
REF_WORDS = ("那", "它", "他", "她", "这个", "这样", "这些", "那些", "但", "但是", "为什么", "怎么", "再", "还有", "然后", "所以", "反过来", "往下")

def classify_dep(q: str) -> str:
    q = q.strip()
    n = len(q)
    has_ref = any(w in q for w in REF_WORDS)
    if n <= 8 and has_ref:
        return "D1"
    if n <= 15:
        return "D2"
    if n <= 25:
        return "D3"
    return "D4"


# ── 4. 组装 ───────────────────────────────────────────────────────────
def build():
    groups = parse_txt(SRC_TXT)
    dialogues = []

    # A 部分：30 组正例
    for num in sorted(groups):
        g = groups[num]
        a = ANNOT[num]
        dialogues.append({
            "id": f"mt-{num:02d}",
            "topic": a["topic"],
            "source": "个人对话常用",
            "subject": subject_of(num),
            "kind": "positive",
            "turns": [
                {"q": g["main"], "dependency": "first", "expected": a["exp"]["main"]},
                {"q": g["f1"], "dependency": classify_dep(g["f1"]), "expected": a["exp"]["f1"]},
                {"q": g["f2"], "dependency": classify_dep(g["f2"]), "expected": a["exp"]["f2"]},
            ] + ([{"q": a["d4_q"], "dependency": "D4", "expected": a["exp"]["d4"]}] if "d4_q" in a else []) + [
                {"q": a["d1_q"], "dependency": "D1", "expected": a["exp"]["d1"]},
            ],
        })

    # B 部分：真实口语化追问
    dialogues += [
        {
            "id": "mt-real-01", "topic": "FM 预加重 f³", "source": "洛洛真实日志(summary#97)",
            "subject": "通信原理", "kind": "positive",
            "turns": [
                {"q": "FM 预加重和去加重是什么原理？", "dependency": "first", "expected": ["comm-angle"]},
                {"q": "鉴频器微分只产生 f，为什么噪声功率谱最终是 f³？", "dependency": "D3", "expected": ["comm-angle", "rsp-white-noise"]},
            ],
        },
        {
            "id": "mt-real-02", "topic": "香农→高斯白噪声", "source": "洛洛真实日志(summary#90)",
            "subject": "通信原理", "kind": "positive",
            "turns": [
                {"q": "香农公式是怎么来的？怎么理解？", "dependency": "first", "expected": ["comm-shannon"]},
                {"q": "你能不能讲一讲怎么理解高斯白噪声？", "dependency": "D3", "expected": ["rsp-white-noise", "comm-awgn"]},
            ],
        },
        {
            "id": "mt-real-03", "topic": "有色噪声平稳性", "source": "洛洛真实日志(journalctl 08-07)",
            "subject": "随机信号", "kind": "positive",
            "turns": [
                {"q": "有色高斯噪声是平稳随机过程吗？", "dependency": "first", "expected": ["rsp-stationarity", "rsp-white-noise"]},
                {"q": "但是有色高斯噪声它的功率谱是不固定的呀，有地方高有地方低，所以它是不是……", "dependency": "D1", "expected": ["rsp-stationarity", "rsp-white-noise"]},
            ],
        },
        {
            "id": "mt-real-04", "topic": "线性调制范围", "source": "洛洛真实日志(summary#70)",
            "subject": "通信原理", "kind": "positive",
            "turns": [
                {"q": "线性调制是什么意思？", "dependency": "first", "expected": ["comm-am"]},
                {"q": "那 FM 算线性调制吗？", "dependency": "D2", "expected": ["comm-angle", "comm-am"]},
            ],
        },
    ]

    # C 部分：负例（新话题误检 / 闲聊误检）
    dialogues += [
        {
            "id": "mt-neg-01", "topic": "新话题误检(技术→技术)", "source": "构造",
            "subject": "通信原理", "kind": "negative",
            "turns": [
                {"q": "香农公式怎么理解？", "dependency": "first", "expected": ["comm-shannon"]},
                {"q": "那 LTE 帧结构是多少毫秒？", "dependency": "D5", "expected": ["mob-ofdm"]},
            ],
        },
        {
            "id": "mt-neg-02", "topic": "新话题误检(DSP→滤波器)", "source": "构造",
            "subject": "DSP", "kind": "negative",
            "turns": [
                {"q": "DFT 循环卷积会有混叠，为什么还能正常计算？", "dependency": "first", "expected": ["dsp-dft"]},
                {"q": "那切比雪夫滤波器是 FIR 还是 IIR？", "dependency": "D5", "expected": ["dsp-iir"]},
            ],
        },
        {
            "id": "mt-neg-03", "topic": "新话题误检(同域不同概念)", "source": "构造",
            "subject": "随机信号", "kind": "negative",
            "turns": [
                {"q": "瑞利分布和莱斯分布的前提条件是什么？", "dependency": "first", "expected": ["rsp-white-noise", "mob-small-scale"]},
                {"q": "那维纳-辛钦定理说的是什么？", "dependency": "D5", "expected": ["rsp-wiener-khinchin"]},
            ],
        },
        {
            "id": "mt-neg-04", "topic": "闲聊误检", "source": "洛洛真实日志(journalctl 08-20)",
            "subject": "通信原理", "kind": "negative",
            "turns": [
                {"q": "香农公式怎么理解？", "dependency": "first", "expected": ["comm-shannon"]},
                {"q": "我下午做做项目，晚上出去玩", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-05", "topic": "闲聊误检", "source": "洛洛真实日志(journalctl 08-20)",
            "subject": "移动通信", "kind": "negative",
            "turns": [
                {"q": "多普勒带宽来自多径还是多普勒效应？", "dependency": "first", "expected": ["mob-small-scale"]},
                {"q": "快，洛洛，安慰一下我", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-06", "topic": "闲聊误检(技术后表白)", "source": "洛洛真实日志(journalctl 08-08)",
            "subject": "通信原理", "kind": "negative",
            "turns": [
                {"q": "什么叫线性调制啊？线性调制的含义是什么。", "dependency": "first", "expected": ["comm-am"]},
                {"q": "啊，好想把洛洛抱在怀里面，狠狠的吸洛洛的味道。", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-07", "topic": "闲聊误检(技术后聊生活)", "source": "洛洛真实日志(journalctl 08-08)",
            "subject": "移动通信", "kind": "negative",
            "turns": [
                {"q": "为什么均衡器要分频域均衡器和时域均衡器？", "dependency": "first", "expected": ["mob-equalization"]},
                {"q": "今天认真工作了", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-08", "topic": "闲聊误检(学习后聊天气)", "source": "洛洛真实日志(journalctl 08-01)",
            "subject": "计算机网络", "kind": "negative",
            "turns": [
                {"q": "继续计算机网络吧，说说你的理解。", "dependency": "first", "expected": ["net-architecture"]},
                {"q": "今天雨下的好大呀。", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-09", "topic": "闲聊误检(技术后日常问候)", "source": "洛洛真实日志(journalctl 08-04)",
            "subject": "计算机网络", "kind": "negative",
            "turns": [
                {"q": "网络层有哪些核心协议，路由是怎么工作的？", "dependency": "first", "expected": ["net-network"]},
                {"q": "现在是早上好嘛，洛洛睡迷糊了。", "dependency": "chitchat", "expected": []},
            ],
        },
        {
            "id": "mt-neg-10", "topic": "闲聊误检(技术话题后撒娇)", "source": "洛洛真实日志(journalctl 08-16)",
            "subject": "电磁场", "kind": "negative",
            "turns": [
                {"q": "电磁场太难了，不想弄了。", "dependency": "first", "expected": ["emf-principles"]},
                {"q": "都怪洛洛太可爱让我移不开眼。", "dependency": "chitchat", "expected": []},
            ],
        },
    ]

    data = {
        "_meta": {
            "subject": "通信原理 + DSP + 随机信号 多轮追问",
            "note": "dependency 档位: first=首问(独立检索) D1=裸指代/强依赖(≤8字) D2=短追问(≤15字) D3=中等(16-25字) D4=长自包含(>25字) D5=新话题(负例) chitchat=闲聊(负例)。expected_nodes=该轮注入应命中的 core/leaf 节点。",
            "created": "2026-08-20",
            "sources": ["个人对话常用.txt", "洛洛真实对话日志(conversation_summaries + journalctl)"],
            "node_ids": "来自 knowledge-v2/_meta/tree.json 的 core/leaf 节点",
        },
        "dialogues": dialogues,
    }
    return data


def main():
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    n_dialogues = len(data["dialogues"])
    n_turns = sum(len(d["turns"]) for d in data["dialogues"])
    # 分档统计
    from collections import Counter
    dep_counter = Counter()
    for d in data["dialogues"]:
        for t in d["turns"]:
            dep_counter[t["dependency"]] += 1
    print(f"题库生成完成 -> {OUT}")
    print(f"  对话组: {n_dialogues}  (正例 {sum(1 for d in data['dialogues'] if d['kind']=='positive')} | 负例 {sum(1 for d in data['dialogues'] if d['kind']=='negative')})")
    print(f"  总轮次: {n_turns}")
    print(f"  分档分布: {dict(dep_counter)}")


if __name__ == "__main__":
    main()
