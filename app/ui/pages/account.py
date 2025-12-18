from __future__ import annotations

import html

from app.ui.pages.base import render_layout


def render_account(*, username: str, is_admin: bool, notice: str = "", error: str = "") -> str:
    notice = (notice or "").strip()
    error = (error or "").strip()
    msg = ""
    if notice:
        msg = f'<div class="badge ok" style="display:block; padding:10px 12px; border-radius:12px;">{html.escape(notice)}</div>'
    if error:
        msg = f'<div class="badge bad" style="display:block; padding:10px 12px; border-radius:12px;">{html.escape(error)}</div>'

    admin_link = (
        '<a class="btn btn-ghost" href="/admin/">管理后台</a>' if is_admin else '<span class="hint">普通用户</span>'
    )

    main = f"""<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">账号</h1>
      <div class="hint" style="margin-top:8px;">当前用户：<b>{html.escape(username)}</b></div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      {admin_link}
      <a class="btn" href="/logout/">退出登录</a>
    </div>
  </div>
</section>

<section class="card">
  <div class="card-title">修改密码</div>
  <div style="margin-top:12px;">{msg}</div>
  <form method="POST" action="/api/account/password" style="margin-top:12px; max-width:520px;">
    <div class="hint" style="margin:10px 0 6px;">当前密码</div>
    <input name="old_password" type="password" autocomplete="current-password" placeholder="••••••••" />
    <div class="hint" style="margin:12px 0 6px;">新密码</div>
    <input name="new_password" type="password" autocomplete="new-password" placeholder="至少 6 位" />
    <div class="hint" style="margin:12px 0 6px;">确认新密码</div>
    <input name="new_password2" type="password" autocomplete="new-password" placeholder="再次输入" />
    <button class="btn btn-primary" type="submit" style="margin-top:14px;">保存</button>
  </form>
</section>

<section class="card">
  <div class="card-title">赞赏支持</div>
  <div class="hint" style="margin-top:12px;">如果这个工具对您有帮助，欢迎赞赏支持作者继续开发与维护 💚</div>
  <div style="display:flex; gap:24px; margin-top:20px; flex-wrap:wrap; justify-content:center; align-items:center;">
    <div style="text-align:center;">
      <div style="font-weight:600; color:var(--brand); margin-bottom:10px;">微信赞赏</div>
      <img class="zoomable" data-zoom="/assets/weixin.jpg" src="/assets/weixin.jpg" alt="微信赞赏码" style="width:360px; height:auto; max-width: 92vw; border-radius:var(--radius); border:1px solid var(--border); box-shadow:var(--shadow); cursor: zoom-in; display:block;">
      <div class="hint" style="margin-top:10px;">点击图片可放大</div>
    </div>
    <div style="text-align:center;">
      <div style="font-weight:600; color:var(--brand); margin-bottom:10px;">支付宝赞赏</div>
      <img class="zoomable" data-zoom="/assets/ali.jpg" src="/assets/ali.jpg" alt="支付宝赞赏码" style="width:360px; height:auto; max-width: 92vw; border-radius:var(--radius); border:1px solid var(--border); box-shadow:var(--shadow); cursor: zoom-in; display:block;">
      <div class="hint" style="margin-top:10px;">点击图片可放大</div>
    </div>
  </div>
  <div class="hint" style="margin-top:16px; text-align:center;">感谢您的支持与鼓励！</div>
</section>"""

    return render_layout(
        title="账号 - 商陆",
        page="account",
        active_nav="account",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )
