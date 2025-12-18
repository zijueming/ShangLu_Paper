from __future__ import annotations

from pathlib import Path


def get_image_size(path: Path) -> tuple[int, int] | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".png":
            return _png_size(path)
        if suffix in {".jpg", ".jpeg"}:
            return _jpeg_size(path)
        if suffix == ".gif":
            return _gif_size(path)
        if suffix == ".webp":
            return _webp_size(path)
    except Exception:
        return None
    return None


def _png_size(path: Path) -> tuple[int, int] | None:
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        chunk_len = int.from_bytes(f.read(4), "big", signed=False)
        chunk_type = f.read(4)
        if chunk_type != b"IHDR" or chunk_len < 8:
            return None
        width = int.from_bytes(f.read(4), "big", signed=False)
        height = int.from_bytes(f.read(4), "big", signed=False)
        return (width, height) if width > 0 and height > 0 else None


def _gif_size(path: Path) -> tuple[int, int] | None:
    with open(path, "rb") as f:
        hdr = f.read(10)
        if len(hdr) < 10:
            return None
        if not (hdr.startswith(b"GIF87a") or hdr.startswith(b"GIF89a")):
            return None
        width = int.from_bytes(hdr[6:8], "little", signed=False)
        height = int.from_bytes(hdr[8:10], "little", signed=False)
        return (width, height) if width > 0 and height > 0 else None


def _jpeg_size(path: Path) -> tuple[int, int] | None:
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            return None

        while True:
            b = f.read(1)
            if not b:
                return None
            if b != b"\xff":
                continue

            # skip fill bytes
            while True:
                marker_b = f.read(1)
                if not marker_b:
                    return None
                if marker_b != b"\xff":
                    break
            marker = marker_b[0]

            # standalone markers without length
            if marker in {0xD8, 0xD9}:
                continue
            if 0xD0 <= marker <= 0xD7:
                continue

            length_bytes = f.read(2)
            if len(length_bytes) != 2:
                return None
            seg_len = int.from_bytes(length_bytes, "big", signed=False)
            if seg_len < 2:
                return None
            payload = f.read(seg_len - 2)
            if len(payload) != seg_len - 2:
                return None

            # SOF markers (baseline/progressive/etc), excluding DHT/DAC/JPG/APP
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                if len(payload) < 7:
                    return None
                height = int.from_bytes(payload[1:3], "big", signed=False)
                width = int.from_bytes(payload[3:5], "big", signed=False)
                return (width, height) if width > 0 and height > 0 else None


def _webp_size(path: Path) -> tuple[int, int] | None:
    with open(path, "rb") as f:
        header = f.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            return None

        chunk_header = f.read(8)
        if len(chunk_header) != 8:
            return None
        chunk_type = chunk_header[:4]
        chunk_size = int.from_bytes(chunk_header[4:8], "little", signed=False)
        payload = f.read(chunk_size)
        if len(payload) != chunk_size:
            return None

        if chunk_type == b"VP8X" and len(payload) >= 10:
            width = 1 + int.from_bytes(payload[4:7], "little", signed=False)
            height = 1 + int.from_bytes(payload[7:10], "little", signed=False)
            return (width, height)

        if chunk_type == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            b1, b2, b3, b4 = payload[1], payload[2], payload[3], payload[4]
            width = 1 + (b1 | ((b2 & 0x3F) << 8))
            height = 1 + (((b2 >> 6) | (b3 << 2) | ((b4 & 0x0F) << 10)) & 0x3FFF)
            return (width, height)

    return None

