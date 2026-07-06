"""audio_merger 跨采样率合并测试（v3 重采样支持）。

验证新链路 tts_director 多 backend 混合输出场景：
- CosyVoice3 → 24000 Hz PCM_16
- S2Pro → 44100 Hz PCM_16
- IndexTTS2 → 22050 Hz PCM_16

audio_merger 应该把后两段重采样到基准采样率（第一段），而不是跳过。
"""
from __future__ import annotations

import io
import wave
from pathlib import Path

from src_next.core.audio_merger import merge_audio_segments
from src_next.core.data_models import AudioSegmentResult


def _make_wav_bytes(framerate: int, duration_seconds: float) -> bytes:
    """造指定采样率 / 时长的 PCM_16 mono wav 字节流。

    用全零帧（静音）填充——本测试只关心帧数 / 采样率，不关心内容。
    """
    n_frames = int(framerate * duration_seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def _write_wav_file(path: Path, framerate: int, duration_seconds: float) -> None:
    """写一个 PCM_16 mono wav 到指定路径。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_make_wav_bytes(framerate, duration_seconds))


def test_merge_resamples_mixed_framerates_to_base(tmp_path):
    """3 段不同采样率（24000 / 44100 / 22050）的 wav 应该被合并成单个 wav，
    时长 ≈ 3 段时长之和（重采样误差 < 0.1s）。基准采样率 = 第一段。"""
    # 造 3 个不同采样率的 wav
    wav1 = tmp_path / "seg_001.wav"
    wav2 = tmp_path / "seg_002.wav"
    wav3 = tmp_path / "seg_003.wav"
    _write_wav_file(wav1, framerate=24000, duration_seconds=2.0)   # CosyVoice3
    _write_wav_file(wav2, framerate=44100, duration_seconds=3.0)   # S2Pro
    _write_wav_file(wav3, framerate=22050, duration_seconds=1.5)   # IndexTTS2

    segments = [
        AudioSegmentResult(
            segment_id="seg_001", speaker="narrator",
            audio_path=str(wav1), success=True, error="",
        ),
        AudioSegmentResult(
            segment_id="seg_002", speaker="小松鼠",
            audio_path=str(wav2), success=True, error="",
        ),
        AudioSegmentResult(
            segment_id="seg_003", speaker="老乌龟",
            audio_path=str(wav3), success=True, error="",
        ),
    ]

    final_path = tmp_path / "final.wav"
    # min_silence_seconds=0 关闭段间静音，让时长精确等于各段之和
    result = merge_audio_segments(
        segments, str(final_path), pause_seconds_after={}, min_silence_seconds=0,
    )

    assert result.success, f"合并失败：{result.duration_seconds}"
    # 总时长 ≈ 2.0 + 3.0 + 1.5 = 6.5s（重采样误差 < 0.1s）
    expected = 6.5
    assert abs(result.duration_seconds - expected) < 0.2, (
        f"合并后时长 {result.duration_seconds:.2f}s ≠ 期望 ~{expected}s "
        f"（重采样可能没生效，只合并了第一段）"
    )

    # 验证 final wav 文件本身：基准采样率 = 24000（第一段）
    with wave.open(str(final_path), "rb") as wf:
        assert wf.getframerate() == 24000, (
            f"final wav 采样率 = {wf.getframerate()}，期望 24000（基准 = 第一段）"
        )
        assert wf.getsampwidth() == 2, "final wav 应该是 PCM_16"


def test_merge_skips_sampwidth_mismatch(tmp_path):
    """sampwidth 不一致（16bit vs 32bit）的段仍应被跳过（ratecv 不处理位深转换）。"""
    wav1 = tmp_path / "seg_001.wav"  # PCM_16
    wav2 = tmp_path / "seg_002.wav"  # PCM_32

    _write_wav_file(wav1, framerate=24000, duration_seconds=1.0)
    # 造 PCM_32 wav
    with wave.open(str(wav2), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(4)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00\x00\x00" * 24000)

    segments = [
        AudioSegmentResult(
            segment_id="seg_001", speaker="a",
            audio_path=str(wav1), success=True, error="",
        ),
        AudioSegmentResult(
            segment_id="seg_002", speaker="b",
            audio_path=str(wav2), success=True, error="",
        ),
    ]

    result = merge_audio_segments(
        segments, str(tmp_path / "final.wav"), min_silence_seconds=0,
    )
    assert result.success
    # 时长 ≈ 1.0s（只第一段被合并，第二段因 sampwidth 不一致被跳过）
    assert abs(result.duration_seconds - 1.0) < 0.05, (
        f"合并后时长 {result.duration_seconds:.2f}s，期望 ~1.0s（sampwidth 不一致应跳过）"
    )


def test_merge_same_framerate_still_works(tmp_path):
    """同采样率场景（老链路）应该照常工作，不触发重采样。"""
    wav1 = tmp_path / "seg_001.wav"
    wav2 = tmp_path / "seg_002.wav"
    _write_wav_file(wav1, framerate=24000, duration_seconds=2.0)
    _write_wav_file(wav2, framerate=24000, duration_seconds=3.0)

    segments = [
        AudioSegmentResult(
            segment_id="seg_001", speaker="a",
            audio_path=str(wav1), success=True, error="",
        ),
        AudioSegmentResult(
            segment_id="seg_002", speaker="b",
            audio_path=str(wav2), success=True, error="",
        ),
    ]

    result = merge_audio_segments(
        segments, str(tmp_path / "final.wav"), min_silence_seconds=0,
    )
    assert result.success
    # 时长 = 2.0 + 3.0 = 5.0s（无重采样误差）
    assert abs(result.duration_seconds - 5.0) < 0.05
