---
id: net-application
title: 应用层（HTTP/TLS/安全）
parent: net-core
depth: 3
type: core
summary: HTTP 演进（1.1→2→3 解决队头阻塞）、TLS 握手、网络安全（SYN Flood/NAT/VPN）
links:
  - id: net-transport
    relation: "HTTP/1.1、HTTP/2 跑在 TCP 上，HTTP/3 改跑 QUIC（UDP），队头阻塞根源在 TCP 有序字节流"
  - id: net-principles
    relation: "应用层是分层模型的顶层"
  - id: net-network
    relation: "DNS 把域名解析成 IP，供网络层寻址使用"
cot:
  origin: "HTTP 的队头阻塞是怎么一步步被解决的？"
  reasoning: |
    1. HTTP/1.1 管道化：一个请求响应慢，阻塞后面所有响应（HTTP 层队头阻塞）
    2. HTTP/2 多路复用：一个 TCP 连接上并行多路流，解决 HTTP 层队头阻塞
    3. 但 TCP 是有序字节流，一个字节丢包后面全等重传 → 仍有 TCP 层队头阻塞
    4. 根源在 TCP 的"有序字节流"模型 → 弃 TCP 改 UDP 重造传输层（QUIC）
    5. HTTP/3 + QUIC：多路独立流，各流独立重传，根治队头阻塞
  conclusion: "队头阻塞的根源在 TCP 有序字节流，HTTP/2 只能缓解，弃 TCP 用 QUIC（UDP）才能根治"
created: 2026-08-15
updated: 2026-08-18
---

## 一句话本质

应用层提供网络服务，核心是 HTTP 演进（解决队头阻塞）与 TLS 加密、网络安全。

## HTTP 演进（一条链）

- HTTP/1.1：持久连接 + 管道化，但有队头阻塞（一个慢请求阻塞后续）
- HTTP/2：多路复用（一个 TCP 连并行多请求）+ HPACK 压缩 + 服务器推送，解决 HTTP/1.1 队头阻塞，但 TCP 层仍有队头阻塞
- HTTP/3：基于 QUIC（UDP），0-RTT 建连、连接迁移、彻底解决 TCP 层队头阻塞

## TLS 握手

Client Hello → Server Hello → 服务器发证书 → 客户端验证 → 预主密钥（公钥加密）→ 双方算会话密钥 → 加密通信。

## 网络安全

- 基本要素：机密性、完整性、可用性、可鉴别性、不可抵赖性
- SYN Flood：伪造源 IP 大量 SYN 耗尽资源 → 防御用 SYN Cookie
- NAT：静态/动态/NAPT，破坏端到端、需穿透（STUN/TURN/ICE）
- VPN：公用网建安全连接（L2TP/IPSec/MPLS）