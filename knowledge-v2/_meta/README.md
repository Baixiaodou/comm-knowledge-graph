# knowledge-v2 架构说明

## 设计理念

**节点即一切。** 树层级（parent/children）、Wiki连接（links）、思维链（cot）都是节点的属性，不是独立系统。

## 目录结构

```
knowledge-v2/
├── _meta/
│   ├── tree.json          # 树拓扑骨架（自动生成，只读）
│   ├── node-spec.md       # 节点格式规范
│   └── README.md          # 本文件
├── nodes/                 # 所有知识节点
│   ├── root.md            # 根节点
│   ├── comm-*.md          # 通信原理相关
│   ├── dsp-*.md           # DSP相关
│   └── ...
└── raw/                   # 原始素材（你的口述文本，只读保留）
```

## 检索流程

```
用户问题
  ↓
1. 树导航：读 tree.json → LLM 定位所属分支
  ↓
2. 节点展开：读目标节点的 content + links
  ↓
3. Wiki扩展：沿 links 读关联节点（1-hop）
  ↓
4. 思维链：如有 cot → 带上推理链
  ↓
5. 组装回答
```

## 与旧 knowledge/ 的关系

| | knowledge/ (旧) | knowledge-v2/ (新) |
|---|---|---|
| thoughts/ | 手动维护的思维树 | nodes/ 统一管理 |
| courses/ | TF-IDF 检索底料 | raw/ 只保留原始素材 |
| 检索方式 | TF-IDF + 向量 | 树导航 + Wiki扩展 |
| 连接 | 无 | links 自动关联 |

旧 knowledge/ 保留不动，knowledge-v2/ 独立演进。
