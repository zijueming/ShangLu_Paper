from __future__ import annotations

from app.ui.pages.base import render_layout


def render_translate() -> str:
    main = """<section class="card">
  <h1 class="page-title" style="margin:0">论文翻译</h1>
  <div class="hint" style="margin-top:8px;">对已解析的论文进行全文翻译（输出到 translated.md，可在“查看 Markdown”里对照查看）。</div>
</section>

<section class="card" style="margin-top:14px;">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div class="card-title" style="margin:0">文献列表</div>
    <div class="hint">只会翻译已解析的 full.md</div>
  </div>
  <table style="margin-top:10px;">
    <thead>
      <tr>
        <th>标题 / 作者</th>
        <th style="width:120px">分析状态</th>
        <th style="width:140px">翻译状态</th>
        <th style="width:220px"></th>
      </tr>
    </thead>
    <tbody id="translate-body">
      <tr><td colspan="4"><span class="hint">加载中…</span></td></tr>
    </tbody>
  </table>
</section>"""

    return render_layout(
        title="论文翻译 - 商陆",
        page="translate",
        active_nav="translate",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )

