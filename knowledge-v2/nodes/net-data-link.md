---
id: net-data-link
title: 数据链路层
parent: net-principles
depth: 2
type: core
summary: CSMA/CD（有线以太网）vs CSMA/CA（无线），差错控制（ARQ/FEC），VLAN 划分广播域
links:
  - id: comm-channel-coding
    relation: "数据链路层的差错控制（ARQ/FEC）与通信原理的信道编码同源"
  - id: mob-multiple-access
    relation: "CSMA/CD 是局域网的多址接入（竞争式），与移动通信的多址（分配式）形成对照"
  - id: comm-multiplexing
    relation: "复用（静态分信道）与多址（动态抢信道）的区别：物理层只管分，链路层管谁怎么接入"
  - id: net-network
    relation: "链路层用 MAC 寻址（本网段），网络层用 IP 寻址（跨网段），ARP 是桥梁"
  - id: net-transport
    relation: "链路层与传输层都有差错/流量控制，但范围不同（相邻节点 vs 端到端）"
cot:
  origin: "为什么有线以太网用 CSMA/CD，无线 WiFi 用 CSMA/CA？"
  reasoning: |
    1. 多台设备共享一条信道 → 需要介质访问控制（谁发、何时发）
    2. 有线（以太网）能全双工、能"边发边听"→ 碰撞发生后能立即检测 → 用 CD（碰撞检测）
    3. 无线无法"边发边听"（发送时本机高功率信号淹没远端回波）→ 检测不到碰撞 → 只能 CA（碰撞避免）
    4. 无线还有隐藏终端（A、C 互不可见）→ 用 RTS/CTS 预约解决
    5. 本质：能不能"边发边听"决定了 CD 还是 CA
  conclusion: "有线能检测所以 CD（撞了再处理），无线检测不了所以 CA（事先预约避免）"
created: 2026-08-15
updated: 2026-08-18
---

## 一句话本质

数据链路层负责相邻节点的帧传输：介质访问控制（CSMA/CD/CA）+ 差错控制（ARQ/FEC）。

## 介质访问控制

- CSMA/CD（有线以太网）：先听后发、边发边听、冲突停发、随机重发，二进制指数退避
- CSMA/CA（无线局域网）：无法边发边听，采用冲突避免、虚拟载波侦听（NAV）、随机退避
- 隐藏终端问题（A、B 互相听不到）→ RTS/CTS 握手解决

## 差错控制

| 方式 | 特点 |
|------|------|
| 检错重发（ARQ） | 检出错误请求重发 |
| 前向纠错（FEC） | 接收端直接纠错 |
| 反馈校验 | 发回发送端比对 |
| 检错丢弃 | 检出直接丢弃 |

## 其他

- VLAN：逻辑分割广播域（基于端口/MAC/协议）
- 二进制指数退避：第 n 次碰撞后随机等 [0, 2^min(n,10)-1]，16 次放弃