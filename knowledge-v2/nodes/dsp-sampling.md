---
id: dsp-sampling
title: 采样与重建
parent: dsp-principles
depth: 2
type: hub
summary: 连续↔离散的桥梁：采样定理、混叠、重建（采样的逆过程）、抽取内插
links:
  - id: dsp-sampling-theorem
    relation: "采样定理：时域/频域一对镜像"
  - id: dsp-reconstruction
    relation: "重建是采样的逆过程，含 ADC/DAC 链路与抽取内插"
  - id: dsp-transforms
    relation: "采样把连续信号数字化，之后一切变换在离散世界展开"
  - id: comm-source-coding
    relation: "通信原理的信源编码采样（PCM）与此同源，奈奎斯特采样是共同的根"
created: 2026-08-14
updated: 2026-08-14
---

## 整体框架

采样是**连接连续世界与离散世界的桥梁**，也是 DSP 的第一性原理。它把连续信号 x_a(t) 变成离散序列 x(n) = x_a(nT)，之后的一切（Z 变换、DTFT、DFT、FFT、滤波器）都在离散世界展开。

## 主线位置

```
连续信号 → ① 采样 → 离散序列 → 变换/滤波 → ② 重建 → 连续信号
```

- **采样**：连续 → 离散（时域乘冲激串 = 频域周期延拓）
- **重建**：离散 → 连续（采样的逆过程，sinc 插值 / ZOH）

## 关键内容

- 三种频率（f / Ω / ω）的关系与归一化
- 混叠（采样率不足，高频伪装成低频）
- 奈奎斯特采样定理（fs ≥ 2fmax）
- 频域采样定理（N ≥ L，时域/频域镜像）
- ADC/DAC 完整链路（抗混叠 → 采样 → 量化 → 数字；数字 → 零阶保持 → 重建滤波）
- 抽取与内插（多采样率处理）

## 关键要点

- 时域采样定理与频域采样定理是**一对镜像**（采样 ↔ 周期延拓）
- ADC 前端抗混叠，DAC 后端抗镜像——采样定理在链路两端的对称应用
