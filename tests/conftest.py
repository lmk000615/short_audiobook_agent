"""short_audiobook_agent 测试共享 fixtures。

注意：本文件中 dataclass / BaseLLMClient 的字段名和签名必须和
``src_next/core/data_models.py`` 与 ``src_next/llm/base.py`` 的实际定义保持一致。
当 src_next 的数据契约升级时（如新增字段、改方法签名），本文件需同步更新。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src_next.core.data_models import (
    CharacterProfile,
    ModelSpecificTTSInstruction,
    Segment,
    VoicebankResult,
)
from src_next.llm.base import BaseLLMClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_CONFIGS_DIR = PROJECT_ROOT / "src_next" / "tts" / "model_configs"


class MockLLMClient(BaseLLMClient):
    """返回预定 JSON 的 LLM 测试替身。

    用法：
        client = MockLLMClient(response={"instructions": [...]})
        # 或模拟异常：
        client = MockLLMClient(response="not valid json",
                               raise_on_call=RuntimeError("..."))

    注意：``BaseLLMClient`` 的真实签名是 ``generate_text(self, prompt, **kwargs)``
    和 ``generate_json(self, prompt, **kwargs)``。system_prompt 通过 kwargs 传入
    （analysis 层调用时用 ``client.generate_json(prompt=user_prompt,
    system_prompt=system_prompt)``）。
    """

    def __init__(self, response: Any = None, raise_on_call: Exception | None = None):
        self._response = response
        self._raise = raise_on_call
        self.call_count = 0
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None
        self.last_kwargs: dict[str, Any] = {}

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        if self._raise:
            raise self._raise
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = kwargs.get("system_prompt")
        self.last_kwargs = dict(kwargs)
        return self._response if isinstance(self._response, str) else json.dumps(self._response)

    def generate_json(self, prompt: str, **kwargs: Any) -> dict | list:
        if self._raise:
            raise self._raise
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = kwargs.get("system_prompt")
        self.last_kwargs = dict(kwargs)
        if isinstance(self._response, (dict, list)):
            return self._response
        # response 是字符串时按 JSON 解析；解析失败抛 JSONDecodeError 让测试红
        return json.loads(self._response)


@pytest.fixture
def mock_llm():
    """MockLLMClient 工厂 fixture。"""
    def _make(response: Any = None, raise_on_call: Exception | None = None) -> MockLLMClient:
        return MockLLMClient(response=response, raise_on_call=raise_on_call)
    return _make


@pytest.fixture
def sample_segments() -> list[Segment]:
    """3 个 segments：1 旁白 + 2 不同 speaker 对白。"""
    return [
        Segment(
            segment_id="seg_001",
            text="小松鼠笑着递给他一个篮子。",
            speaker="narrator",
            segment_type="narration",
            raw_index=0,
        ),
        Segment(
            segment_id="seg_002",
            text="当然来得及，只要你愿意开始。",
            speaker="小松鼠",
            segment_type="dialogue",
            raw_index=1,
        ),
        Segment(
            segment_id="seg_003",
            text="孩子，时间会等你的。",
            speaker="老乌龟",
            segment_type="dialogue",
            raw_index=2,
        ),
    ]


@pytest.fixture
def sample_characters() -> list[CharacterProfile]:
    """3 个角色档案：narrator + 小松鼠（儿童）+ 老乌龟（老年）。

    字段名对齐 src_next/core/data_models.py:CharacterProfile 的实际定义：
    role_type（不是 role）/ age_style（不是 age）/ gender / voice_prompt。
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
def sample_voicebank_result() -> VoicebankResult:
    """speaker → wav 路径映射。voicebank_dir / backend / success 走默认值。"""
    return VoicebankResult(
        speaker_to_voice={
            "narrator": "/tmp/voicebank/narrator.wav",
            "小松鼠": "/tmp/voicebank/xiaosongshu.wav",
            "老乌龟": "/tmp/voicebank/laogui.wav",
        },
    )


@pytest.fixture
def model_configs_all() -> dict[str, dict]:
    """加载全部 model_config，返回 {name: config_dict}。

    加载顺序按文件名排序，保证跨平台稳定。
    """
    result: dict[str, dict] = {}
    for path in sorted(MODEL_CONFIGS_DIR.glob("*.json")):
        cfg = json.loads(path.read_text(encoding="utf-8"))
        result[cfg["name"]] = cfg
    return result


@pytest.fixture
def cosyvoice_config(model_configs_all) -> dict:
    return model_configs_all["CosyVoice3"]


@pytest.fixture
def s2pro_config(model_configs_all) -> dict:
    return model_configs_all["S2Pro"]


@pytest.fixture
def indextts_config(model_configs_all) -> dict:
    return model_configs_all["IndexTTS2"]


@pytest.fixture
def sample_model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    """3 个对齐 sample_segments 的 ModelSpecificTTSInstruction。

    speaker → model 的对应关系：
        narrator → CosyVoice3（旁白稳定叙述）
        小松鼠   → S2Pro（表演型儿童角色）
        老乌龟   → CosyVoice3（老年稳定叙述）

    同 speaker 在本组样本里只出现一次，方便测试同-speaker-一致性 规则时不踩坑。
    """
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="narrator",
            text="小松鼠笑着递给他一个篮子。",
            model="CosyVoice3",
            parameters={"mode": "instruct", "instruct_text": "平稳温和叙述", "speed": 1.0},
            voice_ref="/tmp/voicebank/narrator.wav",
            attempt=1,
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_002",
            speaker="小松鼠",
            text="当然来得及，只要你愿意开始。",
            model="S2Pro",
            parameters={
                "instruction": "活泼小女孩",
                "inline_tags_text": "[excited]当然来得及[pause]只要你愿意开始。",
                "enable_reference_audio": True,
                "temperature": 1.0,
                "top_p": 0.6,
            },
            voice_ref="/tmp/voicebank/xiaosongshu.wav",
            attempt=1,
        ),
        ModelSpecificTTSInstruction(
            segment_id="seg_003",
            speaker="老乌龟",
            text="孩子，时间会等你的。",
            model="CosyVoice3",
            parameters={
                "mode": "instruct",
                "instruct_text": "苍老慈祥的老年男性",
                "speed": 0.85,
            },
            voice_ref="/tmp/voicebank/laogui.wav",
            attempt=1,
        ),
    ]
