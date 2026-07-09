"""Repair prompt 模板。

设计要点（参考 Audio-Oscar §C.18-C.20 + 任务卡 §1.5）：
1. 双锚点：original_parameters（不可漂移） + current_parameters（当前要改的）
2. Critic 反馈完整透传：5 维分数 + suggestions
3. "preserve ... exactly" 强烈措辞，明确列出禁改字段
4. 输出 schema 严格：只输出 parameters JSON
"""
from __future__ import annotations

import json

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


_REPAIR_PROMPT_TEMPLATE = """你是 TTS 合成指令的修复专家。根据 Critic 反馈，调整 parameters 字段以改善合成质量。

## 任务规则（必须严格遵守）

**你只能修改 parameters 字段内的内容。** 以下字段由 schema 硬约束，**绝对不能修改**：
- segment_id（段编号）
- speaker（说话人）
- text（原文，是用户资产）
- model（TTS 模型，跨模型音色不一致）
- voice_ref（参考音频，同一角色必须用同一 voice_ref）

parameters 内的字段（如 instruction / instruct_text / speed / emotion_vector 等）你可以自由调整。

## 输入

### 段信息
- segment_id: {segment_id}
- text: {text}
- speaker: {speaker}
- model: {model}

### 当前 parameters（attempt={attempt}）
{current_parameters_json}

### Critic 评分
- quality: {quality}
- emotion_alignment: {emotion_alignment}
- character_consistency: {character_consistency}
- rhythm_naturalness: {rhythm_naturalness}
- intelligibility: {intelligibility}
- overall: {overall}

### Critic 修复建议
{suggestions}

## 你的任务

参考 Critic 建议，调整 parameters 字段。**保留原 parameters 中你没改的字段**
（merge 而不是 replace）。

## 输出格式

**只输出严格的 JSON 对象**，不要加 markdown 标记、解释性文字或代码块。格式：
{{"parameters": {{"field1": "value1", "field2": "value2", ...}}}}
"""


def build_repair_prompt(
    original: ModelSpecificTTSInstruction,
    segment: Segment,
    critic: CriticResult,
) -> str:
    """Build the repair prompt.

    Note: `original` here is the current instruction (we merge into its parameters).
    The "frozen original" semantics (Audio-Oscar §D.23) is enforced at the loop level
    by the 主开发 integration in Stage 8 — for now, the caller passes the current
    instruction and we merge LLM output into its parameters.
    """
    return _REPAIR_PROMPT_TEMPLATE.format(
        segment_id=segment.segment_id,
        text=segment.text,
        speaker=segment.speaker,
        model=original.model,
        attempt=original.attempt,
        current_parameters_json=json.dumps(original.parameters, ensure_ascii=False, indent=2),
        quality=f"{critic.quality:.2f}",
        emotion_alignment=f"{critic.emotion_alignment:.2f}",
        character_consistency=f"{critic.character_consistency:.2f}",
        rhythm_naturalness=f"{critic.rhythm_naturalness:.2f}",
        intelligibility=f"{critic.intelligibility:.2f}",
        overall=f"{critic.overall:.2f}",
        suggestions=critic.suggestions,
    )
