"""src_next.voicebank

voicebank adapter 层。统一接口见 base.py。

这里保持轻量，只暴露最基础的接口类型。
具体后端请显式从对应模块导入：

    from src_next.voicebank.mock_voicebank import MockVoicebankAdapter
    from src_next.voicebank.qwen_voicegenerator import QwenVoiceGeneratorAdapter

或者用工厂：

    from src_next.voicebank.registry import create_voicebank_adapter
    adapter = create_voicebank_adapter("qwen_voicegenerator", generator_root=..., script_path=...)

不在 __init__.py 中 import 具体后端，避免包初始化时把所有后端依赖都拉进来。
"""

from .base import BaseVoicebankAdapter, VoicebankError

__all__ = [
    "BaseVoicebankAdapter",
    "VoicebankError",
]
