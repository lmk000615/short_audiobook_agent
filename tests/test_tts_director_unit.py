"""TTSDirectorAgent 单元测试（mock LLM）。

任务 3 起步：1:1 契约 + voice_ref 填充。任务 4 续写 fallback / parameters 清洗。
"""
from __future__ import annotations

from src_next.analysis.tts_director import TTSDirectorAgent
from src_next.core.data_models import ModelSpecificTTSInstruction


def test_direct_returns_1to1_with_input_segments(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """输出长度 + segment_id 必须与输入 1:1 对应。"""
    available_models = list(model_configs_all.values())
    llm_response = {
        "instructions": [
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {"instruct_text": "平稳地叙述"}},
            {"segment_id": "seg_002", "model": "S2Pro", "parameters": {"inline_tags_text": "[excited]当然来得及"}},
            {"segment_id": "seg_003", "model": "IndexTTS2", "parameters": {"emotion_vector": [0, 0, 0.5, 0, 0, 0.3, 0, 0.2]}},
        ]
    }
    agent = TTSDirectorAgent(llm_client=mock_llm(llm_response), available_models=available_models)
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    assert len(result) == len(sample_segments)
    assert [inst.segment_id for inst in result] == [s.segment_id for s in sample_segments]
    assert all(isinstance(inst, ModelSpecificTTSInstruction) for inst in result)


def test_direct_fills_voice_ref_from_voicebank(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """每条 instruction 的 voice_ref 应该从 voicebank_result 填充。"""
    llm_response = {
        "instructions": [
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_002", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_003", "model": "CosyVoice3", "parameters": {}},
        ]
    }
    agent = TTSDirectorAgent(
        llm_client=mock_llm(llm_response),
        available_models=list(model_configs_all.values()),
    )
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    expected_paths = {
        "seg_001": "/tmp/voicebank/narrator.wav",
        "seg_002": "/tmp/voicebank/xiaosongshu.wav",
        "seg_003": "/tmp/voicebank/laogui.wav",
    }
    for inst in result:
        assert inst.voice_ref == expected_paths[inst.segment_id], (
            f"voice_ref mismatch for {inst.segment_id}"
        )


def test_fallback_for_missing_segment(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """如果 LLM 漏掉某个 segment，fallback 用 default model + 该 model 的 default 参数填充。"""
    llm_response = {
        "instructions": [
            # 只返回 seg_001 + seg_002；seg_003 缺失
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_002", "model": "S2Pro", "parameters": {}},
        ]
    }
    agent = TTSDirectorAgent(
        llm_client=mock_llm(llm_response),
        available_models=list(model_configs_all.values()),
    )
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    assert len(result) == 3
    fallback_inst = next(inst for inst in result if inst.segment_id == "seg_003")
    assert fallback_inst.model == "CosyVoice3"
    # cosyvoice3.json 的 default 参数
    assert fallback_inst.parameters["mode"] == "instruct"
    assert fallback_inst.parameters["instruct_text"] == ""
    # voice_ref 仍从 voicebank 填充
    assert fallback_inst.voice_ref == "/tmp/voicebank/laogui.wav"


def test_invalid_parameters_field_filtered_to_defaults(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """如果 LLM 返回的 parameters 含无效字段，这些字段被丢弃 + 缺失字段用 default 填充。"""
    llm_response = {
        "instructions": [
            {
                "segment_id": "seg_001",
                "model": "S2Pro",
                "parameters": {
                    "instruction": "[excited]",  # 合法字段
                    "fake_field": "should_be_dropped",  # 不在 schema 的字段——丢弃
                    "temperature": "not_a_number",  # 类型错——用 default 覆盖
                },
            }
        ]
    }
    agent = TTSDirectorAgent(
        llm_client=mock_llm(llm_response),
        available_models=list(model_configs_all.values()),
    )
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    s2pro_inst = next(inst for inst in result if inst.segment_id == "seg_001")
    # 合法字段保留
    assert s2pro_inst.parameters["instruction"] == "[excited]"
    # 非法字段被丢弃
    assert "fake_field" not in s2pro_inst.parameters
    # 缺失字段用 default 填充
    assert s2pro_inst.parameters["enable_reference_audio"] is True
    assert s2pro_inst.parameters["temperature"] == 1.0  # 用 default 覆盖类型错的 LLM 值
