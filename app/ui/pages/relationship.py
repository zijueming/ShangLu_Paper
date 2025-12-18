from __future__ import annotations

from app.ui.pages.base import render_layout


def render_relationship() -> str:
    main = """<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">文献关系图谱</h1>
      <div class="hint" style="margin-top:8px;">AI 分析已阅读文献的内在关联，生成可视化关系网络。</div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <label class="hint" style="display:flex; gap:8px; align-items:center;">
        <span>最多文献</span>
        <select id="rel-max">
          <option value="15">15</option>
          <option value="25">25</option>
          <option value="30" selected>30</option>
          <option value="40">40</option>
          <option value="60">60</option>
        </select>
      </label>
      <button class="btn btn-primary" id="rel-build" type="button">开始 AI 分析</button>
      <button class="btn btn-ghost" id="rel-refresh" type="button">刷新</button>
    </div>
  </div>
</section>

<section class="card">
  <div id="rel-status" class="hint">加载中…</div>
  <div id="rel-empty" class="rel-empty" style="display:none;">
    <div class="rel-empty__icon">🔗</div>
    <div class="rel-empty__title">开始探索文献关系</div>
    <div class="hint" style="margin-top:6px;">使用 AI 智能分析您的文献库，发现论文之间的隐藏联系。</div>
    <button class="btn btn-primary" id="rel-build-big" type="button" style="margin-top:14px; padding:10px 18px;">⚡ 开始 AI 分析</button>
    <div class="hint" style="margin-top:10px;">需要配置 DeepSeek API Key</div>
  </div>
  <div id="rel-canvas-wrap" class="rel-canvas-wrap" style="display:none;">
    <canvas id="rel-canvas"></canvas>
    <div id="rel-tooltip" class="rel-tooltip" style="display:none"></div>
  </div>
</section>"""

    return render_layout(
        title="关系图谱 - 商陆",
        page="relationship",
        active_nav="relationship",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )

