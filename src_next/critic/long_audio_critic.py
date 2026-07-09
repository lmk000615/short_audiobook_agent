"""Qwen3-Omni 长音频综合听感评估客户端。

调 Qwen3-Omni 服务的 /v1/omni/chat 端点（黄区 10.50.121.102:8011），让模型"听"
一段长音频（典型为 audio_final/*.wav，~2 分钟有声书成品），输出 4 维听感评分。

与 src_next/critic/qwen3omni_critic.py 的 Qwen3OmniCritic 互补：
- Qwen3OmniCritic：吃 1-30s 单段 TTS，5 维 0-1，配合 tts_repair 闭环修复
- Qwen3OmniLongAudioCritic（本模块）：吃 ~2 分钟整段，4 维 0-10 + A/B/C/D，离线整本质检

参考实现：test_long_audio.py（621 行一次性脚本）。本模块把它落到 src_next/critic/ 体系，
提供可重用的类 API。

⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本模块串行调每段，不做并发。

已知限制（v1）：
- 切片硬切：30s 边界可能切断句子。v1 不做 overlap。
- 未集成 pipeline：仅离线 QA 工具，没有 hook 进 core/audiobook_pipeline.py。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import soundfile as sf

from src_next.core.data_models import LongAudioCriticResult, LongAudioSegmentScore
from src_next.critic.prompts.long_audio_prompt import (
    LONG_AUDIO_EVAL_PROMPT,
    LONG_AUDIO_SYSTEM_PROMPT,
)


# ─────────────────────────────────────────────────────────────────────────────
# 模块级工具函数（照搬 test_long_audio.py:82-271）
# ─────────────────────────────────────────────────────────────────────────────

_DIMENSIONS = ("emotion_expressiveness", "rhythm", "naturalness", "clarity")


def _compute_grade(score: float) -> str:
    """根据 0-10 分计算 A/B/C/D 等级。"""
    if score >= 7.5:
        return "A"
    if score >= 5.0:
        return "B"
    if score >= 2.5:
        return "C"
    return "D"


def _to_score(value: Any) -> float:
    """将值转换为 0-10 的分数（clamp + 1 位小数）。"""
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return round(max(0.0, min(10.0, score)), 1)


def _to_short_list(value: Any, max_items: int = 2) -> list[str]:
    """将值规范化为短字符串列表（去空 + 截断）。"""
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(x) for x in value if x is not None]
    else:
        items = [str(value)]
    return [x.strip() for x in items if x.strip()][:max_items]


def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 返回的嵌套 scoring dict 归一化为带 grade/problems 的标准结构。"""
    raw_scores = result.get("scores", result)
    final_scores: dict[str, dict[str, Any]] = {}
    score_values: list[float] = []

    for dim in _DIMENSIONS:
        item = raw_scores.get(dim, {}) if isinstance(raw_scores, dict) else {}
        if isinstance(item, dict):
            score = _to_score(item.get("score", 0))
            reason = str(item.get("reason", "")).strip()
            problems = _to_short_list(item.get("problems", []))
        else:
            score = _to_score(item)
            reason = ""
            problems = []

        final_scores[dim] = {
            "score": score,
            "grade": _compute_grade(score),
            "reason": reason,
            "problems": problems,
        }
        score_values.append(score)

    overall_score = round(sum(score_values) / len(score_values), 2)
    return {
        "scores": final_scores,
        "overall_score": overall_score,
        "overall_grade": _compute_grade(overall_score),
        "main_problems": _to_short_list(result.get("main_problems", []), max_items=3),
        "suggestions": _to_short_list(result.get("suggestions", []), max_items=3),
    }


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """从模型输出中提取第一个完整 JSON 对象（花括号平衡计数 + 字符串转义处理）。"""
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError(f"模型输出中没有找到 JSON：\n{text[:200]}")

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        c = text[i]

        if escape:
            escape = False
            continue

        if c == "\\":
            if in_string:
                escape = True
            continue

        if c == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"模型输出中没有找到合法 JSON：\n{text[:500]}")


