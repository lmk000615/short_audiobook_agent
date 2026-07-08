"""TTS 指令修复 Agent。

根据 CriticResult.suggestions 调 LLM，让 LLM 只调整 ModelSpecificTTSInstruction.parameters，
不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）。

参考 Audio-Oscar §C.16-C.17：parameters merge 用"original parameters 作基底 + LLM 输出覆盖"
模式；不可改字段在 schema 层冻结，不依赖 prompt 软约束。
"""
from __future__ import annotations

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
from src_next.critic.prompts.repair_prompt import build_repair_prompt
from src_next.llm.base import BaseLLMClient


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client
