---
id: mob-anti-fading
title: 抗衰落技术
parent: mob-principles
depth: 2
type: hub
summary: 针对信道破坏的对策全景：分集/均衡/交织/扩频/OFDM/MIMO，每种对应一类信道问题
links:
  - id: mob-diversity
    relation: "分集：多个独立衰落信号合并，对抗快衰落（统计择优）"
  - id: mob-equalization
    relation: "均衡与交织：事后补偿 ISI + 分散突发错误"
  - id: mob-spread-spectrum
    relation: "扩频/CDMA：香农逆用，带宽换信噪比，抗干扰抗截获"
  - id: mob-ofdm
    relation: "OFDM：高速→低速正交子载波，把频率选择性变平坦"
  - id: mob-mimo
    relation: "MIMO：多天线，空间维度换速率/可靠性/增益"
  - id: mob-channel
    relation: "每种抗衰落技术都对应信道的一种破坏（问题→对策映射）"
created: 2026-08-15
updated: 2026-08-15
---

## 技术全景（问题 → 对策）

| 信道的破坏 | 抗衰落技术 |
|-----------|-----------|
| 阴影效应（慢衰落） | 衰落储备、小区规划 |
| 多径 → ISI | 均衡器（事后补偿）、OFDM、分集 |
| 多普勒（快衰落） | 频谱补偿、短符号、分集 |
| 远近效应 | 功率控制 |
| 通用（加冗余） | 信道编码、交织 |
| 干扰/截获 | 扩频 |

## 核心逻辑

理解这部分的钥匙是"问题→对策"映射：每一种技术都不是凭空来的，都是针对信道的某一种破坏设计的。反过来说，理解信道就能理解为什么要这些技术。
