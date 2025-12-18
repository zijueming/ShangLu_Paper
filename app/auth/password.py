from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def hash_password(password: str, *, iterations: int = 180_000) -> str:
    password = (password or "").encode("utf-8")
    if not password:
        raise ValueError("empty password")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password, salt, int(iterations), dklen=32)
    return "pbkdf2_sha256$%d$%s$%s" % (
        int(iterations),
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(dk).decode("ascii").rstrip("="),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        alg, it_s, salt_b64, dk_b64 = (stored or "").split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        iterations = int(it_s)
        salt = base64.urlsafe_b64decode(_pad_b64(salt_b64))
        expected = base64.urlsafe_b64decode(_pad_b64(dk_b64))
    except Exception:
        return False

    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(dk, expected)


def _pad_b64(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    pad = "=" * ((4 - (len(v) % 4)) % 4)
    return v + pad

