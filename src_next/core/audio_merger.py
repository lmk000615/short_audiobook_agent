"""src_next/core/audio_merger.py

音频拼接 — 当前为 placeholder。
未来会接入真实 wav 拼接（pydub / ffmpeg / 纯 numpy 等），目前只返回 mock 结果。
"""

from .data_models import AudioSegmentResult, AudioResult


def merge_audio_segments(
    audio_segments: list[AudioSegmentResult],
    final_path: str,
) -> AudioResult:
    """把 audio_segments 拼接成最终音频。

    Placeholder：当前不真正读取或拼接 wav 文件，只汇总每段 AudioSegmentResult 和 success 状态。
    final_path 由调用方负责创建占位文件；本函数只把路径记录到 AudioResult。
    """
    success_count = sum(1 for s in audio_segments if s.success)
    return AudioResult(
        final_audio=final_path,
        audio_segments=list(audio_segments),
        duration_seconds=0.0,
        success=success_count > 0,
    )
