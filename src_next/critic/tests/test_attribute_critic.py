"""AttributeAwareQwen3OmniCritic unit tests.

Mock-based tests run by default. Integration tests (real Qwen3-Omni service) are
skip-marked with `RUN_INTEGRATION=1` env var — see INTEGRATION_HANDOFF.md.
"""
from __future__ import annotations

import json
import os
from typing import Any

import pytest

from src_next.core.data_models import (
    CriticResult,
    DirectorInstruction,
    ModelSpecificTTSInstruction,
    Segment,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_segment_instruction_director() -> tuple[Segment, ModelSpecificTTSInstruction, DirectorInstruction]:
    """Build a representative (segment, instruction, director) triple for tests."""
    seg = Segment(
        segment_id="s1",
        text="窗外下着大雨。",
        speaker="narrator",
        segment_type="narration",
        raw_index=0,
    )
    inst = ModelSpecificTTSInstruction(
        segment_id="s1",
        speaker="narrator",
        text="窗外下着大雨。",
        model="CosyVoice3",
        parameters={"instruct_text": "温暖叙述"},
        attempt=1,
    )
    di = DirectorInstruction(
        segment_id="s1",
        speaker="narrator",
        emotion="sad",
        emotion_intensity=0.8,
        pace=0.85,
        tone="gentle",
        volume="soft",
        pitch="medium_low",
        delivery_instruction="缓慢叙述，带悲伤感",
    )
    return seg, inst, di


def _make_llm_full_response(intensity_match: bool = False,
                            overall_verdict: str = "medium") -> dict[str, Any]:
    """Build a complete mock LLM response with extracted/expected/consistency + 5 dims."""
    return {
        "extracted_attributes": {
            "emotion": "sad",
            "intensity": 0.6,
            "pace": 0.95,
            "volume": "soft",
            "pitch": "medium_low",
            "evidence": "句尾下沉、语速偏慢、气息短促",
        },
        "expected_attributes": {
            # Deliberately different from DirectorInstruction to test "truth source" override
            "emotion": "WRONG_FROM_LLM",
            "intensity": 0.99,
            "pace": 1.30,
        },
        "attribute_consistency": {
            "emotion": {"match": True, "note": "情绪基调一致"},
            "intensity": {"match": intensity_match, "note": "期望 0.8 强烈悲伤，实际 0.6 偏弱"},
            "pace": {"match": True, "note": "语速基本贴合"},
            "volume": {"match": True, "note": ""},
            "pitch": {"match": True, "note": ""},
            "overall_verdict": overall_verdict,
            "inconsistency_summary": "情感强度不足，悲伤感不够到位",
        },
        "scores": {
            "quality": {"score": 8.5, "grade": "A", "reason": "清晰干净", "problems": []},
            "emotion_alignment": {"score": 6.0, "grade": "B", "reason": "悲伤强度不足", "problems": ["强度偏弱"]},
            "character_consistency": {"score": 8.0, "grade": "A", "reason": "符合角色", "problems": []},
            "rhythm_naturalness": {"score": 8.0, "grade": "A", "reason": "节奏自然", "problems": []},
            "intelligibility": {"score": 9.0, "grade": "A", "reason": "字字清晰", "problems": []},
        },
        "overall_score": 7.9,
        "overall_grade": "B",
        "main_problems": ["情感强度不足"],
        "suggestions": ["提高 emotion_intensity 至 0.8"],
    }


class _FakeOkResponse:
    """200 with valid nested scoring JSON in the text field."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return {"request_id": "fake-req-1", "text": json.dumps(self._payload, ensure_ascii=False)}

    @property
    def text(self) -> str:
        return json.dumps(self.json(), ensure_ascii=False)


class _FakeHttp500Response:
    status_code = 500
    text = "internal server error"

    def json(self) -> dict[str, Any]:
        raise ValueError("not JSON")


class _FakeNonJsonResponse:
    """200 but text field is plain English (no JSON)."""

    status_code = 200

    def json(self) -> dict[str, Any]:
        return {"text": "Sorry, I cannot evaluate this audio."}

    @property
    def text(self) -> str:
        return json.dumps(self.json(), ensure_ascii=False)


class _FakeEmptyTextFieldResponse:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {"text": ""}

    @property
    def text(self) -> str:
        return json.dumps(self.json(), ensure_ascii=False)


def _patch_post(monkeypatch, response_obj_or_factory) -> dict[str, Any]:
    """Patch requests.post on the attribute_critic module. Returns captured call kwargs."""
    import src_next.critic.attribute_critic as mod

    captured: dict[str, Any] = {}

    def fake_post(url, json=None, proxies=None, timeout=None, **kw):
        captured["url"] = url
        captured["json"] = json
        captured["proxies"] = proxies
        captured["timeout"] = timeout
        if callable(response_obj_or_factory):
            return response_obj_or_factory()
        return response_obj_or_factory

    monkeypatch.setattr(mod.requests, "post", fake_post)
    return captured


# ─────────────────────────────────────────────────────────────────────────────
# Construction
# ─────────────────────────────────────────────────────────────────────────────


def test_critic_can_be_constructed_with_defaults():
    """AttributeAwareQwen3OmniCritic should construct with documented defaults."""
    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic

    critic = AttributeAwareQwen3OmniCritic()
    assert critic.base_url == "http://10.50.121.102:8011"
    assert critic.timeout == 120
    assert critic.bypass_proxy is True
    # bypass_proxy=True forces proxies to {"http": None, "https": None}
    assert critic._proxies == {"http": None, "https": None}


# ─────────────────────────────────────────────────────────────────────────────
# evaluate success path
# ─────────────────────────────────────────────────────────────────────────────


def test_evaluate_success_full_schema(monkeypatch, tmp_path):
    """Mock 200 + complete schema → all fields parsed correctly."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    captured = _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)

    # HTTP call shape
    assert captured["url"] == "http://10.50.121.102:8011/v1/omni/chat"
    assert "text" in captured["json"]
    assert "audio" in captured["json"]
    assert captured["proxies"] == {"http": None, "https": None}

    # 5 dims normalized to 0-1
    assert result.segment_id == "s1"
    assert 0.84 <= result.quality <= 0.86
    assert 0.59 <= result.emotion_alignment <= 0.61
    assert 0.79 <= result.character_consistency <= 0.81
    assert 0.79 <= result.rhythm_naturalness <= 0.81
    assert 0.89 <= result.intelligibility <= 0.91
    # overall = 5-dim average
    expected_overall = (0.85 + 0.60 + 0.80 + 0.80 + 0.90) / 5
    assert abs(result.overall - expected_overall) < 0.01

    # extracted_attributes from LLM
    assert result.extracted_attributes["emotion"] == "sad"
    assert result.extracted_attributes["intensity"] == 0.6
    assert result.extracted_attributes["evidence"] == "句尾下沉、语速偏慢、气息短促"

    # attribute_consistency from LLM
    assert result.attribute_consistency["overall_verdict"] == "medium"
    assert result.attribute_consistency["intensity"]["match"] is False

    # suggestions merged into str
    assert isinstance(result.suggestions, str)
    assert "emotion_intensity" in result.suggestions or "情感强度" in result.suggestions


def test_expected_attributes_from_director_not_llm(monkeypatch, tmp_path):
    """CRITICAL: result.expected_attributes must follow DirectorInstruction, NOT LLM回填.

    The mock LLM deliberately lies (emotion='WRONG_FROM_LLM', intensity=0.99). The result
    must still reflect DirectorInstruction's truth-source values.
    """
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)

    # expected_attributes must equal DirectorInstruction render, NOT LLM output
    assert result.expected_attributes["emotion"] == "sad"  # not "WRONG_FROM_LLM"
    assert result.expected_attributes["intensity"] == 0.8  # not 0.99
    assert result.expected_attributes["pace"] == 0.85
    assert result.expected_attributes["tone"] == "gentle"
    assert result.expected_attributes["volume"] == "soft"
    assert result.expected_attributes["pitch"] == "medium_low"
    assert result.expected_attributes["delivery_instruction"] == "缓慢叙述，带悲伤感"


