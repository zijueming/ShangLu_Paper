from __future__ import annotations

from app.ui.pages.base import render_layout


def render_weekly() -> str:
    main = """<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">这周干了啥啊</h1>
      <div class="hint">选择本周阅读文献 + 补充工作内容，一键生成周报（可 AI 润色）</div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <label class="pill" style="cursor:pointer;">
        <input id="use-ai" type="checkbox" checked style="margin-right:6px;" />
        AI 润色
      </label>
      <button class="btn" onclick="location.reload()">刷新</button>
    </div>
  </div>
</section>

<div class="grid grid-2" style="margin-top:14px;">
  <div class="grid">
    <section class="card">
      <div class="card-title">选择文献</div>
      <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
        <div style="flex:1; min-width:200px;">
          <div class="hint" style="margin-bottom:6px;">开始日期</div>
          <input id="week-start" type="date" />
        </div>
        <div style="flex:1; min-width:200px;">
          <div class="hint" style="margin-bottom:6px;">结束日期</div>
          <input id="week-end" type="date" />
        </div>
        <div style="display:flex; align-items:flex-end;">
          <button id="btn-filter" class="btn btn-primary">筛选</button>
        </div>
      </div>
      <div id="paper-list" style="margin-top:12px;"><div class="hint">加载中…</div></div>
      <div id="picked" class="hint" style="margin-top:10px;">已选择文献（0）</div>
    </section>

    <section class="card">
      <div class="card-title">补充其他工作（可选）</div>
      <textarea id="extra-work" rows="6" placeholder="- 完成了 XXX 任务&#10;- 遇到的问题与解决方案&#10;- 下周的计划"></textarea>
    </section>

    <div class="split">
      <section class="card">
        <div class="card-title">遇到的问题与解决方案（可选）</div>
        <textarea id="problems" rows="6" placeholder="- 问题：...&#10;- 解决：..."></textarea>
      </section>
      <section class="card">
        <div class="card-title">下周计划（可选）</div>
        <textarea id="next-plan" rows="6" placeholder="- 计划 1&#10;- 计划 2"></textarea>
      </section>
    </div>
  </div>

  <aside class="grid">
    <section class="card">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
        <div class="card-title">生成结果（Markdown）</div>
        <div style="display:flex; gap:10px; align-items:center;">
          <a id="weekly-open" class="btn" href="#" target="_blank" style="display:none">打开文件</a>
          <button id="btn-generate" class="btn btn-primary">生成周报</button>
        </div>
      </div>
      <textarea id="weekly-out" rows="18" placeholder="生成后会显示在这里"></textarea>
      <div class="hint" style="margin-top:8px;">你可以直接复制 Markdown 到飞书/语雀/Notion。</div>
    </section>

    <section class="card">
      <div class="card-title">历史周报</div>
      <div id="weekly-reports"><div class="hint">加载中…</div></div>
    </section>
  </aside>
</div>"""

    return render_layout(
        title="周报 - 商陆",
        page="weekly",
        active_nav="weekly",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )

