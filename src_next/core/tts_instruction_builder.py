"""src_next/core/tts_instruction_builder.py

根据 segments / characters / director_plan / voicebank_result 构建 TTS 指令。
匹配逻辑暂时简单：按 segment_id 找 director，按 speaker 找 voice_ref。
"""

from .data_models import (
    Segment,
    CharacterProfile,
    DirectorInstruction,
    TTSInstruction,
    VoicebankResult,
)


def build_tts_instructions(
    segments: list[Segment],
    characters: list[CharacterProfile],
    director_plan: list[DirectorInstruction],
    voicebank_result: VoicebankResult,
) -> list[TTSInstruction]:
    """组装 TTSInstruction 列表。

    匹配规则：
      * segment_id → director_plan 中的 DirectorInstruction（找不到用默认）。
      * speaker → voicebank_result.speaker_to_voice 中的 voice_ref；
        找不到时回退到 narrator，再找不到为 None。
    """
    director_by_id = {d.segment_id: d for d in director_plan}
    voice_by_speaker = voicebank_result.speaker_to_voice or {}
    _ = characters  # 预留：未来根据 character 调整 voice_prompt / 情绪细节

    instructions: list[TTSInstruction] = []
    for seg in segments:
        director = director_by_id.get(seg.segment_id)
        if director is None:
            director = DirectorInstruction(segment_id=seg.segment_id, speaker=seg.speaker)

        voice_ref = (
            voice_by_speaker.get(seg.speaker)
            or voice_by_speaker.get("narrator")
        )

        instructions.append(
            TTSInstruction(
                segment_id=seg.segment_id,
                speaker=seg.speaker,
                text=seg.text,
                voice_ref=voice_ref,
                emotion=director.emotion,
                pace=director.pace,
                tone=director.tone,
                instruction=director.delivery_instruction,
            )
        )
    return instructions
