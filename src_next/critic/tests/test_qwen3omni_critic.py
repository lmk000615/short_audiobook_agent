"""Qwen3OmniCritic unit tests.

Integration tests (real Qwen3-Omni service) are written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness tests run by default.
"""
from __future__ import annotations

import pytest

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


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


class _FakeOkResponse:
    """Minimal stand-in for requests.Response — 200 with valid scoring JSON."""
    status_code = 200

    def json(self):
        return {
            "request_id": "fake-req-1",
            "text": (
                '{"quality":0.85,"emotion_alignment":0.80,'
                '"character_consistency":0.90,"rhythm_naturalness":0.82,'
                '"intelligibility":0.95,'
                '"suggestions":"音质清晰，情感表达可再增强一些。"}'
            ),
        }

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


def test_evaluate_returns_critic_result_on_success(monkeypatch):
    """Mock 200 + valid scoring JSON → CriticResult with parsed scores."""
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

    # Verify returned CriticResult
    assert result.segment_id == "s1"
    assert 0.84 <= result.quality <= 0.86  # parsed from JSON
    assert 0.94 <= result.intelligibility <= 0.96
    assert 0.0 <= result.overall <= 1.0
    assert isinstance(result.suggestions, str)
    assert result.suggestions  # non-empty


def test_critic_prompt_includes_expected_vs_actual_context():
    """Prompt must contain original text, speaker, expected emotion, and 5-dim schema."""
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

    # Strict JSON schema embedded (Audio-Oscar §7.2)
    assert "suggestions" in prompt