def _get_response_text(data: dict[str, Any]) -> str:
    """从 API 响应 JSON 中提取文本字段（兼容 text/response/content/output）。"""
    for key in ("text", "response", "content", "output"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(data, ensure_ascii=False)


def _aggregate_segment_results(segment_results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总多段切片的评分结果：各维度取均值，main_problems/suggestions 取频次最高。"""
    if not segment_results:
        return {}

    if len(segment_results) == 1:
        return segment_results[0]

    dim_scores: dict[str, list[float]] = {dim: [] for dim in _DIMENSIONS}
    dim_reasons: dict[str, list[str]] = {dim: [] for dim in _DIMENSIONS}
    dim_problems: dict[str, list[str]] = {dim: [] for dim in _DIMENSIONS}
    all_main_problems: list[str] = []
    all_suggestions: list[str] = []

    for seg in segment_results:
        scores = seg.get("scores", {})
        for dim in _DIMENSIONS:
            dim_item = scores.get(dim, {})
            dim_scores[dim].append(dim_item.get("score", 0))
            if dim_item.get("reason"):
                dim_reasons[dim].append(dim_item["reason"])
            dim_problems[dim].extend(dim_item.get("problems", []))
        all_main_problems.extend(seg.get("main_problems", []))
        all_suggestions.extend(seg.get("suggestions", []))

    final_scores: dict[str, dict[str, Any]] = {}
    score_values: list[float] = []

    for dim in _DIMENSIONS:
        scores_list = dim_scores[dim]
        avg_score = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
        reason = dim_reasons[dim][-1] if dim_reasons[dim] else ""
        unique_problems = list(dict.fromkeys(dim_problems[dim]))[:2]

        final_scores[dim] = {
            "score": avg_score,
            "grade": _compute_grade(avg_score),
            "reason": reason,
            "problems": unique_problems,
        }
        score_values.append(avg_score)

    overall_score = round(sum(score_values) / len(score_values), 2)

    top_problems = [p for p, _ in Counter(all_main_problems).most_common(3)]
    top_suggestions = [s for s, _ in Counter(all_suggestions).most_common(3)]

    return {
        "scores": final_scores,
        "overall_score": overall_score,
        "overall_grade": _compute_grade(overall_score),
        "main_problems": top_problems,
        "suggestions": top_suggestions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主类
# ─────────────────────────────────────────────────────────────────────────────

class Qwen3OmniLongAudioCritic:
    """用 Qwen3-Omni 多模态模型评估整段长音频的综合听感。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        segment_duration: float = 30.0,
        max_new_tokens: int = 768,
        temperature: float = 0.0,
        timeout: int = 600,
        bypass_proxy: bool = True,
    ) -> None:
        self.base_url = base_url
        self.segment_duration = segment_duration
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
        self._proxies = {"http": None, "https": None} if bypass_proxy else None

    def evaluate(
        self,
        audio_path: str | Path,
        no_segment: bool = False,
    ) -> LongAudioCriticResult:
        """评估长音频。返回 LongAudioCriticResult（全部段失败也不抛异常）。"""
        audio_path = Path(audio_path).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(f"audio file not found: {audio_path}")

        duration = _get_wav_duration(audio_path)
        effective_segment_duration = 0 if no_segment else self.segment_duration

        # 决定是否切片
        if effective_segment_duration <= 0 or duration <= effective_segment_duration:
            segment_paths = [audio_path]
            temp_segments: list[Path] = []
        else:
            segment_paths = _segment_audio(audio_path, effective_segment_duration)
            temp_segments = [p for p in segment_paths if p != audio_path]

        num_segments = len(segment_paths)
        segment_results: list[dict[str, Any]] = []
        segment_details: list[dict[str, Any]] = []
        total_inference_time = 0.0

        try:
            for idx, seg_path in enumerate(segment_paths, 1):
                audio_data_uri = _encode_audio_as_data_uri(seg_path)
                t0 = time.perf_counter()
                try:
                    parsed = self._call_omni(audio_data_uri)
                    normalized = _normalize_result(parsed)
                    inference_time = time.perf_counter() - t0
                    total_inference_time += inference_time
                    segment_results.append(normalized)
                    segment_details.append({**normalized, "_inference_time": round(inference_time, 2)})
                except Exception as exc:
                    inference_time = time.perf_counter() - t0
                    total_inference_time += inference_time
                    err_detail = {
                        "_failed": True,
                        "_error": f"{type(exc).__name__}: {exc}",
                        "_inference_time": round(inference_time, 2),
                    }
                    segment_details.append(err_detail)
        finally:
            for tmp in temp_segments:
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass

        # 构造结果
        if not segment_results:
            return LongAudioCriticResult(
                audio_file=audio_path.name,
                duration_seconds=round(duration, 2),
                num_segments=num_segments,
                segment_duration=effective_segment_duration,
                scores={},
                overall_score=0.0,
                overall_grade="D",
                main_problems=[],
                suggestions=[],
                segment_details=segment_details,
                base_url=self.base_url,
                timestamp=datetime.now().isoformat(),
                total_inference_time=round(total_inference_time, 2),
                error=f"all {num_segments} segments failed; see segment_details for per-segment errors",
            )

        aggregated = (
            segment_results[0]
            if len(segment_results) == 1
            else _aggregate_segment_results(segment_results)
        )

        scores = {
            dim: LongAudioSegmentScore(
                score=dim_item["score"],
                grade=dim_item["grade"],
                reason=dim_item["reason"],
                problems=dim_item["problems"],
            )
            for dim, dim_item in aggregated["scores"].items()
        }

        return LongAudioCriticResult(
            audio_file=audio_path.name,
            duration_seconds=round(duration, 2),
            num_segments=num_segments,
            segment_duration=effective_segment_duration,
            scores=scores,
            overall_score=aggregated["overall_score"],
            overall_grade=aggregated["overall_grade"],
            main_problems=aggregated["main_problems"],
            suggestions=aggregated["suggestions"],
            segment_details=segment_details,
            base_url=self.base_url,
            timestamp=datetime.now().isoformat(),
            total_inference_time=round(total_inference_time, 2),
            error=None,
        )

    def _call_omni(self, audio_data_uri: str) -> dict[str, Any]:
        """单次 omni/chat 调用，返回解析后的 LLM scoring dict。"""
        url = f"{self.base_url.rstrip('/')}/v1/omni/chat"
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": LONG_AUDIO_SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": LONG_AUDIO_EVAL_PROMPT},
                        {"type": "audio", "audio": audio_data_uri},
                    ],
                },
            ],
            "return_audio": False,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
        }
        resp = requests.post(
            url,
            json=payload,
            proxies=self._proxies,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"omni/chat returned HTTP {resp.status_code}: {resp.text[:200]!r}"
            )
        data = resp.json()
        parsed = _extract_json_from_text(_get_response_text(data))
        if not isinstance(parsed, dict):
            raise ValueError(f"omni/chat response parsed to non-dict: {type(parsed).__name__}")
        return parsed


