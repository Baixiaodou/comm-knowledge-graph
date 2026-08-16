---
id: dsp-fft
title: FFT（快速傅里叶变换）
parent: dsp-dft-fft
depth: 3
type: core
summary: DFT 的快速算法：旋转因子三性质 + 奇偶分治，N²→(N/2)log₂N，蝶形运算
links:
  - id: dsp-dft
    relation: "FFT 算的就是 DFT，结果完全一样，只是快"
  - id: comm-multiplexing
    relation: "OFDM 调制用 IFFT、解调用 FFT，是 FFT 最成功的工程应用"
  - id: dsp-spectrum
    relation: "FFT 是频谱分析的计算工具"
  - id: mob-ofdm
    relation: "OFDM 用 IFFT/FFT 实现调制解调"
cot:
  origin: "N 点 DFT 要 N² 次乘法，N=1024 时 100 万次，怎么提速？"
  reasoning: |
    1. 直接 DFT：每个 X(k) 要 N 次乘法，N 个 X(k) 共 N² 次——实时处理做不到
    2. 旋转因子 W_N = e^(-j2π/N) 有三个性质：周期性（W^(k+N)=W^k）、对称性（W^(k+N/2)=-W^k）、可约性（W^(2k)=W_(N/2)^k）
    3. 利用性质做分治：N 点 DFT 拆成两个 N/2 点（奇偶分组），组合只需 N 次——几乎省一半
    4. 递归拆分直到 2 点 DFT（不需乘法），共 log₂N 层，每层 N/2 个蝶形
    5. 蝶形 = 1 次复数乘 + 2 次复数加，是 FFT 的最小单元
  conclusion: "FFT = 分治 + 复用旋转因子性质，把 N² 降到 (N/2)log₂N，N=1024 快 200 倍，是现代 DSP 基石"
created: 2026-08-14
updated: 2026-08-14
---

## 一句话本质

FFT 不是新变换，是 DFT 的快速算法：分治 + 复用旋转因子性质，把 N² 降到 (N/2)log₂N。

## 为什么需要它

直接 DFT 要 N² 次乘法，N=1024 时 100 万次，实时处理做不到 → 必须提速。

## 核心机制（一条链）

旋转因子三性质（周期/对称/可约）→ 奇偶分治（N 点拆两 N/2 点）→ 递归到 2 点 DFT → log₂N 层 × N/2 蝶形 → (N/2)log₂N

## 关键结论（面试必答）

- 旋转因子 W_N=e^(-j2π/N)：周期性 W^(k+N)=W^k、对称性 W^(k+N/2)=-W^k、可约性 W^(2k)=W_(N/2)^k
- 一个蝶形 = 1 次复数乘 + 2 次复数加
- N=1024 快 200 倍，N=4096 快 700 倍（N 越大优势越明显）
- 工程应用：OFDM 调制解调（IFFT/FFT，详见 [[mob-ofdm]]）、频谱分析、快速卷积
