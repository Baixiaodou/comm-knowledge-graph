# 节点格式规范 v1.0

每一个知识节点 = 一个 Markdown 文件，放在 `nodes/` 下。文件名 = `{id}.md`。

## Frontmatter 字段

```yaml
---
id: comm-ofdm                    # 唯一标识，kebab-case
title: OFDM                      # 显示名称
parent: comm-modulation          # 父节点 id（根节点 parent 为空）
depth: 3                         # 树深度（根=0）
type: hub                        # leaf | hub | core
summary: 频域分解实现子载波正交    # 一句话摘要（LLM 检索用）

links:                           # Wiki 连接
  - id: dsp-fft
    relation: "FFT是OFDM的数学基础"
  - id: mobile-multipath
    relation: "多径效应是OFDM要解决的核心问题"

cot:                             # 思维链（仅 core 节点）
  origin: "频域分解能否统一解决时域多径？"
  reasoning: |
    1. 时域多径 → 符号间干扰(ISI)
    2. 频域看 → 每个子载波经历的是平坦衰落
    3. 子载波正交 + CP → 将多径的破坏控制在CP内
  conclusion: "OFDM = 频域思维 + 工程实现的桥梁"

created: 2026-08-07              # 创建日期
updated: 2026-08-07              # 最后更新
---
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|:---:|------|
| id | ✅ | 唯一标识，命名规则：`{领域}-{概念}`，e.g. `comm-ofdm` |
| title | ✅ | 显示名称 |
| parent | ✅ | 父节点 id，根节点为空字符串 |
| depth | ✅ | 从根节点算起的深度，根=0，自动计算 |
| type | ✅ | `leaf`=叶子知识 / `hub`=枢纽概念 / `core`=核心节点（有 cot） |
| summary | ✅ | 一句话摘要，供 LLM 检索时快速判断相关性 |
| links | ❌ | Wiki 连接列表，无连接可省略或设为 `[]` |
| cot | ❌ | 思维链，仅 core 节点，其他类型不写此字段 |
| created | ✅ | 创建日期 |
| updated | ✅ | 最后修改日期 |

## type 定义

| 类型 | 含义 | 特征 |
|------|------|------|
| `leaf` | 叶子知识 | 无子节点，无 cot |
| `hub` | 枢纽概念 | 有子节点 或 links 数量 ≥ 3，无 cot |
| `core` | 核心节点 | 有 cot 字段，必选 |

## content 区域规范

frontmatter 之后是正文，用 Markdown：

```markdown
## 核心理解
（你的认知框架，不是知识点的堆砌）

## 关键要点
- 要点1：...
- 要点2：...

## 与我知识体系的关联
- [[dsp-fft]]: （为什么关联）
- [[mobile-multipath]]: （为什么关联）
```

## 文件命名

- 文件名 = `{id}.md`，不是 title
- 所有字母小写，连字符分隔
- 示例：`comm-ofdm.md`、`dsp-fourier-transform.md`

## tree.json 自动生成

`_meta/tree.json` 由脚本从所有节点 frontmatter 自动生成，**不手动编辑**：

```json
{
  "nodes": {
    "comm-ofdm": {
      "title": "OFDM",
      "parent": "comm-modulation",
      "depth": 3,
      "type": "hub",
      "link_count": 2,
      "has_cot": false
    }
  }
}
```