def test_evaluate_consistency_driven_suggestions(monkeypatch, tmp_path):
    """When overall_verdict=low, suggestions should be non-empty."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response(overall_verdict="low")
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)

    assert result.attribute_consistency["overall_verdict"] == "low"
    assert result.suggestions  # non-empty


def test_evaluate_missing_extracted_attributes_falls_back(monkeypatch, tmp_path):
    """LLM output missing extracted_attributes → result still constructs with empty dict."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    del payload["extracted_attributes"]
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    assert result.extracted_attributes == {}
    # Other fields still parsed
    assert result.attribute_consistency["overall_verdict"] == "medium"


def test_evaluate_missing_consistency_falls_back(monkeypatch, tmp_path):
    """LLM output missing attribute_consistency → result still constructs with empty dict."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    del payload["attribute_consistency"]
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    assert result.attribute_consistency == {}
    assert result.extracted_attributes["emotion"] == "sad"


# ─────────────────────────────────────────────────────────────────────────────
# Neutral fallback paths
# ─────────────────────────────────────────────────────────────────────────────


def test_neutral_result_on_http_error(monkeypatch, tmp_path):
    """Connection error → neutral fallback (overall=0.5, verdict=unknown)."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    import src_next.critic.attribute_critic as mod

    def raising_post(*a, **kw):
        raise mod.requests.exceptions.ConnectTimeout("simulated timeout")

    monkeypatch.setattr(mod.requests, "post", raising_post)

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic(base_url="http://fake")
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)

    assert result.overall == 0.5
    for v in (result.quality, result.emotion_alignment, result.character_consistency,
              result.rhythm_naturalness, result.intelligibility):
        assert v == 0.5
    assert result.attribute_consistency.get("overall_verdict") == "unknown"
    assert result.extracted_attributes == {}
    # Neutral result still renders expected_attributes from DirectorInstruction
    assert result.expected_attributes["emotion"] == "sad"
    assert "失败" in result.suggestions or "timeout" in result.suggestions.lower()


