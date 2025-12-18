from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.clients.deepseek import DeepSeekClient

_FENCE_RE = re.compile(r"```.*?\n.*?\n```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_HTML_BLOCK_RE = re.compile(r"(?is)<table.*?>.*?</table>")


@dataclass(frozen=True)
class TranslateOptions:
    target_language: str = "zh-CN"
    source_language: str = "auto"
    max_chars_per_chunk: int = 3500
    temperature: float = 0.2


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _protect(pattern: re.Pattern, text: str, tag: str) -> tuple[str, list[str]]:
    items: list[str] = []

    def repl(m: re.Match) -> str:
        items.append(m.group(0))
        return f"[[[{tag}_{len(items) - 1}]]]"

    return pattern.sub(repl, text), items


def _restore(text: str, tag: str, items: list[str]) -> str:
    for i, value in enumerate(items):
        text = text.replace(f"[[[{tag}_{i}]]]", value)
    return text


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n{2,}", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk(parts: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for p in parts:
        add_len = len(p) + (2 if cur else 0)
        if cur and cur_len + add_len > max_chars:
            chunks.append("\n\n".join(cur))
            cur = [p]
            cur_len = len(p)
            continue
        cur.append(p)
        cur_len += add_len

    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def _translate_chunk(client: DeepSeekClient, chunk: str, opts: TranslateOptions) -> str:
    system = (
        "You are a precise academic translator. Translate the provided Markdown into the target language.\n"
        "Keep Markdown structure, links, image paths, bullets, and line breaks exactly.\n"
        "Do not add explanations, prefixes, suffixes, or wrap the output in code fences.\n"
        "If you see placeholders like [[[...]]], keep them unchanged."
    )
    user = f"Target language: {opts.target_language}\n\nTranslate the following content:\n\n{chunk}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return client.chat_completions(messages, temperature=opts.temperature).strip()


def translate_markdown(
    input_markdown: str,
    client: DeepSeekClient,
    opts: TranslateOptions,
    cache_path: Path | None = None,
) -> str:
    text, fences = _protect(_FENCE_RE, input_markdown, "FENCE")
    text, inline_codes = _protect(_INLINE_CODE_RE, text, "INLINE")
    text, tables = _protect(_HTML_BLOCK_RE, text, "TABLE")

    parts = _split_paragraphs(text)
    chunks = _chunk(parts, opts.max_chars_per_chunk)

    cache: dict[str, str] = {}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    out_chunks: list[str] = []
    changed = False

    for chunk in chunks:
        key = _sha256(chunk)
        if key in cache:
            out_chunks.append(cache[key])
            continue

        translated = _translate_chunk(client, chunk, opts)
        cache[key] = translated
        out_chunks.append(translated)
        changed = True

    if cache_path and changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    result = "\n\n".join(out_chunks)
    result = _restore(result, "TABLE", tables)
    result = _restore(result, "INLINE", inline_codes)
    result = _restore(result, "FENCE", fences)
    return result


def translate_markdown_file(
    input_path: Path,
    output_path: Path,
    client: DeepSeekClient,
    opts: TranslateOptions,
) -> None:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    cache_path = output_path.with_suffix(output_path.suffix + ".cache.json")
    translated = translate_markdown(text, client=client, opts=opts, cache_path=cache_path)
    output_path.write_text(translated, encoding="utf-8")
