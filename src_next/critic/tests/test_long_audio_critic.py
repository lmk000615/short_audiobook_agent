"""Qwen3OmniLongAudioCritic 单元测试。

Integration test (real Qwen3-Omni service) skip-marked — see KNOWN_ISSUES.md.
Mock 单测覆盖：默认构造、切片控制（3 种模式）、payload 结构、单段失败容错、
全段失败兜底、grade 区间计算。
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 共用 mock 工具
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_EVAL_RESPONSE_TEXT = (
    '{"scores": {'
    '"emotion_expressiveness": {"score": 8.5, "reason": "情绪自然舒服", "problems": []},'
    '"rhythm": {"score": 8.0, "reason": "节奏流畅", "problems": []},'
    '"naturalness": {"score": 9.0, "reason": "发音自然", "problems": []},'
    '"clarity": {"score": 9.5, "reason": "吐字清晰", "problems": []}'
    '}, "main_problems": [], "suggestions": ["增强情感起伏。"]}'
)


class _FakeOkResponse:
    """Minimal stand-in for requests.Response — 200 with valid scoring JSON in `text` field."""
    status_code = 200

    def __init__(self, text: str = _FAKE_EVAL_RESPONSE_TEXT):
        self._text = text

    def json(self):
        return {"request_id": "fake-req", "text": self._text}

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


class _FakeSFInfo:
    """Stand-in for soundfile.Info — has .frames and .samplerate attributes."""
    def __init__(self, frames: int, samplerate: int):
        self.frames = frames
        self.samplerate = samplerate


def _patch_soundfile(monkeypatch, duration_seconds: float, samplerate: int = 16000):
    """Patch soundfile module used by long_audio_critic to fake audio of given duration.

    - sf.info(path) → _FakeSFInfo(frames=duration*samplerate, samplerate)
    - sf.read(path) → (list of zeros of length frames, samplerate)
    - sf.write(path, data, samplerate, subtype=...) → no-op (writes 1 byte to satisfy file creation)
    """
    import src_next.critic.long_audio_critic as mod

    frames = int(duration_seconds * samplerate)

    def fake_info(path):
        return _FakeSFInfo(frames=frames, samplerate=samplerate)

    def fake_read(path):
        return ([0.0] * frames, samplerate)

    def fake_write(path, data, sr, subtype=None, **kw):
        # 写一个最小占位字节，临时文件实际存在，方便 finally 里的 unlink
        with open(path, "wb") as f:
            f.write(b"\x00")

    monkeypatch.setattr(mod.sf, "info", fake_info)
    monkeypatch.setattr(mod.sf, "read", fake_read)
    monkeypatch.setattr(mod.sf, "write", fake_write)


def _patch_post_success(monkeypatch, captured: dict | None = None):
    """Patch requests.post to always return _FakeOkResponse. Optionally capture payload."""
    import src_next.critic.long_audio_critic as mod

    def fake_post(url, json=None, proxies=None, timeout=None, **kw):
        if captured is not None:
            captured["url"] = url
            captured["json"] = json
            captured["proxies"] = proxies
            captured["timeout"] = timeout
        return _FakeOkResponse()

    monkeypatch.setattr(mod.requests, "post", fake_post)


def _patch_post_sequence(monkeypatch, behaviors):
    """Patch requests.post to return a sequence of behaviors (callable or Exception).

    Each entry in `behaviors` is either:
      - an Exception instance → raised when post is called
      - a callable returning a Response-like object
    """
    import src_next.critic.long_audio_critic as mod

    queue = list(behaviors)

    def fake_post(*a, **kw):
        if not queue:
            raise RuntimeError("test setup error: post called more times than behaviors provided")
        action = queue.pop(0)
        if isinstance(action, Exception):
            raise action
        return action()

    monkeypatch.setattr(mod.requests, "post", fake_post)


# ─────────────────────────────────────────────────────────────────────────────
# 测试用例
# ─────────────────────────────────────────────────────────────────────────────

def test_constructs_with_defaults():
    """Qwen3OmniLongAudioCritic 应该用文档化的默认值构造。"""
    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic

    critic = Qwen3OmniLongAudioCritic()
    assert critic.base_url == "http://10.50.121.102:8011"
    assert critic.segment_duration == 30.0
    assert critic.timeout == 600
    assert critic.max_new_tokens == 768
    assert critic.temperature == 0.0
    assert critic.bypass_proxy is True


def test_evaluate_short_audio_no_chunking(monkeypatch, tmp_path):
    """短音频（< segment_duration）→ 不切片，单次 HTTP 调用，返回 4 维 populated 结果。"""
    _patch_soundfile(monkeypatch, duration_seconds=10.0)
    _patch_post_success(monkeypatch)

    audio_path = tmp_path / "short.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(str(audio_path))

    assert result.num_segments == 1
    assert result.segment_duration == 30.0  # configured default, even though we didn't slice
    assert result.duration_seconds == 10.0
    assert set(result.scores.keys()) == {"emotion_expressiveness", "rhythm", "naturalness", "clarity"}
    assert 8.0 <= result.scores["emotion_expressiveness"].score <= 9.0
    assert result.overall_grade in {"A", "B", "C", "D"}
    assert result.error is None


def test_evaluate_multi_segment_aggregates(monkeypatch, tmp_path):
    """90s 音频 + 默认 30s segment_duration → 切成 3 段，overall 是 3 段均值。"""
    _patch_soundfile(monkeypatch, duration_seconds=90.0)
    _patch_post_success(monkeypatch)

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(str(audio_path))

    assert result.num_segments == 3
    assert len(result.segment_details) == 3
    # 3 段返回相同的 mock response，所以均值应等于单段值
    assert result.scores["emotion_expressiveness"].score == 8.5
    assert result.scores["clarity"].score == 9.5
    # overall = (8.5 + 8.0 + 9.0 + 9.5) / 4 = 8.75
    assert 8.7 <= result.overall_score <= 8.8


def test_evaluate_no_segment_kwarg_forces_whole_audio(monkeypatch, tmp_path):
    """传 no_segment=True 时，即便音频超过 segment_duration，也只发 1 次。"""
    _patch_soundfile(monkeypatch, duration_seconds=90.0)
    call_count = {"n": 0}

    import src_next.critic.long_audio_critic as mod
    def fake_post(*a, **kw):
        call_count["n"] += 1
        return _FakeOkResponse()
    monkeypatch.setattr(mod.requests, "post", fake_post)

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(str(audio_path), no_segment=True)

    assert call_count["n"] == 1
    assert result.num_segments == 1
    assert result.segment_duration == 0  # no_segment → 0


def test_init_segment_duration_zero_also_disables_chunking(monkeypatch, tmp_path):
    """Qwen3OmniLongAudioCritic(segment_duration=0) + 90s audio → 永远只 1 次调用。"""
    _patch_soundfile(monkeypatch, duration_seconds=90.0)
    call_count = {"n": 0}

    import src_next.critic.long_audio_critic as mod
    def fake_post(*a, **kw):
        call_count["n"] += 1
        return _FakeOkResponse()
    monkeypatch.setattr(mod.requests, "post", fake_post)

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic(segment_duration=0)
    result = critic.evaluate(str(audio_path))

    assert call_count["n"] == 1
    assert result.num_segments == 1


def test_payload_uses_messages_format(monkeypatch, tmp_path):
    """抓 captured payload：必须有 messages key + user content 含 audio data-uri。"""
    _patch_soundfile(monkeypatch, duration_seconds=10.0)
    captured: dict = {}
    _patch_post_success(monkeypatch, captured=captured)

    audio_path = tmp_path / "short.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    critic.evaluate(str(audio_path))

    assert "messages" in captured["json"]
    messages = captured["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    user_content = messages[1]["content"]
    text_parts = [c for c in user_content if c.get("type") == "text"]
    audio_parts = [c for c in user_content if c.get("type") == "audio"]
    assert len(text_parts) == 1
    assert len(audio_parts) == 1
    audio_val = audio_parts[0]["audio"]
    assert audio_val.startswith("data:audio/")
    assert "base64," in audio_val

    assert captured["json"]["return_audio"] is False
    assert captured["proxies"] == {"http": None, "https": None}


def test_one_segment_failure_continues(monkeypatch, tmp_path):
    """第 1 段抛 ConnectTimeout，第 2、3 段成功 → overall 用成功段算，segment_details[0] 标记失败。"""
    _patch_soundfile(monkeypatch, duration_seconds=90.0)  # → 3 段

    import src_next.critic.long_audio_critic as mod
    _patch_post_sequence(monkeypatch, [
        mod.requests.exceptions.ConnectTimeout("simulated timeout"),
        _FakeOkResponse,
        _FakeOkResponse,
    ])

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(str(audio_path))

    assert result.num_segments == 3
    assert len(result.segment_details) == 3
    assert result.segment_details[0].get("_failed") is True
    assert "_error" in result.segment_details[0]
    assert result.segment_details[1].get("_failed") is not True
    assert result.error is None  # partial failure 不算全失败
    # overall 应该基于成功的 2 段（mock 同样响应，所以数值不变）
    assert 8.0 <= result.overall_score <= 9.0


def test_all_segments_fail_returns_zero_result(monkeypatch, tmp_path):
    """所有段失败 → overall_score=0.0、overall_grade=D、error 非空，不抛异常。"""
    _patch_soundfile(monkeypatch, duration_seconds=90.0)

    import src_next.critic.long_audio_critic as mod
    _patch_post_sequence(monkeypatch, [
        mod.requests.exceptions.ConnectTimeout("simulated timeout"),
        mod.requests.exceptions.ConnectTimeout("simulated timeout"),
        mod.requests.exceptions.ConnectTimeout("simulated timeout"),
    ])

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"fake wav bytes")

    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic
    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(str(audio_path))

    assert result.overall_score == 0.0
    assert result.overall_grade == "D"
    assert result.error is not None
    assert "failed" in result.error.lower() or "全部" in result.error
    assert result.scores == {}  # 没有成功段可以填 scores


def test_grade_bands():
    """compute_grade 区间边界：A>=7.5, B>=5.0, C>=2.5, D<2.5。"""
    from src_next.critic.long_audio_critic import _compute_grade

    assert _compute_grade(10.0) == "A"
    assert _compute_grade(7.5) == "A"
    assert _compute_grade(7.4) == "B"
    assert _compute_grade(5.0) == "B"
    assert _compute_grade(4.9) == "C"
    assert _compute_grade(2.5) == "C"
    assert _compute_grade(2.4) == "D"
    assert _compute_grade(0.0) == "D"


# ─────────────────────────────────────────────────────────────────────────────
# Integration test — skip-marked. See KNOWN_ISSUES.md to activate.
# ─────────────────────────────────────────────────────────────────────────────

_INTEGRATION_SKIP_REASON = (
    "awaiting Qwen3-Omni service access — verify chain locally first via mock tests; "
    "remove skip + set LONG_AUDIO_FIXTURE env var to point at a real wav to activate."
)


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_long_audio_scores_real_audiobook(monkeypatch):
    """Integration: real audio_final/*.wav 通过真实 Qwen3-Omni 服务评分。

    需要：
    1. 设置环境变量 LONG_AUDIO_FIXTURE 指向一个真实 wav 文件
    2. 去掉上面的 @pytest.mark.skip
    3. 确认 Qwen3-Omni 服务（10.50.121.102:8011）可达
    """
    import os
    from src_next.critic.long_audio_critic import Qwen3OmniLongAudioCritic

    fixture = os.environ.get("LONG_AUDIO_FIXTURE")
    if not fixture:
        pytest.skip("LONG_AUDIO_FIXTURE env var not set")

    # 不要 mock soundfile / requests —— 走真实链路
    monkeypatch.setattr(__import__("sys").modules["src_next.critic.long_audio_critic"].sf,
                        "info", None, raising=False)  # no-op safe guard

    critic = Qwen3OmniLongAudioCritic()
    result = critic.evaluate(fixture)

    assert 0.0 <= result.overall_score <= 10.0
    assert result.overall_grade in {"A", "B", "C", "D"}
    if result.error is None:
        assert set(result.scores.keys()) == {"emotion_expressiveness", "rhythm", "naturalness", "clarity"}
