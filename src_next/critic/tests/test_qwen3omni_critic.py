"""Qwen3OmniCritic unit tests.

Integration tests (real Qwen3-Omni service) are written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness tests run by default.
"""
from __future__ import annotations

import pytest

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


def test_critic_can_be_constructed_with_defaults():
    """Qwen3OmniCritic should construct with the documented default base_url."""
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic

    critic = Qwen3OmniCritic()
    assert critic.base_url == "http://10.50.121.102:8011"
    assert critic.timeout == 120
    assert critic.bypass_proxy is True


def _make_segment_and_instruction():
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
        model="S2Pro",
        parameters={"instruction": "平稳叙述，略带忧伤"},
    )
    return seg, inst


_FAKE_NESTED_RESPONSE_TEXT = (
    '{"scores": {'
    '"quality": {"score": 8.5, "grade": "A", "reason": "清晰干净", "problems": []},'
    '"emotion_alignment": {"score": 8.0, "grade": "A", "reason": "情感匹配", "problems": []},'
    '"character_consistency": {"score": 9.0, "grade": "A", "reason": "符合角色", "problems": []},'
    '"rhythm_naturalness": {"score": 8.2, "grade": "A", "reason": "节奏自然", "problems": []},'
    '"intelligibility": {"score": 9.5, "grade": "A", "reason": "字字清晰", "problems": []}'
    '}, "overall_score": 8.6, "overall_grade": "A",'
    ' "main_problems": [], "suggestions": ["音质清晰，情感表达可再增强一些。"]}'
)


class _FakeOkResponse:
    """Minimal stand-in for requests.Response — 200 with valid nested scoring JSON."""
    status_code = 200

    def json(self):
        return {
            "request_id": "fake-req-1",
            "text": _FAKE_NESTED_RESPONSE_TEXT,
        }

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


def test_evaluate_returns_critic_result_on_success(monkeypatch):
    """Mock 200 + valid nested scoring JSON → CriticResult with parsed + normalized scores."""
    import src_next.critic.qwen3omni_critic as mod

    captured = {}

    def fake_post(url, json=None, proxies=None, timeout=None, **kw):
        captured["url"] = url
        captured["json"] = json
        captured["proxies"] = proxies
        captured["timeout"] = timeout
        return _FakeOkResponse()

    monkeypatch.setattr(mod.requests, "post", fake_post)

    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic()
    seg, inst = _make_segment_and_instruction()

    result = critic.evaluate("/fake/path.wav", seg, inst)

    # Verify HTTP call shape
    assert captured["url"] == "http://10.50.121.102:8011/v1/omni/audio_analysis"
    assert captured["json"]["audio"] == "/fake/path.wav"
    assert captured["json"]["task"] == "sound_analysis"
    assert "text" in captured["json"]  # scoring prompt
    assert captured["proxies"] == {"http": None, "https": None}

    # Verify returned CriticResult — 0-10 scores normalized to 0-1
    assert result.segment_id == "s1"
    assert 0.84 <= result.quality <= 0.86                  # 8.5/10
    assert 0.79 <= result.emotion_alignment <= 0.81        # 8.0/10
    assert 0.89 <= result.character_consistency <= 0.91    # 9.0/10
    assert 0.81 <= result.rhythm_naturalness <= 0.83       # 8.2/10
    assert 0.94 <= result.intelligibility <= 0.96          # 9.5/10
    # overall = 5-dim average (LLM's overall_score intentionally ignored)
    # (0.85+0.80+0.90+0.82+0.95)/5 = 0.864
    assert 0.85 <= result.overall <= 0.88
    assert isinstance(result.suggestions, str)
    assert "情感表达" in result.suggestions                # merged from suggestions list


