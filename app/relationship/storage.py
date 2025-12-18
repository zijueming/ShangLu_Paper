from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def relationship_dir(output_dir: Path) -> Path:
    return output_dir / "relationship_graph"


@dataclass(frozen=True)
class RelationshipPaths:
    base_dir: Path
    meta_path: Path
    graph_path: Path


def get_relationship_paths(output_dir: Path) -> RelationshipPaths:
    base = relationship_dir(output_dir)
    return RelationshipPaths(base_dir=base, meta_path=base / "meta.json", graph_path=base / "graph.json")


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


def read_relationship_meta(output_dir: Path) -> dict[str, Any]:
    paths = get_relationship_paths(output_dir)
    meta = _read_json(paths.meta_path)
    if not meta:
        meta = {"state": "idle", "updated_at": ""}
    if not isinstance(meta.get("state"), str):
        meta["state"] = "idle"
    return meta


def read_relationship_graph(output_dir: Path) -> dict[str, Any]:
    paths = get_relationship_paths(output_dir)
    return _read_json(paths.graph_path)


def update_relationship_meta(output_dir: Path, patch: dict[str, Any]) -> dict[str, Any]:
    paths = get_relationship_paths(output_dir)
    base = _read_json(paths.meta_path)
    patch = dict(patch or {})
    patch["updated_at"] = _now_ts()
    base.update(patch)
    _write_json(paths.meta_path, base)
    return base


def write_relationship_graph(output_dir: Path, graph: dict[str, Any]) -> None:
    paths = get_relationship_paths(output_dir)
    _write_json(paths.graph_path, graph or {})

