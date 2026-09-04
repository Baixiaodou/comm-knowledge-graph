# AI 模拟面试 · 专业课训练器（review）

依附于 `comm-knowledge-graph` 树形知识库（knowledge-v2，90 节点）的 **AI 模拟面试** Web 应用（Streamlit）。**只读知识库、不改树结构**，面试会话与判定记录独立存于本地 `data/review.db`（已被 .gitignore 排除，不会推上 GitHub）。

> 2026-09 重构：**删除 benchmark 题库刷题体系**（question_bank/prompts/generator 已移除），
> 改为"依托 RAG 节点原文 + LLM"的问答训练——即模拟研究生复试的专业课面试，
> 并叠加三层 agent 化能力（跨场次记忆闭环 / 判定校准官 / 面试官风格），见下文。
> 2026-09-04 迭代：**判定改要点覆盖率制（防口语化答对被压"部分正确"）+ score 0~100 连续分评级**；
> 界面改**单页导航**（答题页不堆设置表单，图谱按需加载）、答题输入框随题号自动清空、判定即时展示得分与参考答案。
> ⚠️ 主 README「复习出题插件」章节仍为旧版历史记录，更新前以本文件为准。

## 它做什么

| 模块 | 说明 |
|---|---|
| 🎤 模拟面试 | 选科目范围（知识树任意子树）→ 设时长(5/10/15/20 分钟→约 6/10/14/18 题)、追问深度(温和/标准/深挖/压力测试)、面试官风格(温和引导/学院派严谨/压力测试)、点评时机(结束后一起看/每题立即看/只判分不点评) → AI 面试官出题。每轮一次 LLM 调用 = 判定上一答 + 出下一题，逐轮落盘，刷新/换页不丢 |
| 自适应追问 | 答对才在同一知识点往深追一层，答错下探查基础，不硬堆难度 |
| 🧠 薄弱点闭环 | 开场可选「优先复测上次面试答错的知识点」（默认开）：跨场次聚合历史 wrong/unanswered/offtopic 节点，排到本场候选最前，答错的点下次见面再测 |
| 🔎 判定校准官 | 结束后可对整场记录发起**第二个 LLM 视角**复审（严格挑刺）：逐题给出改判建议（verdict_review）、考生画像、复习计划（≤5 节点带 why/how）。同一场只生成一次，重复点击不重复扣费 |
| 🗺 知识图谱 | 节点颜色 = f(面试历史)：**红=薄弱难点**(一票否决) / 橙·黄·绿=均值 / 灰=未面到；tooltip 显示被问次数 |
| 📋 历史与薄弱 | 场次列表（继续/报告/删除/排除出统计）、单场结业报告、跨场次薄弱知识点聚合（可直接看节点原文补漏） |

**判定纪律**：面试官只依据本轮注入的【候选节点原文】判定（引用原文有据才算对），出题允许学科常识经典问法但判定不越原文，防 AI 外推幻觉。判定五档：答对 / 部分正确 / 答错 / 未答上 / 跑题。

**两个维度的"压力测试"别混淆**：追问深度里的「压力测试」= 深挖 + 反诘 + 边界（答对也追，考应变）；面试官风格里的「压力测试」= 刁钻导师语气（答错揪住不放）。深度管"问到哪一层"，风格管"怎么问"，二者正交。

## Agent 化：本应用是怎么"轻量 agent"的

单 LLM + 状态 + 决策循环，不引入 agent 框架：

1. **判定与出题合一**（每轮 1 次调用）：一次 LLM 调用内先复盘上一答（内部笔记存于判定 JSON），再基于候选知识点原文出下一题——比"先判再出"的两段式省一半调用，且笔记跨轮保留在 prompt 里形成记忆链。
2. **跨场次记忆**（零额外调用）：开场时从 SQLite 聚合历史薄弱节点并前置，面试官 system prompt 会看到"该考生曾在 XX 知识点答错 N 次"，同一批弱点跨场次自动复测。
3. **判定校准官**（每场仅 +1 调用，带缓存）：面试官"当局者迷"时由第二 LLM 用严格标准复核。图谱掌握度仍以面试官判定为准，评审官是诊断参考，不影响主数据。

