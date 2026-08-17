# 复习出题插件（review）

> 依附于 `comm-knowledge-graph` 树形知识库的 AI 复习出题插件。**只读知识库、不改树结构**，所有题目与学习记录独立存储。

## 功能

### 模块 1：定向出题
- 首页渲染**全知识图谱**（74 节点 + 树层级 + 跨树 Wiki 连接），节点颜色实时反映掌握程度。
- 选择任意节点（学科主干 / 树枝 / 叶子），自动学习**该节点及其所有子节点**。
- 题目来源：**优先 benchmark 题库**（116 题，已按 `expected_nodes` 绑定节点），题库答完后可 **AI 生成** 简答 / 判断 / 填空。
- 每题绑定 `question_id` + 一个或多个 `source_nodes`，答案解析**只引用节点原文**。
- 交互：点按钮显示答案 → 显示解析 → 自评掌握程度。

### 模块 2：学习状态记录
- 每做一题，把 `(node_id, question_id, user_mastery, last_review_time, review_count)` 写入本地 SQLite。
- 掌握度五档：未复习 / 初步掌握 / 基本掌握 / 完全掌握 / 薄弱难点。
- 可视化规则：**无记录=灰，有「薄弱难点」=红（一票否决），其余按掌握度均值在橙→黄→绿间渐变**；节点 tooltip 显示做题数（复习强度）。
- 支持按节点查看历史记录与整体掌握情况。

## 快速开始

```bash
# 1. 安装依赖（建议用虚拟环境）
pip install -r requirements.txt

# 2. 配置 API key（出题 / 解析需要；不配也能刷 benchmark 题）
cp .env.example .env        # Windows 用 copy .env.example .env
# 填入 DEEPSEEK_API_KEY（或 SILICONFLOW_API_KEY）

# 3. 启动
streamlit run review/app.py
```

浏览器打开后：
1. 左侧下拉框选择学习节点（含其子节点）；
2. 主区图谱会高亮当前子树，逐题作答；
3. 答完自评掌握度，图谱颜色即时刷新。

## 目录结构

```
review/
├── app.py             # Streamlit 入口
├── config.py          # 路径 / 常量 / .env 读取 / LLM 配置
├── db.py              # SQLite 建表与连接
├── knowledge.py       # 读节点 frontmatter、建树、取子树、拼 AI 上下文
├── question_bank.py   # benchmark 导入 + 题库增删查
├── generator.py       # 调用外部 LLM 出题 / 生成解析
├── records.py         # 学习记录 + 掌握度汇总 + 颜色映射
├── graph_viz.py       # ECharts 知识图谱（自生成 HTML，无额外组件依赖）
├── prompts.py         # 出题 / 解析 prompt 模板
├── requirements.txt
├── .env.example
└── data/review.db     # 本地 SQLite（gitignore，不提交）
```

## 数据模型（SQLite）

- `questions`：题库（question_id / type / stem / answer / analysis / source）
- `question_nodes`：题目 ↔ 节点 多对多（综合题绑定多节点）
- `review_records`：学习记录（node_id / question_id / user_mastery / last_review_time / review_count）

## 边界约束

- **不修改原始知识库**：只读 `knowledge-v2/nodes/` 与 `benchmark/`，绝不写回。
- **记录独立存储**：所有题目、学习记录都在 `review/data/review.db`，与知识库解耦。
- **严格绑定 node_id**：每题、每条记录都关联原知识库节点，不能脱离节点独立运行。
- **调用外部 AI**：出题 / 解析走 OpenAI 兼容接口（DeepSeek / SiliconFlow 等），key 走 `.env`，不进仓库。
