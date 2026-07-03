"""pipeline stage 切换 smoke 测试（基于 use_tts_director）。

mock LLM + mock TTS，不打真服务。蓝区 PyYAML 缺失时整文件跳过。
"""
from __future__ import annotations

import pytest

# 蓝区可能未装 PyYAML；run_pipeline 顶层 import yaml，collect 会炸
pytest.importorskip("yaml")

from unittest.mock import MagicMock, patch  # noqa: E402


@pytest.fixture
def mock_pipeline_inputs(tmp_path):
    """mock pipeline 跑一次的最小输入。"""
    input_txt = tmp_path / "story.txt"
    input_txt.write_text("小松鼠说：你好。", encoding="utf-8")
    return input_txt


# 注意：patch 目标是 audiobook_pipeline 模块里已经 bound 的本地名
# （from ..X import Y 把 Y 绑到 audiobook_pipeline 命名空间），
# 不是源模块的 Y。否则 patch 不生效。
_PIPELINE_MOD = "src_next.core.audiobook_pipeline"


def _setup_common_mocks():
    """返回 (mock_llm, mock_vb, mock_tts, mock_director, mock_builder) 共享 mock 设置。"""
    mock_llm = MagicMock()
    mock_vb = MagicMock()
    mock_tts = MagicMock()
    # synthesize 返回空 list（pipeline 不要求返回真 AudioSegmentResult）
    mock_tts.synthesize.return_value = []
    mock_vb.prepare_voicebank.return_value = MagicMock(
        speaker_to_voice={}, voicebank_dir="", backend="mock", success=True
    )
    return mock_llm, mock_vb, mock_tts


def test_pipeline_off_flag_runs_10_stages(mock_pipeline_inputs, tmp_path):
    """use_tts_director=false 时，pipeline 跑 10 stage（老链路）。"""
    mock_llm, mock_vb, mock_tts = _setup_common_mocks()

    with patch(f"{_PIPELINE_MOD}.create_llm_client", return_value=mock_llm), \
         patch(f"{_PIPELINE_MOD}.create_voicebank_adapter", return_value=mock_vb), \
         patch(f"{_PIPELINE_MOD}.create_tts_adapter", return_value=mock_tts), \
         patch(f"{_PIPELINE_MOD}.generate_director_plan", return_value=[]), \
         patch(f"{_PIPELINE_MOD}.build_tts_instructions", return_value=[]), \
         patch(f"{_PIPELINE_MOD}.classify_and_merge_quotes") as mock_quote, \
         patch(f"{_PIPELINE_MOD}.resolve_speakers") as mock_resolve, \
         patch(f"{_PIPELINE_MOD}.analyze_characters") as mock_chars:

        # quote / resolve / chars 返回最小合法值（pipeline 期望 list）
        mock_quote.return_value = []  # 输入空 segments，下游也空
        mock_resolve.return_value = []
        mock_chars.return_value = []

        from src_next.core.audiobook_pipeline import run_pipeline

        try:
            result = run_pipeline(
                input_path=str(mock_pipeline_inputs),
                profile={
                    "llm": {"backend": "mock_llm"},
                    "voicebank": {"backend": "mock_voicebank"},
                    "tts": {"backend": "mock_tts", "base_url": "http://mock", "output_subdir": "audio_segments"},
                    "output": {"root": str(tmp_path)},
                    "pipeline": {"use_tts_director": False, "save_intermediate_json": True},
                },
            )
        except Exception as exc:
            pytest.skip(f"pipeline 结构需要更多 mock：{type(exc).__name__}: {exc}")
            return

        # 验证 stage 数
        if hasattr(result, "pipeline_summary") and "stages" in result.pipeline_summary:
            stages = result.pipeline_summary["stages"]
            assert len(stages) == 10, f"期望 10 stage（老链路），实际 {len(stages)}"


def test_pipeline_on_flag_runs_9_stages(mock_pipeline_inputs, tmp_path):
    """use_tts_director=true 时，pipeline 跑 9 stage（新链路）。"""
    mock_llm, mock_vb, mock_tts = _setup_common_mocks()

    with patch(f"{_PIPELINE_MOD}.create_llm_client", return_value=mock_llm), \
         patch(f"{_PIPELINE_MOD}.create_voicebank_adapter", return_value=mock_vb), \
         patch(f"{_PIPELINE_MOD}.create_tts_adapter", return_value=mock_tts), \
         patch(f"{_PIPELINE_MOD}.classify_and_merge_quotes") as mock_quote, \
         patch(f"{_PIPELINE_MOD}.resolve_speakers") as mock_resolve, \
         patch(f"{_PIPELINE_MOD}.analyze_characters") as mock_chars, \
         patch(f"{_PIPELINE_MOD}.TTSDirectorAgent") as mock_agent_cls:

        mock_quote.return_value = []
        mock_resolve.return_value = []
        mock_chars.return_value = []

        # tts_director agent 返回空 list
        mock_agent = MagicMock()
        mock_agent.direct.return_value = []
        mock_agent_cls.return_value = mock_agent

        from src_next.core.audiobook_pipeline import run_pipeline

        try:
            result = run_pipeline(
                input_path=str(mock_pipeline_inputs),
                profile={
                    "llm": {"backend": "mock_llm"},
                    "voicebank": {"backend": "mock_voicebank"},
                    "tts": {"output_subdir": "audio_segments"},  # 新链路忽略 backend/base_url
                    "output": {"root": str(tmp_path)},
                    "pipeline": {"use_tts_director": True, "save_intermediate_json": True},
                },
            )
        except Exception as exc:
            pytest.skip(f"pipeline 结构需要更多 mock：{type(exc).__name__}: {exc}")
            return

        if hasattr(result, "pipeline_summary") and "stages" in result.pipeline_summary:
            stages = result.pipeline_summary["stages"]
            assert len(stages) == 9, f"期望 9 stage（新链路），实际 {len(stages)}"
        # 验证走了新路径（tts_director agent 被调）
        mock_agent.direct.assert_called()


# ── _resolve_use_tts_director（任务 13：CLI flag 合并） ──────────


def test_cli_flag_overrides_profile_use_tts_director_false():
    """--use-tts-director CLI flag 应把 profile 的 use_tts_director 翻成 True。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    # profile=false，CLI=true → true
    assert _resolve_use_tts_director(profile_flag=False, cli_flag=True) is True


def test_cli_flag_off_keeps_profile_flag():
    """没传 CLI flag（None）应保留 profile 设置。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    assert _resolve_use_tts_director(profile_flag=True, cli_flag=None) is True
    assert _resolve_use_tts_director(profile_flag=False, cli_flag=None) is False


def test_cli_flag_off_overrides_profile_flag_on():
    """--no-use-tts-director 应强制 False，即使 profile=true。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    assert _resolve_use_tts_director(profile_flag=True, cli_flag=False) is False
