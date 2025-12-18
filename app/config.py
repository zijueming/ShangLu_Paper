"""
Runtime configuration.

Temporarily: configure tokens/keys here directly (no environment variables).

Notes:
  - Do NOT commit real secrets.
  - Prefer creating a local `config_local.py` (already ignored by git) to override values.
"""

from __future__ import annotations

# MinerU
MINERU_TOKEN = ""  # fill your token here (recommended: put it in config_local.py)

# DeepSeek
DEEPSEEK_API_KEY = ""  # fill your api key here (recommended: put it in config_local.py)
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TIMEOUT_S = 120

# Grsai / Nano Banana
GRSAI_API_KEY = ""  # fill your api key here (recommended: put it in config_local.py)
GRSAI_BASE_URL = "https://api.grsai.com"
GRSAI_TIMEOUT_S = 180

# Optional: local overrides (not committed)
try:  # pragma: no cover
    from config_local import *  # type: ignore  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass
