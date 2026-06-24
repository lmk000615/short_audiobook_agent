"""src_next/tts/indextts_http.py

IndexTTS-2 HTTP TTS adapter（黄区内网调用）。

调用方式：HTTP POST 到 ``{base_url}/v1/tts/synthesize``，请求体包含
``{text, reference_audio_base64, emotion_vector, emotion_alpha, ...}``，
响应体直接是 wav 字节流。

和 ``indextts_adapter.py`` 的差异：
* 不跑 subprocess、不依赖本地 indextts env；
* 不需要 ``engine_root`` / ``batch_wrapper_path`` / ``python_executable``；
* 用 ``requests.post`` 直连服务器，默认 bypass 代理；
* 用 base64 把 voice_ref wav 上传到服务器（usage_guide 推荐）。

API 参考：``usage_guide_indextts.md``（项目根目录）。

参数映射（**充分利用 TTSInstruction**）：
    instruction.text              → payload.text
    instruction.voice_ref         → 读取 wav 文件 → base64 → payload.reference_audio_base64
    instruction.emotion           → 8 维 emotion_vector（usage_guide 的 8 种基础情绪）
    instruction.emotion_intensity → payload.emotion_alpha（clamp 到 [0.3, 1.0]，
                                    usage_guide 推荐区间 0.6-1.0，过弱不可见）
    pace / volume / pitch / stress_words / delivery_instruction
                                  → IndexTTS-2 原生不支持，只写 per-segment log

并发：默认 4 线程并发合成，可经 ``extra_args.max_workers`` 调整。
requests 模块级 ``post`` 是线程安全的（不共享 Session）；每段写各自的 log
+ wav，无共享可变状态。为后续 WebUI 的 RTF 优化做准备。
"""

from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from src_next.core.data_models import AudioSegmentResult, TTSInstruction, VoicebankResult

from .base import BaseTTSAdapter, TTSError


urllib3.disable_warnings(InsecureRequestWarning)


_DEFAULT_OUTPUT_SUBDIR = "audio_segments"
_DEFAULT_TIMEOUT_PER_SEG = 60
_DEFAULT_MAX_WORKERS = 4


# ── Emotion → 8 维向量映射（usage_guide_indextts.md 表） ────────────
# 8 维顺序：[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]

_BASE_EMOTION_VECTORS: dict[str, list[float]] = {
    "happy":       [0.8, 0,   0,   0,   0,   0,   0,   0.2],
    "angry":       [0,   0.8, 0,   0,   0,   0,   0,   0.2],
    "sad":         [0,   0,   0.8, 0,   0,   0.1, 0,   0.1],
    "afraid":      [0,   0,   0,   0.8, 0,   0,   0,   0.2],
    "disgusted":   [0,   0,   0,   0,   0.8, 0,   0,   0.2],
    "melancholic": [0,   0,   0,   0,   0,   0.8, 0,   0.2],
    "surprised":   [0,   0,   0,   0,   0,   0,   0.8, 0.2],
    "calm":        [0,   0,   0,   0,   0,   0,   0,   1.0],
}

# analysis/story_director.py 产出的 emotion 词表 → 8 维基础情绪。
# 未命中默认归到 calm（不影响合成，只让 IndexTTS-2 走自然语气）。
_EMOTION_VOCAB_TO_BASE: dict[str, str] = {
    # happy family
    "happy": "happy",
    "joyful": "happy",
    "excited": "happy",
    "playful": "happy",
    "warm": "happy",
    # angry family
    "angry": "angry",
    "serious": "angry",
    # sad family
    "sad": "sad",
    "moved": "sad",
    # afraid family
    "afraid": "afraid",
    "anxious": "afraid",
    # melancholic family
    "melancholic": "melancholic",
    "longing": "melancholic",
    "nostalgic": "melancholic",
    # surprised family
    "surprised": "surprised",
    # calm family
    "calm": "calm",
    "neutral": "calm",
    "gentle": "calm",
}


def _emotion_to_vector(emotion: str) -> list[float]:
    """通用 emotion 词 → IndexTTS-2 8 维向量（固定模板，不随 intensity 变化）。

    intensity 单独走 emotion_alpha 通道（usage_guide 的设计）。
    """
    key = (emotion or "").strip().lower()
    base_key = _EMOTION_VOCAB_TO_BASE.get(key, "calm")
    return list(_BASE_EMOTION_VECTORS[base_key])


def _intensity_to_alpha(intensity: float) -> float:
    """emotion_intensity [0,1] → emotion_alpha。

    usage_guide 推荐 0.6-1.0；过弱（< 0.3）几乎听不出情绪，clamp 下限 0.3。
    """
    try:
        v = float(intensity)
    except (TypeError, ValueError):
        return 0.6
    return max(0.3, min(1.0, v))


# ── adapter 类 ────────────────────────────────────────────────────────