# ─────────────────────────────────────────────────────────────────────────────
# 模块级音频处理工具函数（照搬 test_long_audio.py:82-134）
# ─────────────────────────────────────────────────────────────────────────────

def _get_wav_duration(audio_path: Path) -> float:
    """获取音频时长（秒）——soundfile 优先，wave 兜底。"""
    try:
        info = sf.info(str(audio_path))
        return float(info.frames) / float(info.samplerate)
    except Exception:
        import wave
        with wave.open(str(audio_path), "rb") as wf:
            return float(wf.getnframes()) / float(wf.getframerate())


def _encode_audio_as_data_uri(audio_path: Path) -> str:
    """将音频文件编码为 data URI（base64）。"""
    mime_type, _ = mimetypes.guess_type(str(audio_path))
    if not mime_type:
        mime_type = "audio/wav"
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def _segment_audio(audio_path: Path, segment_duration: float) -> list[Path]:
    """将长音频按指定时长切片，返回临时文件路径列表。调用方负责删除临时文件。"""
    data, samplerate = sf.read(str(audio_path))
    total_samples = len(data)
    samples_per_segment = int(segment_duration * samplerate)

    if total_samples <= samples_per_segment:
        return [audio_path]

    num_segments = (total_samples + samples_per_segment - 1) // samples_per_segment
    segments: list[Path] = []

    for i in range(num_segments):
        start = i * samples_per_segment
        end = min(start + samples_per_segment, total_samples)
        segment_data = data[start:end]

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        sf.write(tmp_path, segment_data, samplerate, subtype="PCM_16")
        segments.append(Path(tmp_path))

    return segments
