from __future__ import annotations

import json
import re
import shutil
import threading
import urllib.parse
from datetime import date, datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.auth import (
    authenticate,
    cleanup_expired_sessions,
    connect as auth_connect,
    create_invite,
    create_session,
    delete_session,
    ensure_schema,
    get_user_by_session,
    list_invites,
    list_users,
    register_user,
    set_invite_disabled,
    set_user_password,
    user_count,
    validate_password,
)
from app.clients.deepseek import DeepSeekClient
from app.clients.grsai import GrsaiClient
from app.draw import create_drawing, delete_drawing, get_drawing_meta, list_drawings, start_drawing_worker
from app.draw.prompt import polish_draw_prompt
from app.jobs.manager import JobPaths, create_job, run_analyze_to_job, run_mineru_to_job, run_translate_to_job, update_meta
from app.relationship import read_relationship_graph, read_relationship_meta, start_build_relationship_graph
from app.tags import add_catalog_tag, apply_job_tags_patch, ensure_catalog_tags, list_catalog_tags, list_tags, remove_catalog_tag
from app.ui.pages import (
    render_account,
    render_admin,
    render_draw,
    render_home,
    render_job,
    render_landing,
    render_login,
    render_register,
    render_relationship,
    render_tags,
    render_translate,
    render_weekly,
)
from app.utils.image_probe import get_image_size
from app.weekly import create_weekly_report, get_weekly_report, list_weekly_reports


def _guess_hint(pdf: str) -> str:
    pdf = (pdf or "").strip()
    try:
        p = Path(pdf)
        return p.stem or "paper"
    except Exception:
        return "paper"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sanitize_job_id(job_id: str) -> str | None:
    job_id = (job_id or "").strip().strip("/")
    if not job_id:
        return None
    if "/" in job_id or "\\" in job_id or ".." in job_id:
        return None
    return job_id


def _sanitize_draw_id(drawing_id: str) -> str | None:
    drawing_id = (drawing_id or "").strip().strip("/")
    if not drawing_id:
        return None
    if "/" in drawing_id or "\\" in drawing_id or ".." in drawing_id:
        return None
    if len(drawing_id) > 80:
        return None
    return drawing_id


def _job_dt(job_id: str, meta: dict) -> datetime | None:
    m = re.match(r"^(\d{8})_(\d{6})", job_id or "")
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S")
        except Exception:
            pass

    updated_at = (meta.get("updated_at") or "").strip()
    if updated_at:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(updated_at, fmt)
            except Exception:
                continue
    return None


def _analysis_summary(analysis_path: Path) -> tuple[str, str, str]:
    a = _read_json(analysis_path)
    title = (a.get("标题") or a.get("title") or a.get("paper_title") or "").strip()
    authors = (a.get("作者") or a.get("authors") or "").strip()
    year = str(a.get("年份") or a.get("year") or "").strip()
    return title, authors, year


def _compact_str_list(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for x in value:
        s = str(x).strip()
        if not s:
            continue
        items.append(s)
        if len(items) >= limit:
            break
    return items


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items if str(x).strip())


def _extract_relevant_snippets(markdown: str, query: str, *, max_chars: int = 1800, max_chunks: int = 3) -> str:
    q = (query or "").strip()
    if len(q) < 2:
        return ""

    text = (markdown or "").strip()
    if not text:
        return ""

    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return ""

    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", q)
    tokens_norm = [t.lower() for t in tokens if t and len(t) >= 2]
    if not tokens_norm:
        tokens_norm = [q.lower()]

    scored: list[tuple[int, str]] = []
    for p in paragraphs:
        p_norm = p.lower()
        score = sum(p_norm.count(t) for t in tokens_norm)
        if score <= 0:
            continue
        scored.append((score, p))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [p for _, p in scored[: max(1, int(max_chunks))]]

    out_parts: list[str] = []
    remain = max(0, int(max_chars))
    for p in picked:
        if remain <= 0:
            break
        seg = p.strip()
        if len(seg) > 900:
            seg = seg[:900].rstrip() + "…"
        if len(seg) + 5 > remain:
            seg = seg[: max(0, remain - 5)].rstrip() + "…"
        if not seg:
            continue
        out_parts.append(seg)
        remain -= len(seg) + 5

    return "\n\n---\n\n".join(out_parts).strip()


