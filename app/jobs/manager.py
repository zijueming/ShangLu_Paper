from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from app.analysis.paper import analyze_paper_markdown_file
from app.clients.deepseek import DeepSeekClient
from app.pdf import mineru
from app.translation.markdown import TranslateOptions, translate_markdown_file
from app.utils.zip_utils import safe_extract_zip


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    job_dir: Path
    zip_path: Path | None
    extracted_dir: Path
    original_md: Path
    translated_md: Path
    analysis_json: Path
    meta_path: Path


def _slugify(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-. ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name)
    return name[:80] or "job"


def create_job(output_dir: Path, hint: str) -> JobPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    job_id = f"{ts}_{_slugify(hint)}"
    job_dir = (output_dir / job_id).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir = job_dir / "result"
    original_md = extracted_dir / "full.md"
    translated_md = extracted_dir / "translated.md"
    analysis_json = job_dir / "analysis.json"
    meta_path = job_dir / "meta.json"
    return JobPaths(
        job_id=job_id,
        job_dir=job_dir,
        zip_path=None,
        extracted_dir=extracted_dir,
        original_md=original_md,
        translated_md=translated_md,
        analysis_json=analysis_json,
        meta_path=meta_path,
    )


def write_meta(meta_path: Path, meta: dict) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def update_meta(meta_path: Path, patch: dict) -> None:
    base: dict = {}
    if meta_path.exists():
        try:
            base = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    patch = dict(patch or {})
    patch["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    base.update(patch)
    write_meta(meta_path, base)


def run_mineru_to_job(job: JobPaths, pdf_path_or_url: str, timeout: int = 600) -> JobPaths:
    update_meta(job.meta_path, {"job_id": job.job_id, "state": "parsing", "pdf": pdf_path_or_url})

    result = mineru.parse_pdf(pdf_path_or_url, output_dir=str(job.job_dir), timeout=timeout)
    if result.get("state") != "done":
        update_meta(job.meta_path, {"state": "failed", "error": result.get("error")})
        raise RuntimeError(result.get("error") or "MinerU parse failed")

    zip_path_raw = result.get("zip_path")
    if not zip_path_raw:
        update_meta(job.meta_path, {"state": "failed", "error": "MinerU did not provide zip_path (full.md unavailable)"})
        raise RuntimeError("MinerU did not provide zip_path (full.md unavailable)")
    zip_path = Path(zip_path_raw).resolve() if zip_path_raw else None
    if zip_path:
        update_meta(job.meta_path, {"state": "parsed", "zip_path": str(zip_path)})
        safe_extract_zip(zip_path, job.extracted_dir)

    if not job.original_md.exists():
        update_meta(job.meta_path, {"state": "failed", "error": "full.md not found in result"})
        raise FileNotFoundError("full.md not found in result zip")

    return JobPaths(
        job_id=job.job_id,
        job_dir=job.job_dir,
        zip_path=zip_path,
        extracted_dir=job.extracted_dir,
        original_md=job.original_md,
        translated_md=job.translated_md,
        analysis_json=job.analysis_json,
        meta_path=job.meta_path,
    )


def run_translate_to_job(
    job: JobPaths,
    *,
    target_language: str = "zh-CN",
    client: DeepSeekClient | None = None,
) -> JobPaths:
    if not job.original_md.exists():
        update_meta(job.meta_path, {"translate_state": "failed", "translate_error": f"missing original Markdown: {job.original_md}"})
        raise FileNotFoundError(f"missing original Markdown: {job.original_md}")

    client = client or DeepSeekClient.from_config()
    update_meta(job.meta_path, {"translate_state": "translating", "translate_language": target_language, "translate_error": ""})

    opts = TranslateOptions(target_language=target_language)
    translate_markdown_file(job.original_md, job.translated_md, client=client, opts=opts)

    update_meta(job.meta_path, {"translate_state": "translated", "translate_language": target_language})
    return job


def run_analyze_to_job(
    job: JobPaths,
    *,
    client: DeepSeekClient | None = None,
    max_chars: int = 25000,
) -> JobPaths:
    if not job.original_md.exists():
        update_meta(job.meta_path, {"state": "failed", "error": f"missing original Markdown: {job.original_md}"})
        raise FileNotFoundError(f"missing original Markdown: {job.original_md}")

    client = client or DeepSeekClient.from_config()
    update_meta(job.meta_path, {"state": "analyzing"})
    analyze_paper_markdown_file(job.original_md, job.analysis_json, client=client, max_chars=max_chars)
    update_meta(job.meta_path, {"state": "analyzed"})
    return job
