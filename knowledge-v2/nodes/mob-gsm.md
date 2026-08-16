---
id: mob-gsm
title: GSM 系统（2G）
parent: mob-systems
depth: 3
type: leaf
summary: 第一代数字蜂窝：TDMA 帧结构（帧→时隙→复帧）、功能实体（HLR/VLR/MSC）、鉴权加密
links:
  - id: mob-multiple-access
    relation: "GSM 采用 TDMA（时分多址）"
  - id: mob-systems
    relation: "GSM 是 2G 代表，第一代数字蜂窝系统"
created: 2026-08-15
updated: 2026-08-15
---
## 一句话本质

第一代数字蜂窝：TDMA 帧结构（帧→时隙→复帧）、功能实体（HLR/VLR/MSC）、鉴权加密


## 帧结构

帧 → 时隙 → 复帧 → 超帧 → 超高帧，每帧含 8 个时隙。

## 功能实体

- HLR（归属位置寄存器）：中央数据库，存储用户参数和状态
- VLR（访问位置寄存器）：存储漫游用户信息
- MSC（移动交换中心）：交换 + 移动管理
- BSC（基站控制器）：控制 BTS、话务集中
- BTS（基站收发台）
- AUC（鉴权中心）：存储 RAND/SRES/Kc 三参数
- SIM 卡：存储用户个人信息和网络管理信息

## 鉴权与加密

鉴权：MSC/VLR 发 RAND 给移动台 → SIM 卡用 RAND+Ki 经 A3 算法得 SRES → 传回网络比对。三参数组：RAND（随机数）、SRES（响应）、Kc（密钥）。加密用 A5 算法 + Kc。

## 其他技术

交织（抗突发错误）、跳频（改善多径误码）、DTX 语音间断传输（降低干扰省电）、分集。
