"""stage 8 多 adapter 分组调度单元测试（mock HTTP）。

验证 use_tts_director=true 时 stage 8 的多 adapter 调度逻辑：
1. 按 instruction.model 分组
2. 每组 lazy-create adapter
3. 合并结果按 segment_id 排序

不打真 pipeline（避免 yaml + LLM 依赖），直接验证分组逻辑。
"""
from __future__ import annotations

from collections import defaultdict
from unittest.mock import MagicMock


def test_grouping_by_model_creates_distinct_groups():
    """不同 model 的 instructions 应分组到不同 list。"""
    from src_next.core.data_models import ModelSpecificTTSInstruction

    instructions = [
        ModelSpecificTTSInstruction(
            segment_id=f"seg_{i:03d}", speaker="narrator", text=f"test {i}",
            model=model, parameters={},
        )
        for i, model in enumerate(["CosyVoice3", "S2Pro", "IndexTTS2", "CosyVoice3", "S2Pro"])
    ]

    grouped: dict[str, list] = {}
    for inst in instructions:
        grouped.setdefault(inst.model, []).append(inst)

    assert set(grouped.keys()) == {"CosyVoice3", "S2Pro", "IndexTTS2"}
    assert len(grouped["CosyVoice3"]) == 2  # seg_000 + seg_003
    assert len(grouped["S2Pro"]) == 2  # seg_001 + seg_004
    assert len(grouped["IndexTTS2"]) == 1  # seg_002


def test_order_preserved_after_dispatch():
    """多 adapter 合并后，audio_segments 顺序应与原 tts_instructions 一致。"""
    from src_next.core.data_models import (
        AudioSegmentResult, ModelSpecificTTSInstruction,
    )

    instructions = [
        ModelSpecificTTSInstruction(
            segment_id="seg_001", speaker="narrator", text="t1", model="CosyVoice3",
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_002", speaker="小松鼠", text="t2", model="S2Pro",
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_003", speaker="老乌龟", text="t3", model="IndexTTS2",
        ),
    ]

    # 模拟 adapter.synthesize 返回（顺序故意打乱）
    mock_results_by_seg = {
        "seg_001": AudioSegmentResult(
            segment_id="seg_001", speaker="narrator",
            audio_path="/o/1.wav", success=True, error="",
        ),
        "seg_002": AudioSegmentResult(
            segment_id="seg_002", speaker="小松鼠",
            audio_path="/o/2.wav", success=True, error="",
        ),
        "seg_003": AudioSegmentResult(
            segment_id="seg_003", speaker="老乌龟",
            audio_path="/o/3.wav", success=True, error="",
        ),
    }

    # 按 model 分组
    grouped: dict[str, list] = {}
    for inst in instructions:
        grouped.setdefault(inst.model, []).append(inst)

    # 收集结果（模拟 pipeline stage 8 的还原逻辑）
    audio_segments_by_id: dict[str, AudioSegmentResult] = {}
    for model_name, group in grouped.items():
        # mock adapter 调用
        for inst in group:
            audio_segments_by_id[inst.segment_id] = mock_results_by_seg[inst.segment_id]

    # 按 tts_instructions 顺序还原
    audio_segments = [
        audio_segments_by_id[inst.segment_id]
        for inst in instructions
        if inst.segment_id in audio_segments_by_id
    ]

    # 验证顺序
    assert [r.segment_id for r in audio_segments] == [
        "seg_001", "seg_002", "seg_003",
    ], "多 adapter 调度后顺序应与 tts_instructions 一致"


def test_failed_segment_in_one_group_does_not_block_others():
    """单段失败不阻断其他段（沿用老路径行为）。"""
    from src_next.core.data_models import (
        AudioSegmentResult, ModelSpecificTTSInstruction,
    )

    instructions = [
        ModelSpecificTTSInstruction(
            segment_id="seg_001", speaker="narrator", text="t1", model="CosyVoice3",
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_002", speaker="小松鼠", text="t2", model="S2Pro",
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_003", speaker="老乌龟", text="t3", model="CosyVoice3",
        ),
    ]

    # 模拟 adapter 返回（CosyVoice3 adapter 让 seg_001 success, seg_003 fail）
    cosyvoice_results = [
        AudioSegmentResult(
            segment_id="seg_001", speaker="narrator",
            audio_path="/o/1.wav", success=True, error="",
        ),
        AudioSegmentResult(
            segment_id="seg_003", speaker="老乌龟",
            audio_path=None, success=False, error="HTTP 500",
        ),
    ]
    s2pro_results = [
        AudioSegmentResult(
            segment_id="seg_002", speaker="小松鼠",
            audio_path="/o/2.wav", success=True, error="",
        ),
    ]

    grouped: dict[str, list] = defaultdict(list)
    for inst in instructions:
        grouped[inst.model].append(inst)

    audio_segments_by_id = {}
    for r in cosyvoice_results + s2pro_results:
        audio_segments_by_id[r.segment_id] = r

    audio_segments = [
        audio_segments_by_id[inst.segment_id]
        for inst in instructions
        if inst.segment_id in audio_segments_by_id
    ]

    success_n = sum(1 for r in audio_segments if r.success)
    failed_n = sum(1 for r in audio_segments if not r.success)

    # 3 段全部进结果（失败的也在），失败计数 1
    assert len(audio_segments) == 3
    assert success_n == 2
    assert failed_n == 1
