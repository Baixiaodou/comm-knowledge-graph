# 历史题库归档说明

本目录存放知识库 benchmark 的**历史版本题库与生成脚本**，均已被 `questions_full.json`（116 题完整库）合并取代，仅供追溯演进过程，**不再用于评测**。

## 演进关系

| 文件 | 说明 | 去向 |
|------|------|------|
| `questions_v3.json`（26 题） | 第 3 版题库 | 已并入 full |
| `questions_v5.json`（35 题） | 第 5 版题库 | 已并入 full |
| `questions_v6_node_test.json`（51 题） | v6 节点测试版 | 已并入 full |
| `questions_node_test.json`（50 题） | 节点测试版 | 已并入 full |
| `cross_questions.json`（14 题） | 跨学科题（无读取方，死产物） | 未并入，独立实验 |
| `build_questions.py` | 生成 questions_v3 的脚本 | 一次性工具 |
| `build_cross_questions.py` | 生成 cross_questions 的脚本 | 一次性工具 |

## 当前有效题库（在 `benchmark/` 根目录）

- `questions.json` —— 27 题单轮基础题库（kb_benchmark 默认）
- `questions_full.json` —— **116 题完整题库**（合并全部历史版本，去重 + 修正标注，meta version 11.0）
- `questions_hard.json` —— 15 题反直觉难题集
- `multiturn_questions.json` —— 44 组多轮追问题库

## 备注

- `questions_full.json` 中的 `-2` 后缀 id（如 `L3-comm-02-2`）是历史合并时 id 冲突去重的结果，非笔误。
- 合并是一次性操作（6 版本去重），无自动化脚本——如需重新合并请参考 `docs/06-项目归档总结.md` 的数据清洗记录。
