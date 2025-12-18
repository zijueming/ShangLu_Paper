"""
End-to-end pipeline: MinerU parse -> DeepSeek translate -> optional viewer serve.
"""

from __future__ import annotations

from pathlib import Path

from app.clients.deepseek import DeepSeekClient
from app.jobs.manager import JobPaths, create_job, run_mineru_to_job, run_translate_to_job
from app.viewer.web import serve_viewer


def run_pdf_pipeline(
    pdf_path_or_url: str,
    output_dir: Path,
    *,
    timeout: int = 600,
    target_language: str = "zh-CN",
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
) -> JobPaths:
    pdf_path_or_url = (pdf_path_or_url or "").strip()
    if not pdf_path_or_url:
        raise ValueError("pdf_path_or_url is required")

    hint = "url" if "://" in pdf_path_or_url else Path(pdf_path_or_url).stem
    job = create_job(output_dir, hint=hint)
    job = run_mineru_to_job(job, pdf_path_or_url, timeout=timeout)

    client = DeepSeekClient.from_config()
    job = run_translate_to_job(job, target_language=target_language, client=client)

    serve_viewer(output_dir, host=host, port=port, open_url=f"/view/{job.job_id}/" if open_browser else None)
    return job
