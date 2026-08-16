---
id: mob-networking
title: 多址与组网
parent: mob-principles
depth: 2
type: hub
summary: 系统级工程：多址技术解决"多用户共享频谱"，蜂窝组网解决"频率复用"，移动性管理解决"移动中保持连接"
links:
  - id: mob-multiple-access
    relation: "多址技术：FDMA/TDMA/CDMA/OFDMA，解决多用户共享频谱"
  - id: mob-duplex
    relation: "双工方式：FDD/TDD，上下行怎么分"
  - id: mob-cellular
    relation: "蜂窝组网：频率复用 + 区群，解决频谱有限 vs 用户众多"
  - id: mob-mobility
    relation: "移动性管理：切换/位置/功率控制，解决用户移动 vs 连接连续"
created: 2026-08-15
updated: 2026-08-15
---

## 核心理解

信道分析完了、抗衰落技术也有了，剩下的问题是"工程上怎么落地"——怎么服务那么多用户（多址）、怎么高效复用频谱（蜂窝）、怎么在移动中保持连接（移动性管理）。这就是三大矛盾的第二、第三条的解决。

## 三大矛盾的后两条

- 频谱有限 vs 用户众多 → 多址技术 + 蜂窝频率复用
- 用户移动 vs 连接连续 → 越区切换 + 位置管理
