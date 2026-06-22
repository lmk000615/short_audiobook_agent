"""src_next/llm/qwen_http.py

Qwen HTTP 客户端 —— 当前蓝区真实可用的 LLM 后端。

调用方式：OpenAI-compatible `/v1/chat/completions`。

环境变量优先级（从明确到通用）：
    QWEN_BASE_URL  >  LLM_BASE_URL
    QWEN_API_KEY   >  LLM_API_KEY
    QWEN_MODEL     >  LLM_MODEL  (默认 qwen3.6-plus)

兼容旧 src/ 的 .env 写法（变量名 LLM_*），但需要把 BASE_URL 改成
OpenAI-compatible 端点。Aliyun DashScope 同时提供：
    Anthropic 格式：https://dashscope.aliyuncs.com/apps/anthropic/v1
    OpenAI 格式：   https://dashscope.aliyuncs.com/compatible-mode/v1

旧 .env 默认指向 Anthropic 端点；用本客户端时需要切换到 compatible-mode。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from .base import BaseLLMClient, LLMError

urllib3.disable_warnings(InsecureRequestWarning)


_DEFAULT_MODEL = "qwen3.6-plus"
_DEFAULT_MAX_TOKENS = 1024
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_TIMEOUT: tuple[float, float] = (10.0, 120.0)  # (connect, read)


class QwenHTTPClient(BaseLLMClient):
    """蓝区可用的 Qwen HTTP 客户端（OpenAI-compatible）。"""

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
            or os.environ.get("QWEN_BASE_URL")
            or env.get("QWEN_BASE_URL")
            or os.environ.get("LLM_BASE_URL")
            or env.get("LLM_BASE_URL")
            or ""
        ).strip()

        self.api_key = (
            api_key
            or os.environ.get("QWEN_API_KEY")
            or env.get("QWEN_API_KEY")
            or os.environ.get("LLM_API_KEY")
            or env.get("LLM_API_KEY")
            or ""
        ).strip()

        self.model = (
            model
            or os.environ.get("QWEN_MODEL")
            or env.get("QWEN_MODEL")
            or os.environ.get("LLM_MODEL")
            or env.get("LLM_MODEL")
            or _DEFAULT_MODEL
        ).strip()

        self.timeout = timeout
        self.bypass_proxy = bypass_proxy

        if not self.base_url:
            raise LLMError(
                "缺少 Qwen base_url。请在 .env 设置 QWEN_BASE_URL "
                "（或兼容变量 LLM_BASE_URL）。"
            )
        if not self.api_key:
            raise LLMError(
                "缺少 Qwen api_key。请在 .env 设置 QWEN_API_KEY "
                "（或兼容变量 LLM_API_KEY）。"
            )

        if "/anthropic/" in self.base_url:
            # 不 raise，留给真实调用时自然失败；这里只做友好提示
            sys.stderr.write(
                "[WARN] QWEN_BASE_URL 指向 Anthropic 兼容端点（含 /anthropic/）。"
                "QwenHTTPClient 使用 OpenAI-compatible /chat/completions，"
                "建议改用 /compatible-mode/v1 端点。\n"
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
                f"Qwen 返回内容无法解析为 JSON：{err}\n"
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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
            raise LLMError(f"Qwen HTTP 请求失败：{err}") from err

        if response.status_code >= 400:
            raise LLMError(
                f"Qwen HTTP 状态码错误：{response.status_code} {response.reason}\n"
                f"响应体前 500 字符：{response.text[:500]}"
            )

        try:
            return response.json()
        except json.JSONDecodeError as err:
            raise LLMError(
                f"Qwen 返回不是合法 JSON：{err}\n"
                f"响应体前 500 字符：{response.text[:500]}"
            ) from err

    def _chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


# ── 模块级共享工具（gemma4_http.py 复用） ────────────────────────────


def _extract_text(data: dict[str, Any]) -> str:
    """从 OpenAI-compatible chat completions 响应中抽取文本。"""
    try:
        choices = data["choices"]
    except (KeyError, TypeError) as err:
        raise LLMError(f"Qwen 响应缺少 choices 字段：{err}\n原始响应：{data}") from err

    if not choices:
        raise LLMError(f"Qwen 响应 choices 为空：{data}")

    message = choices[0].get("message", {}) or {}
    content = message.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # 部分兼容实现返回 [{"type": "text", "text": "..."}]
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        ]
        return "".join(parts)

    raise LLMError(f"Qwen 响应 message.content 格式无法识别：{message}")


def _parse_json_from_text(text: str) -> dict | list:
    """从模型输出中提取 JSON。

    处理顺序：
    1. 去掉 ```json ... ``` / ``` ... ``` 代码块；
    2. 截取第一个 {/ 到最后一个 }/] 之间的内容；
    3. json.loads 解析。
    """
    cleaned = text.strip()

    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
        cleaned = cleaned.split("```", 1)[0]
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            if cleaned.lstrip().startswith("json"):
                cleaned = cleaned.lstrip()[4:]

    cleaned = cleaned.strip()

    obj_start = cleaned.find("{")
    obj_end = cleaned.rfind("}")
    arr_start = cleaned.find("[")
    arr_end = cleaned.rfind("]")

    if obj_start != -1 and (arr_start == -1 or obj_start < arr_start):
        start, end = obj_start, obj_end
    elif arr_start != -1:
        start, end = arr_start, arr_end
    else:
        raise LLMError(f"未在响应中找到 JSON 边界。前 200 字符：{cleaned[:200]}")

    if end <= start:
        raise LLMError(
            f"JSON 边界异常 start={start} end={end}。前 200 字符：{cleaned[:200]}"
        )

    json_str = cleaned[start : end + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as err:
        ctx_start = max(0, err.pos - 80)
        ctx_end = min(len(json_str), err.pos + 80)
        raise LLMError(
            f"JSON 解析失败 at pos={err.pos}：{err.msg}\n"
            f"上下文：...{json_str[ctx_start:ctx_end]}..."
        ) from err


def _load_env_file() -> dict[str, str]:
    """从项目根 .env 文件读取配置（不污染 os.environ）。

    路径与解析方式和旧 src/ 保持一致：
    - 位置：<project_root>/.env
    - 跳过空行 / 注释行（# 开头）
    - 用第一个 = 分隔 key/value
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    config: dict[str, str] = {}
    if not env_path.exists():
        return config
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()
    except OSError:
        pass
    return config


# ── 可选手动测试入口 ────────────────────────────────────────────────
# 用法：python -m src_next.llm.qwen_http
# 本模块不会在 import 阶段发请求；只有显式作为 __main__ 运行时才调用真实 API。
if __name__ == "__main__":
    client = QwenHTTPClient()
    print(f"base_url = {client.base_url}")
    print(f"model    = {client.model}")
    print("\n[generate_text]")
    print(client.generate_text("用一句话介绍你自己。", max_tokens=64))
    print("\n[generate_json]")
    result = client.generate_json(
        '请返回 JSON：{"ok": true, "who": "qwen"}',
        max_tokens=64,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
