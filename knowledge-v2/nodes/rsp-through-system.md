---
id: rsp-through-system
title: 随机信号通过系统
parent: rsp-principles
depth: 2
type: hub
summary: 随机过程过 LTI 系统后统计特性怎么变：输出功率谱 = |H(f)|²·S_X(f)，白噪声经滤波器变有色噪声
links:
  - id: rsp-lti
    relation: "通过 LTI 系统：均值卷积、自相关卷积、功率谱 |H|² 加权"
  - id: rsp-white-noise
    relation: "白噪声与窄带高斯：白噪声过滤波器变有色噪声"
  - id: rsp-estimation
    relation: "功率谱估计：周期图/BT/无偏/一致估计"
  - id: dsp-basics
    relation: "随机过程过系统仍满足 LTI 的卷积关系，用信号与系统工具分析"
created: 2026-08-15
updated: 2026-08-15
---

## 一句话本质

随机信号过 LTI 系统，输出仍是随机过程，但统计特性按 |H(f)|² 加权缩放——这是随机信号处理落地到通信/滤波的关键。
