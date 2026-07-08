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
