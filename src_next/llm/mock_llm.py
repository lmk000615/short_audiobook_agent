"""src_next/llm/mock_llm.py

离线 Mock LLM 实现。

不访问网络、不读 .env、不依赖 GPU。
返回固定的 mock 文本和 mock JSON，用于无服务器 / 无模型时验证 pipeline 数据流。
"""

from typing import Any

from .base import BaseLLMClient


_MOCK_TEXT = (
    "[mock-llm] 这是 MockLLMClient 返回的占位文本。"
    "不访问网络，不读取 .env，不依赖 GPU。"
)

# 故意做成 dict（不是 list），覆盖最常见的「单对象 JSON」分支；
# 调用方需要 list 时自己包一层即可。
_MOCK_JSON: dict[str, Any] = {
    "source": "mock",
    "speaker": "narrator",
    "emotion": "neutral",
    "pace": 1.0,
    "confidence": 0.0,
    "note": "MockLLMClient 占位 JSON。结构稳定，用于测试 pipeline 数据流。",
}


class MockLLMClient(BaseLLMClient):
    """无网络 / 无 .env / 无 GPU 的 Mock 实现。

    所有方法都返回固定值，kwargs 全部忽略。
    适合在：
    * 没有服务器时验证 core pipeline 数据流；
    * 单元测试中替换真实 LLM；
    * CI 环境避免外部依赖。
    """

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        return _MOCK_TEXT

    def generate_json(self, prompt: str, **kwargs: Any) -> dict | list:
        # 返回浅拷贝，避免调用方意外修改模块级常量
        return dict(_MOCK_JSON)