class IndexTTSHTTPAdapter(BaseTTSAdapter):
    """IndexTTS-2 的 HTTP adapter（带情绪向量 + 并发合成）。"""

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
            raise TTSError(
                "IndexTTSHTTPAdapter 缺少 base_url。"
                "请在 profile 配置 tts.base_url，例如 http://10.50.121.102:8009"
            )
        self.output_subdir = (output_subdir or _DEFAULT_OUTPUT_SUBDIR).strip() or _DEFAULT_OUTPUT_SUBDIR
        self.extra_args: dict[str, Any] = dict(extra_args) if extra_args else {}
        self.bypass_proxy = bool(self.extra_args.get("bypass_proxy", True))

    # ── BaseTTSAdapter 实现 ──────────────────────────────────────────

    def synthesize(
        self,
        instructions: list[TTSInstruction],
        voicebank_result: VoicebankResult,
        output_dir: str,
        *,
        dry_run: bool = False,
        limit: int = 0,
        max_workers: int | None = None,
        **_kwargs: Any,
    ) -> list[AudioSegmentResult]:
        audio_dir = Path(output_dir).expanduser() / self.output_subdir
        audio_dir.mkdir(parents=True, exist_ok=True)

        speaker_to_voice = (voicebank_result.speaker_to_voice if voicebank_result else {}) or {}

        config_snapshot = {
            "backend": "indextts_http",
            "base_url": self.base_url,
            "output_subdir": self.output_subdir,
            "extra_args": self.extra_args,
            "dry_run": dry_run,
            "limit": limit,
            "max_workers": max_workers or int(self.extra_args.get("max_workers", _DEFAULT_MAX_WORKERS)),
        }
        (audio_dir / "adapter_config.json").write_text(
            json.dumps(config_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        n = len(instructions) if not limit or limit <= 0 else min(limit, len(instructions))
        timeout = int(self.extra_args.get("timeout_per_seg", _DEFAULT_TIMEOUT_PER_SEG))

        # ── 分类：哪些直接出结果 / 哪些要进线程池 ───────────────────
        results: list[AudioSegmentResult | None] = [None] * len(instructions)
        # 每项：(idx, inst, voice_ref_path)
        to_synth: list[tuple[int, TTSInstruction, Path]] = []
        errors: list[str] = []

        for idx in range(len(instructions)):
            inst = instructions[idx]

            # limit 外
            if idx >= n:
                results[idx] = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False, error="skipped: beyond --limit",
                )
                continue

            # voice_ref 解析
            voice_ref = (inst.voice_ref or "").strip() or (speaker_to_voice.get(inst.speaker) or "").strip()
            if not voice_ref:
                msg = (
                    f"missing voice_ref for speaker={inst.speaker!r}; "
                    "check voicebank_result or tts_instruction_builder fallback chain"
                )
                errors.append(f"{inst.segment_id}: {msg}")
                results[idx] = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False, error=msg,
                )
                continue

            output_wav = audio_dir / inst.output_filename

            # 缓存命中：直接复用
            if output_wav.exists() and output_wav.stat().st_size > 0:
                results[idx] = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=str(output_wav), success=True, error="",
                )
                continue

            voice_ref_path = Path(voice_ref)
            if not voice_ref_path.exists() or voice_ref_path.stat().st_size == 0:
                msg = f"voice_ref wav missing/empty: {voice_ref}"
                errors.append(f"{inst.segment_id}: {msg}")
                results[idx] = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False, error=msg,
                )
                continue

            # dry_run：只写 invocation snapshot
            if dry_run:
                log_path = audio_dir / f"{Path(inst.output_filename).stem}.log"
                self._write_dry_run_log(log_path, inst, voice_ref)
                results[idx] = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False, error="dry_run: not invoked",
                )
                continue

            to_synth.append((idx, inst, voice_ref_path))

        # ── 并发合成 ────────────────────────────────────────────────
        if to_synth:
            workers = max_workers or int(self.extra_args.get("max_workers", _DEFAULT_MAX_WORKERS))
            workers = max(1, min(workers, len(to_synth)))
            print(
                f"[indextts_http] synthesizing {len(to_synth)} segments "
                f"with {workers} workers (timeout={timeout}s/seg)",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="indextts") as ex:
                future_to_idx = {
                    ex.submit(
                        self._synthesize_one,
                        inst, voice_ref_path, audio_dir / inst.output_filename, audio_dir, timeout,
                    ): idx
                    for idx, inst, voice_ref_path in to_synth
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        results[idx] = future.result()
                    except Exception as err:  # noqa: BLE001
                        inst = instructions[idx]
                        msg = f"worker exception: {type(err).__name__}: {err}"
                        errors.append(f"{inst.segment_id}: {msg}")
                        results[idx] = AudioSegmentResult(
                            segment_id=inst.segment_id, speaker=inst.speaker,
                            audio_path=None, success=False, error=msg,
                        )

        # ── 收尾：errors.log + 兜底 None 替换 ──────────────────────
        final_results: list[AudioSegmentResult] = []
        for i, r in enumerate(results):
            if r is None:
                inst = instructions[i]
                r = AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False, error="internal: result not set",
                )
                errors.append(f"{inst.segment_id}: internal result None")
            elif not r.success and not r.error.startswith("skipped"):
                errors.append(f"{r.segment_id}: {r.error}")
            final_results.append(r)

        if errors:
            (audio_dir / "errors.log").write_text(
                "\n".join(errors) + "\n", encoding="utf-8",
            )

        return final_results

    # ── 线程任务（单段合成） ─────────────────────────────────────────

    def _synthesize_one(
        self,
        inst: TTSInstruction,
        voice_ref_path: Path,
        output_wav: Path,
        audio_dir: Path,
        timeout: int,
    ) -> AudioSegmentResult:
        """线程任务：合成单段。异常由调用方捕获。"""
        log_path = audio_dir / f"{Path(inst.output_filename).stem}.log"

        try:
            voice_b64 = base64.b64encode(voice_ref_path.read_bytes()).decode("ascii")
            emotion_vector = _emotion_to_vector(inst.emotion)
            emo_alpha = _intensity_to_alpha(inst.emotion_intensity)

            payload: dict[str, Any] = {
                "text": inst.text,
                "reference_audio_base64": voice_b64,
                "emotion_vector": emotion_vector,
                "emotion_alpha": emo_alpha,
            }
            # extra_args 里的采样参数（可选）
            for k in ("temperature", "top_p", "top_k", "num_beams",
                      "repetition_penalty", "max_text_tokens", "max_mel_tokens",
                      "interval_silence"):
                if k in self.extra_args:
                    payload[k] = self.extra_args[k]

            with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
                logf.write("=== INVOCATION ===\n")
                logf.write(f"POST {self.base_url}/v1/tts/synthesize\n")
                logf.write(f"text={inst.text!r}\n")
                logf.write(f"reference_audio_base64=<{len(voice_b64)} chars>\n")
                logf.write(f"emotion={inst.emotion!r} → vector={emotion_vector}\n")
                logf.write(f"emotion_alpha={emo_alpha} (from intensity={inst.emotion_intensity:.2f})\n")
                logf.write(f"extra_payload_keys={sorted(k for k in payload if k not in ('text', 'reference_audio_base64', 'emotion_vector', 'emotion_alpha'))}\n")
                logf.write("=== STYLE (NOT passed to IndexTTS; logged only) ===\n")
                logf.write(self._format_style_snapshot(inst) + "\n")
                logf.write(f"timeout={timeout}s, bypass_proxy={self.bypass_proxy}\n")
                logf.write("=== OUTPUT ===\n")
                logf.flush()
                wav_bytes = self._post_synthesize(payload, timeout=timeout, logf=logf)

            if not wav_bytes or len(wav_bytes) < 44:
                return AudioSegmentResult(
                    segment_id=inst.segment_id, speaker=inst.speaker,
                    audio_path=None, success=False,
                    error=f"server returned empty/invalid wav ({len(wav_bytes)} bytes); see {log_path.name}",
                )

            output_wav.write_bytes(wav_bytes)
            return AudioSegmentResult(
                segment_id=inst.segment_id, speaker=inst.speaker,
                audio_path=str(output_wav), success=True, error="",
            )
        except Exception as err:  # noqa: BLE001
            return AudioSegmentResult(
                segment_id=inst.segment_id, speaker=inst.speaker,
                audio_path=None, success=False,
                error=f"{type(err).__name__}: {err}",
            )

    # ── 内部工具 ─────────────────────────────────────────────────────

    def _format_style_snapshot(self, inst: TTSInstruction) -> str:
        stress = inst.stress_words if isinstance(inst.stress_words, list) else []
        return (
            f"emotion={inst.emotion}; intensity={inst.emotion_intensity:.2f}; "
            f"tone={inst.tone}; volume={inst.volume}; pitch={inst.pitch}; "
            f"pace={inst.pace:.2f}; pause_hint={inst.pause_hint:.2f}; "
            f"stress_words={stress}; delivery={inst.delivery_instruction!r}"
        )

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
            raise TTSError(f"HTTP 请求失败：{err}") from err

        if response.status_code >= 400:
            try:
                logf.write(f"HTTP {response.status_code} {response.reason}\n")
                logf.write(response.text[:2000] + "\n")
                logf.flush()
            except Exception:
                pass
            raise TTSError(
                f"HTTP {response.status_code} {response.reason}; "
                f"body 前 200 字符：{response.text[:200]}"
            )

        return response.content

    def _write_dry_run_log(
        self,
        log_path: Path,
        inst: TTSInstruction,
        voice_ref: str,
    ) -> None:
        emotion_vector = _emotion_to_vector(inst.emotion)
        emo_alpha = _intensity_to_alpha(inst.emotion_intensity)
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            logf.write("=== DRY RUN ===\n")
            logf.write(f"POST {self.base_url}/v1/tts/synthesize\n")
            logf.write(f"text={inst.text!r}\n")
            logf.write(f"voice_ref={voice_ref}\n")
            logf.write(f"emotion={inst.emotion!r} → vector={emotion_vector}\n")
            logf.write(f"emotion_alpha={emo_alpha}\n")
            logf.write("=== STYLE (NOT passed to IndexTTS; logged only) ===\n")
            logf.write(self._format_style_snapshot(inst) + "\n")
