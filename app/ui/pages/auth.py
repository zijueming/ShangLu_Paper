from __future__ import annotations

import html


def _render_shell(*, title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/assets/app.css" />
</head>
<body class="auth-shell">
  {body_html}
  <footer class="auth-footer">
    决明子2025 • 商陆学术助手
  </footer>
</body>
</html>"""


def render_login(*, error: str = "", next_url: str = "/") -> str:
    err = (error or "").strip()
    err_html = f'<div class="badge bad" style="display:block; padding:12px; border-radius:12px; margin-bottom:16px;">{html.escape(err)}</div>' if err else ""
    body = f"""<div class="auth-card">
  <div style="text-align:center; margin-bottom:32px;">
    <div style="width:48px; height:48px; background:var(--brand); border-radius:12px; display:inline-flex; align-items:center; justify-content:center; color:#fff; font-size:24px; font-weight:800; margin-bottom:16px;">S</div>
    <h1 style="margin:0; font-size:24px; font-weight:800;">登录商陆</h1>
    <div class="hint" style="margin-top:8px;">请输入账号与密码继续</div>
  </div>
  {err_html}
  <form method="POST" action="/api/auth/login">
    <input type="hidden" name="next" value="{html.escape(next_url)}" />
    <div class="hint" style="margin-bottom:8px;">用户名</div>
    <input name="username" autocomplete="username" placeholder="你的用户名" style="width:100%; height:48px; padding:0 16px; margin-bottom:20px;" />
    <div class="hint" style="margin-bottom:8px;">密码</div>
    <input name="password" type="password" autocomplete="current-password" placeholder="••••••••" style="width:100%; height:48px; padding:0 16px; margin-bottom:24px;" />
    <button class="btn btn-primary" type="submit" style="width:100%; height:48px; border-radius:30px; font-size:16px;">登录</button>
  </form>
  <div class="hint" style="margin-top:24px; text-align:center;">
    没有账号？<a class="link" href="/register/?next={html.escape(next_url)}">立即注册</a>
  </div>
</div>"""
    return _render_shell(title="登录 - 商陆", body_html=body)


def render_register(*, error: str = "", require_invite: bool = True, next_url: str = "/") -> str:
    err = (error or "").strip()
    err_html = f'<div class="badge bad" style="display:block; padding:12px; border-radius:12px; margin-bottom:16px;">{html.escape(err)}</div>' if err else ""
    invite = (
        """<div class="hint" style="margin-bottom:8px;">邀请码</div>
    <input name="invite_code" autocomplete="one-time-code" placeholder="输入邀请码" style="width:100%; height:48px; padding:0 16px; margin-bottom:24px;" />"""
        if require_invite
        else """<div class="hint" style="margin-bottom:8px;">邀请码</div>
    <input name="invite_code" placeholder="邀请码（可选）" style="width:100%; height:48px; padding:0 16px; margin-bottom:24px;" />"""
    )
    body = f"""<div class="auth-card">
  <div style="text-align:center; margin-bottom:32px;">
    <div style="width:48px; height:48px; background:var(--brand); border-radius:12px; display:inline-flex; align-items:center; justify-content:center; color:#fff; font-size:24px; font-weight:800; margin-bottom:16px;">S</div>
    <h1 style="margin:0; font-size:24px; font-weight:800;">创建新账号</h1>
    <div class="hint" style="margin-top:8px;">开启高效的科研之旅</div>
  </div>
  {err_html}
  <form method="POST" action="/api/auth/register">
    <input type="hidden" name="next" value="{html.escape(next_url)}" />
    <div class="hint" style="margin-bottom:8px;">用户名</div>
    <input name="username" autocomplete="username" placeholder="字母/数字开头" style="width:100%; height:48px; padding:0 16px; margin-bottom:20px;" />
    <div class="hint" style="margin-bottom:8px;">密码</div>
    <input name="password" type="password" autocomplete="new-password" placeholder="至少 6 位" style="width:100%; height:48px; padding:0 16px; margin-bottom:20px;" />
    {invite}
    <button class="btn btn-primary" type="submit" style="width:100%; height:48px; border-radius:30px; font-size:16px;">注册并登录</button>
  </form>
  <div class="hint" style="margin-top:24px; text-align:center;">
    已有账号？<a class="link" href="/login/?next={html.escape(next_url)}">返回登录</a>
  </div>
</div>"""
    return _render_shell(title="注册 - 商陆", body_html=body)