def _build_job_chat_context(
    output_dir: Path,
    job_id: str,
    *,
    question: str = "",
    mode: str = "lite",
    include_snippets: bool = False,
    snippets_max_chars: int = 1800,
) -> str:
    job_dir = output_dir / job_id
    meta = _read_json(job_dir / "meta.json")
    analysis = _read_json(job_dir / "analysis.json")

    title = (analysis.get("标题") or analysis.get("title") or analysis.get("paper_title") or "").strip()
    authors = (analysis.get("作者") or analysis.get("authors") or "").strip()
    abstract = (analysis.get("摘要") or analysis.get("abstract") or "").strip()

    parts: list[str] = [f"论文ID: {job_id}"]
    if title:
        parts.append(f"标题: {title}")
    if authors:
        parts.append(f"作者: {authors}")

    tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    tags = [str(t).strip() for t in tags if str(t).strip()]
    if tags:
        parts.append("标签: " + ", ".join(tags[:12]))

    if abstract:
        parts.append("摘要:\n" + abstract)

    limits = {"lite": 6, "full": 12}
    limit = limits.get((mode or "").strip().lower(), 6)

    sections: list[tuple[str, Any]] = [
        ("主要结论", analysis.get("主要结论") or analysis.get("main_conclusions")),
        ("创新点", analysis.get("创新点") or analysis.get("innovations")),
        ("实验方法", analysis.get("实验方法") or analysis.get("methods")),
        ("不足之处", analysis.get("不足") or analysis.get("limitations")),
        ("研究启发", analysis.get("研究启发") or analysis.get("insights")),
    ]
    for label, value in sections:
        items = _compact_str_list(value, limit=limit)
        if items:
            parts.append(f"{label}:\n{_format_bullets(items)}")

    if (mode or "").strip().lower() == "full":
        steps = analysis.get("实验详细步骤") or analysis.get("experimental_steps")
        if isinstance(steps, list):
            lines: list[str] = []
            for item in steps[:10]:
                if not isinstance(item, dict):
                    continue
                idx = item.get("步骤") or item.get("step")
                content = str(item.get("内容") or item.get("content") or "").strip()
                if content:
                    lines.append(f"- {idx}. {content}" if idx is not None else f"- {content}")
            if lines:
                parts.append("实验详细步骤:\n" + "\n".join(lines))

        terms = analysis.get("术语解释") or analysis.get("terms") or analysis.get("glossary")
        if isinstance(terms, list):
            lines = []
            for item in terms[:12]:
                if not isinstance(item, dict):
                    continue
                term = str(item.get("术语") or item.get("term") or "").strip()
                desc = str(item.get("解释") or item.get("definition") or "").strip()
                if term and desc:
                    lines.append(f"- {term}: {desc}")
            if lines:
                parts.append("术语解释:\n" + "\n".join(lines))

    if include_snippets and question:
        preferred = job_dir / "result" / "translated.md"
        fallback = job_dir / "result" / "full.md"
        md_path = preferred if preferred.exists() else fallback if fallback.exists() else None
        if md_path:
            md_text = md_path.read_text(encoding="utf-8", errors="replace")
            snippets = _extract_relevant_snippets(md_text, question, max_chars=snippets_max_chars)
            if snippets:
                parts.append(f"与问题相关的片段（来自 {md_path.name}，可能截断）:\n{snippets}")

    return "\n\n".join(parts).strip()


def _list_jobs(output_dir: Path, *, start: date | None = None, end: date | None = None) -> list[dict]:
    items: list[dict] = []
    if not output_dir.exists():
        return items

    for p in output_dir.iterdir():
        if not p.is_dir():
            continue

        meta_path = p / "meta.json"
        result_md = p / "result" / "full.md"
        if not meta_path.exists() and not result_md.exists():
            continue

        meta = _read_json(meta_path)
        dt = _job_dt(p.name, meta)
        if start or end:
            if not dt:
                continue
            d = dt.date()
            if start and d < start:
                continue
            if end and d > end:
                continue

        analysis_path = p / "analysis.json"
        title, authors, year = ("", "", "")
        if analysis_path.exists():
            title, authors, year = _analysis_summary(analysis_path)

        tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        tags = [str(x).strip() for x in tags if str(x).strip()]
        translate_state = str(meta.get("translate_state") or "").strip()
        translate_language = str(meta.get("translate_language") or "").strip()
        has_translation = (p / "result" / "translated.md").exists()

        items.append(
            {
                "job_id": p.name,
                "state": meta.get("state", ""),
                "pdf": meta.get("pdf", meta.get("pdf_original", "")),
                "has_analysis": analysis_path.exists(),
                "updated_at": meta.get("updated_at", ""),
                "title": title,
                "authors": authors,
                "year": year,
                "tags": tags,
                "translate_state": translate_state,
                "translate_language": translate_language,
                "has_translation": has_translation,
            }
        )

    return sorted(items, key=lambda x: x.get("job_id", ""), reverse=True)


def _safe_rel_url(output_dir: Path, file_path: Path) -> str:
    rel = file_path.resolve().relative_to(output_dir.resolve())
    return "/" + urllib.parse.quote(str(rel).replace("\\", "/"))


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")


def _images_from_markdown(result_dir: Path) -> list[Path]:
    md_path = result_dir / "full.md"
    if not md_path.exists():
        return []
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    out: list[Path] = []
    for m in _MD_IMAGE_RE.finditer(text):
        raw = (m.group(1) or "").strip()
        if not raw or raw.startswith("http://") or raw.startswith("https://"):
            continue
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1].strip()
        raw = raw.split()[0].strip()
        raw = urllib.parse.unquote(raw)
        p = (result_dir / raw).resolve()
        try:
            p.relative_to(result_dir.resolve())
        except Exception:
            continue
        if p.exists() and p.is_file():
            out.append(p)
    return out


def _is_likely_figure(path: Path) -> bool:
    try:
        size_bytes = path.stat().st_size
    except Exception:
        return False

    dims = get_image_size(path)
    if dims:
        w, h = dims
        if min(w, h) < 220:
            return False
        if (w * h) < 120_000:
            return False
        aspect = max(w / h, h / w)
        if aspect > 8.0:
            return False
        return True

    return size_bytes >= 80_000


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _collect_image_candidates(result_dir: Path) -> list[Path]:
    ordered: list[Path] = []
    for p in _images_from_markdown(result_dir):
        if p.suffix.lower() in _IMAGE_EXTS:
            ordered.append(p)

    seen = {p.resolve() for p in ordered}
    discovered: list[Path] = []
    for p in result_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
            rp = p.resolve()
            if rp not in seen:
                discovered.append(p)

    discovered.sort(key=lambda x: x.name)
    return ordered + discovered


