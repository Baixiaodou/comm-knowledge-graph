---
id: net-architecture
title: 网络体系结构
parent: net-principles
depth: 2
type: core
summary: OSI 七层 vs TCP/IP 四层，LLC/MAC 子层划分，证实性 vs 非证实性服务
links:
  - id: net-data-link
    relation: "LLC/MAC 是数据链路层的两个子层"
  - id: net-network
    relation: "网络层是体系结构的核心层"
  - id: net-transport
    relation: "传输层是体系结构里唯一端到端的层"
  - id: net-principles
    relation: "体系结构是分层思想（net-principles 的 cot）的落地"
cot:
  origin: "为什么 TCP/IP 四层成为事实标准，而 OSI 七层只用于教学？"
  reasoning: |
    1. OSI 先有理论后有实现，表示层/会话层划分过细，实际由应用自己完成，臃肿低效
    2. TCP/IP 先有实现后有理论，从 ARPANET 真实需求长出，四层刚好够用
    3. 简洁、能用的 TCP/IP 战胜了完备、复杂的 OSI
    4. 但 OSI 概念边界清晰，仍用于教学分析（说"七层""表示层"用的是 OSI 术语）
  conclusion: "OSI 用于教学（概念完备）、TCP/IP 用于运行（简洁可用）——先实现后理论的赢了先理论后实现的"
created: 2026-08-15
updated: 2026-08-18
---

## 一句话本质

网络体系结构 = OSI 七层 vs TCP/IP 四层的分层模型，TCP/IP 是事实标准（更简单）。

## OSI 七层 vs TCP/IP 四层

| OSI 七层 | TCP/IP 四层 |
|