#!/usr/bin/env python3
"""知识树提取工具 — 把你的长文本转成思维骨架，写入 thoughts/

用法:
    python kb_think.py 通信原理 "你的口述长文本..."
    python kb_think.py 通信原理 -f transcript.txt
    python kb_think.py 通信原理 --file transcript.txt --model deepseek-chat

输出:
    knowledge/thoughts/通信原理.md  — 思维主轴 + 核心权衡 + 枢纽概念 + 分支
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"


def load_env():
    """从 tools/.env 或环境变量加载 API key"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    return os.environ.get("DEEPSEEK_API_KEY", "")


def load_existing(subject_key: str) -> dict:
    """读取已有的 thought 文件，提取已填充的字段"""
    path = KNOWLEDGE_DIR / "thoughts" / f"{subject_key}.md"
    if not path.exists():
        return {"path": path, "sections": {}}
    content = path.read_text(encoding="utf-8")
    sections = {}
    current_key = None
    current_content = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current_key and current_content:
                body = "\n".join(current_content).strip()
                if body and "<!--" not in body:
                    sections[current_key] = body
                elif not body:
                    pass
            current_key = line[3:].strip()
            current_content = []
        elif not line.startswith("---") and current_key:
            current_content.append(line)
    if current_key and current_content:
        body = "\n".join(current_content).strip()
        if body and "<!--" not in body:
            sections[current_key] = body
    return {"path": path, "sections": sections}


SYSTEM_PROMPT = """你是一名知识树助教。你的任务是从用户的口述长文本中提取他对一门课的**个人认知框架**。

注意：你不是在整理知识点！你是在提取他的**思维方式**——他怎么理解这门课、他觉得什么重要、他用什么视角串联知识。

请严格按照以下 JSON 格式输出：

```json
{
  "mind_spine": "一句话概括他对这门课的底层认知框架。比如：'他用信源→信道→信宿的主轴理解整个通信系统，把所有模块都看作是对抗噪声和带宽限制的手段'",
  "core_tradeoffs": "他反复提到的几对核心权衡/矛盾。每条10字以内，如：'带宽 vs 功率'、'可靠性 vs 效率'。最多5条",
  "hub_concept": "他心目中这门课的枢纽概念——那个把所有东西串起来的概念。说明为什么。最多3句话",
  "branches": [
    {
      "name": "分支名（从他口述中提取，是他的视角不是课本标题）",
      "insight": "他对这个分支的核心理解，1-2句话",
      "children": ["可展开的子问题1", "可展开的子问题2"]
    }
  ]
}
```

规则：
- 只输出 JSON，不要任何额外文字
- 分支数量 3-6 个
- children 是可展开的子问题，如果有写，没有就空数组
- 保持他的口语表达风格，别改成学术腔
- 如果他提到和个人经历/项目相关的理解，保留
- 如果他明确说了"这块不重要/不太懂"，也记录
"""


def call_deepseek(api_key: str, text: str, model: str = "deepseek-chat") -> dict:
    """调 DeepSeek 提取思维骨架"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:30000]},  # 截断保护
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    raw = resp.choices[0].message.content.strip()
    # 清理可能的 markdown 代码块
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
    import json
    return json.loads(raw)


def build_markdown(data: dict, subject_name: str, existing_sections: dict) -> str:
    """把 JSON 转成 thoughts/ 文档"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    frontmatter = f"""---
title: {subject_name}
tags: []
status: building
last_discussed: {date_str}
---

"""
    # 思维主轴
    spine = existing_sections.get("思维主轴") or data.get("mind_spine", "待提取")
    md = f"## 思维主轴\n\n{spine}\n\n"

    # 核心权衡
    tradeoffs = existing_sections.get("核心权衡") or data.get("core_tradeoffs", [])
    if isinstance(tradeoffs, list):
        tradeoffs_md = "\n".join(f"- {t}" for t in tradeoffs)
    else:
        tradeoffs_md = str(tradeoffs)
    md += f"## 核心权衡\n\n{tradeoffs_md}\n\n"

    # 枢纽概念
    hub = existing_sections.get("枢纽概念") or data.get("hub_concept", "待提取")
    md += f"## 枢纽概念\n\n{hub}\n\n"

    # 分支
    branches = data.get("branches", [])
    md += "## 分支\n\n"
    for i, b in enumerate(branches, 1):
        md += f"### {b['name']}\n\n"
        md += f"- {b['insight']}\n"
        children = b.get("children", [])
        if children:
            md += "- 待展开：\n"
            for c in children:
                md += f"  - [ ] {c}\n"
        else:
            md += "- 暂无子问题\n"
        md += "\n"

    return frontmatter + md


def main():
    parser = argparse.ArgumentParser(description="知识树提取工具")
    parser.add_argument("subject", help="学科名（中文，如：通信原理）")
    parser.add_argument("text", nargs="?", help="口述文本（直接输入）")
    parser.add_argument("-f", "--file", help="从文件读取文本")
    parser.add_argument("--model", default="deepseek-chat", help="DeepSeek 模型")
    parser.add_argument("--dry-run", action="store_true", help="只输出不写文件")
    args = parser.parse_args()

    # 读取输入
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        print("错误：请提供文本（直接输入 或 -f 文件）")
        sys.exit(1)

    # 生成文件名
    import re
    subject_key = re.sub(r'[^\w]', '-', args.subject.lower().strip()).strip('-')

    # 加载 API key
    api_key = load_env()
    if not api_key:
        print("错误：未找到 DEEPSEEK_API_KEY（请在 tools/.env 设置或设置环境变量）")
        sys.exit(1)

    # 查已有内容
    existing = load_existing(subject_key)

    print(f"📡 调 DeepSeek 提取「{args.subject}」的思维骨架...")
    try:
        data = call_deepseek(api_key, text, args.model)
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        sys.exit(1)

    # 生成文档
    md = build_markdown(data, args.subject, existing["sections"])

    if args.dry_run:
        print("\n--- 预览 ---\n")
        print(md)
        return

    # 写入
    existing["path"].parent.mkdir(parents=True, exist_ok=True)
    existing["path"].write_text(md, encoding="utf-8")
    print(f"✅ 已写入 {existing['path']}")

    # 打印摘要
    print(f"\n📋 提取摘要：")
    print(f"  思维主轴: {data.get('mind_spine', '?')}")
    print(f"  核心权衡: {', '.join(data.get('core_tradeoffs', []))}")
    print(f"  分支数: {len(data.get('branches', []))}")
    for b in data.get("branches", []):
        kids = len(b.get("children", []))
        print(f"    - {b['name']} ({'有' if kids else '无'}子问题)")


if __name__ == "__main__":
    main()
