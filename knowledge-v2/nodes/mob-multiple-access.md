---
id: mob-multiple-access
title: 多址技术
parent: mob-networking
depth: 3
type: leaf
summary: 多址技术权威节点：FDMA/TDMA/CDMA/OFDMA 对比，在频/时/码/正交子载波维度分割频谱给多用户
links:
  - id: comm-multiplexing
    relation: "多址是多用户的复用，通信原理的复用多载波是它的理论框架（详见这里）"
  - id: mob-spread-spectrum
    relation: "CDMA 是扩频在码分多址的应用"
  - id: mob-duplex
    relation: "多址解决多用户，双工解决上下行，两者是正交的两个维度"
created: 2026-08-15
updated: 2026-08-15
---
## 一句话本质

多址技术权威节点：FDMA/TDMA/CDMA/OFDMA 对比，在频/时/码/正交子载波维度分割频谱给多用户


## 节点定位（权威节点）

多址技术在通信原理（复用多载波）和移动通信两棵树都出现，这里统一收敛：完整的多址对比（FDMA/TDMA/CDMA/OFDMA）+ 演进历程，检索时两棵树都指向本节点。

## 多址技术对比（完整）

| 多址 | 维度 | 特点 | 缺点 |
|------|------|------|------|
| FDMA | 频域 | 各用户占不同频段 | 需保护带，频谱利用率低 |
| TDMA | 时域 | 各用户占不同时隙 | 需同步 |
| CDMA | 码域 | 正交码，同频同时多用户 | 功率控制难，易互相干扰 |
| OFDMA | 正交子载波 | 子载波重叠但正交，利用率最高 | PAPR 高 |

- 上行多用 SC-FDMA（单载波 FDMA）降低 PAPR（手机端功率受限）

## 演进历程

| 代 | 多址 | 维度 |
|----|------|------|
| 1G（模拟） | FDMA | 频域分 |
| 2G | TDMA（GSM） | 时域分 |
| 3G | CDMA | 码域分 |
| 4G/5G | OFDMA | 正交子载波分 |

## 核心理解

多址技术解决"多个用户怎么共同用同一段频谱"。不同的分割维度：频域（FDMA）、时域（TDMA）、码域（CDMA）、正交子载波（OFDMA）。越往后频谱利用率越高，但也越复杂。

## CDMA 的特点

给每用户一个正交码型，同频、同时间、多用户共存。这是它相对 FDMA/TDMA 的核心优势（不用分频/分时）。
