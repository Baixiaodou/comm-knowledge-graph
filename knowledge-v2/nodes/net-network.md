---
id: net-network
title: 网络层（IP 与路由）
parent: net-core
depth: 3
type: core
summary: IP 寻址与路由选择，ARP（IP→MAC）/RARP，网络互连设备分层
links:
  - id: net-data-link
    relation: "网络层用 IP 寻址，数据链路层用 MAC 寻址，ARP 是两者的桥梁"
  - id: net-transport
    relation: "网络层之上是传输层（端到端）"
  - id: comm-principles
    relation: "路由与寻址是通信模块化在更大尺度的应用"
  - id: net-architecture
    relation: "网络层是体系结构（OSI/TCP-IP）里承上启下的核心层"
cot:
  origin: "为什么需要 IP 和 MAC 两套地址？跨网段怎么寻址？"
  reasoning: |
    1. 只有 MAC：MAC 是平铺的物理编号，不携带位置信息，全网几亿设备无法据此高效路由（只能全局广播）
    2. 只有 IP：IP 分层可聚合，能靠网络号快速路由到目的网段，但同一网段内最终交付仍需物理寻址
    3. 分工：IP 负责"跨网找到路"，MAC 负责"同网找到人"
    4. 跨网段时：帧的目的 MAC 填网关 MAC，目的 IP 才是最终目标 IP
    5. 转发过程中 MAC 每跳都变，IP 全程不变（链路层逐跳寻址、网络层端到端寻址）
  conclusion: "IP 与 MAC 是分层寻址的分工——IP 跨网路由、MAC 同网交付，ARP 连接两者"
created: 2026-08-15
updated: 2026-08-18
---

## 一句话本质

网络层负责跨网段的路由选择与 IP 寻址，核心是"把数据包从源送到目的主机"。

## 网络互连设备分层

| 设备 | 工作层 |
|