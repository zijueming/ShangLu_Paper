from __future__ import annotations

import mimetypes
import threading
import time
from pathlib import Path
from typing import Any

import requests

from app.clients.deepseek import DeepSeekClient
from app.clients.grsai import GrsaiClient
from app.draw.prompt import polish_draw_prompt
from app.draw.storage import DrawingPaths, safe_rel_url, update_drawing_meta


def _guess_ext(url: str, content_type: str | None) -> str:
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".avif"}
    try:
        suffix = Path(str(url or "").split("?")[0]).suffix
        if suffix:
            suffix_norm = suffix.lower()
            if suffix_norm in allowed:
                return suffix_norm
    except Exception:
        pass

    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext and ext.lower() in allowed:
            return ext.lower()
    return ".png"


def _download_file(url: str, dst: Path, *, timeout_s: int = 60) -> tuple[bool, str]:
    url = (url or "").strip()
    if not url:
        return False, "empty url"
    try:
        with requests.get(url, stream=True, timeout=timeout_s) as r:
            r.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        return True, ""
    except Exception as e:
        return False, str(e)


def _extract_data(resp: dict[str, Any]) -> dict[str, Any]:
    if isinstance(resp.get("data"), dict):
        return resp["data"]
    return resp if isinstance(resp, dict) else {}


def _run_drawing(
    paths: DrawingPaths,
    *,
    output_dir: Path,
    prompt: str,
    prompt_override: str,
    model: str,
    aspect_ratio: str,
    image_size: str,
    urls: list[str],
    host: str,
    use_ai: bool,
) -> None:
    try:
        update_drawing_meta(paths.meta_path, {"state": "running", "progress": 0})

        prompt_polished = ""
        prompt_override = (prompt_override or "").strip()
        prompt_final = prompt_override or (prompt or "").strip()
        if use_ai and not prompt_override:
            update_drawing_meta(paths.meta_path, {"state": "polishing"})
            try:
                ds = DeepSeekClient.from_config()
                prompt_polished = polish_draw_prompt(prompt_final, ds)
                prompt_final = prompt_polished or prompt_final
            except Exception as e:
                update_drawing_meta(paths.meta_path, {"warning": f"AI polish skipped: {str(e)}"})

        update_drawing_meta(paths.meta_path, {"prompt_polished": prompt_polished, "prompt_final": prompt_final, "state": "submitting"})

        client = GrsaiClient.from_config(base_url_override=host)
        submit = client.draw_nano_banana(
            {
                "model": model,
                "prompt": prompt_final,
                "aspectRatio": aspect_ratio or "auto",
                "imageSize": image_size or "1K",
                "urls": urls or [],
                "webHook": "-1",
                "shutProgress": False,
            }
        )
        remote_id = str(_extract_data(submit).get("id") or "").strip()
        if not remote_id:
            raise RuntimeError(f"Unexpected nano-banana response: {submit}")

        update_drawing_meta(paths.meta_path, {"remote": {"id": remote_id, "raw": submit}, "state": "running", "progress": 1})

        deadline = time.time() + 60 * 20
        last_progress = 1
        final: dict[str, Any] = {}
        while time.time() < deadline:
            res = client.draw_result(remote_id)
            data = _extract_data(res)
            final = data or final
            progress = int(data.get("progress") or 0)
            status = str(data.get("status") or "").strip()
            failure_reason = str(data.get("failure_reason") or "").strip()
            error = str(data.get("error") or "").strip()

            if progress < last_progress:
                progress = last_progress
            last_progress = progress

            update_drawing_meta(
                paths.meta_path,
                {
                    "state": "running" if status and status not in ("succeeded", "failed") else status or "running",
                    "status": status,
                    "progress": progress,
                    "failure_reason": failure_reason,
                    "error": error,
                },
            )

            if status in ("succeeded", "failed"):
                break
            time.sleep(2)

        status = str(final.get("status") or "").strip()
        if status != "succeeded":
            reason = str(final.get("failure_reason") or final.get("error") or "unknown").strip()
            update_drawing_meta(paths.meta_path, {"state": "failed", "error": reason})
            return

        results = final.get("results") if isinstance(final.get("results"), list) else []
        saved_files: list[str] = []
        normalized_results: list[dict[str, Any]] = []

        for idx, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or "").strip()

            local_url = ""
            if url:
                try:
                    head = requests.head(url, timeout=30, allow_redirects=True)
                    content_type = head.headers.get("Content-Type")
                except Exception:
                    content_type = None
                ext = _guess_ext(url, content_type)
                filename = f"result_{idx}{ext}"
                dst = paths.drawing_dir / filename
                ok, err = _download_file(url, dst)
                if ok:
                    local_url = safe_rel_url(output_dir, dst)
                    saved_files.append(local_url)
                else:
                    content = (content + ("\n" if content else "") + f"[download_failed] {err}").strip()

            normalized_results.append({"url": url, "local_url": local_url, "content": content})

        update_drawing_meta(
            paths.meta_path,
            {
                "state": "succeeded",
                "progress": 100,
                "results": normalized_results,
                "files": saved_files,
            },
        )
    except Exception as e:
        update_drawing_meta(paths.meta_path, {"state": "failed", "error": str(e)})


def start_drawing_worker(
    paths: DrawingPaths,
    *,
    output_dir: Path,
    prompt: str,
    prompt_override: str = "",
    model: str,
    aspect_ratio: str,
    image_size: str,
    urls: list[str],
    host: str,
    use_ai: bool,
) -> None:
    threading.Thread(
        target=_run_drawing,
        kwargs={
            "paths": paths,
            "output_dir": output_dir,
            "prompt": prompt,
            "prompt_override": prompt_override,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
            "urls": urls,
            "host": host,
            "use_ai": use_ai,
        },
        daemon=True,
    ).start()
