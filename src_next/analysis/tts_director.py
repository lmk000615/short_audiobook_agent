"""src_next/analysis/tts_director.py

合并老 stage 7 (story_director) + stage 8 (tts_instruction_builder) 的职责。

LLM 直接看到 model_configs/*.json 的能力描述，为每个 segment 输出
ModelSpecificTTSInstruction（model + parameters），消除原通用字段到
模型字段的中间映射层。

输出契约：
- 与输入 segments 1:1 对应（segment_id 一致）
- per-segment 自由选 model（音色一致性由 voice cloning 保证）
- LLM 漏掉的 segment / 无效 model / 无效 parameters 走 fallback
"""
from __future__ import annotations

import logging
from typing import Any

from src_next.analysis.prompts.tts_director_prompt import (
    build_system_prompt,
    build_user_prompt,
)
from src_next.core.data_models import (
    CharacterProfile,
    ModelSpecificTTSInstruction,
    Segment,
    VoicebankResult,
)
from src_next.llm.base import BaseLLMClient
from src_next.utils.model_config_loader import (
    ModelConfigError,
    get_default_parameters,
    load_model_config,
)

logger = logging.getLogger(__name__)


class TTSDirectorAgent:
    """LLM 驱动的 TTS 导演 agent。

    取代老的 (story_director + tts_instruction_builder) 组合。LLM 直接看到
    model_configs/*.json，按 segment 输出 ModelSpecificTTSInstruction。

    用法：
        agent = TTSDirectorAgent(llm_client, available_models=[...])
        instructions = agent.direct(
            segments=resolved,
            character_profiles=characters,
            voicebank_result=voicebank,
            default_model_name="CosyVoice3",
        )
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        available_models: list[dict[str, Any]],
    ) -> None:
        """
        Args:
            llm_client: 任意 BaseLLMClient 实现（Qwen HTTP / Gemma4 HTTP / Mock）。
            available_models: LLM 可选的 model_config dict 列表。
                应与 backends.yaml:enabled_backends 对应。
        """
        self.llm = llm_client
        self.available_models = available_models
        # 预构建合法 model name 集合，便于快速查
        self._valid_model_names = {cfg["name"] for cfg in available_models}
        # 缓存 system prompt（只依赖 available_models）
        self._system_prompt = build_system_prompt(available_models)

    def direct(
        self,
        segments: list[Segment],
        character_profiles: list[CharacterProfile],
        voicebank_result: VoicebankResult,
        default_model_name: str,
    ) -> list[ModelSpecificTTSInstruction]:
        """通过 LLM 产出 per-segment ModelSpecificTTSInstruction。

        Args:
            segments: 输入 segments（story_resolver 之后）。
            character_profiles: 角色档案（character_analyzer 之后）。
            voicebank_result: voicebank 输出（voicebank stage 之后）。
            default_model_name: fallback model name（LLM 漏掉或返回无效 model 时用）。
                必须在 available_models 里。

        Returns:
            ModelSpecificTTSInstruction 列表，与输入 segments 1:1。

        Raises:
            ModelConfigError: default_model_name 不在 available_models 里
                （这是配置错误，不是 LLM 错误）。
        """
        if default_model_name not in self._valid_model_names:
            raise ModelConfigError(
                f"default_model_name {default_model_name!r} is not in available_models "
                f"(valid: {sorted(self._valid_model_names)})"
            )

        if not segments:
            return []

        user_prompt = build_user_prompt(segments, character_profiles, voicebank_result)
        raw = self.llm.generate_json(
            prompt=user_prompt,
            system_prompt=self._system_prompt,
        )

        instructions_by_id = self._parse_response(raw, segments)

        # 对缺失或无效的 instruction 走 fallback + 注入 voice_ref
        instructions = self._apply_fallback(
            segments,
            instructions_by_id,
            voicebank_result,
            default_model_name,
        )

        return instructions

    # ─────────────────────────────────────────────────────────────────
    # 私有辅助（任务 4 续写）
    # ─────────────────────────────────────────────────────────────────

    def _parse_response(
        self,
        raw_response: Any,
        segments: list[Segment],
    ) -> dict[str, ModelSpecificTTSInstruction]:
        """把 LLM JSON 响应解析为 {segment_id: instruction} dict。

        - 跳过 model name 无效的 entry（fallback 会兜底）。
        - 跳过 segment_id 与任何输入不匹配的 entry（LLM 幻觉）。
        - 缺失的 segment_id 自然不在 dict 里，fallback 会兜底。
        - voice_ref 不在这里填——_apply_fallback 统一注入。
        """
        if not isinstance(raw_response, dict):
            logger.warning("LLM response is not a dict: %r", type(raw_response))
            return {}

        instructions_list = raw_response.get("instructions", [])
        if not isinstance(instructions_list, list):
            logger.warning(
                "LLM response 'instructions' is not a list: %r", type(instructions_list)
            )
            return {}

        valid_segment_ids = {s.segment_id for s in segments}
        result: dict[str, ModelSpecificTTSInstruction] = {}

        for entry in instructions_list:
            if not isinstance(entry, dict):
                continue
            seg_id = entry.get("segment_id")
            if seg_id not in valid_segment_ids:
                logger.warning("Skipping entry with unknown segment_id: %r", seg_id)
                continue

            model_name = entry.get("model")
            if model_name not in self._valid_model_names:
                logger.warning(
                    "segment %r: model %r not in available; will fallback",
                    seg_id, model_name,
                )
                continue

            # speaker/text 从输入 segment 填（LLM 不能改这两个）
            seg = next(s for s in segments if s.segment_id == seg_id)
            result[seg_id] = ModelSpecificTTSInstruction(
                segment_id=seg_id,
                speaker=seg.speaker,
                text=seg.text,
                model=model_name,
                parameters=dict(entry.get("parameters", {}) or {}),
                attempt=1,
            )

        return result

    def _apply_fallback(
        self,
        segments: list[Segment],
        instructions_by_id: dict[str, ModelSpecificTTSInstruction],
        voicebank_result: VoicebankResult,
        default_model_name: str,
    ) -> list[ModelSpecificTTSInstruction]:
        """对缺失 segment_id 填充 + 清洗无效 parameters。

        - 不在 instructions_by_id 里的 segment，用 default_model_name + 该 model 的
          default parameters 构造 fallback instruction。
        - 所有 instruction（LLM 产出的或 fallback 的），都按 model_config schema 清洗：
          无效字段丢弃，缺失字段用 default 填。
        - voice_ref 对每条 instruction 都从 voicebank_result 填充。
        """
        speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", None) or {}
        result: list[ModelSpecificTTSInstruction] = []

        for seg in segments:
            inst = instructions_by_id.get(seg.segment_id)
            if inst is None:
                # 缺失——完整 fallback
                params = get_default_parameters(default_model_name)
                inst = ModelSpecificTTSInstruction(
                    segment_id=seg.segment_id,
                    speaker=seg.speaker,
                    text=seg.text,
                    model=default_model_name,
                    parameters=dict(params),
                    voice_ref=speaker_to_voice.get(seg.speaker, ""),
                    attempt=1,
                )
                logger.info(
                    "segment %r: 应用 fallback（model=%s）",
                    seg.segment_id, default_model_name,
                )
            else:
                # 已存在——按 schema 清洗 parameters
                inst.parameters = self._clean_parameters(inst.model, inst.parameters)
                inst.voice_ref = speaker_to_voice.get(seg.speaker, "")
            result.append(inst)

        return result

    def _clean_parameters(
        self,
        model_name: str,
        raw_params: dict[str, Any],
    ) -> dict[str, Any]:
        """丢弃不在 schema 里的字段；缺失字段用 default 填充。

        不严格校验值类型——类型错的值用 schema default 覆盖。这是故意放宽：
        LLM 偶尔会输出 "true"（字符串）而非 true（bool）等，严格校验会产生
        太多假阴性。
        """
        try:
            cfg = load_model_config(model_name)
        except Exception:
            logger.warning("无法加载 %r 的 model_config；返回原始 params", model_name)
            return dict(raw_params)

        schema = cfg.get("parameters", {})
        cleaned: dict[str, Any] = {}
        # 先填所有 default
        for field_name, spec in schema.items():
            if "default" in spec:
                cleaned[field_name] = spec["default"]
        # 再叠加 LLM 提供的合法字段
        for field_name, value in raw_params.items():
            if field_name not in schema:
                logger.debug(
                    "丢弃 model %r parameters 中的未知字段 %r",
                    model_name, field_name,
                )
                continue
            expected_type = schema[field_name].get("type")
            if not _matches_type(value, expected_type):
                logger.debug(
                    "字段 %r (model %r) 类型不对（实际 %s，期望 %s）；用 default",
                    field_name, model_name, type(value).__name__, expected_type,
                )
                continue
            cleaned[field_name] = value
        return cleaned


def _matches_type(value: Any, expected_type: str | None) -> bool:
    """对 LLM 产出的 parameter 值做宽松类型检查。"""
    if expected_type is None:
        return True
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "bool":
        return isinstance(value, bool)
    if expected_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "list":
        return isinstance(value, list)
    return True
