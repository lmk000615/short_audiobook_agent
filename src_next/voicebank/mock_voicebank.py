"""src_next/voicebank/mock_voicebank.py

离线 Mock voicebank 实现。

不调用真实模型、不访问网络、不依赖 GPU。
为每个 character 生成 `mock://<name>` 占位 voice_ref，用于：
* 无模型 / 无 GPU 环境下验证 core pipeline 数据流；
* 单元测试替换真实 voicebank；
* CI 环境避免外部依赖。
"""

from typing import Any

from src_next.core.data_models import CharacterProfile, VoicebankResult

from .base import BaseVoicebankAdapter


class MockVoicebankAdapter(BaseVoicebankAdapter):
    """无模型 / 无网络 / 无 GPU 的 Mock 实现。"""

    def prepare_voicebank(
        self,
        characters: list[CharacterProfile],
        output_dir: str,
        **kwargs: Any,
    ) -> VoicebankResult:
        # voice_ref 用 mock:// scheme，明显区别于真实文件路径，
        # 避免下游 tts 层误以为这是真实 wav。
        speaker_to_voice = {c.name: f"mock://{c.name}" for c in characters}
        return VoicebankResult(
            speaker_to_voice=speaker_to_voice,
            voicebank_dir=None,  # mock 不写盘
            backend="mock",
            success=True,
        )
