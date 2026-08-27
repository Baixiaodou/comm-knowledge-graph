---
name: kb-ingest
description: 把用户提供的 Word/txt 文档或一段文字按本仓库 RAG 规范吸收进 knowledge-v2 知识库（分流判定 → 成文 → 收尾管线）。当用户要求"吸收/整理文档进知识库"、"把这份讲义做成节点"、"补充知识点"时使用。
---

# kb-ingest · 文档吸收操作规程

把一篇外部资料整理成符合本仓库规范的知识库增量。全程与人协作：先判定、后动笔、必过闸门。

## 第 0 步：建立上下文

1. 通读 [`knowledge-v2/_meta/node-spec.md`](../../knowledge-v2/_meta/node-spec.md)：frontmatter 十字段与 leaf/hub/core 判定铁律；
2. 读仓库 README 的「结论式写法」章节：五段式正文模板；
3. 抽读 1 个现有节点感受文风（推荐 `nodes/comm-awgn.md`：summary = 正文首句、逐词拆解小节）；
4. 摸清库里已有什么：列出 `knowledge-v2/nodes/*.md` 全部节点的 id / title / type / summary（可对节点文件批量 Grep frontmatter 字段），这是后面判定的对照物。七棵主题树前缀：`math / comm / dsp / mob / rsp / emf / net`。

## 第 1 步：分流判定（只判定，不落盘）

把输入切成合理段落（docx 有标题样式按样式切；纯文本按标题行正则或语义分段），对每段的候选知识点**四选一**：

| 判定 | 条件 | 后续动作 |
|------|------|----------|
| `merge_into` | 库中某节点已实质覆盖该内容 | 为该节点拟「追加小节或仅补 links」，不新建文件 |
| `attach` | 相关但未被覆盖 | 在某个现有节点下新建子节点 |
| `new_node` | 所属课程树内的新知识点 | 新建节点，parent 指向该树合适层级 |
| `new_tree` | 与七棵树全无关系的全新主题 | 建 `{prefix}-principles` 课程根 + 子节点；**前缀需用户认可** |

判定结果先以表格呈现给用户（每行含判定、目标节点/父节点、一句理由），**等用户确认后再进入第 2 步**——审核就是这场对话本身，用户可直接改判（"这条不对，并进 XX"）。用户若要求拓展视野，可联网搜索相关主题下文档未覆盖的内容，同样列建议征求选择。

## 第 2 步：成文

**新建节点**（attach / new_node / new_tree）：

- frontmatter 必填八项：`id / title / parent / depth / type / summary / created / updated`（id 用 `{树前缀}-{kebab-case}`，depth = 父 depth + 1，日期填当天）；`links` 与 `cot` 为可选字段（cot 仅 core 节点，写了 cot 就必须是 core）；
- 正文首选新五段式：`一句话本质 → 为什么需要它 → 核心机制（一条链，用 →）→ 关键结论 → 代价与权衡`（node-spec v1.1 起写入正式规范；现有库约 75 个节点已成此风）。三节式（核心理解 / 关键要点 / 与我知识体系的关联）为历史模板，仅存量 hub 可见，新节点不再使用；结尾常以 `[[wiki链接]]：一句话说明` 收束；
- **links 目标白名单**：link 的 id 只能是「现有节点 ∪ 本批新建」（否则 lint 报 broken link）。relation **不设固定词表**，写一句话语义描述（参照 spec 示例风格：『FFT 是 OFDM 的数学基础』『多径效应是 OFDM 要解决的核心问题』），偶配对偶 / 对比 / 同源等短词亦可——全库 300+ 条 relation 以自由描述为主体；
- `summary` = 正文第一句话原样复制（全库惯例）；
- 若出现 `new_tree`：除建课程根外，还要在根节点 `nodes/root.md` 的 links 里补一条指向 `{prefix}-principles` 的 relation（参照七棵树既有写法），保持领域层互联完整。

**并入节点**（merge_into）：向用户展示拟追加的小节文本与新增 links，确认后直接修改正式节点文件：正文末尾（或合适章节后）追加小节、frontmatter 合入新 links、`updated` 改为当天；不动已有正文，`summary` 不变（除非实质改变定位且用户同意）。

## 第 3 步：收尾管线（必做，顺序固定）

```bash
python tools/kb_lint.py             # 必须 0 错误，报错回修
python tools/build_tree.py          # 重建 tree.json（此文件永不手动编辑）
python tools/update_readme_stats.py # 同步 README 统计数字（幂等）
```

三条全绿才算完成；lint 有错回到第 2 步修节点。

## Word 解析辅助

`.docx` 在 AI 环境不能直读时，跑这段转出带层级的文本再走第 0 步：

```bash
pip install python-docx   # 仅首次需要
python - <<'EOF'
from docx import Document
import sys
d = Document(sys.argv[1])
for p in d.paragraphs:
    t = p.text.strip()
    if not t:
        continue
    s = p.style.name.lower()
    if ("heading" in s or "标题" in s) and t:
        print("#" * min(int(s.split()[-1] if s.split()[-1].isdigit() else 1), 4), t)
    else:
        print(t)
EOF
```

## 边界

- 一次吸收一份资料；多份分多次进行，避免单次对话质量下降；
- 只新增/修订 `knowledge-v2/nodes/*.md`；`_meta/tree.json`、README 统计一律交给第 3 步的脚本；
- 开始吸收前确认 git 工作区干净（改动可直接回滚）；若存在未提交改动，先提醒用户处理再动笔；完成后是否 commit 由用户决定；
- 缺 API key 不是问题——skill 形态下判定和撰写由当前 AI 完成，只有第 3 步本地脚本会用到 Python 环境（无第三方依赖）。
