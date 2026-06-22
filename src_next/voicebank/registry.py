"""src_next/voicebank/registry.py

voicebank backend 工厂。

core 层未来只通过本模块的 create_voicebank_adapter 创建 adapter，
不直接 import 具体后端，这样：
* 切换 backend 只改 profile 配置，不改业务代码；
* 新增 backend 只动 registry + 新 adapter 文件，core 不感知。

懒导入：只有用到某 backend 时才 import 对应模块，避免 import src_next.voicebank
时把所有后端依赖都拉进来（保持 __init__.py 轻量）。
"""

from __future__ import annotations

from typing import Any

from .base import BaseVoicebankAdapter, VoicebankError


def create_voicebank_adapter(
    backend: str,
    **config: Any,
) -> BaseVoicebankAdapter:
    """根据 backend 名称创建 voicebank adapter。

    Args:
        backend: 后端标识。当前支持：
            - "mock": MockVoicebankAdapter（离线占位）
            - "qwen_voicegenerator": QwenVoiceGeneratorAdapter（通用，需配路径）
        **config: 传给具体 adapter 构造函数的参数（如 generator_root / script_path）。

    Returns:
        BaseVoicebankAdapter 实例。

    Raises:
        VoicebankError: backend 未知时。
    """
    if backend == "mock":
        # MockVoicebankAdapter 不需要 config 参数
        from .mock_voicebank import MockVoicebankAdapter
        return MockVoicebankAdapter()

    if backend == "qwen_voicegenerator":
        from .qwen_voicegenerator import QwenVoiceGeneratorAdapter
        return QwenVoiceGeneratorAdapter(**config)

    raise VoicebankError(
        f"未知 voicebank backend: {backend!r}。"
        "当前支持: 'mock', 'qwen_voicegenerator'。"
    )
