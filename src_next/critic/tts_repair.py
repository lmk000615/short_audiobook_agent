"""TTS 指令修复 Agent。

根据 CriticResult.suggestions 调 LLM，让 LLM 只调整 ModelSpecificTTSInstruction.parameters，
不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）。

参考 Audio-Oscar §C.16-C.17：parameters merge 用"original parameters 作基底 + LLM 输出覆盖"
模式；不可改字段在 schema 层冻结，不依赖 prompt 软约束。
"""
from __future__ import annotations

import copy
import logging

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
from src_next.critic.prompts.repair_prompt import build_repair_prompt
from src_next.llm.base import BaseLLMClient, LLMError

logger = logging.getLogger(__name__)


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client

    def repair(
        self,
        original: ModelSpecificTTSInstruction,
        segment: Segment,
        critic: CriticResult,
    ) -> ModelSpecificTTSInstruction:
        """根据低分维度和 suggestions，调整 parameters。

        契约：
        - 返回新的 ModelSpecificTTSInstruction，**不改 segment_id / speaker /
          text / model / voice_ref**（避免声音不一致）。
        - attempt 字段 +1。
        - parameters 由 LLM 重写（保留原 parameters 中 LLM 没动的字段）。
        - LLM 失败 → 返回 original（attempt +1），不抛异常。
        """
        next_attempt = original.attempt + 1
        try:
            llm_output = self.llm.generate_json(build_repair_prompt(original, segment, critic))
        except (LLMError, Exception) as exc:  # noqa: BLE001 — by design, any failure → fallback
            logger.warning("repair LLM call failed: %s. Falling back to original parameters.", exc)
            return self._fallback(original, next_attempt)

        new_parameters = self._merge_parameters(original.parameters, llm_output)
        return ModelSpecificTTSInstruction(
            segment_id=original.segment_id,  # frozen
            speaker=original.speaker,         # frozen
            text=original.text,                # frozen
            model=original.model,              # frozen
            parameters=new_parameters,         # merged
            voice_ref=original.voice_ref,      # frozen
            attempt=next_attempt,
        )

    @staticmethod
    def _merge_parameters(original_parameters: dict, llm_output) -> dict:
        """Merge LLM output into original parameters.

        Pattern (Audio-Oscar §C.16 adapted): original as base, LLM overlay.
        Unlike Oscar we don't whitelist against model_configs (task card §1.5 allows
        any parameters field), so we accept any key the LLM provides — but only
        if it's inside the LLM's "parameters" sub-dict.
        """
        if not isinstance(llm_output, dict):
            return copy.deepcopy(original_parameters)

        llm_params = llm_output.get("parameters")
        if not isinstance(llm_params, dict):
            return copy.deepcopy(original_parameters)

        merged = copy.deepcopy(original_parameters)
        merged.update(llm_params)
        return merged

    @staticmethod
    def _fallback(original: ModelSpecificTTSInstruction, next_attempt: int) -> ModelSpecificTTSInstruction:
        """Return original with attempt+1. Used when LLM call fails or output is unusable."""
        return ModelSpecificTTSInstruction(
            segment_id=original.segment_id,
            speaker=original.speaker,
            text=original.text,
            model=original.model,
            parameters=copy.deepcopy(original.parameters),
            voice_ref=original.voice_ref,
            attempt=next_attempt,
        )
