from __future__ import annotations

import html

from app.ui.pages.base import render_layout


def render_job(job_id: str) -> str:
    job_id_esc = html.escape(job_id)
    main = f"""<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
      <a class="btn btn-ghost" href="/">← 返回列表</a>
      <span class="pill">{job_id_esc}</span>
      <span id="state"></span>
      <span id="translate-state"></span>
    </div>
    <div style="display:flex; gap:10px; flex-wrap:wrap;">
      <a id="btn-pdf" class="btn" href="#" target="_blank" style="display:none">阅读 PDF</a>
      <button class="btn btn-primary" id="btn-analyze">重新分析</button>
      <button class="btn" id="btn-translate">翻译全文</button>
      <a class="btn" href="/view/{html.escape(job_id)}/" target="_blank">查看 Markdown</a>
      <button class="btn btn-danger" id="btn-delete">删除</button>
    </div>
  </div>
</section>

<section class="card" style="margin-top:14px;">
  <div id="paper-title" class="page-title" style="margin:0">加载中…</div>
  <div id="paper-meta" class="hint" style="margin-top:8px;"></div>
  <div style="margin-top:10px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
    <span class="pill">标签</span>
    <div id="tag-chips" style="display:flex; gap:8px; flex-wrap:wrap;"></div>
    <select id="tag-select" style="max-width:220px; min-width:180px;"></select>
    <button class="btn" id="tag-add">添加标签</button>
    <a class="btn btn-ghost" href="/tags/">管理标签</a>
  </div>
</section>

<div class="grid grid-2" style="margin-top:14px;">
  <div class="grid">
    <section class="card"><div class="card-title">摘要</div><div id="sec-abs" class="hint">等待分析结果…</div></section>
    <div class="split">
      <section class="card"><div class="card-title">主要结论</div><div id="sec-conc" class="hint"></div></section>
      <section class="card"><div class="card-title">创新点</div><div id="sec-novel" class="hint"></div></section>
    </div>
    <div class="split">
      <section class="card"><div class="card-title">实验方法</div><div id="sec-method" class="hint"></div></section>
      <section class="card"><div class="card-title">不足之处</div><div id="sec-lim" class="hint"></div></section>
    </div>
    <section class="card"><div class="card-title">实验详细步骤</div><div id="sec-steps" class="hint"></div></section>
    <div class="split">
      <section class="card"><div class="card-title">表征方法</div><div id="sec-char" class="hint"></div></section>
      <section class="card"><div class="card-title">研究启发</div><div id="sec-insight" class="hint"></div></section>
    </div>
    <section class="card"><div class="card-title">术语解释</div><div id="sec-terms" class="hint"></div></section>
  </div>
  <aside class="grid">
    <section class="card">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap;">
        <div class="card-title" style="margin:0;">关键图表</div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <span id="figs-info" class="hint"></span>
          <button class="btn btn-ghost" id="figs-more" type="button">查看更多</button>
          <button class="btn btn-ghost" id="figs-toggle" type="button">全部图片</button>
        </div>
      </div>
      <div id="figs" class="hint" style="margin-top:10px;">加载中…</div>
    </section>
  </aside>
</div>

<section class="card" style="margin-top:14px;">
  <details class="debug-details">
    <summary class="card-title">调试信息</summary>
    <pre id="debug" class="codebox"></pre>
  </details>
</section>"""

    return render_layout(
        title=f"文献详情 - {job_id}",
        page="job",
        active_nav="library",
        main_html=main,
        top_right_html='<a class="btn" href="/weekly/">写周报</a><button class="btn" onclick="location.reload()">刷新</button>',
        body_attrs=f'data-job-id="{job_id_esc}"',
    )
