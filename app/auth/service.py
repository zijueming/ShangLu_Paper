from __future__ import annotations

import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.auth.db import init_db
from app.auth.password import hash_password, verify_password


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}$")


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_utc_ts(value: str) -> datetime | None:
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


@dataclass(frozen=True)
class User:
    id: int
    username: str
    is_admin: bool
    created_at: str


def ensure_schema(conn: sqlite3.Connection) -> None:
    init_db(conn)


def normalize_username(username: str) -> str:
    return (username or "").strip()


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username or ""):
        raise ValueError("用户名格式不正确：3-32位，字母/数字开头，可包含 . _ -")


def validate_password(password: str) -> None:
    pw = (password or "")
    if len(pw) < 6:
        raise ValueError("密码至少 6 位")
    if len(pw) > 200:
        raise ValueError("密码过长")


def user_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()
    return int(row["c"] or 0) if row else 0


def get_user_by_username(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT id, username, password_hash, is_admin, created_at FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT id, username, is_admin, created_at FROM users WHERE id = ?", (int(user_id),)).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection, *, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(1000, int(limit or 200)))
    rows = conn.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY id ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    is_admin: bool = False,
) -> User:
    username = normalize_username(username)
    validate_username(username)
    validate_password(password)

    pw_hash = hash_password(password)
    created_at = now_ts()
    try:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, is_admin, created_at) VALUES(?,?,?,?)",
            (username, pw_hash, 1 if is_admin else 0, created_at),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError("用户名已存在") from e
    conn.commit()
    return User(id=int(cur.lastrowid), username=username, is_admin=bool(is_admin), created_at=created_at)


def register_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    invite_code: str = "",
) -> User:
    """
    Register a new user.

    - If this is the first user in DB, invite code is not required and the user becomes admin.
    - Otherwise, invite_code must be valid and will be consumed atomically.
    """
    username = normalize_username(username)
    validate_username(username)
    validate_password(password)

    is_first = user_count(conn) == 0
    is_admin = bool(is_first)
    created_at = now_ts()
    pw_hash = hash_password(password)
    invite_code = (invite_code or "").strip().upper()

    with conn:  # transaction
        if not is_first:
            if not invite_code:
                raise ValueError("邀请码不能为空")
            row = conn.execute(
                "SELECT code, max_uses, uses, disabled FROM invite_codes WHERE code = ?",
                (invite_code,),
            ).fetchone()
            if not row:
                raise ValueError("邀请码无效")
            if int(row["disabled"] or 0) != 0:
                raise ValueError("邀请码已停用")
            if int(row["uses"] or 0) >= int(row["max_uses"] or 1):
                raise ValueError("邀请码已用尽")

        try:
            cur = conn.execute(
                "INSERT INTO users(username, password_hash, is_admin, created_at) VALUES(?,?,?,?)",
                (username, pw_hash, 1 if is_admin else 0, created_at),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError("用户名已存在") from e

        uid = int(cur.lastrowid)
        if not is_first:
            cur2 = conn.execute(
                "UPDATE invite_codes SET uses = uses + 1 WHERE code = ? AND disabled = 0 AND uses < max_uses",
                (invite_code,),
            )
            if cur2.rowcount <= 0:
                raise ValueError("邀请码已用尽")
            conn.execute("INSERT INTO invite_uses(code, user_id, used_at) VALUES(?,?,?)", (invite_code, uid, now_ts()))

    return User(id=uid, username=username, is_admin=is_admin, created_at=created_at)


def set_user_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> None:
    validate_password(new_password)
    pw_hash = hash_password(new_password)
    cur = conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, int(user_id)))
    if cur.rowcount <= 0:
        raise ValueError("用户不存在")
    conn.commit()


def authenticate(conn: sqlite3.Connection, *, username: str, password: str) -> User:
    username = normalize_username(username)
    row = get_user_by_username(conn, username)
    if not row:
        raise ValueError("用户名或密码错误")
    if not verify_password(password, row.get("password_hash") or ""):
        raise ValueError("用户名或密码错误")
    return User(id=int(row["id"]), username=str(row["username"]), is_admin=bool(row["is_admin"]), created_at=str(row["created_at"]))


