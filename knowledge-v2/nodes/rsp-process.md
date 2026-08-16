---
id: rsp-process
title: 随机过程基础
parent: rsp-principles
depth: 2
type: hub
summary: 随机过程的定义（样本 vs 随机变量两视角）、分类、平稳性、数值特征
links:
  - id: rsp-definition
    relation: "随机过程定义与分类：样本/随机变量两个视角，时间/状态连续离散"
  - id: rsp-stationarity
    relation: "平稳性与各态历经：严平稳/宽平稳/各态历经"
  - id: rsp-statistics
    relation: "数值特征：均值/方差/自相关等一二阶统计量"
  - id: dsp-basics
    relation: "随机过程的统计特性建立在 LTI 系统之上，与信号与系统基础互补"
created: 2026-08-15
updated: 2026-08-15
---

## 一句话本质

随机过程 = 一族随时间演化的随机变量的集合，是随机信号处理的数学基础。

## 为什么需要它

现实信号是随机的、不可精确预测，只能用随机过程这个数学模型来刻画——先理解随机过程，才能研究随机信号。