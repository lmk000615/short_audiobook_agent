"""src_next.llm

LLM adapter 层。

这里保持轻量，只暴露最基础的接口类型。
具体后端请显式从对应模块导入，例如：

    from src_next.llm.qwen_http import QwenHTTPClient
    from src_next.llm.mock_llm import MockLLMClient
    from src_next.llm.gemma4_http import Gemma4HTTPClient

这样可以避免 import src_next.llm 时自动加载具体后端，
也避免 python -m src_next.llm.qwen_http 时出现重复加载 warning。
"""

from .base import BaseLLMClient, LLMError

__all__ = [
    "BaseLLMClient",
    "LLMError",
]
