"""save_critic_session() unit tests.

All tests use tmp_path for isolation — no real service calls, no project-root pollution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_next.core.data_models import (
    CriticResult,
    LongAudioCriticResult,
    LongAudioSegmentScore,
    ModelSpecificTTSInstruction,
)
from src_next.critic.persistence import save_critic_session, save_long_audio_critic_session


# ── fixtures ────────────────────────────────────────────────────────────────

def _make_critic_result(quality: float = 0.87, attempt: int = 1) -> CriticResult:
    return CriticResult(
        segment_id="s1",
        quality=quality,
        emotion_alignment=0.82,
        character_consistency=0.91,
        rhythm_naturalness=0.85,
        intelligibility=0.93,
        overall=0.876,
        suggestions="音质清晰；情感稍弱",
        attempt=attempt,
    )


def _make_repair_instruction(attempt: int = 2) -> ModelSpecificTTSInstruction:
    return ModelSpecificTTSInstruction(
        segment_id="s1",
        speaker="narrator",
        text="窗外下着大雨。",
        model="S2Pro",
        parameters={"instruction": "更忧伤一些", "speed": 0.9},
        voice_ref="/path/to/voice.wav",
        attempt=attempt,
    )


@pytest.fixture
def fake_audio(tmp_path: Path) -> Path:
    """A real tiny file (bytes don't matter — persistence just copies them)."""
    p = tmp_path / "seg_001.wav"
    p.write_bytes(b"fake wav bytes for testing")
    return p


# ── tests ───────────────────────────────────────────────────────────────────

def test_save_scoring_only_creates_minimal_folder(fake_audio, tmp_path):
    """Without repair_result, folder contains scoring.json + audio only (no repair.json)."""
    out = tmp_path / "out"
    folder = save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        output_root=out,
    )

    assert folder == out / "critic" / "seg_001"
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["scoring.json", "seg_001.wav"]


def test_save_with_repair_creates_both_jsons(fake_audio, tmp_path):
    """With repair_result, folder contains scoring.json + repair.json + audio."""
    out = tmp_path / "out"
    folder = save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        repair_result=_make_repair_instruction(),
        output_root=out,
    )

    names = sorted(p.name for p in folder.iterdir())
    assert names == ["repair.json", "scoring.json", "seg_001.wav"]


def test_audio_copy_preserves_filename_and_bytes(fake_audio, tmp_path):
    """Copied audio keeps original filename and exact bytes (shutil.copy2)."""
    out = tmp_path / "out"
    save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        output_root=out,
    )

    copied = out / "critic" / "seg_001" / "seg_001.wav"
    assert copied.is_file()
    assert copied.read_bytes() == fake_audio.read_bytes()


def test_folder_named_by_audio_stem(tmp_path):
    """Folder name = Path(audio).stem (extension stripped)."""
    # Nest the audio in a subdirectory to confirm only stem is used, not parent path
    sub = tmp_path / "audio_dir"
    sub.mkdir()
    audio = sub / "narration_007.wav"
    audio.write_bytes(b"x")

    out = tmp_path / "out"
    folder = save_critic_session(
        audio_path=audio,
        critic_result=_make_critic_result(),
        output_root=out,
    )

    assert folder.name == "narration_007"
    assert folder.parent.name == "critic"


def test_custom_output_root_respected(fake_audio, tmp_path):
    """output_root parameter controls where the critic/ tree lands."""
    custom = tmp_path / "custom_root" / "deep"
    folder = save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        output_root=custom,
    )

    assert folder == custom / "critic" / "seg_001"
    assert folder.is_dir()
    # Intermediate dirs auto-created
    assert custom.is_dir()


def test_overwrite_semantics_on_repeated_save(fake_audio, tmp_path):
    """Calling save twice with same audio overwrites — folder count stays at 2, values update."""
    out = tmp_path / "out"

    # First save: quality=0.87, attempt=1
    save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(quality=0.87, attempt=1),
        output_root=out,
    )
    # Second save: quality=0.42, attempt=2 — should overwrite, not version
    save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(quality=0.42, attempt=2),
        output_root=out,
    )

    folder = out / "critic" / "seg_001"
    files = sorted(p.name for p in folder.iterdir())
    assert files == ["scoring.json", "seg_001.wav"]  # still 2 files, not 4

    scoring = json.loads((folder / "scoring.json").read_text(encoding="utf-8"))
    assert scoring["quality"] == pytest.approx(0.42)
    assert scoring["attempt"] == 2  # second call's value won


def test_scoring_json_contents_round_trip(fake_audio, tmp_path):
    """scoring.json contains all CriticResult fields with Chinese preserved (UTF-8)."""
    out = tmp_path / "out"
    save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        output_root=out,
    )

    raw = (out / "critic" / "seg_001" / "scoring.json").read_text(encoding="utf-8")
    # Chinese must not be escaped (\uXXXX) — ensure_ascii=False
    assert "\\u" not in raw
    assert "音质清晰" in raw

    scoring = json.loads(raw)
    assert scoring["segment_id"] == "s1"
    assert scoring["quality"] == pytest.approx(0.87)
    assert scoring["emotion_alignment"] == pytest.approx(0.82)
    assert scoring["character_consistency"] == pytest.approx(0.91)
    assert scoring["rhythm_naturalness"] == pytest.approx(0.85)
    assert scoring["intelligibility"] == pytest.approx(0.93)
    assert scoring["overall"] == pytest.approx(0.876)
    assert scoring["suggestions"] == "音质清晰；情感稍弱"
    assert scoring["attempt"] == 1


