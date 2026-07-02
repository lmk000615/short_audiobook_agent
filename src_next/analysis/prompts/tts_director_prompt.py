"""TTSDirectorAgent 的 system + user prompt 构造器。

设计要点：
- system prompt 注入 available model_configs 的 JSON，让 LLM 看到每个模型
  的完整能力描述（strengths/weaknesses/parameters）。
- user prompt 注入 segments + characters + voicebank 摘要。
- 输出 schema 固定：{"instructions": [{segment_id, model, parameters}, ...]}
- 同 speaker 一致性约束在 system prompt 里（不只靠后处理），让 LLM 主导。
"""
from __future__ import annotations

import json
from typing import Any

from src_next.core.data_models import CharacterProfile, Segment, VoicebankResult


TTS_DIRECTOR_SYSTEM_PROMPT_TEMPLATE = """你是一位资深的有声书 TTS 导演，负责为每个文本段落选择最合适的 TTS 模型并产出该模型的精确合成参数。

# 你的任务
对于输入的每一段 segment，你需要：
1. 根据该段的说话人、内容、情绪、在故事中的角色定位，从下方"可用模型清单"中选择**一个**最合适的 TTS 模型。
2. 输出该模型的 parameters 字段（按各模型 parameters schema 描述填写）。
3. 对于同一说话人的所有段落，**必须使用同一个 model**（保证音色一致性）。

# 可用模型清单
{available_models_json}

# 输出格式（严格 JSON，不要加任何 markdown 代码块标记）
{{
  "instructions": [
    {{
      "segment_id": "<必须与输入 segment 的 segment_id 完全一致>",
      "model": "<可用模型清单里某个模型的 name 字段>",
      "parameters": {{
        <按该模型 parameters schema 描述填写，所有字段都可选，缺省时由系统用 default 填充>
      }}
    }},
    ...
  ]
}}

# 选择模型的决策原则
- **旁白 / narrator**：优先选稳定叙述强的模型（如 CosyVoice3 instruct 模式）。
- **多情绪对白**（一句话内有情绪切换）：优先选支持位置级标签的模型（如 S2Pro）。
- **需要精确情感量化**（如强度可调的悲伤/愤怒）：优先选支持 emotion_vector 的模型（如 IndexTTS2）。
- 别过度使用标签 / emotion_vector——节制使用，让表演自然。

# 同 speaker 一致性约束（重要）
- 同一说话人（speaker 字段相同）的所有 segment，**必须输出同一个 model**。
- 如果一个 speaker 在不同段落情绪差异大，仍然用同一个 model，通过 parameters 调整（如 S2Pro 用不同 inline_tags_text，IndexTTS2 用不同 emotion_vector）。

# parameters 填写规则
- 只输出该 model 在 schema 里声明的字段，不要臆造字段。
- 字段值类型必须匹配 schema 声明（string / bool / float / int / list）。
- 不确定的字段可以省略，系统会用 model_config 的 default 值填充。

# 输出顺序
- instructions 数组的长度和顺序必须与输入 segments 一一对应（按 segment_id 匹配）。
- 不要遗漏任何 segment。如果某个 segment 你不知道该怎么处理，仍然要输出一条（parameters 可以为空对象 {{}}），系统会用 default 兜底。
"""


def build_system_prompt(available_models: list[dict[str, Any]]) -> str:
    """渲染 system prompt，注入 model_configs。

    Args:
        available_models: model_config dict 列表（由 model_config_loader 加载）。

    Returns:
        格式化后的 system prompt 字符串。
    """
    slim_models = []
    for cfg in available_models:
        slim_models.append({
            "name": cfg["name"],
            "short_description": cfg.get("short_description", ""),
            "description": cfg.get("description", ""),
            "strengths": cfg.get("strengths", []),
            "weaknesses": cfg.get("weaknesses", []),
            "best_for": cfg.get("best_for", []),
            "avoid_for": cfg.get("avoid_for", []),
            "voice_input": cfg.get("voice_input", "required_reference"),
            "parameters": cfg.get("parameters", {}),
        })
    return TTS_DIRECTOR_SYSTEM_PROMPT_TEMPLATE.format(
        available_models_json=json.dumps(slim_models, ensure_ascii=False, indent=2)
    )


def build_user_prompt(
    segments: list[Segment],
    character_profiles: list[CharacterProfile],
    voicebank_result: VoicebankResult,
) -> str:
    """构造 user prompt，含 segments + characters + voicebank 摘要。

    把 voicebank 摘要也注入，让 LLM 知道每个 speaker 是否有参考 wav——
    这影响 model 选择（CosyVoice / IndexTTS 必须有 reference；S2Pro 可选）。
    """
    segments_view = [
        {
            "segment_id": s.segment_id,
            "speaker": s.speaker,
            "segment_type": getattr(s, "segment_type", "narration"),
            "text": s.text,
        }
        for s in segments
    ]

    characters_view = [
        {
            "name": c.name,
            # 实际字段是 role_type / age_style，对齐 src_next/core/data_models.py
            "role_type": getattr(c, "role_type", ""),
            "voice_prompt": getattr(c, "voice_prompt", ""),
            "age_style": getattr(c, "age_style", ""),
            "gender": getattr(c, "gender", ""),
            "personality": getattr(c, "personality", ""),
        }
        for c in character_profiles
    ]

    speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}
    voicebank_view = {
        speaker: ("has_reference_wav" if path else "no_reference")
        for speaker, path in speaker_to_voice.items()
    }

    return (
        f"# 故事 segments（共 {len(segments_view)} 段）\n"
        f"{json.dumps(segments_view, ensure_ascii=False, indent=2)}\n\n"
        f"# 角色档案\n"
        f"{json.dumps(characters_view, ensure_ascii=False, indent=2)}\n\n"
        f"# Voicebank 可用性（speaker -> 是否有参考音频）\n"
        f"{json.dumps(voicebank_view, ensure_ascii=False, indent=2)}\n\n"
        f"请按 system prompt 描述的格式，为每一段 segment 输出一条 instruction。"
    )
