from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app import config


_DEFAULT_CN_BASE_URL = "https://grsai.dakka.com.cn"
_DEFAULT_GLOBAL_BASE_URL = "https://api.grsai.com"


def resolve_grsai_base_url(value: str) -> str:
    v = (value or "").strip()
    if v in {"cn", "china", "domestic"}:
        return _DEFAULT_CN_BASE_URL
    if v in {"global", "overseas", "intl"}:
        return _DEFAULT_GLOBAL_BASE_URL
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return _DEFAULT_CN_BASE_URL


@dataclass(frozen=True)
class GrsaiConfig:
    api_key: str
    base_url: str
    timeout_s: int = 180


class GrsaiClient:
    def __init__(self, cfg: GrsaiConfig):
        self._cfg = cfg

    @classmethod
    def from_config(cls, *, base_url_override: str = "") -> "GrsaiClient":
        api_key = (getattr(config, "GRSAI_API_KEY", "") or "").strip()
        if not api_key:
            raise RuntimeError("Missing Grsai API key: set GRSAI_API_KEY or config_local.GRSAI_API_KEY")

        base_url = (base_url_override or getattr(config, "GRSAI_BASE_URL", "") or "").strip()
        base_url = resolve_grsai_base_url(base_url or _DEFAULT_CN_BASE_URL)

        timeout_s = int(getattr(config, "GRSAI_TIMEOUT_S", 180) or 180)
        return cls(GrsaiConfig(api_key=api_key, base_url=base_url, timeout_s=timeout_s))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

    def draw_nano_banana(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._cfg.base_url.rstrip('/')}/v1/draw/nano-banana"
        res = requests.post(url, headers=self._headers(), json=payload, timeout=self._cfg.timeout_s)
        res.raise_for_status()
        data = res.json()
        code = data.get("code")
        if code not in (0, "0", None):
            msg = data.get("msg") or data.get("message") or "request failed"
            raise RuntimeError(f"Grsai draw failed: {msg} (code={code})")
        return data

    def draw_result(self, task_id: str) -> dict[str, Any]:
        url = f"{self._cfg.base_url.rstrip('/')}/v1/draw/result"
        res = requests.post(url, headers=self._headers(), json={"id": task_id}, timeout=self._cfg.timeout_s)
        res.raise_for_status()
        data = res.json()
        code = data.get("code")
        if code not in (0, "0", None):
            msg = data.get("msg") or data.get("message") or "request failed"
            raise RuntimeError(f"Grsai result failed: {msg} (code={code})")
        return data

    def create_chat_completion(self, payload: dict[str, Any], *, stream: bool | None = None) -> requests.Response:
        url = f"{self._cfg.base_url.rstrip('/')}/v1/chat/completions"
        use_stream = bool(payload.get("stream")) if stream is None else bool(stream)
        res = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self._cfg.timeout_s,
            stream=use_stream,
        )
        res.raise_for_status()
        return res

    def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        res = self.create_chat_completion(payload, stream=False)
        return res.json()
