"""属性感知 Critic 的评分 prompt 模板（与 critic_prompt.py 并存）。

设计差异（vs 原 critic_prompt.py）：
1. 两步法：先让 critic **客观提取音频实际属性**（emotion / intensity / pace /
   volume / pitch + evidence），再与 DirectorInstruction 的期望属性**逐项对比**。
2. 期望属性的真相源是上游 DirectorInstruction，prompt 里渲染成固定文本让 critic
   复述（自检用）；scoring 解析时永远取 DirectorInstruction 现场渲染值，不信 LLM。
3. 保留原 5 维评分（quality / emotion_alignment / character_consistency /
   rhythm_naturalness / intelligibility）+ 严格 A/B/C/D 区段锁定，向后兼容
   TTSRepairAgent 闭环。
4. emotion_alignment 的 reason 应直接引用 inconsistency_summary（prompt 里写明联动）。

输出 schema 在原 5 维嵌套结构上新增三段：extracted_attributes / expected_attributes
/ attribute_consistency。详见模块末尾示例。
"""
from __future__ import annotations

from src_next.core.data_models import (
    DirectorInstruction,
    ModelSpecificTTSInstruction,
    Segment,
)


_ATTRIBUTE_CRITIC_PROMPT_TEMPLATE = """请仔细听这段 TTS 合成音频，按下方两步法流程评分。

## 输入信息（Expected）
- 原文: {text}
- 说话人: {speaker}
- 段类型: {segment_type}
- TTS 模型: {model}
- 当前 attempt: {attempt}

## 上游导演指令（DirectorInstruction，唯一真相源）
- emotion（情绪基调）: {expected_emotion}
- emotion_intensity（情绪强度 0.0-1.0）: {expected_intensity}
- pace（语速倍率 0.75-1.30）: {expected_pace}
- tone（语气）: {expected_tone}
- volume（音量 soft/normal/strong）: {expected_volume}
- pitch（音高 low/medium_low/medium/medium_high/high）: {expected_pitch}
- delivery_instruction（综合朗读指导）: {expected_delivery}

---

## 第一步：客观提取音频实际属性

仔细听音频，**只描述你听到的实际表现**，不要与期望对比。在 extracted_attributes 中输出：

- emotion：你听到的情绪类型（如 happy / sad / angry / calm / surprised / anxious /
  nostalgic / playful / serious / gentle / warm / neutral 等，可自由描述）
- intensity：情绪强度 0.0-1.0（0.0 无情绪 / 0.3 内敛 / 0.5 适中 / 0.8 强烈 / 1.0 极致）
- pace：实际语速倍率 0.75-1.30（估算：偏慢 < 1.0 / 适中 = 1.0 / 偏快 > 1.0）
- volume：实际音量（soft / normal / strong）
- pitch：实际音高（low / medium_low / medium / medium_high / high）
- evidence：**必填**，一句话说明你判断的客观依据（如"句尾下沉、语速偏慢、气息短促"）。
  不允许留空——这是防止你瞎猜的硬约束。

---

## 第二步：与上游导演指令逐项对比

针对每个属性，判断音频实际表现是否与上方"上游导演指令"一致。在 attribute_consistency 中输出：

- emotion / intensity / pace / volume / pitch：每项给
  {{"match": true/false, "note": "一句话说明对比结果"}}
  - match=true：基本一致（允许小幅偏差，不影响听感）
  - match=false：明显不一致
  - note：用中文一句话说明，如"期望 0.8 强烈悲伤，实际 0.6 偏弱"
- overall_verdict：high / medium / low
  - high：5 项基本一致
  - medium：1-2 项不一致但整体仍可接受
  - low：3 项及以上不一致，或任一关键属性（emotion / intensity）严重偏离
- inconsistency_summary：中文一句话总结不一致点（一致时填"基本一致"）

---

## 第三步：5 维评分（保留原 critic 严格打分机制）

### 通用打分规则（5 维共用）

- 每个维度必须输出 score 和 grade。
- score 范围 0 到 10，可保留 1 位小数。
- grade 只能是 A、B、C、D。
- 必须先判断 grade，再按对应区间给 score。
- A/B/C/D 四档均分：
  - A：7.5 <= score <= 10.0
  - B：5.0 <= score < 7.5
  - C：2.5 <= score < 5.0
  - D：0.0 <= score < 2.5
- 判断为 A/B/C/D 时，score 必须严格落在对应区间内。
- 请大胆区分好坏，充分使用 0 到 10，不要所有维度都集中在 7 或 8。
- 如果某维度存在明显问题，必须给 C 或 D。
- 如果不同维度差异明显，分数差异也必须明显。
- 不允许 reason 写了明显问题但 grade 仍为 A。

### 评分维度（5 维各自独立）

#### 1. quality 音质清晰度
- 评价重点：清晰度、有无杂音 / 截断 / 失真 / 爆音 / 电流声 / 合成伪影。
- A：音质干净清晰。B：基本清晰，少量不影响听感的小问题。
- C：明显杂音、失真或截断，影响听感。D：严重爆音、机械声或无法辨识。
- 强制扣分：发现"明显截断 / 爆音 / 电流声"最高 C，score 最高 4.9；
  "严重失真 / 无法辨识"最高 D，score 最高 2.4。

#### 2. emotion_alignment 情感匹配度
- **重要联动**：本维度的 reason 必须直接引用第二步的 inconsistency_summary。
  若 inconsistency_summary = "基本一致"，emotion_alignment 不允许低于 B；
  若 overall_verdict = low，emotion_alignment 最高 C。
- 评价重点：实际情感是否与上游导演指令匹配；情绪是否自然、准确、有层次。
- 情绪过弱 / 过强 / 过度表演 / 浮夸 / 用力过猛都要扣分。
- A：情绪自然、准确、有层次，贴合导演指令。B：基本符合，但略平 / 略夸张 / 略用力。
- C：情绪问题明显，偏平或浮夸或用力过猛。D：严重不匹配 / 机械无情绪 / 极度浮夸刺耳。
- 强制扣分：
  - "情绪略夸张 / 略用力 / 表演感略强" → 最高 B，score 最高 7.4
  - "过于浮夸 / 用力过猛 / 戏剧腔明显 / 不够克制 / 听感尴尬" → 最高 C，score 最高 4.9
  - "严重浮夸 / 刺耳 / 严重不匹配 / 完全不像真实对话" → 最高 D，score 最高 2.4

#### 3. character_consistency 角色音色一致性
- 评价重点：声音特征是否符合 {speaker}（结合段类型推断的角色设定）；
  前后音色是否稳定。本场景无独立 reference audio，按"角色设定一致性"判断。
- A：高度符合，声线 / 年龄感 / 性别感稳定。B：大体符合，轻微偏移。
- C：明显偏离。D：性别感 / 年龄感严重错位，或严重音色漂移。
- 强制扣分：
  - "性别感 / 年龄感明显偏离" → 最高 C，score 最高 4.9
  - "严重音色漂移（前后不稳定 / 忽男忽女 / 忽老忽少）" → 最高 D，score 最高 2.4

#### 4. rhythm_naturalness 语速节奏自然度
- 评价重点：语速是否合适（参考导演指令 pace），停顿是否自然，断句是否合理。
- A：语速自然，停顿合理。B：整体较好，少量节奏问题。
- C：节奏一般，明显过快 / 过慢 / 停顿不自然 / 断句生硬。
- D：节奏严重影响听感，割裂 / 拖沓 / 机械。
- 强制扣分：
  - "明显过快 / 过慢 / 机械停顿 / 断句生硬" → 最高 C，score 最高 4.9
  - "节奏严重影响听感" → 最高 D，score 最高 2.4

#### 5. intelligibility 可懂度
- 评价重点：字词是否清晰可辨，有无吞字 / 含糊 / 方言腔过重。
- A：字字清晰。B：个别字略糊但不影响理解。
- C：多处吞字 / 含糊 / 方言腔过重，需要回放才能听清。
- D：大部分字词听不清或无法辨识。
- 强制扣分：
  - "多处吞字 / 含糊 / 方言腔过重" → 最高 C，score 最高 4.9
  - "大部分听不清 / 无法辨识" → 最高 D，score 最高 2.4

---

## 建议规则（重要）

- suggestions 必须只针对 **parameters 字段（如 instruction / speed / emotion_vector /
  instruct_text / style）的调整**。
- **绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定。
- **绝对不要**建议加入新的背景音、音效、配乐——这是语音段，不是音效段。
- 仅当 attribute_consistency.overall_verdict = medium 或 low，或 5 维任一为 C/D 时
  才输出 suggestions；全部 high 且 5 维全 A/B 时 suggestions 可以为空数组 []。
- suggestions 用中文表达，每条一句话，聚焦最高优先级的 1-2 个问题。

---

## 输出格式

**只输出严格的 JSON**，不要加任何 markdown 标记、解释性文字或代码块：

{{
  "extracted_attributes": {{
    "emotion": "...",
    "intensity": 0.0,
    "pace": 0.0,
    "volume": "soft/normal/strong",
    "pitch": "low/medium_low/medium/medium_high/high",
    "evidence": "（必填，客观依据一句话）"
  }},
  "expected_attributes": {{
    "emotion": "{expected_emotion}",
    "intensity": {expected_intensity},
    "pace": {expected_pace},
    "tone": "{expected_tone}",
    "volume": "{expected_volume}",
    "pitch": "{expected_pitch}",
    "delivery_instruction": "{expected_delivery}"
  }},
  "attribute_consistency": {{
    "emotion": {{"match": true, "note": "..."}},
    "intensity": {{"match": false, "note": "..."}},
    "pace": {{"match": true, "note": "..."}},
    "volume": {{"match": true, "note": "..."}},
    "pitch": {{"match": true, "note": "..."}},
    "overall_verdict": "high/medium/low",
    "inconsistency_summary": "..."
  }},
  "scores": {{
    "quality": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": []}},
    "emotion_alignment": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": []}},
    "character_consistency": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": []}},
    "rhythm_naturalness": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": []}},
    "intelligibility": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": []}}
  }},
  "overall_score": 0.0,
  "overall_grade": "A/B/C/D",
  "main_problems": ["整段音频最主要的问题 1（最多 3 条）", "最主要的问题 2"],
  "suggestions": ["修复建议 1（针对 parameters 调整）", "修复建议 2"]
}}

字段说明：
- extracted_attributes.evidence：必填，不允许空字符串
- expected_attributes：复述上方"上游导演指令"段落的内容（仅自检用，scoring 解析时
  会被 DirectorInstruction 现场渲染值覆盖）
- attribute_consistency.overall_verdict：high / medium / low
- scores.<dim>.score：0-10（1 位小数），必须严格落在 grade 对应的区间内
- scores.<dim>.grade：A / B / C / D
- scores.<dim>.reason：评分理由（中文一句话）
- scores.<dim>.problems：该维度下的主要问题列表（0-3 条，无问题则空数组 []）
- scores.emotion_alignment.reason：**必须直接引用 inconsistency_summary**
- overall_score：5 维综合分 0-10（自行加权平均，必须与 overall_grade 区间一致）
- overall_grade：综合等级 A/B/C/D
- main_problems：整段音频最主要的问题（最多 3 条，跨维度合并）
- suggestions：修复建议（每条针对 parameters 调整，遵循上方"建议规则"）
"""


def build_attribute_critic_prompt(
    segment: Segment,
    tts_instruction: ModelSpecificTTSInstruction,
    director_instruction: DirectorInstruction,
) -> str:
    """Build the attribute-aware two-step scoring prompt.

    Renders DirectorInstruction fields as the "expected anchor" — the only source
    of truth for expected attributes. LLM is asked to repeat them in
    ``expected_attributes`` for self-check only; the parsed result always re-renders
    from ``DirectorInstruction`` (see ``AttributeAwareCriticResult.from_json``).
    """
    return _ATTRIBUTE_CRITIC_PROMPT_TEMPLATE.format(
        text=segment.text,
        speaker=segment.speaker,
        segment_type=segment.segment_type,
        model=tts_instruction.model,
        attempt=tts_instruction.attempt,
        expected_emotion=director_instruction.emotion,
        expected_intensity=director_instruction.emotion_intensity,
        expected_pace=director_instruction.pace,
        expected_tone=director_instruction.tone,
        expected_volume=director_instruction.volume,
        expected_pitch=director_instruction.pitch,
        expected_delivery=director_instruction.delivery_instruction or "（未指定）",
    )