## 界面与交互（2026-09-04 精简版）

- **单页导航**（顶部 radio，非 st.tabs）：只渲染当前视图——答题页始终轻快，知识图谱（内嵌 ~1MB echarts）**点开才加载**，消除整页卡顿。
- **专注答题视图**：面试进行中该页只显示答题区（题号进度条 → 问题 → 输入框 → 提交/跳过/结束），不混入设置表单；本场结束自动回到设置页。
- 输入框 key 绑定题号，提交后**必然清空**（换身份而非删状态）；答题中切页再回来，未提交的草稿保留。
- 即时反馈（非「结束后一起看」模式）：判定徽章 + **得分** + 点评 + 参考答案要点（轻量文本）。

## 运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 http://localhost:8501 ，首次使用在**左侧栏「🔑 API 配置」**粘贴 API Key 保存即可（见下），无需手动编辑文件。

### 配置 API Key（两种方式，任选）

| 方式 | 说明 |
|---|---|
| 🖥 页面配置（推荐） | 应用左侧栏常驻「🔑 API 配置」面板：粘贴 key，可选填 base_url / 模型名（高级选项）。保存即写入 `review/.env` 并**当场生效，无需重启**；页面只显示掩码 `sk-xxx…xxxx`，绝不回显完整 key |
| 📄 文件配置 | `cp .env.example .env`（Windows: `copy .env.example .env`），填入 `DEEPSEEK_API_KEY`（或 `SILICONFLOW_API_KEY`）后重启 |

安全：`.env` 已被 .gitignore 排除，不会提交 GitHub；优先读取 `review/.env`，其次兜底复用知识库根 `tools/.env` 的共享 key（不覆盖已有值）。

### LLM 提供商

- 配 `DEEPSEEK_API_KEY` → base `https://api.deepseek.com`，默认模型 `deepseek-chat`（官方别名 → v4-flash 非思考模式，JSON 输出稳定）。
- 只配 `SILICONFLOW_API_KEY` → base `https://api.siliconflow.cn/v1`，默认模型 `Qwen/Qwen3-32B`。
- 默认模型可用环境变量 `REVIEW_MODEL` 覆盖，接口地址用 `REVIEW_BASE_URL` 覆盖。

> ⚠️ 若改配 `deepseek-v4-flash` 必须禁用 thinking（见 config.py 注释），否则 high-effort thinking 破坏结构化 JSON 出题/判定。

### 调用成本（一次完整面试）

- 面试过程：每轮 1 次调用 → 6~18 次（判定 + 出题合一）。
- 本地报告（统计 / 逐题 / 薄弱清单 / 评级）：0 额外调用，纯本地聚合。
- 评审官诊断：单场仅 +1 次调用，同场重复点击读缓存不重复扣费。

## 数据模型（v2）

- `interview_sessions`：场次元信息（scope_root / config_json / status / excluded）
- `interview_turns`：逐轮（question / node_ids / user_answer / judgment JSON）
- `interview_reviews`：判定校准官结果（一场一条：verdict_review / portrait / plan / next_suggestion）
- 旧刷题表（questions / question_nodes / review_records）定义保留以兼容历史 db，新代码不再读写。
- `excluded=1` 的场次不计入图谱掌握度（可在报告下方一键切换）。

## 文件结构

```
review/
├── app.py                # Streamlit UI（3 视图单页导航 + 侧栏 API 配置）
├── config.py             # 路径/档位常量 + LLM 配置读取与安全落盘
├── interview.py          # 面试引擎（纯逻辑，可单测）：会话 CRUD / 出题判定 / 评审官 / 薄弱聚合
├── prompts_interview.py  # 面试官 system/user prompt（深度 × 风格指令）
├── prompts_reviewer.py   # 判定校准官 prompt
├── records.py            # 面试驱动的图谱掌握度聚合与颜色映射
├── knowledge.py          # 知识库节点加载（只读 knowledge-v2/nodes）
├── graph_viz.py          # 图谱渲染（ECharts）
├── db.py                 # SQLite schema + 连接
├── .env.example          # key 配置模板（.env 不入库）
└── static/echarts.min.js # 本地化图表库
```
