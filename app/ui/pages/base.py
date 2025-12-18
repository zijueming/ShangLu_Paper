from __future__ import annotations

import html


def _nav_item(label: str, href: str, *, active: bool) -> str:
    cls = "active" if active else ""
    return f'<a class="{cls}" href="{html.escape(href)}">{html.escape(label)}</a>'


def render_layout(
    *,
    title: str,
    page: str,
    active_nav: str,
    main_html: str,
    top_right_html: str = "",
    body_attrs: str = "",
) -> str:
    nav = "\n".join(
        [
            _nav_item("文献库", "/", active=active_nav == "library"),
            _nav_item("科研绘图", "/draw/", active=active_nav == "draw"),
            _nav_item("关系图谱", "/relationship/", active=active_nav == "relationship"),
            _nav_item("周报", "/weekly/", active=active_nav == "weekly"),
            _nav_item("标签管理", "/tags/", active=active_nav == "tags"),
            _nav_item("论文翻译", "/translate/", active=active_nav == "translate"),
            _nav_item("账号", "/account/", active=active_nav == "account"),
            _nav_item("管理后台", "/admin/", active=active_nav == "admin"),
        ]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/assets/app.css" />
</head>
<body data-page="{html.escape(page)}" {body_attrs}>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-badge"></div>
        <div>商陆</div>
      </div>
      <nav class="nav">
        {nav}
      </nav>
      <div class="sidebar-foot">
        <div style="opacity: 0.6; margin-bottom: 4px;">商陆学术助手</div>
        <div style="font-weight: 600;">v2.0 • Pro</div>
      </div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div class="search">
          <input id="q" type="text" placeholder="搜索标题、作者、标签…" />
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
          <div id="userbar" style="display:flex; gap:10px; align-items:center;"></div>
          {top_right_html}
        </div>
      </div>
      {main_html}
    </main>
  </div>
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
