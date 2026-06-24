"""src_next/voicebank/qwen3_http.py

Qwen3-TTS VoiceDesign HTTP voicebank adapter（黄区内网调用，并发版）。

调用方式：HTTP POST 到 ``{base_url}/v1/voicedesign/generate``，
请求体 ``{text, instruction, language}``，响应体直接是 wav 字节流。

和 ``qwen_voicegenerator.py`` 的差异：
* 不跑 subprocess、不依赖 WSL / 本地 venv；
* 不需要 ``generator_root`` / ``script_path`` / ``model_path`` / ``python_executable``；
* 用 ``requests.post`` 直连服务器，默认 bypass 代理（黄区内网）。

API 参考：``usage_guide_qwen3.md``（项目根目录）。

并发：默认 4 线程并发为多个角色生成 voice reference。角色数通常 3-5，
串行模式下 voicedesign 总耗时 = N × ~30-60s，并发可降到 ~60s 量级。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from src_next.core.data_models import CharacterProfile, VoicebankResult

from .base import BaseVoicebankAdapter, VoicebankError


urllib3.disable_warnings(InsecureRequestWarning)


_DEFAULT_OUTPUT_SUBDIR = "voicebank"
_DEFAULT_LANGUAGE = "Chinese"
_DEFAULT_REFERENCE_TEXT = "你好，欢迎使用语音设计功能，这是一个测试句子。"
_DEFAULT_TIMEOUT = 60
_DEFAULT_MAX_WORKERS = 4


class Qwen3HTTPAdapter(BaseVoicebankAdapter):
    """Qwen3-TTS VoiceDesign 的 HTTP adapter（并发版）。"""

    def __init__(
        self,
        *,
        base_url: str,
        output_subdir: str = _DEFAULT_OUTPUT_SUBDIR,
        extra_args: dict[str, Any] | None = None,
        **_unused: Any,
    ) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        if not self.base_url:
            raise VoicebankError(
                "Qwen3HTTPAdapter 缺少 base_url。"
                "请在 profile 配置 voicebank.base_url，例如 http://10.50.121.102:8007"
            )
        self.output_subdir = (output_subdir or _DEFAULT_OUTPUT_SUBDIR).strip() or _DEFAULT_OUTPUT_SUBDIR
        self.extra_args: dict[str, Any] = dict(extra_args) if extra_args else {}
        self.bypass_proxy = bool(self.extra_args.get("bypass_proxy", True))

    # ── BaseVoicebankAdapter 实现 ────────────────────────────────────

    def prepare_voicebank(
        self,
        characters: list[CharacterProfile],
        output_dir: str,
        *,
        dry_run: bool = False,
        max_workers: int | None = None,
        **_kwargs: Any,
    ) -> VoicebankResult:
        voicebank_dir = Path(output_dir).expanduser() / self.output_subdir
        voicebank_dir.mkdir(parents=True, exist_ok=True)

        config_snapshot = {
            "backend": "qwen3_http",
            "base_url": self.base_url,
            "output_subdir": self.output_subdir,
            "extra_args": self.extra_args,
            "dry_run": dry_run,
            "max_workers": max_workers or int(self.extra_args.get("max_workers", _DEFAULT_MAX_WORKERS)),
        }
        (voicebank_dir / "adapter_config.json").write_text(
            json.dumps(config_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        language = str(self.extra_args.get("language", _DEFAULT_LANGUAGE))
        reference_text = str(self.extra_args.get("reference_text", _DEFAULT_REFERENCE_TEXT))
        timeout = int(self.extra_args.get("timeout_per_char", _DEFAULT_TIMEOUT))

        # ── 分类：哪些直接出结果 / 哪些要进线程池 ───────────────────
        # 缓存命中 → speaker_to_voice 直接放，不进线程池
        speaker_to_voice: dict[str, str] = {}
        errors: list[str] = []
        # to_gen: list of (char_idx, char, instruction, voice_path)
        to_gen: list[tuple[int, CharacterProfile, str, Path]] = []

        for idx, char in enumerate(characters):
            voice_path = voicebank_dir / f"{char.name}.wav"

            if voice_path.exists() and voice_path.stat().st_size > 0:
                speaker_to_voice[char.name] = str(voice_path)
                continue

            instruction = (char.voice_prompt or "").strip() or self._default_instruction(char)

            if dry_run:
                log_path = voicebank_dir / f"{char.name}.log"
                self._write_dry_run_log(log_path, char, instruction, language, reference_text)
                errors.append(f"{char.name}: dry_run, not invoked")
                continue

            to_gen.append((idx, char, instruction, voice_path))

        # ── 并发 voicedesign ────────────────────────────────────────
        if to_gen:
            workers = max_workers or int(self.extra_args.get("max_workers", _DEFAULT_MAX_WORKERS))
            workers = max(1, min(workers, len(to_gen)))
            print(
                f"[qwen3_http] generating {len(to_gen)} voice references "
                f"with {workers} workers (timeout={timeout}s/char)",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qwen3voice") as ex:
                future_to_meta = {
                    ex.submit(
                        self._generate_one, char, instruction, voice_path,
                        language, reference_text, timeout,
                    ): (idx, char.name, voice_path)
                    for idx, char, instruction, voice_path in to_gen
                }
                for future in as_completed(future_to_meta):
                    idx, name, voice_path = future_to_meta[future]
                    try:
                        err_msg = future.result()
                        if err_msg:
                            errors.append(f"{name}: {err_msg}")
                        else:
                            speaker_to_voice[name] = str(voice_path)
                    except Exception as err:  # noqa: BLE001
                        errors.append(f"{name}: worker exception: {type(err).__name__}: {err}")

        if errors:
            (voicebank_dir / "errors.log").write_text(
                "\n".join(errors) + "\n", encoding="utf-8",
            )

        return VoicebankResult(
            speaker_to_voice=speaker_to_voice,
            voicebank_dir=str(voicebank_dir),
            backend="qwen3_http",
            success=(not errors),
        )

    # ── 线程任务（单角色 voicedesign） ──────────────────────────────

    def _generate_one(
        self,
        char: CharacterProfile,
        instruction: str,
        voice_path: Path,
        language: str,
        reference_text: str,
        timeout: int,
    ) -> str:
        """线程任务：为单个角色生成 voice reference。

        Returns:
            错误字符串（成功时为空 ""）。异常由调用方捕获。
        """
        log_path = voice_path.parent / f"{char.name}.log"
        payload: dict[str, Any] = {
            "text": reference_text,
            "instruction": instruction,
            "language": language,
        }
        if "max_new_tokens" in self.extra_args:
            payload["max_new_tokens"] = int(self.extra_args["max_new_tokens"])

        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
                logf.write("=== INVOCATION ===\n")
                logf.write(f"POST {self.base_url}/v1/voicedesign/generate\n")
                logf.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                logf.write(f"character={char.name}, role_type={char.role_type}\n")
                logf.write(f"gender={char.gender}, age_style={char.age_style}\n")
                logf.write(f"timeout={timeout}s, bypass_proxy={self.bypass_proxy}\n")
                logf.write("=== OUTPUT ===\n")
                logf.flush()
                wav_bytes = self._post_voicedesign(payload, timeout=timeout, logf=logf)

            if not wav_bytes or len(wav_bytes) < 44:
                return f"server returned empty/invalid wav ({len(wav_bytes)} bytes); see {log_path.name}"

            voice_path.write_bytes(wav_bytes)
            return ""
        except Exception as err:  # noqa: BLE001
            return f"{type(err).__name__}: {err}"

    # ── 内部工具 ─────────────────────────────────────────────────────

    def _default_instruction(self, char: CharacterProfile) -> str:
        gender = char.gender or "中性"
        age = char.age_style or "成年"
        if char.role_type == "narrator":
            return f"用平稳亲切的{age}{gender}说书人嗓音说"
        return f"用{age}{gender}的嗓音说"

    def _post_voicedesign(
        self,
        payload: dict[str, Any],
        *,
        timeout: int,
        logf: Any,
    ) -> bytes:
        url = f"{self.base_url}/v1/voicedesign/generate"
        proxies = {"http": None, "https": None} if self.bypass_proxy else None
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
                proxies=proxies,
                verify=False,
            )
        except requests.RequestException as err:
            raise VoicebankError(f"HTTP 请求失败：{err}") from err

        if response.status_code >= 400:
            try:
                logf.write(f"HTTP {response.status_code} {response.reason}\n")
                logf.write(response.text[:2000] + "\n")
                logf.flush()
            except Exception:
                pass
            raise VoicebankError(
                f"HTTP {response.status_code} {response.reason}; "
                f"body 前 200 字符：{response.text[:200]}"
            )

        return response.content

    def _write_dry_run_log(
        self,
        log_path: Path,
        char: CharacterProfile,
        instruction: str,
        language: str,
        reference_text: str,
    ) -> None:
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            logf.write("=== DRY RUN ===\n")
            logf.write(f"POST {self.base_url}/v1/voicedesign/generate\n")
            payload = {
                "text": reference_text,
                "instruction": instruction,
                "language": language,
            }
            logf.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            logf.write(f"character={char.name}, role_type={char.role_type}\n")
            logf.write(f"gender={char.gender}, age_style={char.age_style}\n")
