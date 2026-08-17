"""出题与解析的 prompt 模板。核心约束：只基于节点原文，不引入节点外知识。"""

GEN_SYSTEM = """你是通信工程课程的出题老师，任务是基于给定的知识库节点原文出复习题。

严格规则：
1. 只能使用给定节点原文中的知识出题，禁止引入任何节点之外的知识、公式或概念。
2. 每道题必须能在节点原文中找到依据。
3. 输出必须是一个 JSON 数组，数组里每个元素是一道题，格式固定为：
   {"type": "short_answer", "stem": "题干", "answer": "参考答案", "analysis": "解析", "nodes": ["节点id"]}
   type 只能取 short_answer（简答题）、judge（判断题）、fill_blank（填空题）之一。
4. judge 题：题干末尾写"（判断正误并说明理由）"，answer 先写"正确"或"错误"，再解释。
5. fill_blank 题：题干中用 ____（四个下划线）表示空缺，answer 给出应填内容。
6. analysis 必须用节点原文的语言解释为什么，只能引用节点原文，禁止外推。
7. nodes 字段：这道题实际涉及的知识节点 id，必须从「可用节点列表」里选；单一知识点给 1 个，跨知识点综合题可给多个。
8. 只输出 JSON 本身，不要输出任何解释、前后缀或代码围栏。"""


def gen_user(node_contexts: str, node_ids, n: int, types) -> str:
    types_cn = "、".join(types)
    multi = len(node_ids) > 1
    extra = ""
    if multi:
        extra = (
            "本次涉及多个节点，请出若干道「跨节点综合题」："
            "把不同节点之间有关联的知识串联起来设问（例如用 links 里的关系、或同一知识在不同课程下的视角），"
            "综合题在 nodes 字段里列出它涉及的所有节点 id。\n"
        )
    return (
        f"可用节点列表：{', '.join(node_ids)}\n"
        f"出题数量：{n} 道\n"
        f"题型要求：只出这些题型——{types_cn}\n"
        f"{extra}"
        "题目难度：以考察理解为主（机制、权衡、易混点），少出纯背诵题。\n\n"
        "以下是节点原文（唯一出题依据）：\n\n"
        f"{node_contexts}"
    )


ANA_SYSTEM = """你是通信工程课程的答疑老师。根据给定的知识库节点原文，为一道题的答案写出"解析"。

严格规则：
1. 解析只能引用给定节点原文中的内容，禁止引入节点之外的知识。
2. 解析要解释"为什么是这个答案"，并指出本题在节点原文中的依据。
3. 输出纯文本解析，不要用 Markdown 代码围栏，不要重复题干。"""


def ana_user(node_contexts: str, stem: str, answer: str) -> str:
    return (
        f"题目：{stem}\n\n"
        f"参考答案：{answer}\n\n"
        "请只基于下面的节点原文，写出这道题的解析（为什么是这个答案、依据是什么）：\n\n"
        f"{node_contexts}"
    )
