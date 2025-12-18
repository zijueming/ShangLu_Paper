from __future__ import annotations

from app.ui.pages.base import render_layout


def render_draw() -> str:
    main = """<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">科研绘图</h1>
      <div class="hint" style="margin-top:8px;">使用 Nano Banana 生成科研风格图示；支持参考图 URL，并可用 AI 润色提示词。</div>
    </div>
  </div>
</section>

<div class="grid grid-2" style="margin-top:14px;">
  <div class="grid">
    <section class="card">
      <div class="card-title">提示词</div>
      <textarea id="draw-prompt" rows="5" placeholder="例如：画一个 GaAs 太阳能电池 EL 成像实验装置示意图，标注关键部件（CCD、样品、暗箱、偏置电源），白底，科研风格。"></textarea>
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:10px;">
        <button class="btn btn-ghost" id="draw-polish" type="button">AI 润色提示词</button>
        <label class="hint" style="display:flex; gap:8px; align-items:center;">
          <input id="draw-use-ai" type="checkbox" checked />
          <span>生成前自动润色（DeepSeek）</span>
        </label>
      </div>
      <div class="hint" style="margin-top:10px;">润色后（可手动修改）：</div>
      <textarea id="draw-polished" rows="4" placeholder="点击“AI 润色提示词”后会填充在这里；生成时会优先使用这里的内容。"></textarea>
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:10px;">
        <button class="btn btn-primary" id="draw-submit" type="button">生成图片</button>
        <button class="btn btn-ghost" id="draw-clear" type="button">清空</button>
        <span id="draw-tip" class="hint"></span>
      </div>
    </section>

    <section class="card">
      <div class="card-title">生成结果</div>
      <div id="draw-status" class="hint">未开始</div>
      <div id="draw-output" style="margin-top:12px;"></div>
    </section>
  </div>

  <aside class="grid">
    <section class="card">
      <div class="card-title">参数</div>
      <div class="hint" style="margin-bottom:8px;">节点</div>
      <select id="draw-host">
        <option value="">自动（使用配置）</option>
        <option value="cn">国内直连</option>
        <option value="global">海外</option>
      </select>

      <div class="hint" style="margin:12px 0 8px;">模型</div>
      <select id="draw-model">
        <option value="nano-banana-fast">nano-banana-fast</option>
        <option value="nano-banana">nano-banana</option>
        <option value="nano-banana-pro">nano-banana-pro</option>
        <option value="nano-banana-pro-vt">nano-banana-pro-vt</option>
      </select>

      <div class="hint" style="margin:12px 0 8px;">比例</div>
      <select id="draw-ratio">
        <option value="auto">auto</option>
        <option value="1:1">1:1</option>
        <option value="16:9">16:9</option>
        <option value="9:16">9:16</option>
        <option value="4:3">4:3</option>
        <option value="3:4">3:4</option>
        <option value="3:2">3:2</option>
        <option value="2:3">2:3</option>
        <option value="5:4">5:4</option>
        <option value="4:5">4:5</option>
        <option value="21:9">21:9</option>
      </select>

      <div class="hint" style="margin:12px 0 8px;">尺寸（部分模型支持）</div>
      <select id="draw-size">
        <option value="1K">1K</option>
        <option value="2K">2K</option>
        <option value="4K">4K</option>
      </select>

      <div class="hint" style="margin:12px 0 8px;">参考图 URL（每行一个，可选）</div>
      <textarea id="draw-urls" rows="5" placeholder="https://example.com/a.png"></textarea>
    </section>

    <section class="card">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap;">
        <div class="card-title" style="margin:0;">历史记录</div>
        <button class="btn btn-ghost" id="draw-refresh" type="button">刷新</button>
      </div>
      <div id="draw-history" class="hint" style="margin-top:10px;">加载中…</div>
    </section>
  </aside>
</div>"""

    return render_layout(
        title="科研绘图 - 商陆",
        page="draw",
        active_nav="draw",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )

