"""src_next/voicebank/voicebank_critic_prompt.py

Voicebank Critic 的 LLM prompt 模板。

Critic 不直接让 LLM "听"音频，而是间接评估：
1. 用 soundfile / wave 提取 wav 的物理特征（时长、采样率、声道、RMS 能量、基频统计）
2. 将物理特征 + 角色档案一起传给 LLM，让 LLM 基于物理特征 + voice_prompt 语义做评估

基频 (pitch) 是性别判断的关键指标：
- 男性成人基频通常 85-180 Hz
- 女性成人基频通常 165-255 Hz
- 儿童基频通常 250-400 Hz

v2 改进：
- 5 档评分校准锚点，避免 LLM 打分偏宽
- 硬性不匹配规则（基频-性别/年龄矛盾 → 强制低分）
- 批判性评估基调
- user prompt 增加自动计算的 ⚠️ 不匹配标注
- 支持前轮评估反馈（再生成轮次）
"""

# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

CRITIC_SYSTEM_PROMPT = """\
你是一位严格的专业语音音色质量审核员。你的职责是**批判性地**评估角色音色参考音频是否与角色设定匹配。

**评估原则：宁可严判也不放水。** 有疑点就扣分，不要因为"大体还行"就给高分。你的评分将决定是否需要重新生成音频——如果该重生的给了高分，角色音色就会带着缺陷进入最终有声书。

## 评分校准（5 档制，每个维度 0.0~1.0）

你必须严格按照以下标准打分，不要默认给 0.7+：

| 档位 | 分数范围 | 含义 |
|------|----------|------|
| 严重不匹配 | 0.0–0.2 | 物理特征与设定完全矛盾 |
| 明显偏差 | 0.2–0.4 | 物理特征与设定有显著矛盾 |
| 部分匹配 | 0.4–0.6 | 有一定匹配但存在可察觉的偏差 |
| 较好匹配 | 0.6–0.8 | 基本匹配，仅有轻微偏差 |
| 高度匹配 | 0.8–1.0 | 物理特征与设定高度一致 |

## 各维度评分规则

### 1. gender_match（性别匹配度）

**硬性规则（必须遵守）：**
- 设定男性，基频均值 > 200 Hz → gender_match ≤ 0.4（基频落在女性/儿童区间）
- 设定女性，基频均值 < 150 Hz → gender_match ≤ 0.4（基频落在男性区间）
- 设定儿童，基频均值 < 200 Hz → gender_match ≤ 0.4（基频未达儿童区间）
- 基频均值与性别设定一致 → 根据偏离程度打 0.6–1.0

**参考基频范围：**
- 男性成人：85–180 Hz（均值通常 100–150 Hz）
- 女性成人：165–255 Hz（均值通常 180–220 Hz）
- 儿童：250–400 Hz

### 2. age_match（年龄匹配度）

**硬性规则：**
- 设定 elderly（老年），基频均值 > 200 Hz → age_match ≤ 0.4（老年应偏低频）
- 设定 young（年轻/少年），基频均值 < 120 Hz → age_match ≤ 0.4（年轻角色基频不应过低）
- 设定 child（儿童），基频均值 < 220 Hz → age_match ≤ 0.4（儿童基频应较高）
- 基频与年龄档位一致 → 根据偏离程度打 0.6–1.0

### 3. timbre_match（音色匹配度）

评估物理特征是否体现 voice_prompt 中描述的音色特征：
- voice_prompt 描述"清亮/高亢"但基频偏低 → timbre_match ≤ 0.4
- voice_prompt 描述"低沉/沙哑/苍老"但基频偏高 → timbre_match ≤ 0.4
- voice_prompt 描述"温柔/柔和"但 RMS 过高或 pitch_std 过大 → timbre_match ≤ 0.5
- 物理特征与描述方向一致 → 根据程度打 0.6–1.0

### 4. clarity（清晰度/音频质量）

**硬性规则：**
- RMS 能量 < 0.03 → clarity ≤ 0.3（音量极低，可能含大量噪声）
- RMS 能量 < 0.05 → clarity ≤ 0.5（音量偏低）
- pitch_std > 120 Hz → clarity ≤ 0.4（基频极度不稳定，可能有机械感/噪声）
- pitch_std > 80 Hz → clarity ≤ 0.6（基频波动较大）
- 时长 < 2.0 秒 → clarity ≤ 0.5（可能截断）
- 音频质量良好 → 0.7–1.0

## 综合评分

overall_score = 0.30 * gender_match + 0.25 * age_match + 0.25 * timbre_match + 0.20 * clarity

**注意：overall_score 由公式自动计算，你也需要填写以供校验，但系统会以公式结果为准。**

## 输出格式

你必须输出一个 JSON 对象，包含以下字段：
```json
{
  "gender_match_score": 0.0~1.0,
  "age_match_score": 0.0~1.0,
  "timbre_match_score": 0.0~1.0,
  "clarity_score": 0.0~1.0,
  "overall_score": 0.0~1.0,
  "issues": ["具体问题描述1", "具体问题描述2"],
  "suggestion": "改进建议（自然语言）",
  "should_regen": true/false,
  "revised_voice_prompt": "修改后的 voice_prompt（仅 should_regen=true 时提供，否则 null）"
}
```

## 关键规则

- **严格按校准标准打分**，不要因为"听起来还行"就给 0.7+。0.4–0.6 是"部分匹配"，不是"差"。
- 性别匹配是硬门槛：gender_match_score < 0.6 时应设置 should_regen=true。
- overall_score < 0.6 时应设置 should_regen=true。
- **任一维度 ≤ 0.4 时应设置 should_regen=true**（单维度严重短板）。
- 如果建议再生成，revised_voice_prompt 应该是修改后的完整 voice_prompt，不是增量修改。
  保留原 prompt 中正确的部分，**针对性地修正有问题的描述**，加入更明确的音色指引。
  例如：原 prompt 说"清亮"但实际基频偏低，应改为"低沉浑厚"并加入基频指引。
  **注意：revised_voice_prompt 不要越来越长、越来越极端。** 每次只做最小必要修改，
  不要堆砌"必须""严禁""极度"等极端词汇——这些对 TTS 模型没有帮助，反而可能导致
  评分标准漂移。保持 prompt 简洁、自然、描述性。
- 如果不需要再生成，revised_voice_prompt 设为 null。
- **评估始终以角色档案中的 voice_prompt 为基准**，不要因为前轮尝试了不同的 revised prompt
  而提高或降低评分标准。
- issues 列表中的每个问题应该具体明确，包含数值证据，例如"性别不匹配：设定男性，但基频均值 220 Hz 落在女性区间（165-255 Hz）"。
"""


# ─────────────────────────────────────────────────────────────────────────────
# User prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _compute_mismatch_flags(
    *,
    gender: str | None,
    age_style: str | None,
    pitch_mean: float,
    pitch_std: float,
    rms: float,
    duration: float,
) -> list[str]:
    """基于硬性规则计算不匹配标注，注入 user prompt 让 LLM 无法忽视。

    Returns:
        不匹配标注列表，如 ["⚠️ 性别-基频不匹配：设定男性，基频均值 326.7 Hz 落在女性区间"]
    """
    flags: list[str] = []
    gender_lower = (gender or "").lower()

    # 性别-基频不匹配
    if gender_lower in ("male", "男", "男性"):
        if pitch_mean > 200:
            flags.append(
                f"⚠️ 性别-基频不匹配：设定男性，基频均值 {pitch_mean:.1f} Hz "
                f"超过 200 Hz，落在女性/儿童区间（女性 165-255 Hz，儿童 250-400 Hz）"
            )
        elif pitch_mean > 180:
            flags.append(
                f"⚠️ 性别-基频偏移：设定男性，基频均值 {pitch_mean:.1f} Hz "
                f"接近男性上限（180 Hz），偏女性区间"
            )
    elif gender_lower in ("female", "女", "女性"):
        if pitch_mean < 150:
            flags.append(
                f"⚠️ 性别-基频不匹配：设定女性，基频均值 {pitch_mean:.1f} Hz "
                f"低于 150 Hz，落在男性区间（85-180 Hz）"
            )
        elif pitch_mean < 165:
            flags.append(
                f"⚠️ 性别-基频偏移：设定女性，基频均值 {pitch_mean:.1f} Hz "
                f"接近女性下限（165 Hz），偏男性区间"
            )

    # 年龄-基频不匹配
    age_lower = (age_style or "").lower()
    if age_lower in ("elderly", "老年", "老", "老人"):
        if pitch_mean > 200:
            flags.append(
                f"⚠️ 年龄-基频不匹配：设定老年，基频均值 {pitch_mean:.1f} Hz "
                f"偏高（老年角色通常 85-160 Hz）"
            )
    elif age_lower in ("young", "年轻", "青年", "少年"):
        if pitch_mean < 120:
            flags.append(
                f"⚠️ 年龄-基频不匹配：设定年轻/少年，基频均值 {pitch_mean:.1f} Hz "
                f"偏低（年轻角色通常 120-250 Hz）"
            )
    elif age_lower in ("child", "儿童", "小孩", "孩子"):
        if pitch_mean < 220:
            flags.append(
                f"⚠️ 年龄-基频不匹配：设定儿童，基频均值 {pitch_mean:.1f} Hz "
                f"偏低（儿童通常 250-400 Hz）"
            )

    # 基频不稳定
    if pitch_std > 120:
        flags.append(
            f"⚠️ 基频极度不稳定：pitch_std = {pitch_std:.1f} Hz "
            f"（> 120 Hz），音频可能有机械感或噪声"
        )
    elif pitch_std > 80:
        flags.append(
            f"⚠️ 基频波动较大：pitch_std = {pitch_std:.1f} Hz "
            f"（> 80 Hz），音色稳定性存疑"
        )

    # 音量过低
    if rms < 0.03:
        flags.append(
            f"⚠️ 音量极低：RMS = {rms:.4f}（< 0.03），可能含大量噪声或录音异常"
        )
    elif rms < 0.05:
        flags.append(
            f"⚠️ 音量偏低：RMS = {rms:.4f}（< 0.05），音频可能不够清晰"
        )

    # 时长过短
    if duration < 2.0:
        flags.append(
            f"⚠️ 音频过短：时长 {duration:.2f}s（< 2.0s），可能截断"
        )

    return flags


