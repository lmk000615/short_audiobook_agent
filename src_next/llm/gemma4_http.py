"""src_next/llm/gemma4_http.py

Gemma4 HTTP 客户端（OpenAI-compatible）。

服务器正在搬迁，本阶段**只保留结构**，不真实测试。
Gemma4 部署通常不需要 API key（内网直连），因此 Authorization header 可选。
需要支持绕过代理（蓝区开发机常配了全局代理，内网调用要 bypass）。

环境变量：
    GEMMA4_BASE_URL  必填，服务器恢复后在 .env 中配置
    GEMMA4_API_KEY   可选，绝大多数 Gemma4 部署不需要
    GEMMA4_MODEL     可选，默认 gemma4-31B

服务器恢复后只需要在 .env 配置 GEMMA4_BASE_URL，本客户端即可工作；
不需要改 core/analysis 层，也不需要改其他 LLM 后端。
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from .base import BaseLLMClient, LLMError
from .qwen_http import (
    _extract_text,
    _load_env_file,
    _parse_json_from_text,
)


_DEFAULT_MODEL = "gemma4-31B"
_DEFAULT_MAX_TOKENS = 1024
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_TIMEOUT: tuple[float, float] = (10.0, 180.0)


class Gemma4HTTPClient(BaseLLMClient):
    """Gemma4 服务器恢复后启用；本阶段不真实测试。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: tuple[float, float] | float = _DEFAULT_TIMEOUT,
        bypass_proxy: bool = True,
    ) -> None:
        env = _load_env_file()

        self.base_url = (
            base_url
            or os.environ.get("GEMMA4_BASE_URL")
            or env.get("GEMMA4_BASE_URL")
            or ""
        ).strip()

        self.api_key = (
            api_key
            or os.environ.get("GEMMA4_API_KEY")
            or env.get("GEMMA4_API_KEY")
            or ""
        ).strip()

        self.model = (
            model
            or os.environ.get("GEMMA4_MODEL")
            or env.get("GEMMA4_MODEL")
            or _DEFAULT_MODEL
        ).strip()

        self.timeout = timeout
        self.bypass_proxy = bypass_proxy

        if not self.base_url:
            raise LLMError(
                "缺少 Gemma4 base_url。请在 .env 设置 GEMMA4_BASE_URL。"
                "（服务器恢复后启用，本阶段不真实测试。）"
            )

    # ── BaseLLMClient 实现 ──────────────────────────────────────────

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
        timeout: tuple[float, float] | float | None = None,
        **_unused: Any,
    ) -> str:
        payload = self._build_payload(
            prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        data = self._post(payload, timeout=timeout)
        return _extract_text(data)

    def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
        timeout: tuple[float, float] | float | None = None,
        **_unused: Any,
    ) -> dict | list:
        raw = self.generate_text(
            prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        try:
            return _parse_json_from_text(raw)
        except LLMError as err:
            raise LLMError(
                f"Gemma4 返回内容无法解析为 JSON：{err}\n"
                f"原始内容前 500 字符：{raw[:500]}"
            ) from err

    # ── 内部工具 ────────────────────────────────────────────────────

    def _build_payload(
        self,
        user_prompt: str,
        *,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    def _post(
        self,
        payload: dict[str, Any],
        *,
        timeout: tuple[float, float] | float | None,
    ) -> dict[str, Any]:
        url = self._chat_completions_url()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        # Gemma4 内网部署通常不需要鉴权；只有在配置了 key 时才带 Authorization
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        proxies = {"http": None, "https": None} if self.bypass_proxy else None
        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=effective_timeout,
                proxies=proxies,
                verify=False,
            )
        except requests.RequestException as err:
            raise LLMError(f"Gemma4 HTTP 请求失败：{err}") from err

        if response.status_code >= 400:
            raise LLMError(
                f"Gemma4 HTTP 状态码错误：{response.status_code} {response.reason}\n"
                f"响应体前 500 字符：{response.text[:500]}"
            )

        try:
            return response.json()
        except json.JSONDecodeError as err:
            raise LLMError(
                f"Gemma4 返回不是合法 JSON：{err}\n"
                f"响应体前 500 字符：{response.text[:500]}"
            ) from err

    def _chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
