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


def _make_minimal_pcm16_wav() -> bytes:
    """造一个最小合法 PCM_16 wav 字节流（44 字节头 + 100 帧零数据）。

    用于 mock HTTP 返回——之前用 b"RIFF...wav" 不合法，soundfile 会炸，
    导致 cosyvoice _synthesize_model_specific 绕开了 _save_wav_pcm16 转换
    （直接 write_bytes），引入了 production bug：新链路 wav 格式不统一
    让 audio_merger 跳段。让 mock wav 合法 = 测试和生产数据形状一致。
    """
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_cosyvoice_model_specific_passes_through_parameters(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """_synthesize_model_specific 应该把 instruction.parameters 透传给 HTTP，
    不做 emotion→tag 之类的映射（纯透传）。"""
    captured_request: dict = {}

    def fake_http_post(url, **kwargs):
        captured_request["url"] = url
        captured_request.update(kwargs)
        # 返回合法 PCM_16 wav（不是随便的字节流），让 _save_wav_pcm16 能跑通
        return MagicMock(
            content=_make_minimal_pcm16_wav(), status_code=200, headers={},
        )

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


def test_cosyvoice_model_specific_writes_pcm16_not_raw_float(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """回归保护：cosyvoice _synthesize_model_specific 必须调 _save_wav_pcm16
    把 server 返回的 IEEE float wav 转 PCM_16，不能直接 write_bytes。

    背景：之前为绕开 mock wav 让 soundfile 炸，新链路直接 write_bytes，
    导致新链路 cosyvoice 输出 IEEE float wav，s2pro/indextts 输出 PCM_16，
    audio_merger 因格式不一致跳段，final wav 只含 1 段。

    依赖 soundfile + numpy（_save_wav_pcm16 内部 lazy import），蓝区
    未装这两个 deps 时跳过；黄区装了，正常跑。
    """
    pytest.importorskip("soundfile")  # _save_wav_pcm16 用，蓝区跳过

    import wave

    with patch(
        "src_next.tts.cosyvoice_http.requests.post",
        return_value=MagicMock(
            content=_make_minimal_pcm16_wav(), status_code=200, headers={},
        ),
    ):
        cosyvoice_adapter._synthesize_model_specific(
            model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    # 验证落盘 wav 能被 stdlib wave 读，且是 PCM_16 (sampwidth=2)
    out_wav = tmp_path / "audio_segments" / "seg_001.wav"
    assert out_wav.exists(), f"wav 未落盘：{out_wav}"
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getsampwidth() == 2, (
            f"落盘 wav 不是 PCM_16 (sampwidth=2)，实际 sampwidth={wf.getsampwidth()}"
            "——可能 _synthesize_model_specific 又绕开了 _save_wav_pcm16"
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


def test_s2pro_model_specific_reads_prompt_text_when_voice_ref_exists(
    s2pro_adapter, s2pro_model_specific_instructions, voicebank_result, tmp_path
):
    """voice_ref 文件存在时，应触发 _get_prompt_text_for_voice 读同名 .txt 转写。

    回归保护：之前 _get_prompt_text_for_voice 用 self.extra_args.get(...)，
    但 S2ProTTSAdapter.__init__ 不存 self.extra_args → AttributeError。
    黄区端到端测试暴露（蓝区单测的 fixture voice_ref 不存在 → 跳过该路径）。
    """
    import wave

    # 造一个真的 wav 文件 + 同名 .txt 转写
    voice_ref_path = tmp_path / "voicebank" / "xiaosongshu.wav"
    voice_ref_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(voice_ref_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)
    voice_ref_path.with_suffix(".txt").write_text(
        "活泼小女孩的参考音频转写", encoding="utf-8",
    )

    # 改 instruction 的 voice_ref 指向真实 tmp_path
    inst = s2pro_model_specific_instructions[0]
    inst.voice_ref = str(voice_ref_path)

    captured: dict = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return MagicMock(content=b"RIFF" + b"\x00" * 40 + b"wav", status_code=200)

    with patch("src_next.tts.s2pro_adapter.requests.post", side_effect=fake_post):
        s2pro_adapter._synthesize_model_specific(
            s2pro_model_specific_instructions,
            voicebank_result,
            str(tmp_path),
            dry_run=False,
        )

    data = captured.get("data") or {}
    # 同名 .txt 被读到 prompt_text 字段
    assert "活泼小女孩" in data.get("prompt_text", ""), (
        f"_get_prompt_text_for_voice 未读 .txt 转写：{data}"
    )
    assert data.get("enable_reference_audio") == "true", (
        f"reference_audio 字段未透传：{data}"
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
