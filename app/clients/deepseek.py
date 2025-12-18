from __future__ import annotations

from dataclasses import dataclass

import requests

from app import config


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_s: int = 120


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig):
        self._config = config

    @classmethod
    def from_config(cls) -> "DeepSeekClient":
        api_key = (config.DEEPSEEK_API_KEY or "").strip()
        if not api_key:
            raise RuntimeError("Missing DeepSeek API key: set DEEPSEEK_API_KEY or config_local.DEEPSEEK_API_KEY")

        base_url = (config.DEEPSEEK_BASE_URL or "https://api.deepseek.com").strip()
        model = (config.DEEPSEEK_MODEL or "deepseek-chat").strip()
        timeout_s = int(config.DEEPSEEK_TIMEOUT_S or 120)
        return cls(DeepSeekConfig(api_key=api_key, base_url=base_url, model=model, timeout_s=timeout_s))

    def chat_completions(self, messages: list[dict], temperature: float = 0.2) -> str:
        url = f"{self._config.base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
        }
        res = requests.post(url, headers=headers, json=payload, timeout=self._config.timeout_s)
        res.raise_for_status()
        data = res.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # pragma: no cover - defensive
            raise RuntimeError(f"Unexpected DeepSeek response: {data}") from e
