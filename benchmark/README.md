# benchmark/ — 实验代码

> 本目录包含两代实验：第一代 116 题多模型评测（历史报告与题库存档），以及论文阶段重做的实验代码（检索层对照 + 统计检验 + 答案层评测）。知识库本体在 [`knowledge-v2/`](../knowledge-v2/)。

## 论文线脚本

| 文件 | 作用 | 成本 |
|---|---|---|
| `kb_retrieval_experiment.py` | 检索层四组对照：**A** 无图 / **B** 随机重连图（等边数）/ **C** 真实图 / **D** 等候选预算词面——把「候选预算」这个混淆变量控制住，回答「图扩展的收益是否只是多看了几个节点」「收益是否来自边的语义质量」。指标：gold 召回率 / 全找齐率 / 候选池大小。纯标准库，零 API 成本 | 纯 CPU |
| `stats_test_v3.py` | 对 C−A / C−D / C−B 及严格等预算扫描做配对检验：bootstrap 95% CI + 符号翻转置换检验 + Wilcoxon 符号秩（无 scipy 依赖，可复算） | 纯 CPU |
| [`tools/kb_benchmark.py`](../tools/kb_benchmark.py) | 答案层评测：多模型「裸跑 vs +知识库」，匿名裁判按 rubric（0–4 档 + answer_points 逐点核对）打分。key 从环境变量读取 | 需 API key |

## 运行

```bash
# 检索层主实验（参数见 --help；题库需放在 benchmark/v3/questions_v3_unified.json）
python benchmark/kb_retrieval_experiment.py

# 统计检验（读取 benchmark/v3/ 下的实验产出）
python benchmark/stats_test_v3.py

# 答案层评测（先 export DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / DASHSCOPE_API_KEY）
python tools/kb_benchmark.py --limit 3   # 建议先小样试跑
```

## 数据说明

论文处于投稿评审期，统一题库（v3）与原始实验结果**暂未随仓库发布**：检索层实验可在放入题库后自行复跑，答案层与统计检验的具体数字以论文公开发表为准。
