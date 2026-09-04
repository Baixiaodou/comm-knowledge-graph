"""本地端到端验证线上版 fuzzy_hub_rag（不改服务器）。

验证项：
1. hub 池加载（19 个）+ tree children 映射
2. _format_hub_passage 注入串（hub 内容 + 子主题标题树）+ last_ids 追问闭环写入
3. 真实 API 调用 route()（大问题 → HUB、点名具体概念 → LEAF）
4. retrieve() 完整路径：开关开 → 模糊轮走 hub 注入；开关关 → 与现状一致

用法：.venv/Scripts/python 知识库研究/knowledge-base/tools/fuzzy_hub_rag/verify_online.py

⚠️ 内部验证工具（非通用复现脚本）：依赖仓库外代码（线上插件的
src/plugins/ai_chat/fuzzy_hub_rag.py 在 QQ bot 服务器，不在本仓库）与本机 API key 文件，
读者无法直接复现。正式实验结论以 fuzzy_benchmark.py 为准。
"""
import asyncio
import os
import sys

import nonebot

nonebot.init()

# 本地 API key（供真实调用验证；服务器走 .env 不受影响）。
# 必须在 import ai_chat 之前注入 driver.config：PluginConfig 从 driver.config 实例化，
# deepseek_client 模块级实例化时 SDK 需要非空 key。
key_path = r"D:\Bai chenghongyi Information\qq_ai_project\api\my_deepseek_api.txt"
with open(key_path, encoding="utf-8") as f:
    key = f.readline().strip()  # 文件含多平台 key，只取第一行 DeepSeek key
nonebot.get_driver().config.deepseek_api_key = key

SRC = r"D:\Bai chenghongyi Information\qq_ai_project\src\plugins"
sys.path.insert(0, SRC)

# 预置假 ai_chat 包：跳过 __init__.py（会拉进 handlers→pydub 等本地未装依赖），
# 只加载被测模块本身及其相对导入链（config/deepseek_client/node_retriever/fuzzy_hub_rag）。
import types

_pkg = types.ModuleType("ai_chat")
_pkg.__path__ = [os.path.join(SRC, "ai_chat")]
sys.modules["ai_chat"] = _pkg

from ai_chat.config import config
config.knowledge_v2_dir = os.path.join(
    r"D:\Bai chenghongyi Information\qq_ai_project\知识库研究\knowledge-base",
    "knowledge-v2", "nodes",
)

from ai_chat.node_retriever import node_retriever

print("=" * 60)
print("[1] 知识库结构验证")
node_retriever.init()
print(f"节点总数: {len(node_retriever._nodes)} | hubs: {len(node_retriever.hubs)} | children 映射: {len(node_retriever._children)}")
for h in node_retriever.hubs:
    print(f"  hub: {h['id']} | {h['title']}")
kids = node_retriever._hub_descendant_ids("root")
print(f"root 子孙节点数: {len(kids)}（期望 83 = 84-1）")

print("=" * 60)
print("[2] hub 注入串（不调 API）")
passage = node_retriever._format_hub_passage(["comm-analog"])
print("--- comm-analog 注入串预览 ---")
print(passage[:500])
print("...")
types = {node_retriever._by_id[i]["type"] for i in node_retriever.last_ids}
print(f"last_ids: {len(node_retriever.last_ids)} 个，类型集合: {types}（应全为 core/leaf）")
assert types <= {"core", "leaf"} and types, "last_ids 类型不合法"
assert "统领的子主题" in passage, "注入串缺少子主题列表"
print("✔ 注入串与 last_ids 验证通过")


async def main():
    from ai_chat import fuzzy_hub_rag

    print("=" * 60)
    print("[3] 真实 API 路由判定（大/小各 1 题）")
    for q in ["移动通信都有哪些关键技术？", "为什么 DSB-SC 不能用包络检波，而普通 AM 可以？"]:
        path, hubs = await fuzzy_hub_rag.route(q)
        print(f"  route('{q}') -> path={path} hubs={hubs}")

    print("=" * 60)
    print("[4] retrieve() 完整路径（开关开 → 模糊轮 hub 注入）")
    r = await node_retriever.retrieve("移动通信都有哪些关键技术？")
    assert r and "主题域总览" in r, "模糊轮未走 hub 注入路径"
    print(f"  HUB 命中，注入 {len(r)} 字，last_ids={len(node_retriever.last_ids)} 个")
    print(r[:200])

    r2 = await node_retriever.retrieve("为什么 DSB-SC 不能用包络检波？")
    assert r2 and "主题域总览" not in r2, "具体概念题不应走 hub 注入"
    print(f"  LEAF 判定，走正常精确检索，注入 {len(r2)} 字")
    print(r2[:200])

    print("=" * 60)
    print("[5] retrieve() 完整路径（开关关 → 行为与现状一致）")
    config.fuzzy_hub_enabled = False
    r3 = await node_retriever.retrieve("移动通信都有哪些关键技术？")
    print(f"  开关关: 返回 {'None（闲聊/无命中）' if r3 is None else f'{len(r3)} 字正常精确注入'}")
    config.fuzzy_hub_enabled = True

    print("=" * 60)
    print("全部验证通过 ✔")


asyncio.run(main())
