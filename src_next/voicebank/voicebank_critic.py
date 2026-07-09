"""src_next/voicebank/voicebank_critic.py

Voicebank Critic：对 Stage 6 voicebank 生成的角色音色参考 wav 进行质量评估。

核心流程：
    1. 对每个 speaker 的 wav 提取物理特征（基频、RMS、时长等）
    2. 将物理特征 + 角色档案传给 LLM 做四维评分
    3. 评分低于阈值 → 用 revised_voice_prompt 再生成
    4. 再生成后重新评估，最多 max_retries 轮

设计原则：
    - 低耦合：Critic 不是独立 stage，而是 Stage 6 的后置子步骤
    - 默认关闭：pipeline.voicebank_critic.enabled 默认 false
    - 失败降级：任何异常都不阻塞 pipeline
    - 下游无感：Critic 就地更新 voicebank_result.speaker_to_voice，下游 TTS 不感知
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from src_next.core.data_models import (
    CharacterProfile,
    SpeakerCriticResult,
    VoicebankCriticResult,
    VoicebankResult,
)
from src_next.llm.base import BaseLLMClient, LLMError

from .base import BaseVoicebankAdapter, VoicebankError
from .voicebank_critic_prompt import CRITIC_SYSTEM_PROMPT, build_critic_user_prompt

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 物理特征提取
# ─────────────────────────────────────────────────────────────────────────────

def _extract_audio_features(wav_path: str) -> dict[str, Any]:
    """提取 wav 的物理特征供 LLM 评估。

    使用 soundfile 读取音频，numpy 计算统计量。

    Returns:
        字典，含以下键：
        - duration_sec: 时长（秒）
        - sample_rate: 采样率
        - channels: 声道数
        - rms_energy: RMS 能量
        - pitch_mean: 基频均值 (Hz)
        - pitch_std: 基频标准差 (Hz)
        - pitch_min: 基频最小值 (Hz)
        - pitch_max: 基频最大值 (Hz)
        - zero_crossing_rate: 过零率

    Raises:
        Exception: 文件不存在或格式错误时抛出，由调用方 catch。
    """
    data, sr = sf.read(wav_path, dtype="float32")

    # 如果是多声道，取第一声道
    if data.ndim > 1:
        data = data[:, 0]

    n_samples = len(data)
    duration = n_samples / sr if sr > 0 else 0.0

    # RMS 能量
    rms = float(np.sqrt(np.mean(data ** 2))) if n_samples > 0 else 0.0

    # 过零率
    if n_samples > 1:
        signs = np.sign(data)
        zcr = float(np.sum(np.abs(np.diff(signs)) > 0) / (n_samples - 1))
    else:
        zcr = 0.0

    # 基频估计（自相关法，简单但足够用于性别/年龄判断）
    pitch_mean, pitch_std, pitch_min, pitch_max = _estimate_pitch_stats(data, sr)

    return {
        "duration_sec": round(duration, 3),
        "sample_rate": sr,
        "channels": 1 if data.ndim == 1 else data.shape[1],
        "rms_energy": round(rms, 6),
        "pitch_mean": round(pitch_mean, 1) if pitch_mean > 0 else 0.0,
        "pitch_std": round(pitch_std, 1) if pitch_std > 0 else 0.0,
        "pitch_min": round(pitch_min, 1) if pitch_min > 0 else 0.0,
        "pitch_max": round(pitch_max, 1) if pitch_max > 0 else 0.0,
        "zero_crossing_rate": round(zcr, 6),
    }


def _estimate_pitch_stats(
    data: np.ndarray,
    sr: int,
    *,
    fmin: float = 50.0,
    fmax: float = 500.0,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> tuple[float, float, float, float]:
    """用自相关法估计基频统计量。

    Args:
        data: 单声道 float32 音频数据。
        sr: 采样率。
        fmin: 最低基频 (Hz)。
        fmax: 最高基频 (Hz)。
        frame_length: 帧长（采样点数）。
        hop_length: 帧移（采样点数）。

    Returns:
        (pitch_mean, pitch_std, pitch_min, pitch_max)。
        无法检测基频时返回 (0.0, 0.0, 0.0, 0.0)。
    """
    lag_min = max(1, int(sr / fmax))
    lag_max = min(frame_length, int(sr / fmin))

    if lag_max <= lag_min or len(data) < frame_length:
        return 0.0, 0.0, 0.0, 0.0

    pitches: list[float] = []
    for start in range(0, len(data) - frame_length + 1, hop_length):
        frame = data[start : start + frame_length]
        # 去均值
        frame = frame - np.mean(frame)
        frame_rms = np.sqrt(np.mean(frame ** 2))
        if frame_rms < 1e-4:
            continue  # 静音帧跳过

        # 自相关
        corr = np.correlate(frame, frame, mode="full")
        corr = corr[len(corr) // 2 :]  # 取正半部分

        # 在 [lag_min, lag_max] 范围找峰值
        search = corr[lag_min:lag_max]
        if len(search) == 0:
            continue
        peak_idx = np.argmax(search) + lag_min
        if corr[peak_idx] > 0.2 * corr[0]:  # 峰值需足够显著
            pitch = sr / peak_idx
            if fmin <= pitch <= fmax:
                pitches.append(pitch)

    if not pitches:
        return 0.0, 0.0, 0.0, 0.0

    arr = np.array(pitches)
    return (
        float(np.mean(arr)),
        float(np.std(arr)),
        float(np.min(arr)),
        float(np.max(arr)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 再生成音频变化检测
# ─────────────────────────────────────────────────────────────────────────────

def _wav_features_unchanged(
    prev: dict[str, Any],
    curr: dict[str, Any],
    *,
    pitch_tolerance: float = 5.0,
    rms_tolerance: float = 0.005,
    duration_tolerance: float = 0.1,
) -> bool:
    """判断再生成后音频物理特征是否有实质变化。

    当 voicebank adapter 缓存命中或 TTS 模型对 prompt 变化不敏感时，
    再生成可能产出与之前完全相同或几乎相同的 wav。
    此时继续重试无意义，应提前终止。

    Args:
        prev: 前一轮的音频特征字典。
        curr: 当前轮的音频特征字典。
        pitch_tolerance: 基频均值允许偏差 (Hz)。
        rms_tolerance: RMS 能量允许偏差。
        duration_tolerance: 时长允许偏差 (秒)。

    Returns:
        True 表示特征无实质变化（应停止重试）。
    """
    # 比较关键特征：基频均值、RMS、时长
    pitch_diff = abs(prev.get("pitch_mean", 0) - curr.get("pitch_mean", 0))
    rms_diff = abs(prev.get("rms_energy", 0) - curr.get("rms_energy", 0))
    dur_diff = abs(prev.get("duration_sec", 0) - curr.get("duration_sec", 0))

    return pitch_diff <= pitch_tolerance and rms_diff <= rms_tolerance and dur_diff <= duration_tolerance


# ─────────────────────────────────────────────────────────────────────────────
# 逐角色日志格式化
# ─────────────────────────────────────────────────────────────────────────────

def _format_critic_log_line(result: SpeakerCriticResult) -> str:
    """将单角色评估结果格式化为一行可读日志。

    格式示例::

        小红帽  G=0.85 A=0.72 T=0.68 C=0.91 → 0.78  PASS
        大灰狼  G=0.35 A=0.60 T=0.55 C=0.80 → 0.54  REGEN(#1)
        旁白    G=0.50 A=0.50 T=0.50 C=0.50 → 0.50  SKIP

    Args:
        result: 单角色评估结果。

    Returns:
        单行格式化字符串。
    """
    name = result.speaker
    g = result.gender_match_score
    a = result.age_match_score
    t = result.timbre_match_score
    c = result.clarity_score
    o = result.overall_score

    if not result.issues and o == 0.5 and not result.should_regen:
        # 中性评分（评估失败降级）
        verdict = "SKIP"
    elif result.should_regen:
        verdict = f"REGEN(#{result.round_index + 1})"
    else:
        verdict = "PASS"

    return f"  {name:<8s} G={g:.2f} A={a:.2f} T={t:.2f} C={c:.2f} => {o:.2f}  {verdict}"


def _format_critic_summary(result: VoicebankCriticResult) -> str:
    """将 Critic 整体结果格式化为摘要行。

    格式示例::

        4 speakers: 2 PASS, 1 regen(1 improved), 1 below threshold
    """
    if not result.speaker_results:
        return "no speakers evaluated"

    # 按 speaker 取最终轮结果
    by_speaker: dict[str, SpeakerCriticResult] = {}
    for r in result.speaker_results:
        by_speaker[r.speaker] = r  # 后出现的覆盖前面的，即最后一轮

    n_pass = sum(1 for r in by_speaker.values() if not r.should_regen)
    n_regen = result.speakers_regen
    n_improved = result.speakers_improved
    n_below = sum(
        1 for r in by_speaker.values()
        if r.should_regen
    )

    parts = [f"{len(by_speaker)} speakers"]
    parts.append(f"{n_pass} PASS")
    if n_regen > 0:
        parts.append(f"{n_regen} regen({n_improved} improved)")
    if n_below > 0:
        parts.append(f"{n_below} still below threshold")
    return ", ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 评分判断
# ─────────────────────────────────────────────────────────────────────────────

def _should_regen(
    result: SpeakerCriticResult,
    *,
    score_threshold: float = 0.6,
    gender_threshold: float = 0.7,
) -> bool:
    """判断是否需要再生成（多维度分级触发）。

    触发条件（任一满足即触发）：
    1. overall_score < score_threshold
    2. gender_match_score < gender_threshold
    3. 任一维度 ≤ 0.4（单维度严重短板）
    4. 两个及以上维度 < 0.6（多维度偏差叠加）

    Args:
        result: 单角色评估结果。
        score_threshold: overall_score 低于此值触发再生成。
        gender_threshold: gender_match_score 低于此值强制触发再生成。

    Returns:
        True 表示需要再生成。
    """
    # 1. overall 过低
    if result.overall_score < score_threshold:
        return True
    # 2. 性别严重不匹配
    if result.gender_match_score < gender_threshold:
        return True
    # 3. 任一维度严重短板
    dim_scores = [
        result.gender_match_score,
        result.age_match_score,
        result.timbre_match_score,
        result.clarity_score,
    ]
    if min(dim_scores) <= 0.4:
        return True
    # 4. 多维度偏差叠加
    if sum(1 for s in dim_scores if s < 0.6) >= 2:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# LLM 评估结果解析
# ─────────────────────────────────────────────────────────────────────────────

def _parse_critic_json(
    raw: dict | list,
    speaker: str,
    wav_path: str,
    round_index: int,
) -> SpeakerCriticResult:
    """从 LLM 返回的 JSON dict 构造 SpeakerCriticResult。

    自动做：
    - 4 维分数 clamp 到 [0.0, 1.0]
    - 缺失维度补 0.5（中性分）
    - overall_score 自动计算
    - should_regen 根据 _should_regen 逻辑判断
    """
    if not isinstance(raw, dict):
        raw = {}

    def _get_score(key: str) -> float:
        try:
            v = float(raw.get(key, 0.5))
        except (TypeError, ValueError):
            v = 0.5
        return max(0.0, min(1.0, v))

    gender_match = _get_score("gender_match_score")
    age_match = _get_score("age_match_score")
    timbre_match = _get_score("timbre_match_score")
    clarity = _get_score("clarity_score")
    overall = 0.30 * gender_match + 0.25 * age_match + 0.25 * timbre_match + 0.20 * clarity

    issues = raw.get("issues", [])
    if not isinstance(issues, list):
        issues = [str(issues)]

    suggestion = str(raw.get("suggestion", ""))

    revised_prompt = raw.get("revised_voice_prompt")
    if revised_prompt is not None:
        revised_prompt = str(revised_prompt).strip() or None

    # 先构造不带 should_regen 的临时结果，再用 _should_regen 判断
    temp = SpeakerCriticResult(
        speaker=speaker,
        overall_score=overall,
        gender_match_score=gender_match,
        age_match_score=age_match,
        timbre_match_score=timbre_match,
        clarity_score=clarity,
        issues=issues,
        suggestion=suggestion,
        should_regen=False,  # 临时，下面覆盖
        revised_voice_prompt=revised_prompt,
        wav_path=wav_path,
        round_index=round_index,
    )
    temp.should_regen = _should_regen(temp)
    return temp


# ─────────────────────────────────────────────────────────────────────────────
# VoicebankCritic 主类
# ─────────────────────────────────────────────────────────────────────────────

class VoicebankCritic:
    """Voicebank Critic：评估 voicebank 产物质量，必要时触发再生成。

    用法::

        critic = VoicebankCritic(
            llm_client=llm_client,
            vb_adapter=vb_adapter,
            score_threshold=0.5,
            gender_threshold=0.6,
            max_retries=2,
        )
        result = critic.evaluate(
            characters=characters,
            voicebank_result=voicebank_result,
            output_dir=str(output_dir),
        )
        # result 是 VoicebankCriticResult
        # voicebank_result.speaker_to_voice 已就地更新
    """

    def __init__(
        self,
        *,
        llm_client: BaseLLMClient,
        vb_adapter: BaseVoicebankAdapter,
        score_threshold: float = 0.5,
        gender_threshold: float = 0.6,
        max_retries: int = 2,
    ) -> None:
        self.llm_client = llm_client
        self.vb_adapter = vb_adapter
        self.score_threshold = score_threshold
        self.gender_threshold = gender_threshold
        self.max_retries = max(0, max_retries)

    def evaluate(
        self,
        *,
        characters: list[CharacterProfile],
        voicebank_result: VoicebankResult,
        output_dir: str,
    ) -> VoicebankCriticResult:
        """评估所有 speaker 的音色参考，必要时再生成。

        Args:
            characters: 角色档案列表。
            voicebank_result: Stage 6a 的产物（会被就地更新）。
            output_dir: pipeline 输出目录。

        Returns:
            VoicebankCriticResult，含每个角色的最终评估和再生成历史。
        """
        speaker_results: list[SpeakerCriticResult] = []
        regen_history: list[dict] = []
        total_rounds = 0
        speakers_regen = 0
        speakers_improved = 0

        # 构建 name → CharacterProfile 映射
        char_map: dict[str, CharacterProfile] = {c.name: c for c in characters}

        # ── Critic 逐角色日志收集（用于终端输出 + critic.log）─────
        critic_log_lines: list[str] = []

        for speaker, wav_path in voicebank_result.speaker_to_voice.items():
            char = char_map.get(speaker)
            if not char:
                logger.warning("voicebank_critic: speaker %r 不在 characters 中，跳过", speaker)
                continue

            # 检查 wav 是否是真实文件（mock 模式下是占位字符串）
            if not Path(wav_path).exists():
                logger.info(
                    "voicebank_critic: speaker %r 的 wav 不存在 (%s)，跳过评估",
                    speaker, wav_path,
                )
                skip_result = SpeakerCriticResult(
                    speaker=speaker,
                    wav_path=wav_path,
                    round_index=0,
                    suggestion="wav 文件不存在，跳过评估",
                )
                speaker_results.append(skip_result)
                critic_log_lines.append(_format_critic_log_line(skip_result))
                continue

            # ── 首次评估 ────────────────────────────────────────────
            prev_score = -1.0
            current_result: SpeakerCriticResult | None = None
            prev_result_for_feedback: SpeakerCriticResult | None = None
            current_char = char
            # 保留原始 voice_prompt，始终用它做评估基准（避免目标漂移）
            eval_char = char
            did_regen = False
            prev_wav_features: dict | None = None

            for round_idx in range(self.max_retries + 1):
                total_rounds += 1

                # 提取当前 wav 的物理特征（用于"无变化"检测）
                try:
                    current_features = _extract_audio_features(wav_path)
                except Exception:
                    current_features = None

                # 检测再生成后 wav 是否有实质变化
                if round_idx > 0 and prev_wav_features is not None and current_features is not None:
                    if _wav_features_unchanged(prev_wav_features, current_features):
                        logger.warning(
                            "voicebank_critic: %s 再生成后音频特征无变化，"
                            "模型无法通过 prompt 调整此音频，停止重试",
                            speaker,
                        )
                        break

                prev_wav_features = current_features

                # 始终用原始 voice_prompt 评估（避免 revised_prompt 越来越严格导致分数下降）
                current_result = self._evaluate_speaker(
                    character=eval_char,
                    wav_path=wav_path,
                    round_index=round_idx,
                    prev_result=prev_result_for_feedback,
                )
                speaker_results.append(current_result)
                prev_result_for_feedback = current_result  # 供下一轮反馈用
                # ── 逐角色日志输出 ──────────────────────────────────
                log_line = _format_critic_log_line(current_result)
                logger.info("voicebank_critic: %s", log_line.strip())
                critic_log_lines.append(log_line)

                if not current_result.should_regen:
                    # 通过评估，不需要再生成
                    break

                if round_idx >= self.max_retries:
                    # 已达最大重试次数，保留当前 wav
                    logger.warning(
                        "voicebank_critic: %s 评分仍不达标 (score=%.2f)，"
                        "已达 max_retries=%d，保留当前 wav",
                        speaker, current_result.overall_score, self.max_retries,
                    )
                    break

                # ── 触发再生成 ─────────────────────────────────────
                did_regen = True
                speakers_regen += 1
                revised_prompt = current_result.revised_voice_prompt or current_char.voice_prompt

                logger.info(
                    "voicebank_critic: %s score=%.2f (gender=%.2f) → regen round %d",
                    speaker, current_result.overall_score,
                    current_result.gender_match_score, round_idx + 1,
                )

                regen_record = {
                    "speaker": speaker,
                    "round_index": round_idx,
                    "original_score": current_result.overall_score,
                    "original_gender_score": current_result.gender_match_score,
                    "original_voice_prompt": current_char.voice_prompt,
                    "revised_voice_prompt": revised_prompt,
                }

                # 用修订后的 prompt 构造新的 CharacterProfile（仅用于再生成）
                regen_char = CharacterProfile(
                    name=current_char.name,
                    role_type=current_char.role_type,
                    gender=current_char.gender,
                    age_style=current_char.age_style,
                    personality=current_char.personality,
                    voice_prompt=revised_prompt,
                    confidence=current_char.confidence,
                    aliases=current_char.aliases,
                )

                # 单角色再生成
                try:
                    # 删除旧 wav，避免 adapter 缓存跳过
                    old_wav_path = Path(wav_path)
                    if old_wav_path.exists():
                        old_wav_path.unlink()
                        logger.info(
                            "voicebank_critic: deleted old wav %s for regen",
                            old_wav_path,
                        )

                    regen_result = self.vb_adapter.prepare_voicebank(
                        [regen_char], output_dir,
                    )
                    if regen_result.success and speaker in regen_result.speaker_to_voice:
                        new_wav = regen_result.speaker_to_voice[speaker]
                        # 就地更新 voicebank_result
                        voicebank_result.speaker_to_voice[speaker] = new_wav
                        wav_path = new_wav
                        current_char = regen_char
                        # 注意：eval_char 保持不变（原始 voice_prompt），
                        # current_char 更新为 regen_char（用于下一轮的 prev_result 反馈）
                    else:
                        logger.warning(
                            "voicebank_critic: %s 再生成失败，保留原 wav",
                            speaker,
                        )
                        regen_record["regen_error"] = "adapter 返回 success=False 或 speaker 不在结果中"
                        regen_history.append(regen_record)
                        break
                except (VoicebankError, Exception) as err:
                    logger.warning(
                        "voicebank_critic: %s 再生成异常: %s，保留原 wav",
                        speaker, err,
                    )
                    regen_record["regen_error"] = f"{type(err).__name__}: {err}"
                    regen_history.append(regen_record)
                    break

                regen_record["new_wav_path"] = wav_path
                regen_history.append(regen_record)

            # 检查再生成后是否提升
            if current_result is not None and did_regen:
                if current_result.overall_score > prev_score if prev_score >= 0 else True:
                    speakers_improved += 1

            # 记录首次评估分数（用于 speakers_improved 判断）
            if did_regen and current_result is not None:
                first_result = next(
                    (r for r in speaker_results if r.speaker == speaker and r.round_index == 0),
                    None,
                )
                last_result = next(
                    (r for r in reversed(speaker_results) if r.speaker == speaker),
                    None,
                )
                if first_result and last_result and last_result.overall_score > first_result.overall_score:
                    speakers_improved += 1

        # 修正 speakers_improved 计数（上面逻辑可能重复计数，重新算）
        speakers_improved = self._count_improved(speaker_results)

        critic_result = VoicebankCriticResult(
            speaker_results=speaker_results,
            regen_history=regen_history,
            enabled=True,
            total_rounds=total_rounds,
            speakers_regen=speakers_regen,
            speakers_improved=speakers_improved,
        )

        # ── 保存 critic.log 到 voicebank 目录 ──────────────────────
        try:
            vb_dir = Path(output_dir) / "voicebank"
            vb_dir.mkdir(parents=True, exist_ok=True)
            log_path = vb_dir / "critic.log"
            summary = _format_critic_summary(critic_result)
            log_content = "Voicebank Critic Evaluation Log\n"
            log_content += "=" * 50 + "\n"
            log_content += f"Summary: {summary}\n"
            log_content += "-" * 50 + "\n"
            for line in critic_log_lines:
                log_content += line + "\n"
            log_path.write_text(log_content, encoding="utf-8")
            logger.info("voicebank_critic: log saved to %s", log_path)
        except Exception as err:
            logger.warning("voicebank_critic: failed to save critic.log: %s", err)

        return critic_result

    def _evaluate_speaker(
        self,
        *,
        character: CharacterProfile,
        wav_path: str,
        round_index: int,
        prev_result: SpeakerCriticResult | None = None,
    ) -> SpeakerCriticResult:
        """评估单个 speaker 的音色参考。

        Args:
            character: 角色档案。
            wav_path: 当前评估的 wav 路径。
            round_index: 第几轮评估（0=首次）。
            prev_result: 前一轮的评估结果（仅再生成轮次有值，用于构造反馈）。

        Returns:
            SpeakerCriticResult。评估失败时返回中性评分（不触发再生成）。
        """
        # 1. 提取物理特征
        try:
            features = _extract_audio_features(wav_path)
        except Exception as err:
            logger.warning(
                "voicebank_critic: %s 物理特征提取失败: %s，使用中性评分",
                character.name, err,
            )
            return SpeakerCriticResult(
                speaker=character.name,
                overall_score=0.5,
                gender_match_score=0.5,
                age_match_score=0.5,
                timbre_match_score=0.5,
                clarity_score=0.5,
                issues=[f"物理特征提取失败: {err}"],
                suggestion="无法评估，保留当前 wav",
                should_regen=False,
                wav_path=wav_path,
                round_index=round_index,
            )

        # 2. 构造前轮反馈（仅再生成轮次）
        prev_feedback: str | None = None
        if prev_result is not None:
            feedback_lines = [
                f"上一轮评估结果（round #{prev_result.round_index}）：",
                f"- gender_match = {prev_result.gender_match_score:.2f}",
                f"- age_match = {prev_result.age_match_score:.2f}",
                f"- timbre_match = {prev_result.timbre_match_score:.2f}",
                f"- clarity = {prev_result.clarity_score:.2f}",
                f"- overall = {prev_result.overall_score:.2f}",
            ]
            if prev_result.issues:
                feedback_lines.append("- 问题：" + "；".join(prev_result.issues))
            if prev_result.suggestion:
                feedback_lines.append(f"- 建议：{prev_result.suggestion}")
            if prev_result.revised_voice_prompt:
                feedback_lines.append(
                    f"- 上一轮用于再生成的 revised_voice_prompt：{prev_result.revised_voice_prompt}"
                )
            feedback_lines.append(
                f"\n注意：评估基准始终是原始 voice_prompt：{character.voice_prompt}"
            )
            prev_feedback = "\n".join(feedback_lines)

        # 3. 构造 prompt 并调用 LLM
        user_prompt = build_critic_user_prompt(
            speaker_name=character.name,
            voice_prompt=character.voice_prompt,
            gender=character.gender,
            age_style=character.age_style,
            audio_features=features,
            prev_round_feedback=prev_feedback,
        )

        try:
            raw_json = self.llm_client.generate_json(
                user_prompt,
                system_prompt=CRITIC_SYSTEM_PROMPT,
                temperature=0.3,
            )
        except LLMError as err:
            logger.warning(
                "voicebank_critic: %s LLM 评估失败: %s，使用中性评分",
                character.name, err,
            )
            return SpeakerCriticResult(
                speaker=character.name,
                overall_score=0.5,
                gender_match_score=0.5,
                age_match_score=0.5,
                timbre_match_score=0.5,
                clarity_score=0.5,
                issues=[f"LLM 评估失败: {err}"],
                suggestion="无法评估，保留当前 wav",
                should_regen=False,
                wav_path=wav_path,
                round_index=round_index,
            )

        # 4. 解析结果
        return _parse_critic_json(raw_json, character.name, wav_path, round_index)

    @staticmethod
    def _count_improved(speaker_results: list[SpeakerCriticResult]) -> int:
        """统计再生成后评分提升的角色数。"""
        # 按 speaker 分组，取首轮和末轮评分
        by_speaker: dict[str, list[SpeakerCriticResult]] = {}
        for r in speaker_results:
            by_speaker.setdefault(r.speaker, []).append(r)

        count = 0
        for results in by_speaker.values():
            if len(results) < 2:
                continue  # 没有再生成过
            first = min(results, key=lambda r: r.round_index)
            last = max(results, key=lambda r: r.round_index)
            if last.overall_score > first.overall_score:
                count += 1
        return count


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数：供 pipeline 调用
# ─────────────────────────────────────────────────────────────────────────────

def run_voicebank_critic(
    *,
    characters: list[CharacterProfile],
    voicebank_result: VoicebankResult,
    llm_client: BaseLLMClient,
    vb_adapter: BaseVoicebankAdapter,
    output_dir: str,
    critic_config: dict[str, Any] | None = None,
) -> VoicebankCriticResult:
    """运行 Voicebank Critic（供 pipeline 调用的入口函数）。

    此函数是 pipeline 集成点。Critic 配置来自 profile 的
    pipeline.voicebank_critic 块。enabled=false 时直接返回空结果。

    Args:
        characters: 角色档案列表。
        voicebank_result: Stage 6a 的产物（会被就地更新）。
        llm_client: LLM 客户端。
        vb_adapter: voicebank adapter（用于再生成）。
        output_dir: pipeline 输出目录。
        critic_config: profile 中 pipeline.voicebank_critic 的配置字典。

    Returns:
        VoicebankCriticResult。
    """
    cfg = critic_config or {}
    enabled = bool(cfg.get("enabled", False))

    if not enabled:
        return VoicebankCriticResult(enabled=False)

    score_threshold = float(cfg.get("score_threshold", 0.5))
    gender_threshold = float(cfg.get("gender_threshold", 0.6))
    max_retries = int(cfg.get("max_retries", 2))

    critic = VoicebankCritic(
        llm_client=llm_client,
        vb_adapter=vb_adapter,
        score_threshold=score_threshold,
        gender_threshold=gender_threshold,
        max_retries=max_retries,
    )

    try:
        result = critic.evaluate(
            characters=characters,
            voicebank_result=voicebank_result,
            output_dir=output_dir,
        )
    except Exception as err:
        # 整体异常降级：保留原 voicebank_result
        logger.error("voicebank_critic: 整体异常: %s，降级保留原 voicebank_result", err)
        return VoicebankCriticResult(
            enabled=True,
            regen_history=[{"error": f"Critic 整体异常: {type(err).__name__}: {err}"}],
        )

    return result