def test_neutral_result_on_http_500(monkeypatch, tmp_path):
    """HTTP 500 → neutral fallback."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    _patch_post(monkeypatch, _FakeHttp500Response())

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic(base_url="http://fake")
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    assert result.overall == 0.5
    assert result.attribute_consistency.get("overall_verdict") == "unknown"
    assert "500" in result.suggestions or "失败" in result.suggestions


def test_neutral_result_on_json_parse_error(monkeypatch, tmp_path):
    """200 but text is plain English with no JSON → neutral fallback."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    _patch_post(monkeypatch, _FakeNonJsonResponse())

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic(base_url="http://fake")
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    assert result.overall == 0.5
    assert result.attribute_consistency.get("overall_verdict") == "unknown"


def test_neutral_result_on_empty_text_field(monkeypatch, tmp_path):
    """200 but text field empty → neutral fallback."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    _patch_post(monkeypatch, _FakeEmptyTextFieldResponse())

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic(base_url="http://fake")
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    assert result.overall == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility / conversion
# ─────────────────────────────────────────────────────────────────────────────


def test_to_critic_result_compat(monkeypatch, tmp_path):
    """to_critic_result() output must be consumable by TTSRepairAgent without raising."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()

    result = critic.evaluate(str(audio_path), seg, inst, di)
    base = result.to_critic_result()

    assert isinstance(base, CriticResult)
    assert base.segment_id == result.segment_id
    assert base.quality == result.quality
    assert base.emotion_alignment == result.emotion_alignment
    assert base.character_consistency == result.character_consistency
    assert base.rhythm_naturalness == result.rhythm_naturalness
    assert base.intelligibility == result.intelligibility
    assert base.overall == result.overall
    assert base.suggestions == result.suggestions
    assert base.attempt == result.attempt

    # The converted result must be needs_repair-compatible with same threshold logic
    assert base.needs_repair(threshold=0.7, overall_floor=0.75) == \
        result.needs_repair(threshold=0.7, overall_floor=0.75)


