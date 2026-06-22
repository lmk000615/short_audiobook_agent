"""src_next/core/audiobook_pipeline.py

Mock 主流程：把 txt → segments → ... → pipeline_result 整条数据流跑通。

本模块不调用真实 LLM、不调用真实 TTS、不访问服务器。
characters / director_plan / voicebank_result / audio_segments 目前都是 mock。
重点是验证 core 层数据流和中间产物落盘是否正常。
"""

import json
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path

from .audio_merger import merge_audio_segments
from .data_models import (
    AudioResult,
    AudioSegmentResult,
    CharacterProfile,
    DirectorInstruction,
    PipelineResult,
    StoryInput,
    VoicebankResult,
)
from .logging_utils import log_item, log_stage_done, log_stage_start
from .segment_builder import build_segments
from .tts_instruction_builder import build_tts_instructions


def _story_name_from_path(input_path: str) -> str:
    """从输入路径提取 story_name（不带扩展名的文件名）。"""
    return Path(input_path).stem


def _serialize(obj):
    """递归把 dataclass / list / dict 转成 JSON 可序列化结构。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def _save_json(obj, path: Path) -> None:
    """保存为 UTF-8 JSON（缩进 2，保留中文）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_serialize(obj), f, ensure_ascii=False, indent=2)


def run_mock_core_pipeline(
    input_path: str,
    output_root: str = "output-src-next-core",
) -> PipelineResult:
    """运行最小 mock pipeline，验证 core 层数据流。"""
    story_name = _story_name_from_path(input_path)
    output_dir = Path(output_root) / story_name
    json_dir = output_dir / "json"
    audio_final_dir = output_dir / "audio_final"

    stage_timings: dict = {}
    artifacts: dict = {}

    try:
        # 1. 读 txt + 构造 StoryInput
        text = Path(input_path).read_text(encoding="utf-8-sig")
        story_input = StoryInput(
            story_name=story_name,
            text=text,
            source_path=str(input_path),
        )

        # 2. build_segments
        log_stage_start("1/8", "文本切分")
        t0 = time.time()
        segments = build_segments(story_input)
        stage_timings["build_segments"] = round(time.time() - t0, 3)
        _save_json(segments, json_dir / "segments.json")
        artifacts["segments"] = str(json_dir / "segments.json")
        log_stage_done("1/8", "文本切分")
        log_item(f"生成 {len(segments)} 个 segments")

        # 3. mock characters
        log_stage_start("2/8", "角色档案 (mock)")
        t0 = time.time()
        characters = [
            CharacterProfile(
                name="narrator",
                role_type="narrator",
                gender="neutral",
                age_style="adult",
                personality="旁白",
                voice_prompt="mock narrator voice",
                confidence=1.0,
            )
        ]
        stage_timings["mock_characters"] = round(time.time() - t0, 3)
        _save_json(characters, json_dir / "characters.json")
        artifacts["characters"] = str(json_dir / "characters.json")
        log_stage_done("2/8", "角色档案 (mock)")
        log_item(f"生成 {len(characters)} 个角色档案")

        # 4. mock director_plan
        log_stage_start("3/8", "导演计划 (mock)")
        t0 = time.time()
        director_plan = [
            DirectorInstruction(
                segment_id=seg.segment_id,
                speaker=seg.speaker,
                emotion="neutral",
                pace=1.0,
                tone="neutral",
                pause_hint=0.0,
                delivery_instruction="mock delivery",
            )
            for seg in segments
        ]
        stage_timings["mock_director_plan"] = round(time.time() - t0, 3)
        _save_json(director_plan, json_dir / "director_plan.json")
        artifacts["director_plan"] = str(json_dir / "director_plan.json")
        log_stage_done("3/8", "导演计划 (mock)")
        log_item(f"生成 {len(director_plan)} 条导演指导")

        # 5. mock voicebank_result
        log_stage_start("4/8", "Voicebank (mock)")
        t0 = time.time()
        voicebank_result = VoicebankResult(
            speaker_to_voice={"narrator": "mock://voice/narrator"},
            voicebank_dir=str(output_dir / "voicebank"),
            backend="mock",
            success=True,
        )
        stage_timings["mock_voicebank"] = round(time.time() - t0, 3)
        _save_json(voicebank_result, json_dir / "voicebank_result.json")
        artifacts["voicebank_result"] = str(json_dir / "voicebank_result.json")
        log_stage_done("4/8", "Voicebank (mock)")
        log_item(f"准备了 {len(voicebank_result.speaker_to_voice)} 个 voice reference")

        # 6. build_tts_instructions
        log_stage_start("5/8", "TTS 指令构建")
        t0 = time.time()
        tts_instructions = build_tts_instructions(
            segments=segments,
            characters=characters,
            director_plan=director_plan,
            voicebank_result=voicebank_result,
        )
        stage_timings["build_tts_instructions"] = round(time.time() - t0, 3)
        _save_json(tts_instructions, json_dir / "tts_instructions.json")
        artifacts["tts_instructions"] = str(json_dir / "tts_instructions.json")
        log_stage_done("5/8", "TTS 指令构建")
        log_item(f"生成 {len(tts_instructions)} 条 tts 指令")

        # 7. mock audio_segments
        log_stage_start("6/8", "音频合成 (mock)")
        t0 = time.time()
        audio_segments = [
            AudioSegmentResult(
                segment_id=seg.segment_id,
                speaker=seg.speaker,
                audio_path=f"mock://audio/{seg.segment_id}",
                success=True,
            )
            for seg in segments
        ]
        stage_timings["mock_audio_segments"] = round(time.time() - t0, 3)
        log_stage_done("6/8", "音频合成 (mock)")
        log_item(f"mock 合成 {len(audio_segments)} 段音频")

        # 8. merge_audio_segments + 占位文件
        log_stage_start("7/8", "音频拼接")
        t0 = time.time()
        audio_final_dir.mkdir(parents=True, exist_ok=True)
        final_audio_path = audio_final_dir / f"{story_name}_mock.txt"
        final_audio_path.write_text(
            f"[MOCK AUDIO PLACEHOLDER]\n"
            f"story: {story_name}\n"
            f"segments: {len(audio_segments)}\n"
            f"generated_by: src_next/core/audiobook_pipeline.py (mock)\n",
            encoding="utf-8",
        )
        audio_result = merge_audio_segments(audio_segments, str(final_audio_path))
        stage_timings["merge_audio"] = round(time.time() - t0, 3)
        _save_json(audio_result, json_dir / "audio_result.json")
        artifacts["audio_result"] = str(json_dir / "audio_result.json")
        log_stage_done("7/8", "音频拼接")
        log_item(f"最终音频: {audio_result.final_audio}")

        # 9. 汇总 pipeline_result
        log_stage_start("8/8", "汇总")
        pipeline_result = PipelineResult(
            story_name=story_name,
            output_dir=str(output_dir),
            final_audio=audio_result.final_audio,
            success=True,
            stage_timings=stage_timings,
            artifacts=artifacts,
            error="",
        )
        _save_json(pipeline_result, json_dir / "pipeline_result.json")
        log_stage_done("8/8", "汇总")
        log_item(f"pipeline success: {pipeline_result.success}")

        return pipeline_result

    except Exception as e:
        return PipelineResult(
            story_name=story_name,
            output_dir=str(output_dir),
            final_audio="",
            success=False,
            stage_timings=stage_timings,
            artifacts=artifacts,
            error=str(e),
        )
