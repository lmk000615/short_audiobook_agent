"""Critic 评分 prompt 模板。

设计要点（参考 Audio-Oscar §B.6-B.14 + 任务卡 §1.4 + 声纹评分场景成熟 prompt）：
1. "Expected vs Actual" 对照——把 segment.text / speaker / 期望情感喂给 critic
2. 5 维评分针对 TTS 场景定制（quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility）
3. 严格打分机制：每维 0-10 分 + A/B/C/D 四档 + 强制扣分区间锁定，解决 LLM 倾向打"安全高分"导致好坏难分的问题
4. 嵌套 JSON schema（scores.<dim>.{score,grade,reason,problems}），比扁平 JSON 信息密度更高
5. 强调"不要画蛇添足"——只能给修复 parameters 的建议，不能加新内容
"""
from __future__ import annotations

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


_CRITIC_PROMPT_TEMPLATE = """请仔细听这段 TTS 合成音频，并严格按下方规则评分。

## 输入信息（Expected）
- 原文: {text}
- 说话人: {speaker}
- 段类型: {segment_type}
- TTS 模型: {model}
- 期望情感 / 风格: {expected_emotion}
- 期望语速: {expected_speed}

## 通用打分规则（5 维共用）

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

## 评分维度（5 维各自独立）

### 1. quality 音质清晰度

评价重点：
- 音频清晰度，有无杂音、截断、失真、爆音、电流声。
- 是否有合成伪影、麦克风杂音或编码失真。

等级标准：
A：音质干净清晰，无明显瑕疵。
B：基本清晰，少量不影响听感的小问题。
C：明显杂音、失真或截断，影响听感。
D：严重爆音、机械声或无法辨识。

强制扣分：
- 若发现"明显截断 / 爆音 / 电流声"，最高 C，score 最高 4.9。
- 若判断为"严重失真 / 无法辨识"，最高 D，score 最高 2.4。

### 2. emotion_alignment 情感匹配度

评价重点：
- 实际情感是否与"期望情感 / 风格"（{expected_emotion}）匹配。
- 情绪是否自然、准确、有层次，强弱适度。
- 是否有合理的语气起伏、重音、强调和语调变化。
- 不能只看情绪"强不强"，还要判断是否克制、真实、舒服。
- 情绪过弱、过强、过度表演、浮夸、用力过猛都要扣分。
- 角色对白应既有角色感又不过度戏剧化；旁白应有讲述感，不能像夸张朗诵腔。

等级标准：
A：情绪自然、准确、有层次，强弱适度，贴合角色或旁白状态，真实舒服且有表现力。只有非常贴合且不过度时才能给 A。
B：情绪基本符合内容，有一定起伏和表现力，但略平、略夸张、略用力或层次不足。
C：情绪问题明显，可能偏平，也可能浮夸、用力过猛或戏剧腔明显；能听出情绪，但不够自然舒服。
D：情绪严重不匹配、机械无情绪，或极度浮夸、刺耳、尴尬，严重影响角色可信度和听感。

强制扣分：
- 若判断为"情绪略夸张 / 略用力 / 表演感略强"，emotion_alignment 最高 B，score 最高 7.4。
- 若判断为"过于浮夸 / 用力过猛 / 情绪过强 / 戏剧腔明显 / 不够克制 / 听感尴尬"，最高 C，score 最高 4.9。
- 若判断为"严重浮夸 / 刺耳 / 情绪严重不匹配 / 完全不像真实对话"，最高 D，score 最高 2.4。
- 不允许仅因"情绪强烈"或"起伏明显"给 A，必须同时满足自然、匹配、适度、舒服。

### 3. character_consistency 角色音色一致性

评价重点：
- 声音特征是否符合 {speaker}（结合 {segment_type} 推断的角色设定：性别感、年龄感、声线厚度、发声位置）。
- 前后音色是否稳定，有无明显音色漂移。
- 注意：本场景无独立 reference audio，按"角色设定一致性"判断（不是和某段参考音频比对）。
- 如果只是情绪变化但说话人身份和核心音色一致，应给较高分。

等级标准：
A：高度符合角色设定，声线、年龄感、性别感和音色质感稳定一致。
B：大体符合，但声线厚度、音高或发声位置有轻微偏移。
C：明显偏离角色设定，只部分保留应有的声音特征。
D：差异很大，性别感、年龄感或声线厚度严重错位，或存在严重音色漂移（忽男忽女 / 忽老忽少）。

强制扣分：
- 若"性别感 / 年龄感明显偏离角色设定"，最高 C，score 最高 4.9。
- 若"严重音色漂移（前后不稳定、忽男忽女、忽老忽少）"，最高 D，score 最高 2.4。

### 4. rhythm_naturalness 语速节奏自然度

评价重点：
- 语速是否合适（参考"期望语速 {expected_speed}"），停顿是否自然。
- 断句是否合理，是否符合有声书 / 旁白 / 对白听感。
- 是否存在过快、过慢、断句奇怪、停顿机械、节奏割裂等问题。
- 是否能让听众舒服理解内容。

等级标准：
A：语速自然，停顿合理，节奏流畅，像自然讲述或真实对话。
B：整体节奏较好，语速基本合适，但有少量停顿、断句或节奏问题。
C：节奏一般，存在明显过快、过慢、停顿不自然或断句生硬。
D：节奏较差，语速或停顿严重影响听感，听起来割裂、拖沓或机械。

强制扣分：
- 若"明显过快 / 过慢 / 机械停顿 / 断句生硬"，最高 C，score 最高 4.9。
- 若"节奏严重影响听感（割裂 / 拖沓 / 机械）"，最高 D，score 最高 2.4。

### 5. intelligibility 可懂度

评价重点：
- 文本内容是否清晰可辨，有无吞字、含糊、方言腔过重。
- 是否影响听众理解具体内容（不是"听清楚情绪"，而是"听清楚字词"）。

等级标准：
A：字字清晰，无吞字含糊。
B：个别字略糊但不影响理解。
C：多处吞字、含糊或方言腔过重，需要回放才能听清。
D：大部分字词听不清或无法辨识。

强制扣分：
- 若"多处吞字 / 含糊 / 方言腔过重"，最高 C，score 最高 4.9。
- 若"大部分听不清 / 无法辨识"，最高 D，score 最高 2.4。

## 建议规则（重要）

- 建议必须只针对 **parameters 字段（如 instruction / speed / emotion_vector / instruct_text / style）的调整**。
- **绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定。
- **绝对不要**建议加入新的背景音、音效、配乐——这是语音段，不是音效段。
- suggestions 列表用中文表达，每条一句话，聚焦最高优先级的 1-2 个问题。

## 输出格式

**只输出严格的 JSON**，不要加任何 markdown 标记、解释性文字或代码块：

{{
  "scores": {{
    "quality": {{"score": 0.0, "grade": "A/B/C/D", "reason": "该维度评分理由（中文一句话）", "problems": ["该维度下的主要问题 1", "问题 2"]}},
    "emotion_alignment": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": ["..."]}},
    "character_consistency": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": ["..."]}},
    "rhythm_naturalness": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": ["..."]}},
    "intelligibility": {{"score": 0.0, "grade": "A/B/C/D", "reason": "...", "problems": ["..."]}}
  }},
  "overall_score": 0.0,
  "overall_grade": "A/B/C/D",
  "main_problems": ["整段音频最主要的问题 1（跨维度合并，最多 3 条）", "最主要的问题 2"],
  "suggestions": ["修复建议 1（针对 parameters 调整）", "修复建议 2"]
}}

字段说明：
- score: 该维度的 0-10 分（1 位小数），必须严格落在 grade 对应的区间内
- grade: 该维度的 A/B/C/D 等级
- reason: 该维度的评分理由（中文一句话）
- problems: 该维度下的主要问题列表（0-3 条，无问题则空数组 []）
- overall_score: 5 维综合分 0-10（自行加权平均，权重自行判断；必须与 overall_grade 区间一致）
- overall_grade: 综合等级 A/B/C/D
- main_problems: 整段音频最主要的问题（最多 3 条，跨维度合并）
- suggestions: 修复建议列表（每条针对 parameters 调整，遵循上方"建议规则"）
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
    """Build the scoring prompt for /v1/omni/chat's text field.

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
