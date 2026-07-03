"""Critic 评分 prompt 模板。

设计要点（参考 Audio-Oscar §B.6-B.14 + 任务卡 §1.4）：
1. "Expected vs Actual" 对照——把 segment.text / speaker / 期望情感喂给 critic
2. 5 维评分针对 TTS 场景定制（不是 Oscar 的 3 维）
3. 嵌入严格 JSON schema 示例，比抽象描述稳定得多
4. suggestions 限制为中文一句话，避免 repair LLM 信息过载
5. 强调"不要画蛇添足"——只能给修复 parameters 的建议，不能加新内容
"""
from __future__ import annotations

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


_CRITIC_PROMPT_TEMPLATE = """请仔细听这段 TTS 合成音频，并对照以下信息评分。

## 原文
{text}

## 期望表现
- 说话人: {speaker}
- 段类型: {segment_type}
- TTS 模型: {model}
- 期望情感 / 风格: {expected_emotion}
- 期望语速: {expected_speed}

## 评分维度（每项 0.0-1.0，浮点数保留 2 位）
1. quality: 音质清晰度（有无杂音、截断、失真、爆音）
2. emotion_alignment: 情感是否与"期望情感 / 风格"一致
3. character_consistency: 声音特征是否符合 {speaker} 的角色设定
4. rhythm_naturalness: 语速、停顿、语调是否自然
5. intelligibility: 文本内容是否清晰可辨、有无吞字或含糊

## 建议规则（重要）
- 建议必须只针对 **parameters 字段（如 instruction / speed / emotion_vector）的调整**。
- **绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定。
- **绝对不要**建议加入新的背景音、音效、配乐——这是语音段，不是音效段。
- 建议用一句中文表达，聚焦最高优先级的 1-2 个问题。

## 输出格式
**只输出严格的 JSON**，不要加任何 markdown 标记、解释性文字或代码块：
{{"quality":0.85,"emotion_alignment":0.80,"character_consistency":0.90,"rhythm_naturalness":0.82,"intelligibility":0.95,"suggestions":"建议内容"}}
"""


def _extract_expected_emotion(parameters: dict) -> str:
    """CosyVoice3 用 instruct_text，S2Pro 用 instruction，IndexTTS 用 emotion_vector。"""
    for key in ("instruct_text", "instruction", "emotion", "emotion_vector", "style"):
        v = parameters.get(key)
        if v:
            return str(v)
    return "未指定"


def _extract_expected_speed(parameters: dict) -> str:
    speed = parameters.get("speed")
    if speed is None:
        return "未指定（用模型默认）"
    return str(speed)


def build_critic_prompt(
    segment: Segment,
    tts_instruction: ModelSpecificTTSInstruction,
) -> str:
    """Build the scoring prompt for audio_analysis's text field.

    Embeds original text + speaker + expected emotion as the "expected" side of the
    Audio-Oscar "Expected vs Actual" pattern, so the Critic can do semantic alignment.
    """
    return _CRITIC_PROMPT_TEMPLATE.format(
        text=segment.text,
        speaker=segment.speaker,
        segment_type=segment.segment_type,
        model=tts_instruction.model,
        expected_emotion=_extract_expected_emotion(tts_instruction.parameters),
        expected_speed=_extract_expected_speed(tts_instruction.parameters),
    )
