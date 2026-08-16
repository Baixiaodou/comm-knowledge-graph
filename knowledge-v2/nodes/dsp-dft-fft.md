---
id: dsp-dft-fft
title: DFT 与 FFT
parent: dsp-principles
depth: 2
type: hub
summary: DFT 是唯一能计算机实现的傅里叶变换；FFT 是其快速算法（分治/蝶形）
links:
  - id: dsp-dft
    relation: "DFT：隐含周期性、循环卷积、与 DTFT/Z 的关系"
  - id: dsp-fft
    relation: "FFT：旋转因子三性质 + 分治，N²→N·logN"
  - id: dsp-spectrum
    relation: "DFT 是频谱分析的实际工具（加窗/栅栏/分辨率都发生在 DFT 层面）"
  - id: mob-ofdm
    relation: "OFDM 用 IFFT/FFT 调制解调，是 DFT 最成功的工程应用；循环前缀对应循环卷积"
created: 2026-08-14
updated: 2026-08-14
---

## 整体框架

- **DFT**：时域 N 点 ↔ 频域 N 点，是唯一能放进计算机的傅里叶变换（时域频域都离散）
- **FFT**：DFT 的快速算法（不是新变换），利用旋转因子周期性/对称性/可约性，把 N² 次乘法降到 (N/2)log₂N 次

## 关键内容

- DFT 的隐含周期性（= DFS 的主值序列，一切「循环」性质的根源）
- 循环卷积 vs 线性卷积（补零法用 DFT 算线性卷积）
- FFT 的分治思想（奇偶拆分）、蝶形运算、位倒序
- 快速卷积（长序列卷积用 FFT 加速）

## 与其他部分的连接

- DTFT 频域采样 = DFT（N ≥ L 无混叠）
- Z 变换取单位圆 = DTFT，再频域采样 = DFT
- OFDM 是 DFT/FFT 最成功的工程应用（IFFT 调制、FFT 解调、CP 对应循环卷积）

## 关键要点

- DFT 隐含周期性：有限长序列被当成周期序列算（DFS 主值），循环卷积/循环移位都源于此
- FFT 快 200 倍（N=1024），是现代 DSP 的基石
