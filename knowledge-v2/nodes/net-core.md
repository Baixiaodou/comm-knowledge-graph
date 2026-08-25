---
id: net-core
title: 计网核心机制（分层与封装）
parent: net-principles
depth: 2
type: hub
summary: 计算机网络的核心机制=分层：每层只做一件事、层间靠接口（封装/解封装）协作，OSI 七层 vs TCP/IP 四层是同一思想的两种划分
links:
  - id: net-architecture
    relation: "分层思想的两种落地：OSI 七层 vs TCP/IP 四层"
  - id: net-application
    relation: "应用层：HTTP/TLS 基于传输层服务"
  - id: net-transport
    relation: "传输层：TCP/UDP 在网际层之上提供端到端服务"
  - id: net-network
    relation: "网络层：IP 寻址与路由"
  - id: net-data-link
    relation: "数据链路层：相邻节点间帧传输"
created: 2026-08-26
---
## 一句话本质

计网的核心机制是**分层**：把端到端通信拆成若干层，每层只做一件事，层与层之间通过接口（封装/解封装）协作——OSI 七层与 TCP/IP 四层是同一思想的两种划分方式。

## 核心理解

网络要解决的根本问题是「两台远隔万里的主机如何可靠通信」。直接做成一坨太复杂，分层把问题拆解：

- 每层只对自己的上层负责，向下层要服务；
- 数据自上而下逐层**封装**（加头部），自下而上逐层**解封装**（剥头部）；
- 对等层之间逻辑通信（虚拟通信），实际传输走下层物理通路。

TCP/IP 四层（应用/传输/网际/网络接口）是工程落地，OSI 七层是理论划分——常问「为什么 TCP/IP 活了而 OSI 死了」：分层是思想，不是教条。

## 关键要点

- 分层原则：每层只做一件事，层间接口清晰（封装/解封装）
- 四层 vs 七层：TCP/IP 务实（合并表示/会话层），OSI 理想（分层更细）
- 各层职责：应用层（HTTP/TLS/安全）→ 传输层（TCP/UDP 端到端）→ 网络层（IP 寻址路由）→ 数据链路层（相邻节点帧）
- 核心权衡：可靠性（TCP 重传/拥塞控制）vs 效率（UDP 无状态低延迟）；分层带来性能开销 vs 工程可维护性
