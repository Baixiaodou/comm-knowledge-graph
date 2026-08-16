---
id: net-network
title: 网络层（IP 与路由）
parent: net-principles
depth: 2
type: leaf
summary: IP 寻址与路由选择，ARP（IP→MAC）/RARP，网络互连设备分层
links:
  - id: net-data-link
    relation: "网络层用 IP 寻址，数据链路层用 MAC 寻址，ARP 是两者的桥梁"
  - id: net-transport
    relation: "网络层之上是传输层（端到端）"
  - id: comm-principles
    relation: "路由与寻址是通信模块化在更大尺度的应用"
created: 2026-08-15
updated: 2026-08-15
---

## 一句话本质

网络层负责跨网段的路由选择与 IP 寻址，核心是"把数据包从源送到目的主机"。

## 网络互连设备分层

| 设备 | 工作层 |
|