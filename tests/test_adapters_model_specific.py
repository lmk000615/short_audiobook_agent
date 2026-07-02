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
from src_next.tts.indextts_http import IndexTTSHTTPAdapter
from src_next.tts.s2pro_adapter import S2ProTTSAdapter


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


# ── S2Pro adapter 双接口测试（任务 7） ─────────────────────────────


@pytest.fixture
def s2pro_adapter():
    return S2ProTTSAdapter(
        base_url="http://mock:8010",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout_per_seg": 10, "enable_reference_audio": True},
    )


@pytest.fixture
def s2pro_model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="小松鼠",
            text="太棒了！",
            model="S2Pro",
            parameters={
                "instruction": "[excited]",
                "inline_tags_text": "[excited]太棒了！",
                "enable_reference_audio": True,
                "temperature": 0.9,
                "top_p": 0.7,
            },
            voice_ref="/tmp/voicebank/xiaosongshu.wav",
            attempt=1,
        ),
    ]


def test_s2pro_synthesize_routes_to_model_specific(
    s2pro_adapter, s2pro_model_specific_instructions, voicebank_result, tmp_path
):
    """当 instructions[0] 是 ModelSpecificTTSInstruction 时走新路径。"""
    with patch.object(
        s2pro_adapter, "_synthesize_model_specific",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_ms, patch.object(
        s2pro_adapter, "_synthesize_legacy",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_legacy:
        s2pro_adapter.synthesize(
            s2pro_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True
        )
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_s2pro_model_specific_passes_through_inline_tags(
    s2pro_adapter, s2pro_model_specific_instructions, voicebank_result, tmp_path
):
    """当 inline_tags_text 提供，它覆盖 instruction.text 作为 HTTP 的 `text` 字段。
    instruction 字段原样透传（不从 emotion 映射）。"""
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(content=b"RIFF" + b"\x00" * 40 + b"wav", status_code=200)

    with patch("src_next.tts.s2pro_adapter.requests.post", side_effect=fake_post):
        s2pro_adapter._synthesize_model_specific(
            s2pro_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    assert captured.get("url"), "HTTP post 未被调用"
    # S2Pro 8010 用 multipart/form-data，data 是 form dict
    data = captured.get("data") or {}
    text_value = data.get("text", "")
    assert "[excited]" in text_value, (
        f"inline_tags_text 未透传：text={text_value!r}"
    )
    # instruction 字段全局透传（LLM 已经直接给出 [excited]，不做 emotion→tag mapping）
    assert data.get("instruction") == "[excited]", (
        f"instruction 字段未透传：{data}"
    )


# ── IndexTTS adapter 双接口测试（任务 8） ──────────────────────────


@pytest.fixture
def indextts_adapter():
    return IndexTTSHTTPAdapter(
        base_url="http://mock:8009",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout_per_seg": 10},
    )


@pytest.fixture
def indextts_model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="老乌龟",
            text="孩子，时间会等你的。",
            model="IndexTTS2",
            parameters={
                "emotion_vector": [0, 0, 0.6, 0, 0, 0.4, 0, 0],
                "emotion_alpha": 0.7,
                "temperature": 0.8,
            },
            voice_ref="/tmp/voicebank/laogui.wav",
            attempt=1,
        ),
    ]


def test_indextts_synthesize_routes_to_model_specific(
    indextts_adapter, indextts_model_specific_instructions, voicebank_result, tmp_path
):
    """当 instructions[0] 是 ModelSpecificTTSInstruction 时走新路径。"""
    with patch.object(
        indextts_adapter, "_synthesize_model_specific",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_ms, patch.object(
        indextts_adapter, "_synthesize_legacy",
        return_value=[MagicMock(spec=AudioSegmentResult)],
    ) as mock_legacy:
        indextts_adapter.synthesize(
            indextts_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True
        )
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_indextts_model_specific_passes_through_emotion_vector(
    indextts_adapter, indextts_model_specific_instructions, voicebank_result, tmp_path
):
    """instruction.parameters 的 emotion_vector 应原样透传给 HTTP JSON body
    （不是从通用 emotion 字段推导）。"""
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(content=b"RIFF" + b"\x00" * 40 + b"wav", status_code=200)

    with patch("src_next.tts.indextts_http.requests.post", side_effect=fake_post):
        indextts_adapter._synthesize_model_specific(
            indextts_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    assert captured.get("url"), "HTTP post 未被调用"
    # IndexTTS 用 JSON body
    json_body = captured.get("json") or {}
    assert json_body.get("emotion_vector") == [0, 0, 0.6, 0, 0, 0.4, 0, 0], (
        f"emotion_vector 未透传：{json_body}"
    )
    assert json_body.get("emotion_alpha") == 0.7, (
        f"emotion_alpha 未透传：{json_body}"
    )
