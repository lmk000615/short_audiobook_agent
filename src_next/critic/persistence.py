"""Critic/Repair 产物持久化。

把一次评估的 scoring JSON + repair JSON + 输入音频副本归档到
<output_root>/critic/<audio_stem>/ 下，方便事后回看与调试。

设计选择：
- 独立 helper，不耦合 Qwen3OmniCritic.evaluate() / TTSRepairAgent.repair()
- 默认输出根目录 = 项目根 / output（可通过 output_root 参数覆盖）
- 同名音频重评覆盖既有文件（不版本化；attempt 字段在 JSON 内体现）
- repair.json 仅当传入 repair_result 时才写

save_long_audio_critic_session() 是对称的长音频版本：归档到
<output_root>/critic/long_audio/<audio_stem>/ 下。

save_attribute_critic_session() 是属性感知版本的归档函数：归档到
<output_root>/critic/<audio_stem>/（与 save_critic_session 同目录），
scoring.json 内嵌 extracted/expected/consistency 三段。
"""
from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from src_next.core.data_models import (
    CriticResult,
    LongAudioCriticResult,
    ModelSpecificTTSInstruction,
)
from src_next.critic.attribute_result import AttributeAwareCriticResult
from src_next.utils.file_utils import save_json_file


def _default_output_root() -> Path:
    """项目根的 output/ 目录。

    persistence.py 位于 src_next/critic/persistence.py，上溯 3 层 =
    parents[0]=critic/ → parents[1]=src_next/ → parents[2]=项目根。
    """
    return Path(__file__).resolve().parents[2] / "output"


def save_critic_session(
    audio_path: str | Path,
    critic_result: CriticResult,
    repair_result: ModelSpecificTTSInstruction | None = None,
    output_root: str | Path | None = None,
) -> Path:
    """把一次 critic 评估（可选 + repair）的产物落盘到 output/critic/<audio_stem>/。

    Args:
        audio_path: 被评估的音频文件路径。必须存在（evaluate 已读过它做 base64）。
        critic_result: Qwen3OmniCritic.evaluate() 的返回值。
        repair_result: TTSRepairAgent.repair() 的返回值；None 表示未触发修复。
        output_root: 输出根目录；None 时默认项目根的 output/。

    Returns:
        实际写入的文件夹路径（<output_root>/critic/<audio_stem>/）。

    写入文件:
        - scoring.json  ← CriticResult 序列化（dataclasses.asdict）
        - repair.json   ← ModelSpecificTTSInstruction 序列化（仅当 repair_result 非 None）
        - <audio_filename>  ← 输入音频的副本（保留原文件名与扩展名）

    同名音频重评时覆盖既有文件（不版本化）。
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    root = Path(output_root) if output_root is not None else _default_output_root()
    folder = root / "critic" / audio_path.stem
    folder.mkdir(parents=True, exist_ok=True)

    save_json_file(dataclasses.asdict(critic_result), folder / "scoring.json")

    if repair_result is not None:
        save_json_file(dataclasses.asdict(repair_result), folder / "repair.json")

    shutil.copy2(audio_path, folder / audio_path.name)

    return folder


def save_long_audio_critic_session(
    audio_path: str | Path,
    result: LongAudioCriticResult,
    output_root: str | Path | None = None,
) -> Path:
    """把一次长音频 critic 评估的产物落盘到 <output_root>/critic/long_audio/<audio_stem>/。

    与 save_critic_session 对称，但目录多嵌套一层 long_audio/，避免和分段 critic
    产物混在一起。

    Args:
        audio_path: 被评估的音频文件路径。必须存在。
        result: Qwen3OmniLongAudioCritic.evaluate() 的返回值。
        output_root: 输出根目录；None 时默认项目根的 output/。

    Returns:
        实际写入的文件夹路径（<output_root>/critic/long_audio/<audio_stem>/）。

    写入文件:
        - scoring.json   ← LongAudioCriticResult 序列化（dataclasses.asdict，含 segment_details 内嵌）
        - <audio_filename>  ← 输入音频的副本（保留原文件名与扩展名）

    同名音频重评时覆盖既有文件（不版本化）。
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    root = Path(output_root) if output_root is not None else _default_output_root()
    folder = root / "critic" / "long_audio" / audio_path.stem
    folder.mkdir(parents=True, exist_ok=True)

    save_json_file(dataclasses.asdict(result), folder / "scoring.json")
    shutil.copy2(audio_path, folder / audio_path.name)

    return folder


def save_attribute_critic_session(
    audio_path: str | Path,
    result: AttributeAwareCriticResult,
    repair_result: ModelSpecificTTSInstruction | None = None,
    output_root: str | Path | None = None,
) -> Path:
    """把一次属性感知 critic 评估的产物落盘到 output/critic/<audio_stem>/。

    与 ``save_critic_session`` 落盘目录相同（同一段音频只会用一种 critic 评估，
    不会冲突）；scoring.json 内嵌 extracted_attributes / expected_attributes /
    attribute_consistency 三段（通过 ``dataclasses.asdict`` 自动展开）。

    Args:
        audio_path: 被评估的音频文件路径。必须存在。
        result: ``AttributeAwareQwen3OmniCritic.evaluate()`` 的返回值。
        repair_result: 可选的 ``TTSRepairAgent.repair()`` 返回值（注意：repair
            接收的是 ``CriticResult``，调用方需先 ``result.to_critic_result()``
            转换后再传给 repair，再把 repair 返回值传到这里）。None 表示未触发修复。
        output_root: 输出根目录；None 时默认项目根的 output/。

    Returns:
        实际写入的文件夹路径（<output_root>/critic/<audio_stem>/）。

    写入文件:
        - scoring.json  ← AttributeAwareCriticResult 序列化（含三段属性数据）
        - repair.json   ← ModelSpecificTTSInstruction 序列化（仅当 repair_result 非 None）
        - <audio_filename>  ← 输入音频的副本

    同名音频重评时覆盖既有文件（不版本化）。
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    root = Path(output_root) if output_root is not None else _default_output_root()
    folder = root / "critic" / audio_path.stem
    folder.mkdir(parents=True, exist_ok=True)

    save_json_file(dataclasses.asdict(result), folder / "scoring.json")

    if repair_result is not None:
        save_json_file(dataclasses.asdict(repair_result), folder / "repair.json")

    shutil.copy2(audio_path, folder / audio_path.name)

    return folder
