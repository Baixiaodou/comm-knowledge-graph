# AI 模拟面试 · 专业课训练器（review）

依附于 `comm-knowledge-graph` 树形知识库（knowledge-v2，90 节点）的 **AI 模拟面试** Web 应用（Streamlit）。**只读知识库、不改树结构**，面试会话与判定记录独立存于本地 `data/review.db`（已被 .gitignore 排除，不会推上 GitHub）。

> 2026-09 重构：**删除 benchmark 题库刷题体系**（question_bank/prompts/generator 已移除），
> 改为"依托 RAG 节点原文 + LLM"的问答训练——即模拟研究生复试的专业课面试。
> 功能与数据模型说明见主 README「复习出题插件」章节的历史版本记录（主 README 更新前以本文件为准）。

## 它做什么

| 模块 | 说明 |
|---|---|
| 🎤 模拟面试 | 选科目范围（知识树任意子树）→ 设时长(5/10/15/20 分钟→约 6/10/14/18 题)、追问深度(温和/标准/深挖/压力测试)、点评时机(结束后一起看/每题立即看/只判分不点评) → AI 面试官出题。每轮一次 LLM 调用 = 判定上一答 + 出下一题，逐轮落盘，刷新/换页不丢 |
| 自适应追问 | 答对才在同一知识点往深追一层，答错下探查基础，不硬堆难度；压力测试档会揪住答错的点反诘一轮 |
| 🗺 知识图谱 | 节点颜色 = f(面试历史)：**红=薄弱难点**(一票否决) / 橙·黄·绿=均值 / 灰=未面到；tooltip 显示被问次数 |
| 📋 历史与薄弱 | 场次列表（继续/报告/删除）、单场结业报告、跨场次薄弱知识点聚合（可直接看节点原文补漏） |

**判定纪律**：面试官只依据本轮注入的【候选节点原文】判定（引用原文有据才算对），出题允许学科常识经典问法但判定不越原文，防 AI 外推幻觉。

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env，填入 DEEPSEEK_API_KEY（或 SILICONFLOW_API_KEY）
streamlit run app.py
```

浏览器打开 http://localhost:8501 。

> LLM 默认模型 `deepseek-chat`（官方别名 → v4-flash 非思考模式，JSON 稳定）。
> ⚠️ 若改配 `deepseek-v4-flash` 必须禁用 thinking（见 config.py 注释），否则 high-effort thinking 破坏结构化 JSON。

## 数据模型（v2）

- `interview_sessions`：场次元信息（scope_root / config_json / status / excluded）
- `interview_turns`：逐轮（question / node_ids / user_answer / judgment JSON）
- 旧刷题表（questions / question_nodes / review_records）定义保留以兼容历史 db，新代码不再读写。
- `excluded=1` 的场次不计入图谱掌握度（可在报告下方一键切换）。
