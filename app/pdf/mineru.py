"""
MinerU PDF parsing helper.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import requests

from app import config


def parse_pdf(pdf_path: str, output_dir: str | None = None, timeout: int = 600, model_version: str = "vlm") -> dict:
    """
    Parse a PDF (local path or URL) with MinerU and return a dict: {"state": "...", "zip_path": "..."}.
    """
    token = (getattr(config, "MINERU_TOKEN", "") or "").strip()
    if not token:
        raise RuntimeError("Missing MinerU token: set MINERU_TOKEN or config_local.MINERU_TOKEN")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    pdf_path = (pdf_path or "").strip().strip('"').strip("'")
    if not pdf_path:
        raise ValueError("pdf_path is empty")

    if _is_url(pdf_path):
        pdf_url = pdf_path
        if output_dir is None:
            output_dir = "./"
        task_id = _create_task(headers, pdf_url, model_version)
        suggested_name = os.path.basename(urlparse(pdf_url).path) or "result.pdf"
        return _wait_and_download(task_id, headers, output_dir, timeout, suggested_name=suggested_name)

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"file not found: {pdf_path}")

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or "./"

    file_name = os.path.basename(pdf_path)
    upload_batch_id, upload_url = _get_upload_url(headers, file_name)
    _upload_file(upload_url, pdf_path)
    return _wait_and_download_batch(upload_batch_id, headers, output_dir, timeout, suggested_name=file_name)


def _is_url(value: str) -> bool:
    return bool(value) and (value.startswith("http://") or value.startswith("https://"))


def _get_upload_url(headers: dict, file_name: str) -> tuple[str, str]:
    res = requests.post(
        "https://mineru.net/api/v4/file-urls/batch",
        headers=headers,
        json={"files": [{"name": file_name, "is_ocr": True}]},
        timeout=30,
    )
    batch_data = res.json()
    if batch_data.get("code") != 0:
        raise RuntimeError(f"failed to get upload url: {batch_data.get('msg') or batch_data}")

    data = batch_data.get("data") or {}

    batch_id = data.get("batch_id")
    file_urls = data.get("file_urls") or []
    if file_urls:
        upload_url = file_urls[0]
        if not batch_id:
            raise RuntimeError(f"missing batch_id in response: {batch_data}")
        return batch_id, upload_url

    files = data.get("files") or []
    if files and isinstance(files, list):
        upload_url = (files[0] or {}).get("presigned_url")
        if upload_url:
            if not batch_id:
                raise RuntimeError(f"missing batch_id in response: {batch_data}")
            return batch_id, upload_url

    raise RuntimeError(f"cannot parse upload url: {batch_data}")


def _upload_file(upload_url: str, pdf_path: str) -> None:
    with open(pdf_path, "rb") as f:
        upload_res = requests.put(upload_url, data=f, timeout=300)
    if not (200 <= upload_res.status_code < 300):
        raise RuntimeError(f"upload failed: {upload_res.status_code} {upload_res.text[:200]}")


def _create_task(headers: dict, url: str, model_version: str) -> str:
    res = requests.post(
        "https://mineru.net/api/v4/extract/task",
        headers=headers,
        json={"url": url, "model_version": model_version},
        timeout=30,
    )
    data = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"create task failed: {data.get('msg') or data}")

    task_id = (data.get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"missing task_id: {data}")
    return task_id


def _wait_and_download(task_id: str, headers: dict, output_dir: str, timeout: int, suggested_name: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"parse timeout after {timeout} seconds")

        res = requests.get(
            f"https://mineru.net/api/v4/extract/task/{task_id}",
            headers={"Authorization": headers["Authorization"]},
            timeout=30,
        )
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(f"query status failed: {data.get('msg') or data}")

        result = data.get("data") or {}
        state = result.get("state")

        if state == "done":
            zip_url = result.get("full_zip_url")
            if zip_url:
                base_name = os.path.splitext(os.path.basename(suggested_name or "result.pdf"))[0] or "result"
                zip_path = os.path.join(output_dir, f"{base_name}_result.zip")

                zip_res = requests.get(zip_url, timeout=300)
                with open(zip_path, "wb") as f:
                    f.write(zip_res.content)

                return {"state": "done", "zip_path": zip_path, "task_id": task_id}

            return {
                "state": "failed",
                "error": "MinerU response missing full_zip_url; cannot download result zip",
                "task_id": task_id,
            }

        if state == "failed":
            return {"state": "failed", "error": result.get("err_msg"), "task_id": task_id}

        time.sleep(3)


def _wait_and_download_batch(batch_id: str, headers: dict, output_dir: str, timeout: int, suggested_name: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"parse timeout after {timeout} seconds")

        res = requests.get(
            f"https://mineru.net/api/v4/extract-results/batch/{batch_id}",
            headers={"Authorization": headers["Authorization"]},
            timeout=30,
        )
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(f"query status failed: {data.get('msg') or data}")

        results = (data.get("data") or {}).get("extract_result") or []
        if not results:
            time.sleep(3)
            continue

        result = results[0] or {}
        state = result.get("state")

        if state == "done":
            zip_url = result.get("full_zip_url")
            if zip_url:
                base_name = os.path.splitext(os.path.basename(suggested_name or "result.pdf"))[0] or "result"
                zip_path = os.path.join(output_dir, f"{base_name}_result.zip")

                zip_res = requests.get(zip_url, timeout=300)
                with open(zip_path, "wb") as f:
                    f.write(zip_res.content)

                return {"state": "done", "zip_path": zip_path, "batch_id": batch_id}

            return {
                "state": "failed",
                "error": "MinerU response missing full_zip_url; cannot download result zip",
                "batch_id": batch_id,
            }

        if state == "failed":
            return {"state": "failed", "error": result.get("err_msg"), "batch_id": batch_id}

        time.sleep(3)
