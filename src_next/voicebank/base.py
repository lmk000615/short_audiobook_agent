"""src_next/voicebank/base.py

统一 voicebank adapter 接口。

voicebank 层负责：speaker / character → voice_ref（音色参考）。
voicebank 层不负责：正文 TTS 合成（那是 tts/ 的事）。

所有 voicebank 后端（Mock / QwenVoiceGenerator / 未来 IndexTTS / FishPro / CosyVoice）
都要实现 BaseVoicebankAdapter。core 层只依赖这个接口，不直接 import 具体后端。
具体使用哪个后端由 registry + profile 决定。
"""

from abc import ABC, abstractmethod
from typing import Any

from src_next.core.data_models import CharacterProfile, VoicebankResult


class VoicebankError(Exception):
    """voicebank 调用失败的统一异常。

    所有 BaseVoicebankAdapter 实现都应把底层错误（模型缺失、脚本失败、配置不合法、
    subprocess 超时等）包装成 VoicebankError 抛出。这样上层只需要 catch 一种异常。
    """


class BaseVoicebankAdapter(ABC):
    """所有 voicebank 后端的统一接口。

    只暴露一个方法：
        prepare_voicebank(characters, output_dir, **kwargs) -> VoicebankResult

    * 输入：list[CharacterProfile]（由 analysis 层产生）。
    * 输出：VoicebankResult，核心字段是 speaker_to_voice（speaker 名 → voice_ref 路径）。
    * voice_ref 的具体含义由后端决定：
        - mock：'mock://<name>' 占位字符串；
        - qwen_voicegenerator：.wav 文件路径；
        - 未来 cosyvoice：可能是 embedding id 或 path；
        - 未来 indextts：可能是 .wav 或 .npz 路径。

    后端选择由 profiles/ 配置 + registry.create_voicebank_adapter 决定。
    """

    @abstractmethod
    def prepare_voicebank(
        self,
        characters: list[CharacterProfile],
        output_dir: str,
        **kwargs: Any,
    ) -> VoicebankResult:
        """为每个角色准备 voice reference，返回 speaker → voice_ref 映射。

        Args:
            characters: 角色档案列表（含 narrator + 各角色）。
            output_dir: 本次 pipeline 的输出根目录；后端可在其下创建子目录。
            **kwargs: 后端特定参数（如 dry_run / 超时 / 重试次数）。

        Returns:
            VoicebankResult，关键字段 speaker_to_voice 必须覆盖所有 characters。
            失败时 success=False（具体含义见各后端实现）。
        """
