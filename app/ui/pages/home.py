from __future__ import annotations

from app.ui.pages.base import render_layout


def render_home() -> str:
    main = """<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">我的文献</h1>
      <div class="hint">解析 PDF → DeepSeek 输出要点 → 关键图表预览</div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <input id="file" type="file" accept="application/pdf" style="display:none" />
      <button class="btn btn-primary" id="btn-import">导入文献</button>
    </div>
  </div>

  <div class="hint" style="margin-top:10px;">
    点击“导入文献”选择本地 PDF，将自动解析并生成：摘要 / 结论 / 创新点 / 实验方法 / 不足 / 步骤 / 表征 / 启发。
  </div>
</section>

<section class="card" style="margin-top:14px;">
  <div class="card-title">文献列表</div>
  <table>
    <thead>
      <tr>
        <th>标题 / 作者</th>
        <th style="width:88px">年份</th>
        <th style="width:120px">状态</th>
        <th style="width:160px">更新时间</th>
        <th style="width:180px"></th>
      </tr>
    </thead>
    <tbody id="jobs-body">
      <tr><td colspan="5"><span class="hint">加载中…</span></td></tr>
    </tbody>
  </table>
</section>"""

    return render_layout(
        title="文献库 - 商陆",
        page="home",
        active_nav="library",
        main_html=main,
        top_right_html='<a class="btn" href="/weekly/">写周报</a><button class="btn" onclick="location.reload()">刷新</button>',
    )
