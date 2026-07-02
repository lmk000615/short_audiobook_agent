"""adapter _synthesize_model_specific 单元测试（mock HTTP）。

任务 6 起步：cosyvoice_http 双接口。任务 7/8 续写 s2pro / indextts。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_next.core.data_models import (
    AudioSegmentResult,
    ModelSpecificTTSInstruction,
    TTSInstruction,
    VoicebankResult,
)
from src_next.tts.cosyvoice_http import CosyVoiceHTTPAdapter


@pytest.fixture
def cosyvoice_adapter():
    """创建 mock base_url 的 adapter（不发真 HTTP）。"""
    return CosyVoiceHTTPAdapter(
        base_url="http://mock:8005",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout": 10},
    )


@pytest.fixture
def model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="narrator",
            text="测试文本",
            model="CosyVoice3",
            parameters={
                "mode": "instruct",
                "instruct_text": "用平静的语气说",
            },
            voice_ref="/tmp/voicebank/narrator.wav",
            attempt=1,
        ),
    ]


@pytest.fixture
def voicebank_result() -> VoicebankResult:
    # 注意：VoicebankResult 没有 config_snapshot 字段（plan bug），只用 speaker_to_voice
    return VoicebankResult(
        speaker_to_voice={"narrator": "/tmp/voicebank/narrator.wav"},
    )


def test_cosyvoice_synthesize_routes_to_model_specific_when_input_is_model_specific(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """当 instructions[0] 是 ModelSpecificTTSInstruction 时，synthesize() 应该
    调用 _synthesize_model_specific（而不是 _synthesize_legacy）。"""
    with patch.object(
        cosyvoice_adapter, "_synthesize_model_specific",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_ms, patch.object(
        cosyvoice_adapter, "_synthesize_legacy",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_legacy:
        cosyvoice_adapter.synthesize(
            model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True
        )
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_cosyvoice_synthesize_routes_to_legacy_when_input_is_legacy(
    cosyvoice_adapter, voicebank_result, tmp_path
):
    """当 instructions[0] 是 TTSInstruction（老格式），synthesize() 应该调 _synthesize_legacy。"""
    legacy_instructions = [
        TTSInstruction(
            segment_id="seg_001",
            speaker="narrator",
            text="测试",
            output_filename="seg_001.wav",
        ),
    ]
    with patch.object(
        cosyvoice_adapter, "_synthesize_model_specific",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_ms, patch.object(
        cosyvoice_adapter, "_synthesize_legacy",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_legacy:
        cosyvoice_adapter.synthesize(
            legacy_instructions, voicebank_result, str(tmp_path), dry_run=True
        )
        mock_legacy.assert_called_once()
        mock_ms.assert_not_called()


def test_cosyvoice_model_specific_passes_through_parameters(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """_synthesize_model_specific 应该把 instruction.parameters 透传给 HTTP，
    不做 emotion→tag 之类的映射（纯透传）。"""
    captured_request: dict = {}

    def fake_http_post(url, **kwargs):
        captured_request["url"] = url
        captured_request.update(kwargs)
        # 返回最小合法 wav 字节（够过长度检查，写盘用 write_bytes 不解码）
        return MagicMock(content=b"RIFF" + b"\x00" * 40 + b"wav", status_code=200, headers={})

    with patch("src_next.tts.cosyvoice_http.requests.post", side_effect=fake_http_post):
        cosyvoice_adapter._synthesize_model_specific(
            model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    # 验证 HTTP 请求体含 instruction.parameters（透传）
    assert captured_request.get("url"), "HTTP post 未被调用"
    # cosyvoice adapter 用 json= 传 payload
    request_data = captured_request.get("json") or captured_request.get("data") or {}
    if isinstance(request_data, dict):
        # instruct_text '用平静的语气说' 应该被拼进 prompt_text
        assert any("平静" in str(v) for v in request_data.values()), (
            f"instruct_text '用平静的语气说' 未体现在 HTTP 请求：{request_data}"
        )