def _generate_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def list_invites(conn: sqlite3.Connection, *, limit: int = 300) -> list[dict[str, Any]]:
    limit = max(1, min(2000, int(limit or 300)))
    rows = conn.execute(
        """
        SELECT code, max_uses, uses, disabled, created_at, created_by
        FROM invite_codes
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_invite(
    conn: sqlite3.Connection,
    *,
    created_by: int | None,
    max_uses: int = 1,
    code: str = "",
) -> dict[str, Any]:
    max_uses = max(1, min(100, int(max_uses or 1)))
    code = (code or "").strip().upper()
    if code:
        if len(code) < 6 or len(code) > 32:
            raise ValueError("邀请码长度需 6-32")
        if not re.match(r"^[A-Z0-9_-]+$", code):
            raise ValueError("邀请码只能包含 A-Z/0-9/_/-")
    else:
        code = _generate_invite_code()

    created_at = now_ts()
    try:
        conn.execute(
            "INSERT INTO invite_codes(code, max_uses, uses, disabled, created_at, created_by) VALUES(?,?,?,?,?,?)",
            (code, max_uses, 0, 0, created_at, int(created_by) if created_by is not None else None),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError("邀请码已存在") from e
    conn.commit()
    return {"code": code, "max_uses": max_uses, "uses": 0, "disabled": 0, "created_at": created_at}


def set_invite_disabled(conn: sqlite3.Connection, code: str, *, disabled: bool) -> None:
    code = (code or "").strip().upper()
    cur = conn.execute("UPDATE invite_codes SET disabled = ? WHERE code = ?", (1 if disabled else 0, code))
    if cur.rowcount <= 0:
        raise ValueError("邀请码不存在")
    conn.commit()


def consume_invite(conn: sqlite3.Connection, code: str, *, user_id: int) -> None:
    code = (code or "").strip().upper()
    if not code:
        raise ValueError("邀请码不能为空")

    with conn:  # transaction
        row = conn.execute(
            "SELECT code, max_uses, uses, disabled FROM invite_codes WHERE code = ?",
            (code,),
        ).fetchone()
        if not row:
            raise ValueError("邀请码无效")
        if int(row["disabled"] or 0) != 0:
            raise ValueError("邀请码已停用")
        max_uses = int(row["max_uses"] or 1)
        uses = int(row["uses"] or 0)
        if uses >= max_uses:
            raise ValueError("邀请码已用尽")

        conn.execute("UPDATE invite_codes SET uses = uses + 1 WHERE code = ?", (code,))
        conn.execute(
            "INSERT INTO invite_uses(code, user_id, used_at) VALUES(?,?,?)",
            (code, int(user_id), now_ts()),
        )


def create_session(conn: sqlite3.Connection, *, user_id: int, ttl_s: int = 14 * 24 * 3600) -> str:
    ttl_s = max(300, min(180 * 24 * 3600, int(ttl_s or 0)))
    token = secrets.token_urlsafe(32)
    created = utc_now()
    expires = created + timedelta(seconds=ttl_s)
    ts = utc_ts(created)
    with conn:
        conn.execute(
            "INSERT INTO sessions(token, user_id, created_at, last_seen_at, expires_at) VALUES(?,?,?,?,?)",
            (token, int(user_id), ts, ts, utc_ts(expires)),
        )
    return token


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    with conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def cleanup_expired_sessions(conn: sqlite3.Connection) -> int:
    now = utc_ts(utc_now())
    with conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return int(cur.rowcount or 0)


def get_user_by_session(conn: sqlite3.Connection, token: str) -> User | None:
    token = (token or "").strip()
    if not token:
        return None
    row = conn.execute(
        """
        SELECT s.token, s.user_id, s.expires_at, u.username, u.is_admin, u.created_at
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    if not row:
        return None
    exp = parse_utc_ts(str(row["expires_at"] or ""))
    if not exp or exp < utc_now():
        delete_session(conn, token)
        return None

    with conn:
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token = ?", (utc_ts(utc_now()), token))

    return User(
        id=int(row["user_id"]),
        username=str(row["username"]),
        is_admin=bool(row["is_admin"]),
        created_at=str(row["created_at"]),
    )
