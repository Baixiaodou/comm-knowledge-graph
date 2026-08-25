---
id: net-transport
title: 传输层（TCP/UDP）
parent: net-core
depth: 3
type: core
summary: TCP（面向连接、可靠、有流量/拥塞控制）vs UDP（无连接、快），可靠性换速度的权衡
links:
  - id: comm-channel-coding
    relation: "TCP 的可靠传输（确认/重传/序号）就是通信原理 ARQ 在传输层的实现"
  - id: net-data-link
    relation: "传输层与数据链路层都有差错/流量控制，但范围不同（端到端 vs 相邻节点）"
  - id: net-principles
    relation: "传输层是分层的端到端层"
  - id: net-network
    relation: "传输层之下是网络层（主机到主机），传输层补上端口实现进程到进程"
  - id: net-application
    relation: "应用层协议跑在 TCP/UDP 之上（HTTP/DNS 等），传输层是应用层与网络层的中介"
cot:
  origin: "同一份数据要可靠地送到对端，该用 TCP 还是 UDP？"
  reasoning: |
    1. TCP 面向连接：三次握手建立，确认/重传/序号/计时器保证可靠
    2. TCP 有流量控制和拥塞控制（滑动窗口、慢启动）
    3. UDP 无连接、不可靠，但快（无握手、无重传开销）
    4. 权衡：可靠性换速度——TCP 适合可靠性要求高，UDP 适合实时应用
  conclusion: "TCP/UDP = 可靠性与速度的权衡；TCP 用确认重传换可靠，UDP 用不可靠换低延迟"
created: 2026-08-15
updated: 2026-08-18
---

## 一句话本质

TCP（面向连接、可靠、有流量/拥塞控制）vs UDP（无连接、快），是可靠性与速度的权衡。

## TCP vs UDP

| 对比 | TCP | UDP |
|