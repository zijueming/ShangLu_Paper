from __future__ import annotations

from app.clients.deepseek import DeepSeekClient


def polish_draw_prompt(prompt: str, client: DeepSeekClient) -> str:
    raw = (prompt or "").strip()
    if not raw:
        return ""

    system = (
        "你是一个科研绘图提示词润色助手。\n"
        "请把用户的提示词润色成更适合图像生成模型的高质量提示词，用于生成“科研风格”的图示/插图。\n"
        "要求：\n"
        "1) 只输出润色后的提示词，不要输出任何解释或前后缀。\n"
        "2) 不改变用户意图，不捏造具体数值/实验结果；不确定写“文中未明确”。\n"
        "3) 默认风格：干净白底、学术插图、清晰结构、可读标注、线条简洁、出版级。\n"
        "4) 如果用户描述的是图表/示意图/流程图/结构图，请补充：布局、配色、标注、分辨率等关键信息。\n"
    )
    user = "原始提示词：\n" + raw
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    out = client.chat_completions(messages, temperature=0.2)
    return (out or "").strip().strip('"').strip()

