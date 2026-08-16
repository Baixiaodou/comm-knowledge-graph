---
id: mob-duplex
title: 双工方式（FDD/TDD）
parent: mob-networking
depth: 3
type: leaf
summary: FDD 上下行不同频率（需成对频段），TDD 上下行同频率不同时隙，各有权衡
links:
  - id: mob-multiple-access
    relation: "双工（上下行）和多址（多用户）是两个正交维度"
  - id: comm-principles
    relation: "双工本质是资源分配问题，对应通信原理的两个资源（频率/时间）"
created: 2026-08-15
updated: 2026-08-15
---
## 一句话本质

FDD 上下行不同频率（需成对频段），TDD 上下行同频率不同时隙，各有权衡


## FDD vs TDD

| | FDD | TDD |
|--|-----|-----|
| 上下行 | 不同频率 | 同频率、不同时隙 |
| 频段 | 需成对频段 | 不需成对 |
| 特点 | 同时收发 | 时分收发 |

## TDD 的优势与不足

- 优势：信道估计容易（上下行同频互易）、灵活设置不对称带宽、利用零碎频段、不需收发隔离器
- 不足：移动速度受限、覆盖半径小、发射功率受限
