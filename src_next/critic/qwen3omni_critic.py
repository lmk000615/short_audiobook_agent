"""Qwen3-Omni 音频评估客户端。

调 Qwen3-Omni 服务的 /v1/omni/audio_analysis 端点（黄区 10.50.121.102:8011），
让模型"听"一段 TTS 合成音频，输出 5 维评分 + 修复建议。

⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。

⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
如果服务返回的不是评分 JSON，按 KNOWN_ISSUES.md §2 切换到 /v1/omni/chat。
"""
from __future__ import annotations

import json
import re

import requests

from src_next.critic.prompts.critic_prompt import build_critic_prompt
from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)


def _strip_code_fence(raw: str) -> str:
    """Strip leading/trailing ```json ... ``` fences if present."""
    return _CODE_FENCE_RE.sub("", raw.strip())


def _extract_first_json(raw: str) -> dict | None:
    """Find the first balanced {...} block in raw using raw_decode. Returns None if not found."""
    decoder = json.JSONDecoder()
    s = raw.strip()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = decoder.raw_decode(s[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def _parse_scoring_json(raw_text: str) -> dict:
    """Parse Qwen3-Omni's response text into a scoring dict.

    Three-step fallback (borrowed from Audio-Oscar's parse_llm_json_payload):
      1. Strip ```json fences
      2. Try json.loads directly
      3. Fall back to raw_decode scanning for first {...}

    Raises ValueError if no JSON object can be extracted.
    """
    cleaned = _strip_code_fence(raw_text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    obj = _extract_first_json(cleaned)
    if obj is None:
        raise ValueError(f"no JSON object found in response: {raw_text[:200]!r}")
    return obj


_CRITIC_DIMS = ("quality", "emotion_alignment", "character_consistency",
                "rhythm_naturalness", "intelligibility")


def _normalize_nested_scoring(scoring: dict, segment_id: str, attempt: int) -> dict:
    """Convert LLM's nested schema to CriticResult.from_json-compatible flat dict.

    LLM output (new nested 0-10 + A/B/C/D schema):
        {"scores": {"quality": {"score": 8.5, "grade": "A", ...}, ...},
         "overall_score": 8.6, "overall_grade": "A",
         "main_problems": [...], "suggestions": [...]}

    Returns flat dict (compatible with CriticResult.from_json):
        {"segment_id": ..., "quality": 0.85, ..., "suggestions": "p1；s1"}

    Note: LLM's overall_score is intentionally ignored — CriticResult.from_json
    computes overall from 5-dim average (LLM's overall is redundant info).

    If the input is already flat (legacy schema), returns it with segment_id/attempt defaulted.
    """
    if "scores" not in scoring or not isinstance(scoring["scores"], dict):
        scoring.setdefault("segment_id", segment_id)
        scoring.setdefault("attempt", attempt)
        return scoring

    def _extract_dim_score(dim_name: str) -> float:
        dim_obj = scoring["scores"].get(dim_name, {})
        if not isinstance(dim_obj, dict):
            return 5.0
        try:
            raw = float(dim_obj.get("score", 5.0))
        except (TypeError, ValueError):
            raw = 5.0
        return max(0.0, min(10.0, raw))

    flat = {dim: _extract_dim_score(dim) / 10.0 for dim in _CRITIC_DIMS}
    flat["segment_id"] = segment_id
    flat["attempt"] = attempt

    main_problems = scoring.get("main_problems", []) or []
    suggestions_list = scoring.get("suggestions", []) or []
    combined: list[str] = []
    for item in list(main_problems) + list(suggestions_list):
        s = str(item).strip()
        if s and s not in combined:
            combined.append(s)
    flat["suggestions"] = "；".join(combined[:3]) if combined else "无具体建议"

    return flat


class Qwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频质量。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        timeout: int = 120,
        bypass_proxy: bool = True,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
        self._proxies = {"http": None, "https": None} if bypass_proxy else None

    def evaluate(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
    ) -> CriticResult:
        """评估单段音频。失败不抛异常，返回 overall=0.5 中性结果。"""
        try:
            return self._evaluate_inner(audio_path, segment, tts_instruction)
        except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback
            return self._neutral_result(segment.segment_id, tts_instruction.attempt, str(exc))

    def _evaluate_inner(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
    ) -> CriticResult:
        prompt_text = build_critic_prompt(segment, tts_instruction)
        payload = {
            "audio": audio_path,
            "task": "sound_analysis",
            "text": prompt_text,
            "return_audio": False,
            "max_new_tokens": 1024,
        }
        url = f"{self.base_url}/v1/omni/audio_analysis"
        resp = requests.post(
            url,
            json=payload,
            proxies=self._proxies,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"audio_analysis returned HTTP {resp.status_code}: {resp.text[:200]!r}"
            )
        data = resp.json()
        raw_text = str(data.get("text", ""))
        if not raw_text:
            raise RuntimeError("audio_analysis returned empty text field")
        scoring = _parse_scoring_json(raw_text)
        flat = _normalize_nested_scoring(scoring, segment.segment_id, tts_instruction.attempt)
        return CriticResult.from_json(flat, attempt=tts_instruction.attempt)

    @staticmethod
    def _neutral_result(segment_id: str, attempt: int, err_msg: str) -> CriticResult:
        """Neutral 0.5 fallback when evaluation fails — per task card §1.3.1.

        Note: deliberately 0.5 (not 0.0 like Audio-Oscar) so that transient
        failures (network blips) don't force unnecessary repair cascades.
        """
        return CriticResult(
            segment_id=segment_id,
            quality=0.5,
            emotion_alignment=0.5,
            character_consistency=0.5,
            rhythm_naturalness=0.5,
            intelligibility=0.5,
            overall=0.5,
            suggestions=f"评估失败：{err_msg}，建议人工复核",
            attempt=attempt,
        )
