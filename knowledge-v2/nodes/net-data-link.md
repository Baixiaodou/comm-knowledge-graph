---
id: net-data-link
title: 数据链路层
parent: net-principles
depth: 2
type: leaf
summary: CSMA/CD（有线以太网）vs CSMA/CA（无线），差错控制（ARQ/FEC），VLAN 划分广播域
links:
  - id: comm-channel-coding
    relation: "数据链路层的差错控制（ARQ/FEC）与通信原理的信道编码同源"
  - id: mob-multiple-access
    relation: "CSMA/CD 是局域网的多址接入（竞争式），与移动通信的多址（分配式）形成对照"
created: 2026-08-15
updated: 2026-08-15
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