def test_critic_prompt_includes_expected_vs_actual_context():
    """Prompt must contain original text, speaker, expected emotion, and strict grading rules."""
    from src_next.critic.prompts.critic_prompt import build_critic_prompt

    seg, inst = _make_segment_and_instruction()
    prompt = build_critic_prompt(seg, inst)

    # Expected vs Actual pattern (Audio-Oscar §B.14)
    assert "窗外下着大雨" in prompt  # original text
    assert "narrator" in prompt  # speaker
    assert "平稳叙述" in prompt  # expected emotion from parameters

    # 5 dimensions (task card §1.3.1)
    for dim in ("quality", "emotion_alignment", "character_consistency",
                "rhythm_naturalness", "intelligibility"):
        assert dim in prompt

    # Strict grading — A/B/C/D bands with explicit score ranges
    assert "7.5 <= score" in prompt
    assert "5.0 <= score" in prompt
    assert "2.5 <= score" in prompt

    # Forced deduction keywords (区段锁定)
    assert "略夸张" in prompt
    assert "7.4" in prompt
    assert "4.9" in prompt
    assert "2.4" in prompt

    # Anti safe-scoring constraint
    assert "大胆区分好坏" in prompt
    assert "不要所有维度都集中在 7 或 8" in prompt

    # Nested JSON schema keywords
    for kw in ("scores", "grade", "problems", "main_problems",
               "overall_score", "overall_grade", "suggestions"):
        assert kw in prompt

    # Hard constraints (建议规则) preserved
    assert "绝对不要" in prompt
    assert "text" in prompt
    assert "speaker" in prompt
    assert "model" in prompt

    # Reasonable length
    assert 200 <= len(prompt) <= 5000


def test_from_json_legacy_flat_schema_still_works():
    """from_json should still accept old flat 0-1 schema (backwards compat)."""
    legacy = {
        "segment_id": "s1",
        "quality": 0.85,
        "emotion_alignment": 0.80,
        "character_consistency": 0.90,
        "rhythm_naturalness": 0.82,
        "intelligibility": 0.95,
        # no "overall" key — should fall back to 5-dim average
    }
    result = CriticResult.from_json(legacy, attempt=1)
    assert result.segment_id == "s1"
    assert abs(result.quality - 0.85) < 0.01
    assert abs(result.emotion_alignment - 0.80) < 0.01
    assert abs(result.character_consistency - 0.90) < 0.01
    assert abs(result.rhythm_naturalness - 0.82) < 0.01
    assert abs(result.intelligibility - 0.95) < 0.01
    expected_overall = (0.85 + 0.80 + 0.90 + 0.82 + 0.95) / 5
    assert abs(result.overall - expected_overall) < 0.01


def test_normalize_nested_scoring_clamps_and_merges_suggestions():
    """_normalize_nested_scoring clamps out-of-range scores + dedup/limit suggestions."""
    from src_next.critic.qwen3omni_critic import _normalize_nested_scoring

    nested = {
        "scores": {
            "quality": {"score": 12.0, "grade": "A", "reason": "r1", "problems": []},      # > 10
            "emotion_alignment": {"score": -1.0, "grade": "D", "reason": "r2", "problems": []},  # < 0
            "character_consistency": {"score": 7.5, "grade": "A", "reason": "r3", "problems": []},
            "rhythm_naturalness": {"score": 6.0, "grade": "B", "reason": "r4", "problems": []},
            "intelligibility": {"score": 8.0, "grade": "A", "reason": "r5", "problems": []},
        },
        "overall_score": 7.0,
        "overall_grade": "B",
        "main_problems": ["问题A", "问题B", "问题A"],         # dedup → ["问题A", "问题B"]
        "suggestions": ["建议1", "建议2", "建议3", "建议4"],  # combined cap 3 after dedup
    }
    flat = _normalize_nested_scoring(nested, "s1", 1)

    # Clamp verification (0-10 → 0-1)
    assert flat["quality"] == 1.0              # 12.0 clamped to 10.0 / 10 = 1.0
    assert flat["emotion_alignment"] == 0.0    # -1.0 clamped to 0.0
    assert abs(flat["character_consistency"] - 0.75) < 0.001
    assert abs(flat["rhythm_naturalness"] - 0.60) < 0.001
    assert abs(flat["intelligibility"] - 0.80) < 0.001

    # LLM's overall_score is intentionally ignored — flat dict should NOT contain "overall"
    # (let CriticResult.from_json compute 5-dim average)
    assert "overall" not in flat

    # Suggestions: dedup + max 3 + ；-joined
    assert "问题A" in flat["suggestions"]
    assert flat["suggestions"].count("问题A") == 1  # dedup happened
    parts = flat["suggestions"].split("；")
    assert len(parts) <= 3  # max 3 entries

    # Metadata passthrough
    assert flat["segment_id"] == "s1"
    assert flat["attempt"] == 1
