"""属性感知 Critic 的评估结果数据结构。

与 ``core/data_models.py:CriticResult`` 并存（不继承）：

- ``CriticResult`` 是 5 维扁平 0-1 分，面向 ``TTSRepairAgent`` 闭环消费
- ``AttributeAwareCriticResult`` 在 5 维之上增加三段结构化属性数据：
  * ``extracted_attributes`` — critic 听音频后客观提取的实际属性
  * ``expected_attributes`` — 从 ``DirectorInstruction`` 现场渲染的期望属性
  * ``attribute_consistency`` — 每个属性的 match/note + overall_verdict

为什么不继承 ``CriticResult``：
- ``TTSRepairAgent.repair()`` 签名写死接收 ``CriticResult``，继承会让鸭子类型
  "看起来能消费"实际丢字段，掩盖 bug。明确分开 + ``to_critic_result()`` 转换更安全。
- ``CriticResult.from_json`` 字段语义是"扁平 0-1 分"，与 LLM 返回的嵌套结构正交；
  继承会强迫重写 ``from_json``，反而更乱。

真相源约定：``expected_attributes`` **永远来自 ``DirectorInstruction`` 现场渲染**，
不取 LLM 回填值。LLM 在 prompt 里被要求"复述"期望属性仅用于 prompt 自检，不进入
结果对象。这避免 LLM 抄错期望值导致一致性结论失真。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src_next.core.data_models import CriticResult, DirectorInstruction
from src_next.critic.qwen3omni_critic import _normalize_nested_scoring


@dataclass
class AttributeAwareCriticResult:
    """单段音频的属性感知评估结果（5 维 + 提取属性 + 期望属性 + 一致性）。

    Attributes
    ----------
    segment_id : str
        对应的 segment 编号。
    quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility : float
        原 5 维评分（0-1 扁平，与 ``CriticResult`` 同语义）。
    overall : float
        5 维均值（0-1）。
    suggestions : str
        修复建议（中文自由文本），与 ``CriticResult.suggestions`` 同语义，供
        ``TTSRepairAgent`` 通过 ``to_critic_result()`` 消费。
    attempt : int
        本次评估对应的合成 attempt（首次=1，第一次修复后重评=2 ...）。
    extracted_attributes : dict[str, Any]
        critic 听音频后客观提取的实际属性。典型键：
        ``emotion`` / ``intensity`` / ``pace`` / ``volume`` / ``pitch`` / ``evidence``。
        ``evidence`` 是 critic 必须填的"我听到了什么"自然语言证据。
    expected_attributes : dict[str, Any]
        从 ``DirectorInstruction`` 现场渲染的期望属性。**真相源永远是 DirectorInstruction**，
        不取 LLM 回填值。
    attribute_consistency : dict[str, Any]
        一致性判断。结构：
        ``{"<attr>": {"match": bool, "note": str}, ...,
          "overall_verdict": "high/medium/low",
          "inconsistency_summary": str}``
    """

    segment_id: str
    quality: float
    emotion_alignment: float
    character_consistency: float
    rhythm_naturalness: float
    intelligibility: float
    overall: float
    suggestions: str
    attempt: int
    extracted_attributes: dict[str, Any] = field(default_factory=dict)
    expected_attributes: dict[str, Any] = field(default_factory=dict)
    attribute_consistency: dict[str, Any] = field(default_factory=dict)

    def needs_repair(self, threshold: float = 0.7, overall_floor: float = 0.75) -> bool:
        """与 ``CriticResult.needs_repair`` 同款逻辑。

        触发条件（任一）：任一维度 < threshold，或 overall < overall_floor。
        """
        dims = (
            self.quality,
            self.emotion_alignment,
            self.character_consistency,
            self.rhythm_naturalness,
            self.intelligibility,
        )
        return min(dims) < threshold or self.overall < overall_floor

    def to_critic_result(self) -> CriticResult:
        """降级为 ``CriticResult``，供现有 ``TTSRepairAgent`` / ``save_critic_session`` 复用。

        丢失字段：``extracted_attributes`` / ``expected_attributes`` / ``attribute_consistency``。
        """
        return CriticResult(
            segment_id=self.segment_id,
            quality=self.quality,
            emotion_alignment=self.emotion_alignment,
            character_consistency=self.character_consistency,
            rhythm_naturalness=self.rhythm_naturalness,
            intelligibility=self.intelligibility,
            overall=self.overall,
            suggestions=self.suggestions,
            attempt=self.attempt,
        )

    @staticmethod
    def _render_expected(director: DirectorInstruction) -> dict[str, Any]:
        """从 ``DirectorInstruction`` 现场渲染期望属性 dict。

        这是期望属性的**唯一真相源**——LLM 在 prompt 里被要求复述，但 ``from_json``
        永远从这里取，不信任 LLM 回填。
        """
        return {
            "emotion": director.emotion,
            "intensity": director.emotion_intensity,
            "pace": director.pace,
            "tone": director.tone,
            "volume": director.volume,
            "pitch": director.pitch,
            "delivery_instruction": director.delivery_instruction,
        }

    @classmethod
    def from_json(
        cls,
        raw_llm_output: dict[str, Any],
        director_instruction: DirectorInstruction,
        segment_id: str,
        attempt: int = 1,
    ) -> "AttributeAwareCriticResult":
        """从 LLM 返回的完整 nested dict 构造结果对象。

        Parameters
        ----------
        raw_llm_output : dict
            LLM 返回的完整 JSON（已经过 ``_parse_scoring_json`` 解析）。
            期望含键：``scores`` / ``extracted_attributes`` / ``attribute_consistency`` /
            ``main_problems`` / ``suggestions``。
        director_instruction : DirectorInstruction
            上游导演指令。期望属性从这里现场渲染，不从 LLM 输出取。
        segment_id : str
            对应 segment 编号。优先用调用方传入的，而不是信任 LLM 输出。
        attempt : int
            本次评估对应的合成 attempt。

        复用 ``_normalize_nested_scoring``（来自 ``qwen3omni_critic``）把嵌套 0-10
        分数扁平化为 0-1，复用 ``CriticResult.from_json`` 处理 clamp / 缺失补 0.5 /
        overall 计算。
        """
        flat = _normalize_nested_scoring(raw_llm_output, segment_id, attempt)
        base = CriticResult.from_json(flat, attempt=attempt)

        extracted = raw_llm_output.get("extracted_attributes") or {}
        if not isinstance(extracted, dict):
            extracted = {}

        consistency = raw_llm_output.get("attribute_consistency") or {}
        if not isinstance(consistency, dict):
            consistency = {}

        expected = cls._render_expected(director_instruction)

        return cls(
            segment_id=base.segment_id,
            quality=base.quality,
            emotion_alignment=base.emotion_alignment,
            character_consistency=base.character_consistency,
            rhythm_naturalness=base.rhythm_naturalness,
            intelligibility=base.intelligibility,
            overall=base.overall,
            suggestions=base.suggestions,
            attempt=base.attempt,
            extracted_attributes=extracted,
            expected_attributes=expected,
            attribute_consistency=consistency,
        )

    @classmethod
    def neutral(
        cls,
        segment_id: str,
        attempt: int,
        director_instruction: DirectorInstruction,
        err_msg: str,
    ) -> "AttributeAwareCriticResult":
        """评估失败时的中性 fallback（overall=0.5）。

        与 ``Qwen3OmniCritic._neutral_result`` 对称：5 维全部 0.5，避免一次网络
        抖动就触发不必要的修复级联。期望属性仍从 ``DirectorInstruction`` 渲染
        （保留诊断信息），但 ``extracted_attributes`` 为空、``attribute_consistency``
        的 overall_verdict 标记为 ``unknown``。
        """
        return cls(
            segment_id=segment_id,
            quality=0.5,
            emotion_alignment=0.5,
            character_consistency=0.5,
            rhythm_naturalness=0.5,
            intelligibility=0.5,
            overall=0.5,
            suggestions=f"评估失败：{err_msg}，建议人工复核",
            attempt=attempt,
            extracted_attributes={},
            expected_attributes=cls._render_expected(director_instruction),
            attribute_consistency={"overall_verdict": "unknown"},
        )
