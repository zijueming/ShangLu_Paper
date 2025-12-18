from __future__ import annotations

from app.ui.pages.base import render_layout


def render_tags() -> str:
    main = """<section class="card">
  <h1 class="page-title" style="margin:0">标签管理</h1>
  <div class="hint" style="margin-top:8px;">在文献详情页添加/删除标签，这里用于浏览与筛选。</div>
</section>

<div class="grid grid-2" style="margin-top:14px;">
  <section class="card">
    <div class="card-title">标签列表</div>
    <div style="display:flex; gap:10px; align-items:center; margin:10px 0;">
      <input id="new-tag" type="text" placeholder="新建标签（回车）" />
      <button id="btn-new-tag" class="btn btn-primary" style="white-space:nowrap;">新建</button>
    </div>
    <div id="tags-list" class="hint">加载中…</div>
  </section>
  <section class="card">
    <div class="card-title">文献</div>
    <div id="tags-jobs" class="hint">请选择一个标签</div>
  </section>
</div>"""

    return render_layout(
        title="标签管理 - 商陆",
        page="tags",
        active_nav="tags",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )
