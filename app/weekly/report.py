from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.clients.deepseek import DeepSeekClient


def _weekly_dir(output_dir: Path) -> Path:
    return output_dir / "weekly_reports"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_date(value: str) -> date:
    value = (value or "").strip()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _job_link(job_id: str) -> str:
    return f"/job/{job_id}/"


def _pick_analysis_fields(analysis: dict) -> dict:
    def pick(*keys: str, default=""):
        for k in keys:
            v = analysis.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return default

    def pick_list(*keys: str):
        for k in keys:
            v = analysis.get(k)
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
        return []

    def pick_steps(*keys: str):
        for k in keys:
            v = analysis.get(k)
            if isinstance(v, list):
                out = []
                for item in v:
                    if isinstance(item, dict):
                        step = item.get("步骤", item.get("step", item.get("index", "")))
                        content = item.get("内容", item.get("content", ""))
                        if str(content).strip():
                            out.append({"步骤": int(step) if str(step).isdigit() else step, "内容": str(content).strip()})
                    elif str(item).strip():
                        out.append({"步骤": "", "内容": str(item).strip()})
                return out
        return []

    return {
        "标题": pick("标题", "title", "paper_title", default="未提及"),
        "作者": pick("作者", "authors", default="未提及"),
        "年份": pick("年份", "year", default=""),
        "摘要": pick("摘要", "abstract", default="未提及"),
        "主要结论": pick_list("主要结论", "main_conclusions"),
        "创新点": pick_list("创新点", "innovations"),
        "实验方法": pick_list("实验方法", "methods"),
        "不足": pick_list("不足", "limitations"),
        "实验详细步骤": pick_steps("实验详细步骤", "experimental_steps"),
        "表征方法": pick_list("表征方法", "characterization_methods"),
        "研究启发": pick_list("研究启发", "insights"),
    }


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- 未提及"
    return "\n".join(f"- {x}" for x in items)


def _render_steps(steps: list[dict]) -> str:
    if not steps:
        return "- 未提及"
    lines: list[str] = []
    for i, s in enumerate(steps, start=1):
        content = str(s.get("内容", "")).strip()
        if not content:
            continue
        idx = s.get("步骤", i)
        lines.append(f"{idx}. {content}")
    return "\n".join(lines) if lines else "- 未提及"