def test_repair_json_contents_round_trip(fake_audio, tmp_path):
    """repair.json contains all ModelSpecificTTSInstruction fields including parameters dict."""
    out = tmp_path / "out"
    save_critic_session(
        audio_path=fake_audio,
        critic_result=_make_critic_result(),
        repair_result=_make_repair_instruction(),
        output_root=out,
    )

    repair = json.loads((out / "critic" / "seg_001" / "repair.json").read_text(encoding="utf-8"))
    assert repair["segment_id"] == "s1"
    assert repair["speaker"] == "narrator"
    assert repair["text"] == "窗外下着大雨。"
    assert repair["model"] == "S2Pro"
    assert repair["parameters"] == {"instruction": "更忧伤一些", "speed": 0.9}
    assert repair["voice_ref"] == "/path/to/voice.wav"
    assert repair["attempt"] == 2


def test_missing_audio_raises_file_not_found(tmp_path):
    """audio_path that doesn't exist → FileNotFoundError (not silent skip)."""
    out = tmp_path / "out"
    with pytest.raises(FileNotFoundError):
        save_critic_session(
            audio_path=tmp_path / "nonexistent.wav",
            critic_result=_make_critic_result(),
            output_root=out,
        )


# ─────────────────────────────────────────────────────────────────────────────
# save_long_audio_critic_session() tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_long_audio_segment_score(score: float = 8.5) -> LongAudioSegmentScore:
    return LongAudioSegmentScore(
        score=score,
        grade="A" if score >= 7.5 else "B" if score >= 5.0 else "C" if score >= 2.5 else "D",
        reason="听感自然舒服",
        problems=[],
    )


def _make_long_audio_result(audio_file: str = "story_final.wav") -> LongAudioCriticResult:
    return LongAudioCriticResult(
        audio_file=audio_file,
        duration_seconds=120.0,
        num_segments=4,
        segment_duration=30.0,
        scores={
            "emotion_expressiveness": _make_long_audio_segment_score(8.5),
            "rhythm": _make_long_audio_segment_score(8.0),
            "naturalness": _make_long_audio_segment_score(9.0),
            "clarity": _make_long_audio_segment_score(9.5),
        },
        overall_score=8.75,
        overall_grade="A",
        main_problems=[],
        suggestions=["增强情感起伏。"],
        segment_details=[{"_inference_time": 12.3}],
        base_url="http://10.50.121.102:8011",
        timestamp="2026-07-09T12:00:00",
        total_inference_time=49.2,
        error=None,
    )


def test_save_long_audio_session_writes_scoring_and_audio(tmp_path):
    """save_long_audio_critic_session() 应该写出 scoring.json + 音频副本。"""
    audio = tmp_path / "story_final.wav"
    audio.write_bytes(b"fake long audio bytes")

    out = tmp_path / "out"
    folder = save_long_audio_critic_session(
        audio_path=audio,
        result=_make_long_audio_result(),
        output_root=out,
    )

    assert (folder / "scoring.json").is_file()
    assert (folder / "story_final.wav").is_file()
    assert (folder / "story_final.wav").read_bytes() == b"fake long audio bytes"

    scoring = json.loads((folder / "scoring.json").read_text(encoding="utf-8"))
    assert scoring["overall_score"] == pytest.approx(8.75)
    assert scoring["overall_grade"] == "A"
    assert scoring["audio_file"] == "story_final.wav"
    assert set(scoring["scores"].keys()) == {"emotion_expressiveness", "rhythm", "naturalness", "clarity"}
    assert scoring["scores"]["emotion_expressiveness"]["score"] == pytest.approx(8.5)
    # 中文不被 \u 转义
    assert "增强情感起伏" in (folder / "scoring.json").read_text(encoding="utf-8")


def test_save_long_audio_session_uses_nested_folder(tmp_path):
    """目录结构应该是 <root>/critic/long_audio/<stem>/（嵌套在 critic/ 下，不是顶层 critic_long_audio/）。"""
    audio = tmp_path / "story_final.wav"
    audio.write_bytes(b"x")

    out = tmp_path / "out"
    folder = save_long_audio_critic_session(
        audio_path=audio,
        result=_make_long_audio_result(),
        output_root=out,
    )

    # folder 路径必须是 out/critic/long_audio/story_final/
    assert folder == out / "critic" / "long_audio" / "story_final"
    assert folder.name == "story_final"
    assert folder.parent.name == "long_audio"
    assert folder.parent.parent.name == "critic"
    # 不是顶层 critic_long_audio
    assert not (out / "critic_long_audio").exists()
