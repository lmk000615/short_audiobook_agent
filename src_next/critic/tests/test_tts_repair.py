"""TTSRepairAgent unit tests.

Integration test (real LLM via profile) is written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness + behavior tests run by default.
"""
from __future__ import annotations

from src_next.core.data_models import (
    CriticResult,
    ModelSpecificTTSInstruction,
    Segment,
)


def _make_inputs(
    parameters: dict | None = None,
    scores: dict | None = None,
):
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
        parameters=parameters or {"instruction": "平稳叙述", "speed": 1.0},
        voice_ref="/voicebank/narrator_v1.wav",
        attempt=1,
    )
    s = scores or {}
    critic = CriticResult(
        segment_id="s1",
        quality=s.get("quality", 0.5),
        emotion_alignment=s.get("emotion_alignment", 0.4),
        character_consistency=s.get("character_consistency", 0.9),
        rhythm_naturalness=s.get("rhythm_naturalness", 0.6),
        intelligibility=s.get("intelligibility", 0.85),
        overall=s.get("overall", 0.65),
        suggestions="情感表达偏弱，建议增强悲伤语气，降低语速至 0.85。",
        attempt=1,
    )
    return seg, inst, critic


class _FakeLLMClient:
    """Mock BaseLLMClient for testing repair merge logic."""

    def __init__(self, returned_json: dict | list | None, raise_exc: Exception | None = None):
        self._returned = returned_json
        self._raise = raise_exc
        self.captured_prompt: str | None = None

    def generate_text(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

    def generate_json(self, prompt: str, **kwargs) -> dict | list:
        self.captured_prompt = prompt
        if self._raise:
            raise self._raise
        if self._returned is None:
            raise RuntimeError("no mock return value configured")
        return self._returned


def test_repair_agent_constructs_with_llm_client():
    """TTSRepairAgent takes a BaseLLMClient in __init__."""
    from src_next.critic.tts_repair import TTSRepairAgent

    fake_llm = _FakeLLMClient(returned_json={})
    agent = TTSRepairAgent(llm_client=fake_llm)
    assert agent.llm is fake_llm


def test_repair_prompt_contains_all_required_context():
    """Prompt must include original params, current params, critic scores, suggestions, AND
    the explicit 'do not touch these fields' constraint."""
    from src_next.critic.prompts.repair_prompt import build_repair_prompt

    seg, inst, critic = _make_inputs()
    prompt = build_repair_prompt(original=inst, segment=seg, critic=critic)

    # Audio-Oscar §C.18 dual-anchor pattern: original AND current parameters
    assert "instruction" in prompt  # current parameter visible
    assert "1.0" in prompt  # current speed visible

    # Critic feedback (Audio-Oscar §C.20 — show scores + suggestions)
    assert "emotion_alignment" in prompt
    assert "0.40" in prompt or "0.4" in prompt  # emotion_alignment score visible
    assert "情感表达偏弱" in prompt  # suggestion text visible

    # Audio-Oscar §C.19 strong "exactly" language for immutable fields
    for frozen_field in ("segment_id", "speaker", "text", "model", "voice_ref"):
        assert frozen_field in prompt


def test_repair_merges_llm_output_into_parameters():
    """LLM returns partial parameters → result.parameters = original + LLM overlay."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs(
        parameters={"instruction": "平稳叙述", "speed": 1.0, "voice_character": "calm"}
    )
    # LLM only changes speed — instruction and voice_character must be preserved
    fake_llm = _FakeLLMClient(returned_json={"parameters": {"speed": 0.85}})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    assert result.parameters["speed"] == 0.85  # LLM change applied
    assert result.parameters["instruction"] == "平稳叙述"  # original preserved
    assert result.parameters["voice_character"] == "calm"  # original preserved


def test_repair_increments_attempt():
    """Result.attempt must be original.attempt + 1."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    inst.attempt = 1
    fake_llm = _FakeLLMClient(returned_json={"parameters": {}})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)
    assert result.attempt == 2


def test_repair_preserves_immutable_top_level_fields():
    """Schema-frozen fields (segment_id/speaker/text/model/voice_ref) must equal original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    # LLM tries to break the contract by changing everything
    fake_llm = _FakeLLMClient(returned_json={
        "parameters": {"speed": 0.85},
        "segment_id": "HACKED",
        "speaker": "HACKED",
        "text": "HACKED",
        "model": "HACKED",
        "voice_ref": "HACKED",
    })
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    assert result.segment_id == "s1"
    assert result.speaker == "narrator"
    assert result.text == "窗外下着大雨。"
    assert result.model == "S2Pro"
    assert result.voice_ref == "/voicebank/narrator_v1.wav"


def test_repair_returns_original_plus_one_when_llm_raises():
    """LLM exception → fallback to original (attempt+1), no raise."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    inst.attempt = 1
    fake_llm = _FakeLLMClient(returned_json=None, raise_exc=RuntimeError("LLM down"))
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Fallback: same parameters, attempt bumped
    assert result.parameters == inst.parameters
    assert result.attempt == 2
    assert result.segment_id == inst.segment_id
    assert result.model == inst.model


def test_repair_handles_llm_returning_non_dict_parameters():
    """LLM returns {"parameters": "garbage"} → ignore garbage, keep original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    fake_llm = _FakeLLMClient(returned_json={"parameters": "not a dict"})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Original parameters preserved, no crash
    assert result.parameters == inst.parameters


def test_repair_handles_llm_returning_non_dict_top_level():
    """LLM returns a list instead of dict → fallback to original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    fake_llm = _FakeLLMClient(returned_json=["unexpected", "list"])
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)
    assert result.parameters == inst.parameters
    assert result.attempt == inst.attempt + 1


# ─────────────────────────────────────────────────────────────────────────────
# Integration test — skip-marked. See KNOWN_ISSUES.md §1 to activate.
# ─────────────────────────────────────────────────────────────────────────────

import pytest  # noqa: E402 — top of file already imports pytest, but be defensive


_INTEGRATION_SKIP_REASON = (
    "awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"
)


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_repair_with_real_llm_adjusts_parameters(real_llm):
    """Integration: real LLM should change at least one parameter when given a low emotion_alignment score."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs(
        parameters={"instruction": "平稳叙述", "speed": 1.0}
    )
    # Critic says emotion_alignment is weak → LLM should adjust instruction
    agent = TTSRepairAgent(llm_client=real_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Contract: immutable fields untouched
    assert result.segment_id == "s1"
    assert result.speaker == "narrator"
    assert result.text == "窗外下着大雨。"
    assert result.model == "S2Pro"
    assert result.voice_ref == inst.voice_ref
    assert result.attempt == 2

    # Behavior: at least one parameter changed (most likely instruction or speed)
    changed_keys = [
        k for k in result.parameters
        if result.parameters[k] != inst.parameters.get(k)
    ]
    assert len(changed_keys) > 0, (
        f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"
    )