def test_needs_repair_threshold():
    """needs_repair uses same logic as CriticResult: any dim < threshold OR overall < floor."""
    from src_next.critic.attribute_result import AttributeAwareCriticResult

    # All dims high → no repair
    high = AttributeAwareCriticResult(
        segment_id="s1", quality=0.9, emotion_alignment=0.9,
        character_consistency=0.9, rhythm_naturalness=0.9,
        intelligibility=0.9, overall=0.9, suggestions="", attempt=1,
    )
    assert high.needs_repair(threshold=0.7, overall_floor=0.75) is False

    # One dim low → repair
    one_low = AttributeAwareCriticResult(
        segment_id="s1", quality=0.5, emotion_alignment=0.9,
        character_consistency=0.9, rhythm_naturalness=0.9,
        intelligibility=0.9, overall=0.82, suggestions="", attempt=1,
    )
    assert one_low.needs_repair(threshold=0.7, overall_floor=0.75) is True

    # Overall low → repair
    overall_low = AttributeAwareCriticResult(
        segment_id="s1", quality=0.74, emotion_alignment=0.74,
        character_consistency=0.74, rhythm_naturalness=0.74,
        intelligibility=0.74, overall=0.74, suggestions="", attempt=1,
    )
    assert overall_low.needs_repair(threshold=0.7, overall_floor=0.75) is True


# ─────────────────────────────────────────────────────────────────────────────
# Prompt rendering
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_renders_expected_attributes():
    """Prompt must contain concrete DirectorInstruction values, not generic placeholders."""
    from src_next.critic.prompts.attribute_critic_prompt import build_attribute_critic_prompt

    seg, inst, di = _make_segment_instruction_director()
    prompt = build_attribute_critic_prompt(seg, inst, di)

    # Concrete DirectorInstruction values must render
    assert "sad" in prompt
    assert "0.8" in prompt           # emotion_intensity
    assert "0.85" in prompt          # pace
    assert "gentle" in prompt        # tone
    assert "soft" in prompt          # volume
    assert "medium_low" in prompt    # pitch
    assert "缓慢叙述，带悲伤感" in prompt  # delivery_instruction

    # Segment / instruction fields
    assert "窗外下着大雨" in prompt
    assert "narrator" in prompt
    assert "CosyVoice3" in prompt

    # Two-step structure keywords
    assert "extracted_attributes" in prompt
    assert "expected_attributes" in prompt
    assert "attribute_consistency" in prompt
    assert "overall_verdict" in prompt
    assert "inconsistency_summary" in prompt
    assert "evidence" in prompt  # mandatory field

    # Strict grading retained
    assert "7.5 <= score" in prompt
    assert "5.0 <= score" in prompt
    assert "2.5 <= score" in prompt
    assert "大胆区分好坏" in prompt

    # Linkage rule: emotion_alignment.reason must reference inconsistency_summary
    assert "inconsistency_summary" in prompt
    assert "emotion_alignment" in prompt

    # Reasonable length (prompt is longer than original due to two-step scaffolding)
    assert 2000 <= len(prompt) <= 10000


# ─────────────────────────────────────────────────────────────────────────────
# Persistence (light check — full persistence tests live in test_persistence.py pattern)
# ─────────────────────────────────────────────────────────────────────────────


