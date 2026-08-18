# 复习出题插件（review）

依附于 `comm-knowledge-graph` 树形知识库的 AI 复习出题插件（Streamlit Web）。**只读知识库、不改树结构**，题目与学习记录独立存储。

> 完整的功能说明、数据模型、边界约束与后续规划见主 README 的「复习出题插件」章节 → [../README.md](../README.md)

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env，填入 DEEPSEEK_API_KEY（或 SILICONFLOW_API_KEY）
streamlit run app.py
```

浏览器打开 http://localhost:8501 。

> ⚠️ 当前为初版（MVP）。
