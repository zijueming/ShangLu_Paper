from __future__ import annotations

import json
import re
import time
from pathlib import Path

from app.jobs.manager import update_meta

_WS_RE = re.compile(r"\s+")


def normalize_tag(tag: str) -> str:
    tag = _WS_RE.sub(" ", (tag or "").strip())
    tag = tag.strip("#").strip()
    return tag[:32]


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        nt = normalize_tag(str(t))
        if not nt:
            continue
        key = nt.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(nt)
        if len(out) >= 20:
            break
    return out


def _catalog_path(output_dir: Path) -> Path:
    return output_dir / "tags_catalog.json"


def list_catalog_tags(output_dir: Path) -> list[str]:
    path = _catalog_path(output_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("tags"), list):
        tags = [str(x) for x in data.get("tags") if str(x).strip()]
    elif isinstance(data, list):
        tags = [str(x) for x in data if str(x).strip()]
    else:
        tags = []
    return normalize_tags(tags)


def _write_catalog_tags(output_dir: Path, tags: list[str]) -> None:
    path = _catalog_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tags": normalize_tags(tags), "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_catalog_tag(output_dir: Path, tag: str) -> list[str]:
    cur = list_catalog_tags(output_dir)
    nt = normalize_tag(tag)
    if not nt:
        return cur
    merged = normalize_tags(cur + [nt])
    _write_catalog_tags(output_dir, merged)
    return merged


def remove_catalog_tag(output_dir: Path, tag: str) -> list[str]:
    cur = list_catalog_tags(output_dir)
    rm = normalize_tag(tag).lower()
    if not rm:
        return cur
    merged = [t for t in cur if t.lower() != rm]
    _write_catalog_tags(output_dir, merged)
    return merged


def ensure_catalog_tags(output_dir: Path, tags: list[str]) -> list[str]:
    cur = list_catalog_tags(output_dir)
    merged = normalize_tags(cur + [str(x) for x in (tags or [])])
    _write_catalog_tags(output_dir, merged)
    return merged


def apply_job_tags_patch(meta_path: Path, *, add: str | None = None, remove: str | None = None, tags: list[str] | None = None) -> list[str]:
    current: list[str] = []
    if meta_path.exists():
        try:
            import json

            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tags"), list):
                current = [str(x) for x in data.get("tags") if str(x).strip()]
        except Exception:
            current = []

    if tags is not None:
        next_tags = normalize_tags([str(x) for x in tags])
        update_meta(meta_path, {"tags": next_tags})
        return next_tags

    cur_norm = normalize_tags([str(x) for x in current])

    if add:
        add_n = normalize_tag(add)
        if add_n:
            cur_norm = normalize_tags(cur_norm + [add_n])

    if remove:
        rm = normalize_tag(remove).lower()
        if rm:
            cur_norm = [t for t in cur_norm if t.lower() != rm]

    update_meta(meta_path, {"tags": cur_norm})
    return cur_norm


def list_tags(output_dir: Path) -> list[dict]:
    tags: dict[str, dict] = {}
    if not output_dir.exists():
        return []

    for job_dir in output_dir.iterdir():
        if not job_dir.is_dir():
            continue
        meta_path = job_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            continue

        job_id = job_dir.name
        job_tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        job_tags = normalize_tags([str(x) for x in job_tags])
        if not job_tags:
            continue

        # Optional extra info from analysis.json
        title = ""
        authors = ""
        analysis_path = job_dir / "analysis.json"
        if analysis_path.exists():
            try:
                import json

                a = json.loads(analysis_path.read_text(encoding="utf-8"))
                if isinstance(a, dict):
                    title = str(a.get("标题") or a.get("title") or a.get("paper_title") or "").strip()
                    authors = str(a.get("作者") or a.get("authors") or "").strip()
            except Exception:
                pass

        for t in job_tags:
            key = t
            item = tags.get(key)
            if not item:
                item = {"tag": t, "count": 0, "jobs": []}
                tags[key] = item
            item["count"] += 1
            item["jobs"].append({"job_id": job_id, "title": title, "authors": authors})

    # Include catalog tags even if not used by any job.
    for t in list_catalog_tags(output_dir):
        if t not in tags:
            tags[t] = {"tag": t, "count": 0, "jobs": []}

    return sorted(tags.values(), key=lambda x: (-int(x.get("count", 0)), str(x.get("tag", ""))))
