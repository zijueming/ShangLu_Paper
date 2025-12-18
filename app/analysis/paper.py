from __future__ import annotations

import json
import re
from pathlib import Path

from app.clients.deepseek import DeepSeekClient

_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]+\)")


def _normalize_markdown(markdown: str, max_chars: int) -> str:
    text = (markdown or "").strip()
    text = _IMAGE_RE.sub("[[IMAGE]]", text)
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    tail_len = min(5000, max_chars // 3)
    head_len = max_chars - tail_len
    head = text[:head_len]
    tail = text[-tail_len:]
    return head + "\n\n[[TRUNCATED]]\n\n" + tail


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {"raw": raw}


def analyze_paper_markdown(
    paper_markdown: str,
    client: DeepSeekClient,
    *,
    max_chars: int = 25000,
    temperature: float = 0.2,
) -> dict:
    content = _normalize_markdown(paper_markdown, max_chars=max_chars)
    system = (
        "你是一个严谨的学术论文阅读助手。请基于用户提供的论文内容，输出结构化中文信息。\n"
        "要求：\n"
        "1) 只输出合法 JSON，不要输出其他任何文字。\n"
        "2) JSON 必须包含以下键：标题、作者、摘要、主要结论、创新点、实验方法、不足、实验详细步骤、表征方法、研究启发、术语解释。\n"
        "3) 类型约束：\n"
        '   - 标题: string（若无法确定写“未提及”）\n'
        '   - 作者: string（若无法确定写“未提及”）\n'
        '   - 摘要: string（100-200字）\n'
        "   - 主要结论/创新点/实验方法/不足/表征方法/研究启发: string 数组（3-8条，每条≤80字）\n"
        '   - 实验详细步骤: 数组，每项为 {"步骤": int, "内容": string}\n'
        '   - 术语解释: 数组，每项为 {"术语": string, "解释": string}（5-15条，每条≤80字）\n'
        "4) 若文中未提及：数组给空数组[]；字符串字段写“未提及”。\n"
        "5) 不要捏造具体数值/数据集/参数；不确定请写“文中未明确”。\n"
    )
    user = f"论文内容（可能被截断）：\n\n{content}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    out = client.chat_completions(messages, temperature=temperature)
    return _extract_json(out)


def analyze_paper_markdown_file(
    input_path: Path,
    output_path: Path,
    client: DeepSeekClient,
    *,
    max_chars: int = 25000,
    temperature: float = 0.2,
) -> dict:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    data = analyze_paper_markdown(text, client=client, max_chars=max_chars, temperature=temperature)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
