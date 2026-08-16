---
id: comm-multiplexing
title: 复用与多载波
parent: comm-digital
depth: 3
type: core
summary: 复用与多址：在频/时/码/正交子载波维度分割信道给多用户，OFDM 是其核心代表（详见 mob-ofdm 权威节点）
links:
  - id: comm-rf-mod
    relation: "复用处理之后才进入射频调制"
  - id: comm-receiver
    relation: "解复用是接收端逆过程"
  - id: comm-isi
    relation: "复用（如 OFDM）是抗多径 ISI 的方式之一，与均衡器互补"
  - id: mob-ofdm
    relation: "OFDM 的完整内容（原理/CP/PAPR）在移动通信树的权威节点，这里只讲复用视角"
cot:
  origin: "频谱有限、用户众多，怎么让多个信号共享同一条信道？"
  reasoning: |
    1. 核心思想：把信道资源在多个维度上分割，每个用户占一个子空间
    2. 频域分：FDMA（各占频段，需保护带）
    3. 时域分：TDMA（各占时隙，需同步）
    4. 码域分：CDMA（正交码，同频同时）
    5. 正交子载波分：OFDMA（子载波重叠但正交，频谱利用率最高）
    6. 越往后分割越精细、频谱利用率越高，但实现越复杂
  conclusion: "复用 = 把信道在频/时/码/正交子载波维度分割；OFDM 是频域复用的极致（详见 mob-ofdm）"
created: 2026-08-13
updated: 2026-08-15
---

## 一句话本质

复用与多址 = 把信道资源在频/时/码/正交子载波维度分割给多用户，OFDM 是频域复用的极致。

## 为什么需要它

频谱有限、用户众多，还要让高速数据适应信道——复用让多用户共享信道、多载波让高速转低速。

## 关键结论

- 复用维度：频域（FDMA）、时域（TDMA）、码域（CDMA）、正交子载波（OFDMA）
- 越往后分割越精细、频谱利用率越高，但实现越复杂
- OFDM 完整原理 → [[mob-ofdm]] 权威节点
- 多址完整对比 → [[mob-multiple-access]] 权威节点

## 关联

- [[comm-rf-mod]]：复用处理后进入射频调制
