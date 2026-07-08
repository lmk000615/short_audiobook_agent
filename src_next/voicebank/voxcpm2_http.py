"""src_next/voicebank/voxcpm2_http.py

VoxCPM2 (openbmb/VoxCPM2) VoiceDesign HTTP voicebank adapter（黄区内网调用，并发版）。

调用方式：HTTP POST 到 ``{base_url}/v1/tts/synthesize``，
请求体 ``{text}`` 单字段——**音色描述内嵌在 text 开头**，形如：
    "(年轻女性，温柔甜美的声音)你好，欢迎使用 VoxCPM2。"
响应体直接是 wav 字节流（48 kHz）。

和 ``qwen3_http.py`` 的差异：
* endpoint 不同：``/v1/voicedesign/generate`` → ``/v1/tts/synthesize``；
* payload 不同：``{text, instruction, language}`` 三字段 → ``{text}`` 单字段
  （VoxCPM2 把音色描述用括号内嵌到 text 开头，不单独传 instruction）；
* 输出采样率不同：24 kHz → **48 kHz**（VoxCPM2 内置超分）；
* 不支持 language 字段（VoxCPM2 自动识别 30 种语言，无需指定）。

和 ``qwen3_http.py`` 的相同点：
* 4 worker 并发为多个角色生成 voice reference；
* bypass_proxy=True 默认开启（黄区硬约束，CLAUDE.md §5.6）；
* 失败角色记 errors.log，不阻断其他角色；
* 缓存命中（同名 wav 已存在）自动跳过；
* 支持 dry_run（不真实调用，只写日志）。

**v1 范围**：只支持 voice_design 模式（无 reference_audio）。
克隆模式（reference_audio / prompt_audio + prompt_text）留 v2，
因为需要 ``core/data_models.py`` 扩展字段（违反 §5 不变量）。

采样率提示：
    本后端输出 **48 kHz** wav。下游 TTS adapter（cosyvoice_http / indextts_http /
    s2pro_http）若需要 24/22 kHz，由 adapter 自行重采样（参考 commit e8c6b2c
    audio_merger 跨 backend 重采样逻辑）。voicebank 层不重采样。

API 参考：``usage_guide_voicecpm2.md``（项目根目录）。
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
_DEFAULT_REFERENCE_TEXT = "你好，欢迎使用 VoxCPM2 角色音色生成系统。"
_DEFAULT_TIMEOUT = 90  # VoxCPM2 显存 8 GB，比 Qwen3 大；首次推理有 30s warm-up
_DEFAULT_MAX_WORKERS = 4


class VoxCPM2HTTPAdapter(BaseVoicebankAdapter):
    """VoxCPM2 VoiceDesign 的 HTTP adapter（并发版）。"""

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
                "VoxCPM2HTTPAdapter 缺少 base_url。"
                "请在 profile 配置 voicebank.base_url，例如 http://10.50.121.102:8012"
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
            "backend": "voxcpm2_http",
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

        reference_text = str(self.extra_args.get("reference_text", _DEFAULT_REFERENCE_TEXT))
        timeout = int(self.extra_args.get("timeout_per_char", _DEFAULT_TIMEOUT))

        # ── 分类：哪些直接出结果 / 哪些要进线程池 ───────────────────
        speaker_to_voice: dict[str, str] = {}
        errors: list[str] = []
        # to_gen: list of (char_idx, char, voice_prompt, voice_path)
        to_gen: list[tuple[int, CharacterProfile, str, Path]] = []

        for idx, char in enumerate(characters):
            voice_path = voicebank_dir / f"{char.name}.wav"

            if voice_path.exists() and voice_path.stat().st_size > 0:
                speaker_to_voice[char.name] = str(voice_path)
                continue

            voice_prompt = (char.voice_prompt or "").strip() or self._default_prompt(char)

            if dry_run:
                log_path = voicebank_dir / f"{char.name}.log"
                self._write_dry_run_log(log_path, char, voice_prompt, reference_text)
                errors.append(f"{char.name}: dry_run, not invoked")
                continue

            to_gen.append((idx, char, voice_prompt, voice_path))

        # ── 并发 voicedesign ────────────────────────────────────────
        if to_gen:
            workers = max_workers or int(self.extra_args.get("max_workers", _DEFAULT_MAX_WORKERS))
            workers = max(1, min(workers, len(to_gen)))
            print(
                f"[voxcpm2_http] generating {len(to_gen)} voice references "
                f"with {workers} workers (timeout={timeout}s/char)",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="voxcpm2voice") as ex:
                future_to_meta = {
                    ex.submit(
                        self._generate_one, char, voice_prompt, voice_path,
                        reference_text, timeout,
                    ): (idx, char.name, voice_path)
                    for idx, char, voice_prompt, voice_path in to_gen
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
            backend="voxcpm2_http",
            success=(not errors),
        )

    # ── 线程任务（单角色 voicedesign） ──────────────────────────────

    def _generate_one(
        self,
        char: CharacterProfile,
        voice_prompt: str,
        voice_path: Path,
        reference_text: str,
        timeout: int,
    ) -> str:
        """线程任务：为单个角色生成 voice reference。

        Returns:
            错误字符串（成功时为空 ""）。异常由调用方捕获。
        """
        log_path = voice_path.parent / f"{char.name}.log"
        # VoxCPM2 voice_design：把描述内嵌到 text 开头，括号包裹
        text = f"({voice_prompt}){reference_text}"
        payload: dict[str, Any] = {"text": text}

        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
                logf.write("=== INVOCATION ===\n")
                logf.write(f"POST {self.base_url}/v1/tts/synthesize\n")
                logf.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                logf.write(f"character={char.name}, role_type={char.role_type}\n")
                logf.write(f"gender={char.gender}, age_style={char.age_style}\n")
                logf.write(f"timeout={timeout}s, bypass_proxy={self.bypass_proxy}\n")
                logf.write(f"expected sample_rate=48000 Hz\n")
                logf.write("=== OUTPUT ===\n")
                logf.flush()
                wav_bytes = self._post_synthesize(payload, timeout=timeout, logf=logf)

            if not wav_bytes or len(wav_bytes) < 44:
                return f"server returned empty/invalid wav ({len(wav_bytes)} bytes); see {log_path.name}"

            voice_path.write_bytes(wav_bytes)
            return ""
        except Exception as err:  # noqa: BLE001
            return f"{type(err).__name__}: {err}"

    # ── 内部工具 ─────────────────────────────────────────────────────

    def _default_prompt(self, char: CharacterProfile) -> str:
        """角色音色描述兜底（当 CharacterProfile.voice_prompt 为空时）。"""
        gender = char.gender or "中性"
        age = char.age_style or "成年"
        if char.role_type == "narrator":
            return f"{age}{gender}，平稳亲切的说书人嗓音"
        return f"{age}{gender}，自然清晰的角色嗓音"

    def _post_synthesize(
        self,
        payload: dict[str, Any],
        *,
        timeout: int,
        logf: Any,
    ) -> bytes:
        url = f"{self.base_url}/v1/tts/synthesize"
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
        voice_prompt: str,
        reference_text: str,
    ) -> None:
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            logf.write("=== DRY RUN ===\n")
            logf.write(f"POST {self.base_url}/v1/tts/synthesize\n")
            text = f"({voice_prompt}){reference_text}"
            payload = {"text": text}
            logf.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            logf.write(f"character={char.name}, role_type={char.role_type}\n")
            logf.write(f"gender={char.gender}, age_style={char.age_style}\n")
            logf.write(f"expected sample_rate=48000 Hz (not actually invoked)\n")
