from __future__ import annotations

import html
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.utils.zip_utils import safe_extract_zip


def _job_from_zip_name(name: str) -> str | None:
    if not name.endswith("_result.zip"):
        return None
    return name[: -len("_result.zip")]


def list_jobs(output_dir: Path) -> list[str]:
    jobs: set[str] = set()

    if not output_dir.exists():
        return []

    for path in output_dir.iterdir():
        if path.is_file():
            job = _job_from_zip_name(path.name)
            if job:
                jobs.add(job)
        elif path.is_dir():
            if (path / "full.md").exists() or (path / "result" / "full.md").exists():
                jobs.add(path.name)

    return sorted(jobs)


def ensure_extracted(output_dir: Path, job: str) -> Path:
    job_dir = output_dir / job
    md_path_v2 = job_dir / "result" / "full.md"
    if md_path_v2.exists():
        return job_dir / "result"

    md_path_v1 = job_dir / "full.md"
    if md_path_v1.exists():
        return job_dir

    if job_dir.exists() and job_dir.is_dir():
        zips = sorted(job_dir.glob("*_result.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if zips:
            safe_extract_zip(zips[0], job_dir / "result")
            if (job_dir / "result" / "full.md").exists():
                return job_dir / "result"

    zip_path = output_dir / f"{job}_result.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"zip not found: {zip_path}")

    extracted_dir = output_dir / job
    safe_extract_zip(zip_path, extracted_dir)
    if not (extracted_dir / "full.md").exists():
        raise FileNotFoundError(f"full.md missing in zip: {zip_path}")
    return extracted_dir


def _render_index(output_dir: Path) -> str:
    jobs = list_jobs(output_dir)
    items = "\n".join(f'<li><a href="/view/{urllib.parse.quote(job)}/">{html.escape(job)}</a></li>' for job in jobs)
    if not items:
        items = '<li style="color:#666">No jobs yet. Run the pipeline to generate output.</li>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MinerU Results</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji"; margin: 24px; }}
    .wrap {{ max-width: 980px; margin: 0 auto; }}
    code {{ background:#f6f8fa; padding: 0 4px; border-radius: 4px; }}
    ul {{ padding-left: 18px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h2>MinerU Results</h2>
    <p>Output directory: <code>{html.escape(str(output_dir))}</code></p>
    <ul>{items}</ul>
  </div>
</body>
</html>"""


def _render_view(job: str) -> str:
    job_escaped = html.escape(job)
    md_url = f"/{urllib.parse.quote(job)}/result/full.md"
    md_translated_url = f"/{urllib.parse.quote(job)}/result/translated.md"
    base_href = f"/{urllib.parse.quote(job)}/result/"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <base href="{base_href}">
  <title>{job_escaped}</title>
  <link rel="stylesheet" href="/assets/app.css" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.1/github-markdown.min.css">
  <style>
    body {{ margin: 0; background: #fff; }}
    header {{
      position: sticky; top: 0; z-index: 10;
      display:flex; gap: 12px; align-items:center;
      padding: 10px 14px; border-bottom: 1px solid #eee; background: rgba(255,255,255,.92); backdrop-filter: blur(6px);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    }}
    header a {{ color:#0969da; text-decoration:none; }}
    header a:hover {{ text-decoration:underline; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 16px; }}
    .markdown-body {{ font-size: 16px; line-height: 1.7; }}
    table {{ display: block; overflow-x: auto; }}
    img {{ max-width: 100%; height: auto; }}
    .hint {{ color:#666; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .panel {{ border: 1px solid #eee; border-radius: 10px; overflow: hidden; }}
    .panel h3 {{ margin: 0; padding: 10px 12px; border-bottom: 1px solid #eee; background: #fafafa; font: 600 14px/1.2 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .panel .body {{ padding: 14px; }}
    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
      }},
      options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
    }};
  </script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body data-page="viewer" data-job-id="{job_escaped}">
  <header>
    <a href="/">← Back</a>
    <div style="font-weight:600">{job_escaped}</div>
    <div class="hint">Tables are usually HTML inside full.md; HTML rendering stays on.</div>
  </header>
  <div class="container">
    <div class="grid">
      <section class="panel">
        <h3>Original</h3>
        <div id="content-original" class="body markdown-body">Loading...</div>
      </section>
      <section class="panel">
        <h3>Translated</h3>
        <div id="content-translated" class="body markdown-body">Translation not generated yet.</div>
      </section>
    </div>
  </div>
  <script>
    async function waitFor(fn, timeoutMs = 15000) {{
      const start = Date.now();
      while (true) {{
        const v = fn();
        if (v) return v;
        if (Date.now() - start > timeoutMs) throw new Error('dependency load timeout');
        await new Promise((r) => setTimeout(r, 50));
      }}
    }}

    async function main() {{
      const mdFactory = await waitFor(() => window.markdownit);
      const md = mdFactory({{
        html: true,
        linkify: true,
        breaks: true,
        typographer: true
      }});

      async function renderInto(url, el, notFoundText) {{
        const resp = await fetch(url, {{ cache: 'no-store' }});
        if (!resp.ok) {{
          el.textContent = notFoundText || ('Read markdown failed: ' + resp.status);
          return false;
        }}
        const mdText = await resp.text();
        el.innerHTML = md.render(mdText);
        return true;
      }}

      const ok1 = await renderInto({json_escape(md_url)}, document.getElementById('content-original'));
      await renderInto({json_escape(md_translated_url)}, document.getElementById('content-translated'), 'Translation not generated.');

      if (ok1 && window.MathJax?.typesetPromise) await window.MathJax.typesetPromise();
    }}
    window.addEventListener('DOMContentLoaded', () => {{
      main().catch((e) => {{
        document.getElementById('content-original').textContent = 'Render failed: ' + (e?.message || e);
      }});
    }});
  </script>
  <button id="ai-fab" class="ai-fab" type="button" style="display:none" aria-label="打开 AI 对话">AI</button>
  <div id="ai-chat" class="ai-chat" aria-hidden="true">
    <div class="ai-chat__panel" role="dialog" aria-modal="true" aria-label="AI 对话">
      <div class="ai-chat__header">
        <div style="font-weight:800;">AI 对话</div>
        <div class="ai-chat__tools">
          <select id="ai-chat-model" title="模型"></select>
          <label class="ai-chat__toggle" title="附带从译文/原文中检索的少量相关段落（更费 token）">
            <input id="ai-chat-snippets" type="checkbox" />
            相关片段
          </label>
          <button id="ai-chat-clear" class="btn btn-ghost" type="button">清空</button>
          <button id="ai-chat-close" class="btn btn-ghost" type="button">关闭</button>
        </div>
      </div>
      <div id="ai-chat-messages" class="ai-chat__messages"></div>
      <div class="ai-chat__footer">
        <textarea id="ai-chat-input" placeholder="输入你的问题…（Enter 发送，Shift+Enter 换行）"></textarea>
        <button id="ai-chat-send" class="btn btn-primary" type="button">发送</button>
      </div>
      <div class="ai-chat__hint">默认仅发送“摘要/要点”以节省 token；勾选“相关片段”会额外附带少量检索到的段落。</div>
    </div>
  </div>
  <script src="/assets/app.js" defer></script>
</body>
</html>"""


def json_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r")
    return f"\"{escaped}\""


class ViewerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, output_dir: Path | None = None, **kwargs):
        self._output_dir = output_dir or Path(directory or ".")
        super().__init__(*args, directory=str(self._output_dir), **kwargs)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._send_html(_render_index(self._output_dir))

        if path.startswith("/view/"):
            job = urllib.parse.unquote(path[len("/view/") :]).strip("/")
            if not job:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            try:
                ensure_extracted(self._output_dir, job)
            except Exception as e:
                return self._send_html(f"<pre style='white-space:pre-wrap'>Cannot prepare preview: {html.escape(str(e))}</pre>", status=500)

            return self._send_html(_render_view(job))

        return super().do_GET()

    def _send_html(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):  # noqa: A003
        return


def serve_viewer(output_dir: Path, host: str = "127.0.0.1", port: int = 8000, open_url: str | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    def handler(*args, **kwargs):
        return ViewerHandler(*args, output_dir=output_dir, directory=str(output_dir), **kwargs)

    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Viewer is running at {url}")

    if open_url:
        full = urllib.parse.urljoin(url, open_url.lstrip("/"))

        def _open():
            time.sleep(0.3)
            webbrowser.open(full)

        threading.Thread(target=_open, daemon=True).start()

    httpd.serve_forever()