def _key_figures(candidates: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in candidates:
        if _is_likely_figure(p):
            out.append(p)
    return out or candidates


def _list_figures(output_dir: Path, job_id: str, *, limit: int = 8, mode: str = "key") -> dict[str, Any]:
    result_dir = output_dir / job_id / "result"
    if not result_dir.exists():
        return {"figures": [], "total": 0, "mode": mode, "limit": limit}

    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 8

    max_limit = 400
    if limit_i < 1:
        limit_i = max_limit
    limit_i = min(limit_i, max_limit)

    candidates = _collect_image_candidates(result_dir)
    mode_norm = (mode or "key").strip().lower()
    selected = candidates if mode_norm == "all" else _key_figures(candidates)
    total = len(selected)

    return {
        "figures": [_safe_rel_url(output_dir, p) for p in selected[:limit_i]],
        "total": total,
        "mode": "all" if mode_norm == "all" else "key",
        "limit": limit_i,
    }


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, output_dir: Path | None = None, **kwargs):
        self._base_output_dir = (output_dir or Path(directory or ".")).resolve()
        self._output_dir = self._base_output_dir
        self._assets_dir = Path(__file__).resolve().parent / "assets"
        self._cached_user = None
        super().__init__(*args, directory=str(self._base_output_dir), **kwargs)

    _SESSION_COOKIE_NAME = "sl_session"
    _SESSION_TTL_S = 14 * 24 * 3600

    def _db(self):
        conn = auth_connect(self._base_output_dir)
        ensure_schema(conn)
        return conn

    def _get_cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        try:
            c = SimpleCookie()
            c.load(raw)
            morsel = c.get(name)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def _set_cookie_header(self, name: str, value: str, *, max_age: int | None = None) -> str:
        parts = [f"{name}={value}", "Path=/", "HttpOnly", "SameSite=Lax"]
        if max_age is not None:
            parts.append(f"Max-Age={int(max_age)}")
        return "; ".join(parts)

    def _clear_session_cookie(self) -> str:
        return self._set_cookie_header(self._SESSION_COOKIE_NAME, "", max_age=0)

    def _load_user(self):
        if self._cached_user is not None:
            return self._cached_user
        token = self._get_cookie(self._SESSION_COOKIE_NAME)
        if not token:
            self._cached_user = None
            return None
        conn = self._db()
        try:
            cleanup_expired_sessions(conn)
            user = get_user_by_session(conn, token)
            self._cached_user = user
            return user
        finally:
            conn.close()

    def _user_output_dir(self, user_id: int) -> Path:
        uid = int(user_id)
        return (self._base_output_dir / "users" / str(uid)).resolve()

    def _apply_user_context(self, user) -> None:
        if not user:
            return
        udir = self._user_output_dir(user.id)
        udir.mkdir(parents=True, exist_ok=True)
        self._output_dir = udir
        # Used by SimpleHTTPRequestHandler for static files.
        self.directory = str(udir)

    def _redirect(self, location: str, *, headers: dict[str, str] | None = None, status: int = 302) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _require_user(self, *, api: bool) -> Any:
        user = self._load_user()
        if user:
            self._apply_user_context(user)
            return user
        if api:
            self._send_json({"error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return None
        self._redirect("/")
        return None

    def _is_json_request(self) -> bool:
        ctype = (self.headers.get("Content-Type", "") or "").lower()
        return "application/json" in ctype

    def _read_urlencoded_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        if not body:
            return {}
        try:
            params = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
            return {k: (v[0] if isinstance(v, list) and v else "") for k, v in params.items()}
        except Exception:
            return {}

    def _read_form(self) -> dict[str, Any]:
        ctype = (self.headers.get("Content-Type", "") or "").lower()
        if "application/json" in ctype:
            return self._read_json_body()
        if "application/x-www-form-urlencoded" in ctype:
            return self._read_urlencoded_body()
        # Fallback: try JSON, then urlencoded.
        data = self._read_json_body()
        return data if data else self._read_urlencoded_body()

    def do_GET(self):  # noqa: N802
        self._cached_user = None
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query or "")

        if path.startswith("/assets/"):
            name = path[len("/assets/") :].strip("/")
            return self._send_asset(name)

        if path in ("/login", "/login/"):
            if self._load_user():
                return self._redirect("/")
            err = (query.get("error") or [""])[0].strip()
            next_url = (query.get("next") or ["/"])[0].strip() or "/"
            return self._send_html(render_login(error=err, next_url=next_url))

        if path in ("/register", "/register/"):
            if self._load_user():
                return self._redirect("/")
            err = (query.get("error") or [""])[0].strip()
            next_url = (query.get("next") or ["/"])[0].strip() or "/"
            conn = self._db()
            try:
                require_invite = user_count(conn) > 0
            finally:
                conn.close()
            return self._send_html(render_register(error=err, require_invite=require_invite, next_url=next_url))

        if path in ("/logout", "/logout/"):
            token = self._get_cookie(self._SESSION_COOKIE_NAME)
            if token:
                conn = self._db()
                try:
                    delete_session(conn, token)
                finally:
                    conn.close()
            return self._redirect("/login/", headers={"Set-Cookie": self._clear_session_cookie()})

        if path.startswith("/api/"):
            return self._handle_api_get(parsed)

        user = self._load_user()
        if path in ("/", "/index.html"):
            if user:
                self._apply_user_context(user)
                return self._send_html(render_home())
            return self._send_html(render_landing())

        if not user:
            next_url = urllib.parse.quote(self.path or "/")
            return self._redirect(f"/login/?next={next_url}")
        self._apply_user_context(user)

        if path.startswith("/job/"):
            job = _sanitize_job_id(urllib.parse.unquote(path[len("/job/") :]))
            if not job:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)
            return self._send_html(render_job(job))

        if path in ("/weekly", "/weekly/"):
            return self._send_html(render_weekly())

        if path in ("/draw", "/draw/"):
            return self._send_html(render_draw())

        if path in ("/tags", "/tags/"):
            return self._send_html(render_tags())

        if path in ("/translate", "/translate/"):
            return self._send_html(render_translate())

        if path in ("/relationship", "/relationship/"):
            return self._send_html(render_relationship())

        if path in ("/account", "/account/"):
            notice = (query.get("notice") or [""])[0].strip()
            err = (query.get("error") or [""])[0].strip()
            return self._send_html(render_account(username=user.username, is_admin=bool(user.is_admin), notice=notice, error=err))

        if path in ("/admin", "/admin/"):
            if not bool(getattr(user, "is_admin", False)):
                return self._redirect("/account/?error=" + urllib.parse.quote("需要管理员权限"))
            notice = (query.get("notice") or [""])[0].strip()
            err = (query.get("error") or [""])[0].strip()
            conn = self._db()
            try:
                invites = list_invites(conn)
                users = list_users(conn)
            finally:
                conn.close()
            return self._send_html(render_admin(username=user.username, invites=invites, users=users, notice=notice, error=err))

        if path.startswith("/view/"):
            job = _sanitize_job_id(urllib.parse.unquote(path[len("/view/") :]))
            if not job:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)

            from app.viewer.web import ensure_extracted as viewer_ensure_extracted
            from app.viewer.web import _render_view as viewer_render_view

            try:
                viewer_ensure_extracted(self._output_dir, job)
            except Exception as e:
                return self._send_html(
                    f"<pre style='white-space:pre-wrap'>Cannot prepare preview: {str(e)}</pre>",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            return self._send_html(viewer_render_view(job))

        return super().do_GET()

    def do_POST(self):  # noqa: N802
        self._cached_user = None
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        return self._handle_api_post(parsed)

    def _handle_api_get(self, parsed: urllib.parse.ParseResult) -> None:
        user = self._require_user(api=True)
        if not user:
            return
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query or "")

        if path == "/api/me":
            return self._send_json({"user": {"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}})

        if path == "/api/jobs":
            start = (query.get("start") or [""])[0].strip()
            end = (query.get("end") or [""])[0].strip()
            start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
            end_d = datetime.strptime(end, "%Y-%m-%d").date() if end else None
            return self._send_json({"jobs": _list_jobs(self._output_dir, start=start_d, end=end_d)})

        if path == "/api/draw/list":
            limit_raw = (query.get("limit") or [""])[0].strip()
            try:
                limit = int(limit_raw) if limit_raw else 50
            except Exception:
                limit = 50
            return self._send_json({"drawings": list_drawings(self._output_dir, limit=limit)})

        if path.startswith("/api/draw/"):
            drawing_id = _sanitize_draw_id(urllib.parse.unquote(path[len("/api/draw/") :]))
            if not drawing_id:
                return self._send_json({"error": "invalid drawing id"}, status=HTTPStatus.NOT_FOUND)
            meta = get_drawing_meta(self._output_dir, drawing_id)
            if not meta:
                return self._send_json({"error": "drawing not found"}, status=HTTPStatus.NOT_FOUND)
            return self._send_json(meta)

        if path == "/api/relationship":
            meta = read_relationship_meta(self._output_dir)
            graph = read_relationship_graph(self._output_dir)
            return self._send_json({"meta": meta, "graph": graph})

        if path.startswith("/api/jobs/") and path.endswith("/meta"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/meta")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)
            meta = _read_json(self._output_dir / job_id / "meta.json")
            if not isinstance(meta.get("tags"), list):
                meta["tags"] = []
            meta["has_translation"] = (self._output_dir / job_id / "result" / "translated.md").exists()
            return self._send_json(meta)

        if path.startswith("/api/jobs/") and path.endswith("/analysis"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/analysis")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)
            analysis_path = self._output_dir / job_id / "analysis.json"
            if not analysis_path.exists():
                return self._send_json({"error": "analysis not found"}, status=HTTPStatus.NOT_FOUND)
            return self._send_json(_read_json(analysis_path))

        if path.startswith("/api/jobs/") and path.endswith("/figures"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/figures")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)
            limit_raw = (query.get("limit") or [""])[0].strip()
            mode = (query.get("mode") or ["key"])[0].strip()
            try:
                limit = int(limit_raw) if limit_raw else 8
            except Exception:
                limit = 8
            return self._send_json(_list_figures(self._output_dir, job_id, limit=limit, mode=mode))

        if path == "/api/weekly/list":
            return self._send_json({"reports": list_weekly_reports(self._output_dir)})

        if path == "/api/tags":
            return self._send_json({"tags": list_tags(self._output_dir)})

        if path == "/api/tags/catalog":
            # Tag options for dropdown selection: include catalog + already-used job tags.
            tags = [str(x.get("tag") or "").strip() for x in list_tags(self._output_dir)]
            tags = [t for t in tags if t]
            return self._send_json({"tags": tags})

        if path.startswith("/api/weekly/"):
            report_id = path[len("/api/weekly/") :].strip("/")
            if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
                return self._send_json({"error": "invalid report id"}, status=HTTPStatus.NOT_FOUND)
            rep = get_weekly_report(self._output_dir, report_id)
            markdown = rep.read_markdown()
            open_url = f"/weekly_reports/{urllib.parse.quote(report_id)}.md" if markdown else ""
            return self._send_json({"report_id": report_id, "meta": rep.read_meta(), "markdown": markdown, "open_url": open_url})

        return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_api_post(self, parsed: urllib.parse.ParseResult) -> None:
        path = parsed.path

        if path == "/api/auth/login":
            payload = self._read_form()
            username = str(payload.get("username") or "").strip()
            password = str(payload.get("password") or "").strip()
            next_url = str(payload.get("next") or "").strip()
            if not next_url.startswith("/"):
                next_url = "/"

            if not username or not password:
                if self._is_json_request():
                    return self._send_json({"error": "missing username/password"}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/login/?error=" + urllib.parse.quote("请输入用户名和密码"))

            conn = self._db()
            try:
                u = authenticate(conn, username=username, password=password)
                token = create_session(conn, user_id=u.id, ttl_s=self._SESSION_TTL_S)
            except Exception as e:
                if self._is_json_request():
                    return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/login/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()

            headers = {"Set-Cookie": self._set_cookie_header(self._SESSION_COOKIE_NAME, token, max_age=self._SESSION_TTL_S)}
            if self._is_json_request():
                return self._send_json({"ok": True, "user": {"username": u.username, "is_admin": bool(u.is_admin)}}, headers=headers)
            return self._redirect(next_url or "/", headers=headers)

        if path == "/api/auth/register":
            payload = self._read_form()
            username = str(payload.get("username") or "").strip()
            password = str(payload.get("password") or "").strip()
            invite_code = str(payload.get("invite_code") or "").strip()
            next_url = str(payload.get("next") or "").strip()
            if not next_url.startswith("/"):
                next_url = "/"

            if not username or not password:
                if self._is_json_request():
                    return self._send_json({"error": "missing username/password"}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/register/?error=" + urllib.parse.quote("请输入用户名和密码"))

            conn = self._db()
            try:
                u = register_user(conn, username=username, password=password, invite_code=invite_code)
                token = create_session(conn, user_id=u.id, ttl_s=self._SESSION_TTL_S)
            except Exception as e:
                if self._is_json_request():
                    return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/register/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()

            headers = {"Set-Cookie": self._set_cookie_header(self._SESSION_COOKIE_NAME, token, max_age=self._SESSION_TTL_S)}
            if self._is_json_request():
                return self._send_json({"ok": True, "user": {"username": u.username, "is_admin": bool(u.is_admin)}}, headers=headers)
            return self._redirect(next_url or "/", headers=headers)

        if path == "/api/auth/logout":
            token = self._get_cookie(self._SESSION_COOKIE_NAME)
            if token:
                conn = self._db()
                try:
                    delete_session(conn, token)
                finally:
                    conn.close()
            headers = {"Set-Cookie": self._clear_session_cookie()}
            if self._is_json_request():
                return self._send_json({"ok": True}, headers=headers)
            return self._redirect("/login/", headers=headers)

        user = self._require_user(api=True)
        if not user:
            return

        if path == "/api/account/password":
            payload = self._read_form()
            old_pw = str(payload.get("old_password") or "").strip()
            new_pw = str(payload.get("new_password") or "").strip()
            new_pw2 = str(payload.get("new_password2") or "").strip()
            if not old_pw or not new_pw:
                if self._is_json_request():
                    return self._send_json({"error": "missing password"}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/account/?error=" + urllib.parse.quote("请输入完整信息"))
            if new_pw != new_pw2:
                if self._is_json_request():
                    return self._send_json({"error": "password mismatch"}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/account/?error=" + urllib.parse.quote("两次输入的新密码不一致"))
            try:
                validate_password(new_pw)
            except Exception as e:
                if self._is_json_request():
                    return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/account/?error=" + urllib.parse.quote(str(e)))

            conn = self._db()
            try:
                authenticate(conn, username=user.username, password=old_pw)
                set_user_password(conn, user.id, new_pw)
            except Exception as e:
                if self._is_json_request():
                    return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
                return self._redirect("/account/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()

            if self._is_json_request():
                return self._send_json({"ok": True})
            return self._redirect("/account/?notice=" + urllib.parse.quote("密码已更新"))

        if path == "/api/admin/invites/create":
            if not bool(getattr(user, "is_admin", False)):
                return self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)
            payload = self._read_form()
            code = str(payload.get("code") or "").strip()
            try:
                max_uses = int(payload.get("max_uses") or 1)
            except Exception:
                max_uses = 1

            conn = self._db()
            try:
                inv = create_invite(conn, created_by=user.id, max_uses=max_uses, code=code)
            except Exception as e:
                return self._redirect("/admin/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()

            return self._redirect("/admin/?notice=" + urllib.parse.quote(f"已创建邀请码：{inv.get('code')}"))

        if path.startswith("/api/admin/invites/") and path.endswith("/disable"):
            if not bool(getattr(user, "is_admin", False)):
                return self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)
            code = path[len("/api/admin/invites/") : -len("/disable")].strip("/")
            payload = self._read_form()
            disabled = str(payload.get("disabled") or "1").strip()
            disabled_bool = disabled not in {"0", "false", "False", ""}
            conn = self._db()
            try:
                set_invite_disabled(conn, code, disabled=disabled_bool)
            except Exception as e:
                return self._redirect("/admin/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()
            return self._redirect("/admin/?notice=" + urllib.parse.quote("已更新邀请码状态"))

        if path.startswith("/api/admin/users/") and path.endswith("/password"):
            if not bool(getattr(user, "is_admin", False)):
                return self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)
            uid_raw = path[len("/api/admin/users/") : -len("/password")].strip("/")
            try:
                uid = int(uid_raw)
            except Exception:
                return self._redirect("/admin/?error=" + urllib.parse.quote("用户ID无效"))

            payload = self._read_form()
            new_pw = str(payload.get("new_password") or "").strip()
            if not new_pw:
                return self._redirect("/admin/?error=" + urllib.parse.quote("请输入新密码"))
            try:
                validate_password(new_pw)
            except Exception as e:
                return self._redirect("/admin/?error=" + urllib.parse.quote(str(e)))

            conn = self._db()
            try:
                set_user_password(conn, uid, new_pw)
            except Exception as e:
                return self._redirect("/admin/?error=" + urllib.parse.quote(str(e)))
            finally:
                conn.close()
            return self._redirect("/admin/?notice=" + urllib.parse.quote("已重置用户密码"))

        if path == "/api/draw/polish":
            payload = self._read_json_body()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                return self._send_json({"error": "missing prompt"}, status=HTTPStatus.BAD_REQUEST)
            try:
                client = DeepSeekClient.from_config()
                out = polish_draw_prompt(prompt, client)
            except Exception as e:
                return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json({"prompt": out})

        if path == "/api/draw/create":
            payload = self._read_json_body()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                return self._send_json({"error": "missing prompt"}, status=HTTPStatus.BAD_REQUEST)

            prompt_override = str(payload.get("prompt_override") or "").strip()

            model = str(payload.get("model") or "nano-banana-fast").strip() or "nano-banana-fast"
            aspect_ratio = str(payload.get("aspectRatio") or "auto").strip() or "auto"
            image_size = str(payload.get("imageSize") or "1K").strip() or "1K"
            host = str(payload.get("host") or "").strip()
            use_ai = bool(payload.get("use_ai", True))

            urls_raw = payload.get("urls") or []
            urls: list[str] = []
            if isinstance(urls_raw, str):
                urls = [x.strip() for x in urls_raw.splitlines() if x.strip()]
            elif isinstance(urls_raw, list):
                urls = [str(x).strip() for x in urls_raw if str(x).strip()]

            drawing = create_drawing(
                self._output_dir,
                prompt=prompt,
                prompt_override=prompt_override,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                urls=urls,
                host=host,
                use_ai=use_ai,
            )
            start_drawing_worker(
                drawing,
                output_dir=self._output_dir,
                prompt=prompt,
                prompt_override=prompt_override,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                urls=urls,
                host=host,
                use_ai=use_ai,
            )
            return self._send_json({"id": drawing.drawing_id})

        if path == "/api/relationship/build":
            payload = self._read_json_body()
            try:
                max_papers = int(payload.get("max_papers") or 30)
            except Exception:
                max_papers = 30
            force = bool(payload.get("force", False))
            try:
                meta = start_build_relationship_graph(self._output_dir, max_papers=max_papers, force=force)
            except Exception as e:
                return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json({"meta": meta})

        if path.startswith("/api/draw/") and path.endswith("/delete"):
            drawing_id = _sanitize_draw_id(urllib.parse.unquote(path[len("/api/draw/") : -len("/delete")]))
            if not drawing_id:
                return self._send_json({"error": "invalid drawing id"}, status=HTTPStatus.NOT_FOUND)
            try:
                ok = delete_drawing(self._output_dir, drawing_id)
            except ValueError:
                return self._send_json({"error": "invalid drawing id"}, status=HTTPStatus.NOT_FOUND)
            if not ok:
                return self._send_json({"error": "drawing not found"}, status=HTTPStatus.NOT_FOUND)
            return self._send_json({"id": drawing_id, "deleted": True})

        if path == "/api/jobs/upload":
            form = self._read_multipart_form()
            file_part = form.get("_files", {}).get("file")
            if not file_part:
                return self._send_json({"error": "missing file"}, status=HTTPStatus.BAD_REQUEST)

            filename, content = file_part
            name = Path(filename).name if filename else "paper.pdf"
            if not name.lower().endswith(".pdf"):
                return self._send_json({"error": "only PDF is supported"}, status=HTTPStatus.BAD_REQUEST)

            timeout = int(form.get("timeout") or 600)
            max_chars = int(form.get("max_chars") or 25000)

            job = create_job(self._output_dir, hint=Path(name).stem)
            dest = job.job_dir / "paper.pdf"
            dest.write_bytes(content)
            update_meta(
                job.meta_path,
                {
                    "job_id": job.job_id,
                    "state": "queued",
                    "pdf": str(dest),
                    "pdf_original": name,
                    "pdf_local": dest.name,
                    "tags": [],
                },
            )

            def worker():
                try:
                    run_mineru_to_job(job, str(dest), timeout=timeout)
                    client = DeepSeekClient.from_config()
                    run_analyze_to_job(job, client=client, max_chars=max_chars)
                except Exception as e:
                    update_meta(job.meta_path, {"state": "failed", "error": str(e)})

            threading.Thread(target=worker, daemon=True).start()
            return self._send_json({"job_id": job.job_id})

        if path.startswith("/api/jobs/") and path.endswith("/delete"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/delete")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)

            job_dir = (self._output_dir / job_id).resolve()
            try:
                job_dir.relative_to(self._output_dir.resolve())
            except Exception:
                return self._send_json({"error": "invalid job path"}, status=HTTPStatus.BAD_REQUEST)

            if not job_dir.exists() or not job_dir.is_dir():
                return self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)

            try:
                shutil.rmtree(job_dir)
            except Exception as e:
                return self._send_json({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

            return self._send_json({"ok": True, "job_id": job_id})

        if path == "/api/jobs/create":
            payload = self._read_json_body()
            pdf = str(payload.get("pdf", "")).strip()
            timeout = int(payload.get("timeout", 600) or 600)
            max_chars = int(payload.get("max_chars", 25000) or 25000)
            if not pdf:
                return self._send_json({"error": "pdf is required"}, status=HTTPStatus.BAD_REQUEST)
            if "://" in pdf:
                return self._send_json({"error": "暂不支持 URL 导入，请使用本地 PDF 路径"}, status=HTTPStatus.BAD_REQUEST)

            job = create_job(self._output_dir, hint=_guess_hint(pdf))
            update_meta(job.meta_path, {"job_id": job.job_id, "state": "queued", "pdf": pdf, "tags": []})

            def worker():
                try:
                    pdf_clean = pdf.strip().strip('"').strip("'")
                    if "://" not in pdf_clean:
                        src = Path(pdf_clean)
                        if src.exists() and src.is_file():
                            suffix = src.suffix if src.suffix else ".pdf"
                            dest = job.job_dir / f"paper{suffix}"
                            shutil.copy2(src, dest)
                            update_meta(job.meta_path, {"pdf_original": pdf_clean, "pdf_local": dest.name})

                    run_mineru_to_job(job, pdf, timeout=timeout)
                    client = DeepSeekClient.from_config()
                    run_analyze_to_job(job, client=client, max_chars=max_chars)
                except Exception as e:
                    update_meta(job.meta_path, {"state": "failed", "error": str(e)})

            threading.Thread(target=worker, daemon=True).start()
            return self._send_json({"job_id": job.job_id})

        if path.startswith("/api/jobs/") and path.endswith("/analyze"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/analyze")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)

            job_dir = self._output_dir / job_id
            meta_path = job_dir / "meta.json"
            if not meta_path.exists():
                return self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)

            extracted_dir = job_dir / "result"
            job = JobPaths(
                job_id=job_id,
                job_dir=job_dir,
                zip_path=None,
                extracted_dir=extracted_dir,
                original_md=extracted_dir / "full.md",
                translated_md=extracted_dir / "translated.md",
                analysis_json=job_dir / "analysis.json",
                meta_path=meta_path,
            )

            def worker():
                try:
                    client = DeepSeekClient.from_config()
                    run_analyze_to_job(job, client=client)
                except Exception as e:
                    update_meta(job.meta_path, {"state": "failed", "error": str(e)})

            threading.Thread(target=worker, daemon=True).start()
            return self._send_json({"job_id": job_id})

        if path.startswith("/api/jobs/") and path.endswith("/translate"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/translate")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)

            job_dir = self._output_dir / job_id
            meta_path = job_dir / "meta.json"
            extracted_dir = job_dir / "result"
            if not meta_path.exists():
                return self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)

            payload = self._read_json_body()
            lang = str(payload.get("lang", "zh-CN") or "zh-CN").strip() or "zh-CN"

            job = JobPaths(
                job_id=job_id,
                job_dir=job_dir,
                zip_path=None,
                extracted_dir=extracted_dir,
                original_md=extracted_dir / "full.md",
                translated_md=extracted_dir / "translated.md",
                analysis_json=job_dir / "analysis.json",
                meta_path=meta_path,
            )

            def worker():
                try:
                    client = DeepSeekClient.from_config()
                    run_translate_to_job(job, target_language=lang, client=client)
                except Exception as e:
                    update_meta(job.meta_path, {"translate_state": "failed", "translate_error": str(e)})

            threading.Thread(target=worker, daemon=True).start()
            return self._send_json({"job_id": job_id})

        if path.startswith("/api/jobs/") and path.endswith("/chat"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/chat")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)

            job_dir = self._output_dir / job_id
            if not job_dir.exists():
                return self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)

            payload = self._read_json_body()
            model = str(payload.get("model") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            stream = bool(payload.get("stream", True))

            context_mode = "lite"
            include_snippets = False
            snippets_max_chars = 1800

            context_raw = payload.get("context")
            if isinstance(context_raw, str):
                v = context_raw.strip().lower()
                if "full" in v:
                    context_mode = "full"
                if "snippet" in v or "excerpt" in v:
                    include_snippets = True
            elif isinstance(context_raw, dict):
                context_mode = str(context_raw.get("mode") or context_mode).strip().lower() or context_mode
                include_snippets = bool(context_raw.get("snippets") or context_raw.get("include_snippets"))
                try:
                    snippets_max_chars = int(context_raw.get("snippets_max_chars") or context_raw.get("max_chars") or snippets_max_chars)
                except Exception:
                    snippets_max_chars = 1800

            messages_raw = payload.get("messages") or []
            messages: list[dict[str, str]] = []
            if isinstance(messages_raw, list):
                for m in messages_raw:
                    if not isinstance(m, dict):
                        continue
                    role = str(m.get("role") or "").strip()
                    content = str(m.get("content") or "").strip()
                    if not content:
                        continue
                    if role not in {"user", "assistant"}:
                        continue
                    messages.append({"role": role, "content": content})

            question = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    question = str(m.get("content") or "").strip()
                    break

            ctx = _build_job_chat_context(
                self._output_dir,
                job_id,
                question=question,
                mode=context_mode,
                include_snippets=include_snippets,
                snippets_max_chars=snippets_max_chars,
            )

            system_prompt = (
                "你是一个严谨的学术论文问答助手。你会收到论文的结构化摘要，以及（可选）与问题相关的原文/译文片段。\n"
                "要求：\n"
                "1) 尽量只基于提供的信息回答；如果信息不足，明确说明并告诉用户需要哪一段原文/数据。\n"
                "2) 不要编造文中未明确给出的具体数值、数据集、参数；不确定就说不确定。\n"
                "3) 默认用中文回答，除非用户明确要求英文。\n"
            )

            forward_keys = {
                "temperature",
                "top_p",
                "max_tokens",
                "max_completion_tokens",
                "presence_penalty",
                "frequency_penalty",
                "stop",
            }
            upstream_payload = {k: payload[k] for k in forward_keys if k in payload}
            upstream_payload.update(
                {
                    "model": model,
                    "stream": stream,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": ctx},
                        *messages,
                    ],
                }
            )

            try:
                client = GrsaiClient.from_config()
            except Exception as e:
                return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)

            if stream:
                try:
                    upstream = client.create_chat_completion(upstream_payload, stream=True)
                except Exception as e:
                    return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)

                try:
                    self.close_connection = True
                    self.send_response(HTTPStatus.OK)
                    ctype = upstream.headers.get("Content-Type") or "text/event-stream; charset=utf-8"
                    self.send_header("Content-Type", ctype)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()

                    for chunk in upstream.iter_content(chunk_size=4096):
                        if not chunk:
                            continue
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    return
                finally:
                    upstream.close()

            try:
                data = client.chat_completions(upstream_payload)
            except Exception as e:
                return self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json(data)

        if path.startswith("/api/jobs/") and path.endswith("/tags"):
            job_id = _sanitize_job_id(urllib.parse.unquote(path[len("/api/jobs/") : -len("/tags")]))
            if not job_id:
                return self._send_json({"error": "invalid job id"}, status=HTTPStatus.NOT_FOUND)
            meta_path = self._output_dir / job_id / "meta.json"
            if not meta_path.exists():
                return self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)

            payload = self._read_json_body()
            if isinstance(payload.get("tags"), list):
                tags = apply_job_tags_patch(meta_path, tags=[str(x) for x in payload.get("tags")])
                ensure_catalog_tags(self._output_dir, tags)
            else:
                add = str(payload.get("add") or "").strip() or None
                remove = str(payload.get("remove") or "").strip() or None
                tags = apply_job_tags_patch(meta_path, add=add, remove=remove)
                if add:
                    add_catalog_tag(self._output_dir, add)
            return self._send_json({"job_id": job_id, "tags": tags})

        if path == "/api/tags/catalog":
            payload = self._read_json_body()
            add = str(payload.get("add") or "").strip() or None
            remove = str(payload.get("remove") or "").strip() or None
            if add:
                tags = add_catalog_tag(self._output_dir, add)
                return self._send_json({"tags": tags})
            if remove:
                tags = remove_catalog_tag(self._output_dir, remove)
                return self._send_json({"tags": tags})
            return self._send_json({"error": "missing add/remove"}, status=HTTPStatus.BAD_REQUEST)

        if path == "/api/weekly/create":
            payload = self._read_json_body()
            start_date = str(payload.get("start_date", "")).strip()
            end_date = str(payload.get("end_date", "")).strip()
            job_ids_raw = payload.get("job_ids") or []
            job_ids = [str(x).strip() for x in job_ids_raw if str(x).strip()]
            extra_work = str(payload.get("extra_work", "") or "")
            problems = str(payload.get("problems", "") or "")
            next_plan = str(payload.get("next_plan", "") or "")
            use_ai = bool(payload.get("use_ai", True))

            if not start_date or not end_date:
                return self._send_json({"error": "start_date and end_date are required"}, status=HTTPStatus.BAD_REQUEST)
            if not job_ids:
                return self._send_json({"error": "job_ids is required"}, status=HTTPStatus.BAD_REQUEST)

            for jid in job_ids:
                if not _sanitize_job_id(jid):
                    return self._send_json({"error": f"invalid job id: {jid}"}, status=HTTPStatus.BAD_REQUEST)

            report = create_weekly_report(
                self._output_dir,
                start_date=start_date,
                end_date=end_date,
                job_ids=job_ids,
                extra_work=extra_work,
                problems=problems,
                next_plan=next_plan,
                use_ai=use_ai,
            )
            markdown = report.read_markdown()
            open_url = f"/weekly_reports/{urllib.parse.quote(report.report_id)}.md"
            return self._send_json({"report_id": report.report_id, "markdown": markdown, "open_url": open_url})

        return self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        if not body:
            return {}
        try:
            data = json.loads(body.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _read_multipart_form(self) -> dict[str, Any]:
        ctype = (self.headers.get("Content-Type", "") or "").strip()
        m = re.match(r"^multipart/form-data;\s*boundary=(.+)$", ctype, flags=re.IGNORECASE)
        if not m:
            return {"_files": {}}

        boundary = m.group(1).strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        boundary_bytes = ("--" + boundary).encode("utf-8", errors="ignore")

        length = int(self.headers.get("Content-Length", "0") or "0")
        data = self.rfile.read(length) if length > 0 else b""
        if not data:
            return {"_files": {}}

        fields: dict[str, str] = {}
        files: dict[str, tuple[str, bytes]] = {}

        parts = data.split(boundary_bytes)
        for part in parts:
            if not part:
                continue
            if part.startswith(b"--"):
                # final boundary marker
                continue
            if part.startswith(b"\r\n"):
                part = part[2:]
            if part.endswith(b"\r\n"):
                part = part[:-2]
            if not part:
                continue

            header_blob, sep, body = part.partition(b"\r\n\r\n")
            if not sep:
                continue

            header_lines = header_blob.decode("utf-8", errors="replace").split("\r\n")
            headers: dict[str, str] = {}
            for line in header_lines:
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

            disp = headers.get("content-disposition", "")
            disp_parts = [p.strip() for p in disp.split(";") if p.strip()]
            if not disp_parts:
                continue

            params: dict[str, str] = {}
            for seg in disp_parts[1:]:
                if "=" not in seg:
                    continue
                k, v = seg.split("=", 1)
                params[k.strip()] = v.strip().strip('"')

            name = params.get("name", "")
            filename = params.get("filename", "")
            if not name:
                continue

            if filename:
                files[name] = (filename, body)
            else:
                fields[name] = body.decode("utf-8", errors="replace")

        fields["_files"] = files
        return fields

    def _send_asset(self, name: str) -> None:
        content_types = {
            "app.css": "text/css; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "weixin.jpg": "image/jpeg",
            "ali.jpg": "image/jpeg",
        }

        ctype = content_types.get(name)
        if not ctype:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        path = (self._assets_dir / name).resolve()
        try:
            path.relative_to(self._assets_dir.resolve())
        except Exception:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body: str, status: int = 200, *, headers: dict[str, str] | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj: Any, status: int = 200, *, headers: dict[str, str] | None = None) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):  # noqa: A003
        return


def serve_app(output_dir: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure SQLite schema exists (users/invites/sessions).
    conn = auth_connect(output_dir)
    try:
        ensure_schema(conn)
    finally:
        conn.close()

    def handler(*args, **kwargs):
        return AppHandler(*args, output_dir=output_dir, directory=str(output_dir), **kwargs)

    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"App is running at {url}")
    httpd.serve_forever()
