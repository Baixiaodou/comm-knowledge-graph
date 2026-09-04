# 历史实验脚本归档说明

本目录存放评测工具链的**历史实验/分析脚本**，均已被正式工具取代或属一次性分析，仅供追溯方法演进，**不再用于日常评测**。当前有效工具见 `tools/` 根目录。

## 归档清单

| 文件 | 原用途 | 去向 |
|------|------|------|
| `kb_think.py` | 长文本 → 思维骨架（写入 thoughts/） | 一次性整理工具 |
| `analyze_d1_overlap.py` | 分析 need_history 判定与题库 D1 标注的重叠度 | 多轮追问专项分析 |
| `analyze_gain.py` | 分析多轮追问原始结果增益（含硬编码本机路径） | 一次性分析 |
| `analyze_negatives.py` | 负例档（chitchat/D5）误检/偏离详情分析 | 多轮追问专项分析 |
| `mine_negatives.py` | 从真实日志挖「技术问题→闲聊」相邻对作负例候选 | 负例数据挖掘 |
| `test_links_inject.py` | links 三种注入层次对比（关系描述/邻居摘要/邻居全文） | links 研究中间实验 |
| `test_top5_links.py` | top-5+links vs top-10+links 对比 | 检索方案演进实验（→ method F） |
| `test_top34.py` | top-3+links vs top-4+links vs top-10 完整对比 | 检索方案演进实验（→ method F） |
| `validate_multiturn.py` | 校验追问题库 expected_nodes 合法性与分档分布 | 题库校验工具（已被 gen_multiturn_benchmark 的生成-校验流程覆盖） |

> 注：`analyze_*.py` 等脚本内含硬编码本机绝对路径（`RAW = r"D:\..."`），不可直接跨机复现；如需复用请先改为参数化输入。
