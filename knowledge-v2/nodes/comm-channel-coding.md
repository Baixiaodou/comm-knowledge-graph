---
id: comm-channel-coding
title: 信道编码
parent: comm-digital
depth: 3
type: leaf
summary: 加冗余提供检错纠错，线性分组码/LDPC/卷积码，核心是前向纠错能力
links:
  - id: comm-source-coding
    relation: "对偶：信源编码去冗余（有效性），信道编码加冗余（可靠性）"
  - id: comm-shannon
    relation: "信道编码的目标是逼近香农极限"
  - id: comm-awgn
    relation: "信道编码对抗信道噪声，逼近香农极限"
created: 2026-08-13
updated: 2026-08-13
---
## 一句话本质

加冗余提供检错纠错，线性分组码/LDPC/卷积码，核心是前向纠错能力


## 核心理解

信道编码更偏数学、更偏理论。核心逻辑是**增加冗余**——冗余没带来新信息量，但提供了**检错纠错**的机会。目的：接收方知道传得对不对，能力强甚至能纠错。

## 差错控制方式（四种）

| 方式 | 特点 |
|