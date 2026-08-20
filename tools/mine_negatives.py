# -*- coding: utf-8 -*-
"""从洛洛 8 月真实日志挖「技术问题 → 换话题/闲聊」相邻对，作为负例候选。

输出: source_raw_data/negative_candidates.txt（人工挑选后进 benchmark）
"""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "source_raw_data", "aug_messages.log")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "source_raw_data", "negative_candidates.txt")

TECH = re.compile(r"(FFT|DFT|DTFT|卷积|滤波|采样|混叠|频谱|信号|噪声|带宽|信噪比|衰落|多普勒|瑞利|莱斯|信道|编码|OFDM|调频|FM|AM|DSB|SSB|相位|频域|时域|功率|能量|香农|交织|循环码|频率|调制|解调|正交|MIMO|天线|电磁|傅里叶|拉普拉斯|Z变换|冲激|窗函数|吉布斯|奈奎斯特|抽取|内插|上采样|下采样|采样率|分辨率|线性|因果|稳定|极点|零点|反馈|双线性|预畸变|群时延|码间串扰|幅度|相位失真|FIR|IIR|切比雪夫|巴特沃斯|高斯|随机|包络|相干|多径|直射|反射|路径损耗|生成多项式|纠错|检错|冗余|频谱泄露|栅栏效应|加窗|主瓣|旁瓣|过渡带|计算机网络|OSI|TCP|IP|HTTP|帧结构|LTE|均衡器|智能体|本地部署|GPU|显存|量化|模型)")

def is_noise(t):
    if not t or len(t) > 100:
        return True
    if t.startswith("<faceType"):
        return True
    return False

# 解析日志
msgs = []
with open(SRC, encoding="utf-8", errors="replace") as f:
    for line in f:
        m = re.match(r".*?(\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[INFO\] ai_chat \| 收到消息: (.*)", line)
        if m:
            t = m.group(2).strip()
            if not is_noise(t):
                msgs.append({"ts": "2026-" + m.group(1), "text": t})

# 找相邻对：上一句含技术词，下一句是闲聊/换话题
pairs = []
for i in range(1, len(msgs)):
    prev, cur = msgs[i-1]["text"], msgs[i]["text"]
    if TECH.search(prev) and not TECH.search(cur) and len(cur) <= 40:
        pairs.append((prev, cur, msgs[i]["ts"][:16]))

# 去重 + 输出
seen = set()
lines = []
for prev, cur, ts in pairs:
    key = (prev[:20], cur[:20])
    if key in seen:
        continue
    seen.add(key)
    lines.append(f"[{ts}] {prev}\n  → {cur}\n")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"技术→非技术 相邻对候选: {len(lines)} 条")
print(f"已输出 -> {OUT}")
print("\n=== 前 40 条预览 ===")
for l in lines[:40]:
    print(l)
