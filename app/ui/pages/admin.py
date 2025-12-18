from __future__ import annotations

import html
from typing import Any

from app.ui.pages.base import render_layout


def _badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{html.escape(text)}</span>'


def render_admin(
    *,
    username: str,
    invites: list[dict[str, Any]],
    users: list[dict[str, Any]],
    notice: str = "",
    error: str = "",
) -> str:
    notice = (notice or "").strip()
    error = (error or "").strip()
    msg = ""
    if notice:
        msg = f'<div class="badge ok" style="display:block; padding:10px 12px; border-radius:12px;">{html.escape(notice)}</div>'
    if error:
        msg = f'<div class="badge bad" style="display:block; padding:10px 12px; border-radius:12px;">{html.escape(error)}</div>'

    invite_rows = ""
    for inv in invites:
        code = str(inv.get("code") or "")
        max_uses = int(inv.get("max_uses") or 1)
        uses = int(inv.get("uses") or 0)
        disabled = bool(inv.get("disabled"))
        created_at = str(inv.get("created_at") or "")
        state = _badge("disabled", "bad") if disabled else (_badge("used up", "warn") if uses >= max_uses else _badge("active", "ok"))
        action = (
            f'<form method="POST" action="/api/admin/invites/{html.escape(code)}/disable" style="display:inline">'
            f'<input type="hidden" name="disabled" value="{1 if not disabled else 0}" />'
            f'<button class="btn btn-ghost" type="submit" style="padding:4px 10px; font-size:12px;">{"启用" if disabled else "停用"}</button>'
            f"</form>"
        )
        invite_rows += f"""<tr>
  <td><code>{html.escape(code)}</code></td>
  <td>{uses}/{max_uses}</td>
  <td>{state}</td>
  <td class="hint">{html.escape(created_at)}</td>
  <td style="text-align:right">{action}</td>
</tr>"""

    invite_table = (
        f"""<table style="margin-top:10px;">
  <thead><tr><th>邀请码</th><th style="width:120px">使用</th><th style="width:120px">状态</th><th>创建时间</th><th style="width:140px"></th></tr></thead>
  <tbody>{invite_rows}</tbody>
</table>"""
        if invite_rows
        else '<div class="hint" style="margin-top:10px;">暂无邀请码</div>'
    )

    user_rows = ""
    for u in users:
        uid = int(u.get("id") or 0)
        uname = str(u.get("username") or "")
        is_admin = bool(u.get("is_admin"))
        created_at = str(u.get("created_at") or "")
        role = _badge("admin", "ok") if is_admin else _badge("user", "warn")
        reset_form = f"""<form method="POST" action="/api/admin/users/{uid}/password" style="display:flex; gap:8px; justify-content:flex-end;">
  <input name="new_password" type="password" placeholder="新密码(>=6)" style="width:160px; padding:8px 10px;" />
  <button class="btn btn-ghost" type="submit" style="padding:4px 10px; font-size:12px;">重置</button>
</form>"""
        user_rows += f"""<tr>
  <td>{uid}</td>
  <td><b>{html.escape(uname)}</b></td>
  <td>{role}</td>
  <td class="hint">{html.escape(created_at)}</td>
  <td style="text-align:right">{reset_form}</td>
</tr>"""

    users_table = (
        f"""<table style="margin-top:10px;">
  <thead><tr><th style="width:80px">ID</th><th>用户名</th><th style="width:120px">角色</th><th>创建时间</th><th style="width:320px"></th></tr></thead>
  <tbody>{user_rows}</tbody>
</table>"""
        if user_rows
        else '<div class="hint" style="margin-top:10px;">暂无用户</div>'
    )

    main = f"""<section class="card">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 class="page-title" style="margin:0">管理后台</h1>
      <div class="hint" style="margin-top:8px;">当前管理员：<b>{html.escape(username)}</b></div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <a class="btn" href="/account/">账号</a>
      <a class="btn" href="/logout/">退出</a>
    </div>
  </div>
</section>

<section class="card">
  <div class="card-title">邀请码</div>
  <div style="margin-top:12px;">{msg}</div>
  <form method="POST" action="/api/admin/invites/create" style="display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; margin-top:12px;">
    <div>
      <div class="hint" style="margin:0 0 6px;">自定义邀请码（可选）</div>
      <input name="code" placeholder="留空自动生成" style="width:220px;" />
    </div>
    <div>
      <div class="hint" style="margin:0 0 6px;">最大使用次数</div>
      <select name="max_uses" style="width:160px;">
        <option value="1" selected>1</option>
        <option value="3">3</option>
        <option value="5">5</option>
        <option value="10">10</option>
      </select>
    </div>
    <button class="btn btn-primary" type="submit">创建邀请码</button>
  </form>
  {invite_table}
</section>

<section class="card">
  <div class="card-title">用户</div>
  <div class="hint" style="margin-top:8px;">重置密码后用户可直接使用新密码登录（建议提醒用户立即修改）。</div>
  {users_table}
</section>"""

    return render_layout(
        title="管理后台 - 商陆",
        page="admin",
        active_nav="admin",
        main_html=main,
        top_right_html='<a class="btn" href="/">返回文献库</a>',
    )

