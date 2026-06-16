"""Thin wrapper for OpenAI-compatible LLM endpoints.

Uses `requests` directly to call the API in OpenAI Chat Completions format.
Works with DeepSeek, DashScope, or any OpenAI-compatible API.
"""

import json
import os
import re
from typing import Any

import requests

from . import config


class LLMClient:
    def __init__(self) -> None:
        self.base_url = config.LLM_BASE_URL.rstrip("/")
        self.api_key = config.LLM_API_KEY
        self.model = config.LLM_MODEL

    def chat_json(self, system_prompt: str, user_text: str, max_retries: int = 3) -> dict[str, Any]:
        """Send a single-turn prompt and parse the response as JSON.

        Retries on HTTP errors and JSON parse failures.
        """
        # 代理配置 - 使用 Windows 系统代理
        proxy_url = "http://proxysg.huawei.com:8080"
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": config.LLM_MAX_TOKENS,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_text},
                        ],
                    },
                    proxies=proxies,
                    verify=False,  # 禁用SSL验证（公司代理会检查HTTPS）
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"]
                if not raw or not raw.strip():
                    raise ValueError("Empty response from LLM")
                return _parse_json_lenient(raw)
            except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
        raise RuntimeError(f"Failed after {max_retries} attempts: {last_error}")


def _extract_text(resp: Any) -> str:
    """Flatten the Anthropic response content into a single string."""
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    """Parse JSON, tolerating ```json fenced blocks or trailing prose."""
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        # Fall back to the outermost {...} span
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            raw = match.group(0)
    return json.loads(raw)
