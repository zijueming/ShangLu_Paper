from __future__ import annotations
import html

def render_landing() -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>商陆 - 下一代科研文献管理</title>
  <link rel="stylesheet" href="/assets/app.css" />
  <style>
    body {{ background: #fff; margin:0; padding:0; overflow-x: hidden; }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 40px;
      position: sticky;
      top: 0;
      background: rgba(255,255,255,0.8);
      backdrop-filter: blur(12px);
      z-index: 100;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 1.25rem;
      font-weight: 800;
      color: var(--text);
      text-decoration: none;
    }}
    .logo-icon {{
      width: 32px;
      height: 32px;
      background: var(--brand);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 18px;
    }}
  </style>
</head>
<body class="landing">
  <header class="header">
    <a href="/" class="logo">
      <div class="logo-icon">S</div>
      <span>商陆</span>
    </a>
    <div style="display:flex; gap:20px; align-items:center;">
      <a href="/login/" class="link" style="font-weight:500;">登录</a>
      <a href="/register/" class="btn btn-primary" style="padding: 8px 20px; border-radius: 30px;">免费注册</a>
    </div>
  </header>

  <main class="landing-hero">
    <div class="landing-badge">● AI 驱动的科研新体验</div>
    <h1 class="landing-title">
      让科研阅读<br/>
      <span>回归纯粹与高效</span>
    </h1>
    <p class="landing-sub">
      商陆 不仅仅是一个文献管理工具。它集成了最先进的 AI 解析、自动翻译与
      知识图谱构建，为您打造沉浸式的深度阅读环境。
    </p>
    <div class="landing-actions">
      <a href="/register/" class="btn btn-primary" style="border-radius: 30px;">立即开始 →</a>
      <a href="/login/" class="btn" style="border-radius: 30px; background: #fff; border: 1.5px solid var(--border);">了解更多</a>
    </div>
  </main>

  <footer class="auth-footer" style="padding: 40px 0;">
    决明子2025 • 商陆学术助手
  </footer>
</body>
</html>"""
