---
id: rsp-detection-estimation
title: 信号检测与估计
parent: rsp-principles
depth: 2
type: hub
summary: 从被噪声污染的信号中提取/恢复信息：信号检测（似然比+6准则）+ 参数估计（5准则+克拉美罗界）+ 波形滤波（维纳/卡尔曼）
links:
  - id: rsp-detection
    relation: "信号检测：似然比检测 + 6 准则 + 判决概率"
  - id: rsp-parameter-estimation
    relation: "参数估计与滤波：5 准则 + 克拉美罗界 + 维纳/卡尔曼"
  - id: rsp-white-noise
    relation: "检测估计建立在噪声的统计模型（高斯白/色噪声）之上"
  - id: comm-receiver
    relation: "匹配滤波器是信号检测在通信接收端的应用"
created: 2026-08-15
updated: 2026-08-15
---

## 一句话本质

信号检测与估计 = 用贝叶斯统计（统计决策理论）从噪声污染的信号中提取、恢复信息，是随机信号处理的直接应用。
