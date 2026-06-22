"""src_next/llm/base.py

统一 LLM 接口定义。

所有 LLM 后端（Mock / Qwen / Gemma4 / 未来 local）都要实现 BaseLLMClient。
analysis 层（story_resolver / character_analyzer / story_director）只能依赖
这个抽象接口，不能直接 import 具体后端，这样后续切换模型不需要改业务代码。
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMError(Exception):
    """LLM 调用失败的统一异常。

    所有 BaseLLMClient 实现都需要把底层错误（HTTP 错误码、超时、JSON 解析失败、
    配置缺失）包装成 LLMError 抛出。这样上层只需要 catch 一种异常。
    """


class BaseLLMClient(ABC):
    """所有 LLM 后端的统一接口。

    只暴露两个方法：
    * generate_text(prompt, **kwargs) -> str
      接收 prompt，返回模型生成的纯文本。

    * generate_json(prompt, **kwargs) -> dict | list
      接收 prompt，返回已解析的 JSON 对象。
      具体后端负责处理 ```json 代码块剥离 / 首尾解释性文字剔除 / json.loads。
      解析失败时抛 LLMError。

    kwargs 由具体后端解释（常见字段：system_prompt / max_tokens / temperature /
    timeout）。analysis 层不假设 kwargs 一定被使用，只把它们当 optional。
    """

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """接收 prompt，返回模型生成的纯文本。"""

    @abstractmethod
    def generate_json(self, prompt: str, **kwargs: Any) -> dict | list:
        """接收 prompt，返回已解析的 JSON（dict 或 list）。解析失败抛 LLMError。"""