def test_persistence_writes_extracted_expected_consistency(monkeypatch, tmp_path):
    """save_attribute_critic_session must write scoring.json with all three new keys."""
    audio_path = tmp_path / "seg.wav"
    audio_path.write_bytes(b"fake wav bytes")

    payload = _make_llm_full_response()
    _patch_post(monkeypatch, _FakeOkResponse(payload))

    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    from src_next.critic.persistence import save_attribute_critic_session

    critic = AttributeAwareQwen3OmniCritic()
    seg, inst, di = _make_segment_instruction_director()
    result = critic.evaluate(str(audio_path), seg, inst, di)

    output_root = tmp_path / "out"
    folder = save_attribute_critic_session(
        audio_path=str(audio_path),
        result=result,
        output_root=str(output_root),
    )

    scoring_path = folder / "scoring.json"
    assert scoring_path.is_file()
    with open(scoring_path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    # Three new keys must be present
    assert "extracted_attributes" in saved
    assert "expected_attributes" in saved
    assert "attribute_consistency" in saved

    # 5 dims + overall + suggestions still there
    for k in ("quality", "emotion_alignment", "character_consistency",
              "rhythm_naturalness", "intelligibility", "overall", "suggestions"):
        assert k in saved

    # Audio copied
    assert (folder / "seg.wav").is_file()


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — skipped by default. Set RUN_INTEGRATION=1 to activate.
# See INTEGRATION_HANDOFF.md for environment prerequisites.
# ─────────────────────────────────────────────────────────────────────────────

_INTEGRATION_SKIP_REASON = (
    "set RUN_INTEGRATION=1 to activate; needs yellow-zone network + Qwen3-Omni service "
    "(10.50.121.102:8011). See src_next/critic/tests/INTEGRATION_HANDOFF.md."
)

_integration_skip = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason=_INTEGRATION_SKIP_REASON,
)


@pytest.fixture(scope="session")
def real_attribute_critic():
    """Real AttributeAwareQwen3OmniCritic pointing at the yellow-zone service.

    Defined here (not in conftest.py) to keep the original conftest untouched —
    the attribute-aware critic is a parallel implementation.
    """
    from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
    return AttributeAwareQwen3OmniCritic(base_url="http://10.50.121.102:8011")


@pytest.mark.integration
@_integration_skip
def test_integration_evaluate_real_audio(real_attribute_critic, good_narration_wav):
    """Integration: real omni/chat call returns a complete AttributeAwareCriticResult.

    Asserts structural completeness, not specific scores (LLM output varies).
    """
    seg, inst, di = _make_segment_instruction_director()

    result = real_attribute_critic.evaluate(good_narration_wav, seg, inst, di)

    assert result.segment_id == "s1"
    for v in (result.quality, result.emotion_alignment, result.character_consistency,
              result.rhythm_naturalness, result.intelligibility, result.overall):
        assert 0.0 <= v <= 1.0
    assert isinstance(result.suggestions, str)
    assert isinstance(result.extracted_attributes, dict)
    assert isinstance(result.expected_attributes, dict)
    assert isinstance(result.attribute_consistency, dict)
    # Truth-source invariant still holds on real LLM output
    assert result.expected_attributes["emotion"] == di.emotion
    assert result.expected_attributes["intensity"] == di.emotion_intensity


@pytest.mark.integration
@_integration_skip
def test_integration_persistence_round_trip(real_attribute_critic, good_narration_wav, tmp_path):
    """Integration: end-to-end evaluate → save → reload scoring.json structurally."""
    seg, inst, di = _make_segment_instruction_director()

    result = real_attribute_critic.evaluate(good_narration_wav, seg, inst, di)

    from src_next.critic.persistence import save_attribute_critic_session
    folder = save_attribute_critic_session(
        audio_path=good_narration_wav,
        result=result,
        output_root=str(tmp_path / "out"),
    )
    scoring_path = folder / "scoring.json"
    assert scoring_path.is_file()

    with open(scoring_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    for key in ("extracted_attributes", "expected_attributes", "attribute_consistency",
                "quality", "emotion_alignment", "overall", "suggestions"):
        assert key in saved, f"missing key in saved scoring.json: {key}"