def _build_markdown(
    *,
    start_date: date,
    end_date: date,
    papers: list[dict],
    extra_work: str,
    problems: str,
    next_plan: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# 周报（{start_date.isoformat()} ~ {end_date.isoformat()}）")
    lines.append("")
    lines.append(f"## 本周阅读文献（{len(papers)}）")
    lines.append("")

    if not papers:
        lines.append("- 本周未选择文献")
    else:
        for idx, p in enumerate(papers, start=1):
            title = p.get("标题", "未提及")
            authors = p.get("作者", "未提及")
            year = p.get("年份", "")
            meta = "，".join([x for x in [authors, year] if x])
            link = p.get("_link", "")
            title_line = f"{idx}. {title}"
            if link:
                title_line = f"{idx}. [{title}]({link})"
            lines.append(title_line + (f"（{meta}）" if meta else ""))
            lines.append(f"   - 摘要：{p.get('摘要','未提及')}")
            lines.append("   - 主要结论：")
            lines.append("     " + _render_bullets(p.get("主要结论", [])).replace("\n", "\n     "))
            lines.append("   - 创新点：")
            lines.append("     " + _render_bullets(p.get("创新点", [])).replace("\n", "\n     "))
            lines.append("   - 实验方法：")
            lines.append("     " + _render_bullets(p.get("实验方法", [])).replace("\n", "\n     "))
            lines.append("   - 不足：")
            lines.append("     " + _render_bullets(p.get("不足", [])).replace("\n", "\n     "))
            lines.append("   - 研究启发：")
            lines.append("     " + _render_bullets(p.get("研究启发", [])).replace("\n", "\n     "))
            lines.append("")

    lines.append("## 本周完成工作")
    lines.append("")
    lines.append(extra_work.strip() or "- （待补充）")
    lines.append("")

    lines.append("## 遇到的问题与解决方案")
    lines.append("")
    lines.append(problems.strip() or "- （待补充）")
    lines.append("")

    lines.append("## 下周计划")
    lines.append("")
    lines.append(next_plan.strip() or "- （待补充）")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _polish_with_ai(client: DeepSeekClient, payload: dict) -> str:
    system = (
        "你是一个专业的科研周报写作助手。\n"
        "请基于用户提供的结构化信息，输出一份中文周报（Markdown 格式）。\n"
        "要求：\n"
        "1) 只输出 Markdown，不要输出解释。\n"
        "2) 结构包含：标题、【本周阅读文献】、【本周完成工作】、【遇到的问题与解决方案】、【下周计划】。\n"
        "3) 文献部分：每篇控制在 8-12 行内，突出主要结论/创新点/不足/启发。\n"
        "4) 不要捏造论文中不存在的事实或数值；不确定写“文中未明确”。\n"
    )
    user = "输入 JSON：\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return client.chat_completions(messages, temperature=0.2).strip()


@dataclass(frozen=True)
class WeeklyReport:
    report_id: str
    meta_path: Path
    markdown_path: Path

    def read_meta(self) -> dict:
        return _read_json(self.meta_path)

    def read_markdown(self) -> str:
        if not self.markdown_path.exists():
            return ""
        return self.markdown_path.read_text(encoding="utf-8", errors="replace")


def list_weekly_reports(output_dir: Path) -> list[dict]:
    base = _weekly_dir(output_dir)
    if not base.exists():
        return []

    items: list[dict] = []
    for meta_path in sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = _read_json(meta_path)
        report_id = meta.get("report_id") or meta_path.stem
        items.append(
            {
                "report_id": report_id,
                "start_date": meta.get("start_date", ""),
                "end_date": meta.get("end_date", ""),
                "created_at": meta.get("created_at", ""),
                "use_ai": bool(meta.get("use_ai", False)),
            }
        )
    return items


def get_weekly_report(output_dir: Path, report_id: str) -> WeeklyReport:
    base = _weekly_dir(output_dir)
    return WeeklyReport(
        report_id=report_id,
        meta_path=base / f"{report_id}.json",
        markdown_path=base / f"{report_id}.md",
    )


def create_weekly_report(
    output_dir: Path,
    *,
    start_date: str,
    end_date: str,
    job_ids: list[str],
    extra_work: str = "",
    problems: str = "",
    next_plan: str = "",
    use_ai: bool = True,
    client: DeepSeekClient | None = None,
) -> WeeklyReport:
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if sd > ed:
        raise ValueError("start_date must be <= end_date")

    ts = time.strftime("%Y%m%d_%H%M%S")
    report_id = f"{sd.strftime('%Y%m%d')}_{ed.strftime('%Y%m%d')}_{ts}"

    base = _weekly_dir(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    report = get_weekly_report(output_dir, report_id)

    papers: list[dict] = []
    for job_id in job_ids:
        analysis_path = (output_dir / job_id / "analysis.json").resolve()
        analysis = _read_json(analysis_path)
        fields = _pick_analysis_fields(analysis)
        fields["_job_id"] = job_id
        fields["_link"] = _job_link(job_id)
        papers.append(fields)

    payload = {
        "start_date": sd.isoformat(),
        "end_date": ed.isoformat(),
        "papers": papers,
        "extra_work": extra_work,
        "problems": problems,
        "next_plan": next_plan,
    }

    if use_ai:
        client = client or DeepSeekClient.from_config()
        markdown = _polish_with_ai(client, payload)
    else:
        markdown = _build_markdown(
            start_date=sd,
            end_date=ed,
            papers=papers,
            extra_work=extra_work,
            problems=problems,
            next_plan=next_plan,
        )

    report.markdown_path.write_text(markdown, encoding="utf-8")
    report.meta_path.write_text(
        json.dumps(
            {
                "report_id": report_id,
                "start_date": sd.isoformat(),
                "end_date": ed.isoformat(),
                "job_ids": job_ids,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "use_ai": use_ai,
                "markdown_path": str(report.markdown_path.name),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report