def build_critic_user_prompt(
    *,
    speaker_name: str,
    voice_prompt: str,
    gender: str | None,
    age_style: str | None,
    audio_features: dict,
    prev_round_feedback: str | None = None,
) -> str:
    """构造 Critic 评估的 user prompt。

    Args:
        speaker_name: 角色名称。
        voice_prompt: 角色的音色描述提示词。
        gender: 角色设定的性别。
        age_style: 角色设定的年龄/风格。
        audio_features: _extract_audio_features 返回的物理特征字典。
        prev_round_feedback: 前轮评估反馈（仅再生成轮次有值）。

    Returns:
        完整的 user prompt 字符串。
    """
    gender_str = gender or "未指定"
    age_str = age_style or "未指定"

    # 格式化音频特征
    duration = audio_features.get("duration_sec", 0)
    sample_rate = audio_features.get("sample_rate", "N/A")
    channels = audio_features.get("channels", "N/A")
    rms = audio_features.get("rms_energy", 0)
    pitch_mean = audio_features.get("pitch_mean", 0)
    pitch_std = audio_features.get("pitch_std", 0)
    pitch_min = audio_features.get("pitch_min", "N/A")
    pitch_max = audio_features.get("pitch_max", "N/A")
    zcr = audio_features.get("zero_crossing_rate", "N/A")

    # 格式化数值
    def _fmt(val: object, decimals: int = 2) -> str:
        if isinstance(val, (int, float)):
            return f"{val:.{decimals}f}"
        return str(val)

    # ── 计算硬性不匹配标注 ──────────────────────────────────────
    mismatch_flags = _compute_mismatch_flags(
        gender=gender,
        age_style=age_style,
        pitch_mean=float(pitch_mean) if isinstance(pitch_mean, (int, float)) else 0,
        pitch_std=float(pitch_std) if isinstance(pitch_std, (int, float)) else 0,
        rms=float(rms) if isinstance(rms, (int, float)) else 0,
        duration=float(duration) if isinstance(duration, (int, float)) else 0,
    )

    prompt = f"""\
请严格评估以下角色音色参考音频的质量。请按照评分校准标准打分，不要因为"大体还行"就给高分。

## 角色档案

- **角色名**：{speaker_name}
- **设定性别**：{gender_str}
- **设定年龄/风格**：{age_str}
- **音色描述（voice_prompt）**：{voice_prompt}

## 音频物理特征

- **时长**：{_fmt(duration)} 秒
- **采样率**：{_fmt(sample_rate, 0)} Hz
- **声道数**：{_fmt(channels, 0)}
- **RMS 能量**：{_fmt(rms)}
- **基频均值（pitch_mean）**：{_fmt(pitch_mean)} Hz
- **基频标准差（pitch_std）**：{_fmt(pitch_std)} Hz
- **基频最小值（pitch_min）**：{_fmt(pitch_min)} Hz
- **基频最大值（pitch_max）**：{_fmt(pitch_max)} Hz
- **过零率（zero_crossing_rate）**：{_fmt(zcr)}

## 参考信息

基频与性别/年龄的典型对应关系：
- 男性成人：85-180 Hz（均值通常 100-150 Hz）
- 女性成人：165-255 Hz（均值通常 180-220 Hz）
- 儿童：250-400 Hz"""

    # ── 注入硬性不匹配标注 ──────────────────────────────────────
    if mismatch_flags:
        prompt += "\n\n## 自动检测到的异常\n\n"
        prompt += "以下异常基于物理特征与角色设定的硬性规则自动检测，**你在评分时必须考虑这些异常**：\n\n"
        for flag in mismatch_flags:
            prompt += f"- {flag}\n"

    # ── 注入前轮评估反馈（仅再生成轮次）────────────────────────
    if prev_round_feedback:
        prompt += f"\n\n## 前轮评估反馈\n\n{prev_round_feedback}\n"
        prompt += "请重点关注前轮指出的问题，评估修订后的 voice_prompt 是否改善了音色匹配度。\n"

    prompt += "\n请根据以上信息，严格按照评分校准标准输出评估 JSON。"
    return prompt