"""TTSDirectorAgent 集成测试（真 Gemma4 LLM）。

PR 合并前手动运行：
    pytest tests/test_tts_director_integration.py -v -m integration

CI fast 模式默认跳过。蓝区无 Gemma4 服务，只能在黄区跑。

依赖 yellow_qwen3http_cosyvoicehttp.yaml 配置的 Gemma4 HTTP LLM。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src_next.analysis.tts_director import TTSDirectorAgent
from src_next.core.data_models import (
    CharacterProfile,
    Segment,
    VoicebankResult,
)
from src_next.utils.model_config_loader import load_all_model_configs

# yaml + create_llm_client 走 lazy import（在 _load_llm_from_profile 内）：
# 蓝区可能未装 PyYAML，让模块至少能被 pytest collect（marker 才能生效）。


PROFILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "src_next" / "profiles" / "yellow_qwen3http_cosyvoicehttp.yaml"
)


def _load_llm_from_profile():
    """用 yellow profile 加载真 LLM client（Gemma4 HTTP）。

    PyYAML / registry 在函数内 lazy import，让模块顶层不依赖它们。
    """
    import yaml  # noqa: WPS433  (lazy import for blue-zone collectability)

    from src_next.llm.registry import create_llm_client  # noqa: WPS433

    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    llm_cfg = profile["llm"]
    return create_llm_client(
        llm_cfg["backend"],
        **{k: v for k, v in llm_cfg.items() if k != "backend"},
    )


@pytest.fixture
def integration_segments() -> list[Segment]:
    """样例故事 segments（5 段，3 speaker）。"""
    return [
        Segment(
            segment_id="seg_001",
            segment_type="narration",
            speaker="narrator",
            text="清晨，小松鼠蹦蹦跳跳地穿过森林。",
        ),
        Segment(
            segment_id="seg_002",
            segment_type="dialogue",
            speaker="小松鼠",
            text="乌龟爷爷，您今天怎么这么慢呀？",
        ),
        Segment(
            segment_id="seg_003",
            segment_type="narration",
            speaker="narrator",
            text="老乌龟抬起头，慢慢地说。",
        ),
        Segment(
            segment_id="seg_004",
            segment_type="dialogue",
            speaker="老乌龟",
            text="孩子，时间会等你的，慢慢来。",
        ),
        Segment(
            segment_id="seg_005",
            segment_type="dialogue",
            speaker="小松鼠",
            text="那我陪您一起走！",
        ),
    ]


@pytest.fixture
def integration_characters() -> list[CharacterProfile]:
    """角色档案：narrator + 小松鼠（儿童）+ 老乌龟（老年）。

    字段名对齐 src_next/core/data_models.py:CharacterProfile 实际定义
    （role_type / age_style / voice_prompt / gender）。
    """
    return [
        CharacterProfile(
            name="narrator",
            role_type="narrator",
            gender="neutral",
            age_style="adult",
            voice_prompt="平稳温和的中性叙述音",
        ),
        CharacterProfile(
            name="小松鼠",
            role_type="character",
            gender="female",
            age_style="child",
            voice_prompt="活泼轻快的小女孩声音",
        ),
        CharacterProfile(
            name="老乌龟",
            role_type="character",
            gender="male",
            age_style="elderly",
            voice_prompt="苍老低沉的老年男性声音",
        ),
    ]


@pytest.fixture
def integration_voicebank() -> VoicebankResult:
    """speaker → wav 路径映射。"""
    return VoicebankResult(
        speaker_to_voice={
            "narrator": "/tmp/voicebank/narrator.wav",
            "小松鼠": "/tmp/voicebank/xiaosongshu.wav",
            "老乌龟": "/tmp/voicebank/laogui.wav",
        },
    )


@pytest.mark.integration
def test_tts_director_with_real_gemma4(
    integration_segments, integration_characters, integration_voicebank
):
    """端到端：真 Gemma4 LLM 产出合法 ModelSpecificTTSInstruction[]。

    验证：
    - LLM 返回可解析 JSON
    - 输出与输入 segments 1:1
    - 所有 model name 都在 available_models 里
    - voice_ref 从 voicebank 填充
    - LLM 在做差异化决策（至少有一条非 default model）
    """
    llm = _load_llm_from_profile()
    available_models = list(load_all_model_configs().values())

    agent = TTSDirectorAgent(llm_client=llm, available_models=available_models)
    result = agent.direct(
        segments=integration_segments,
        character_profiles=integration_characters,
        voicebank_result=integration_voicebank,
        default_model_name="CosyVoice3",
    )

    # 1:1 契约
    assert len(result) == 5
    assert [inst.segment_id for inst in result] == [
        s.segment_id for s in integration_segments
    ]

    # 合法性
    valid_names = {cfg["name"] for cfg in available_models}
    for inst in result:
        assert inst.model in valid_names, f"非法 model：{inst.model}"
        assert inst.voice_ref, f"{inst.segment_id} 的 voice_ref 为空"

    # 合理性 sanity check：至少有一条非 default model
    # （证明 LLM 在做 per-segment 差异化决策，而不是图省事全选 default）
    non_default = [inst for inst in result if inst.model != "CosyVoice3"]
    assert len(non_default) >= 1, (
        "LLM 给全部 5 段都选了 CosyVoice3——可能没在做差异化决策。"
        "Prompt 可能需要更强的决策引导。"
    )
