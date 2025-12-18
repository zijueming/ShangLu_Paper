"""
Zip helper with path safety (prevents Zip Slip).
"""

from __future__ import annotations

import posixpath
import shutil
import zipfile
from pathlib import Path


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            name = (info.filename or "").replace("\\", "/")
            norm = posixpath.normpath(name)
            parts = [p for p in norm.split("/") if p and p != "."]
            if not parts:
                continue
            if any(p == ".." for p in parts):
                raise ValueError(f"unsafe zip member: {info.filename}")

            out_path = (dest_dir / Path(*parts)).resolve()
            if dest_root not in out_path.parents and out_path != dest_root:
                raise ValueError(f"zip slip detected: {info.filename}")

            if getattr(info, "is_dir", None) and info.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
