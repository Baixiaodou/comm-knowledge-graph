---
id: rsp-autocorrelation
title: 自相关函数
parent: rsp-correlation
depth: 3
type: leaf
summary: 信号和自己延迟副本的相似程度，性质：偶函数、R(0)最大、白噪声自相关=δ
links:
  - id: rsp-wiener-khinchin
    relation: "自相关是维纳-辛钦的入口（自相关↔功率谱）"
  - id: comm-awgn
    relation: "白噪声的自相关是 δ 函数，正是 AWGN 不相关的统计基础"
  - id: rsp-lti
    relation: "自相关函数通过系统后的变化见 LTI 节点"
created: 2026-08-15
updated: 2026-08-15
---

## 一句话本质

自相关函数 = 信号和它自己延迟副本的相似程度，是刻画随机信号最重要的二阶统计量。

## 核心性质

- 偶函数：R(τ) = R(-τ)
- 峰值在原点：|R(τ)| ≤ R(0)（R(0) = 均方值，最大）
- 周期函数的自相关同周期
- 白噪声自相关 = δ 函数（只在 τ=0 处非零，不同时刻不相关）

## 为什么重要

随机信号本身不可做傅里叶变换，但自相关是确定函数、可做傅里叶变换 → 维纳-辛钦把它连到功率谱，自相关就成了随机信号频域分析的入口。