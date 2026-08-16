---
id: dsp-reconstruction
title: 重建与多采样率
parent: dsp-sampling
depth: 3
type: leaf
summary: 重建是采样的逆过程（sinc插值/ZOH/ADC-DAC链路），外加抽取与内插
links:
  - id: dsp-sampling-theorem
    relation: "采样定理保证可无损恢复，这里给出怎么恢复"
  - id: dsp-filter
    relation: "重建滤波器（抗镜像低通）与 ADC 抗混叠滤波器是采样定理的对称应用"
  - id: dsp-sampling
    relation: "重建是采样的逆过程"
created: 2026-08-14
updated: 2026-08-14
---
## 一句话本质

重建是采样的逆过程（sinc插值/ZOH/ADC-DAC链路），外加抽取与内插


## 核心理解

采样定理只回答了「能无损恢复」，没说「怎么恢复」。**重建是采样的逆过程**。

## 理想重建：sinc 插值

x_a(t) = Σ x(n)·sinc((t-nT)/T)——每个采样点贡献一个 sinc 脉冲，叠加还原原信号。理想 sinc 滤波器物理不可实现（非因果、无限长）。

## 实际 DAC：零阶保持（ZOH）

DAC 输出阶梯状波形（保持每个采样值）。频域等效乘 sinc 函数 → 幅度失真（高频衰减）+ 镜像残留 → 需要**重建低通滤波器**补偿。

## ADC/DAC 完整链路（对称之美）

```
模拟输入 → 抗混叠低通 → 采样保持 → 量化 → 数字信号（ADC）
数字信号 → DAC（零阶保持）→ 重建低通 → 模拟输出（DAC）
```

- ADC 前端**抗混叠**（采样前限带）
- DAC 后端**抗镜像/重建**（采样后滤镜像）
- 采样定理在链路两端的对称应用

## 多采样率处理（抽取与内插）

| 操作 | 频谱变化 | 对策 |
|