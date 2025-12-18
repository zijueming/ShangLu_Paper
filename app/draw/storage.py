from __future__ import annotations

import json
import shutil
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def drawings_dir(output_dir: Path) -> Path:
    return output_dir / "drawings"


def safe_rel_url(output_dir: Path, file_path: Path) -> str:
    rel = file_path.resolve().relative_to(output_dir.resolve())
    return "/" + urllib.parse.quote(str(rel).replace("\\", "/"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_drawing_meta(meta_path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    base = _read_json(meta_path)
    patch = dict(patch or {})
    patch["updated_at"] = _now_ts()
    base.update(patch)
    _write_json(meta_path, base)
    return base


@dataclass(frozen=True)
class DrawingPaths:
    drawing_id: str
    drawing_dir: Path
    meta_path: Path


def create_drawing(
    output_dir: Path,
    *,
    prompt: str,
    prompt_override: str = "",
    model: str,
    aspect_ratio: str,
    image_size: str,
    urls: list[str],
    host: str,
    use_ai: bool,
) -> DrawingPaths:
    base = drawings_dir(output_dir)
    base.mkdir(parents=True, exist_ok=True)

    drawing_id = uuid.uuid4().hex
    ddir = (base / drawing_id).resolve()
    ddir.mkdir(parents=True, exist_ok=True)

    meta_path = ddir / "meta.json"
    meta: dict[str, Any] = {
        "id": drawing_id,
        "created_at": _now_ts(),
        "updated_at": _now_ts(),
        "state": "queued",
        "progress": 0,
        "status": "",
        "failure_reason": "",
        "error": "",
        "warning": "",
        "request": {
            "prompt": (prompt or "").strip(),
            "prompt_override": (prompt_override or "").strip(),
            "model": (model or "").strip(),
            "aspectRatio": (aspect_ratio or "").strip(),
            "imageSize": (image_size or "").strip(),
            "urls": urls or [],
            "host": (host or "").strip(),
            "use_ai": bool(use_ai),
        },
        "remote": {"id": "", "raw": {}},
        "results": [],
        "files": [],
        "prompt_polished": "",
        "prompt_final": "",
    }
    _write_json(meta_path, meta)

    return DrawingPaths(drawing_id=drawing_id, drawing_dir=ddir, meta_path=meta_path)


def get_drawing_meta(output_dir: Path, drawing_id: str) -> dict[str, Any]:
    meta_path = drawings_dir(output_dir) / drawing_id / "meta.json"
    return _read_json(meta_path)


def list_drawings(output_dir: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    base = drawings_dir(output_dir)
    if not base.exists():
        return []

    items: list[dict[str, Any]] = []
    for meta_path in base.glob("*/meta.json"):
        meta = _read_json(meta_path)
        if not meta:
            continue
        items.append(
            {
                "id": meta.get("id") or meta_path.parent.name,
                "state": meta.get("state", ""),
                "progress": meta.get("progress", 0),
                "updated_at": meta.get("updated_at", ""),
                "model": meta.get("request", {}).get("model", ""),
                "prompt": meta.get("request", {}).get("prompt", ""),
                "prompt_final": meta.get("prompt_final", ""),
                "files": meta.get("files", []),
            }
        )

    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items[: max(1, int(limit or 50))]


def delete_drawing(output_dir: Path, drawing_id: str) -> bool:
    base = drawings_dir(output_dir).resolve()
    target = (base / drawing_id).resolve()
    try:
        target.relative_to(base)
    except Exception:
        raise ValueError("invalid drawing id") from None

    if not target.exists():
        return False
    shutil.rmtree(target, ignore_errors=False)
    return True
