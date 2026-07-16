"""属性感知 Qwen3-Omni 音频评估客户端（与 qwen3omni_critic.py 并存）。

差异（vs ``Qwen3OmniCritic``）：
- evaluate 多接收一个 ``DirectorInstruction`` 参数，作为期望属性的真相源
- 调 ``build_attribute_critic_prompt`` 而非 ``build_critic_prompt``
- 返回 ``AttributeAwareCriticResult``（含 extracted/expected/consistency 三段）
- 失败 fallback 调 ``AttributeAwareCriticResult.neutral``

复用（来自 ``qwen3omni_critic.py``）：
- ``_parse_scoring_json``：JSON 解析三步 fallback（去 fence → json.loads → raw_decode）
- HTTP 端点 / payload 结构 / base64 编码 / proxy 配置全部一致

不抽公共基类：本次是并存方案，过早抽象会绑死未来去留。HTTP 调用代码物理复制
（约 15 行）的成本可接受，换取解耦。

⚠️ 与 ``Qwen3OmniCritic`` 同样：服务端有 infer_lock，同一时间只处理一个请求——
本客户端不做并发，上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from src_next.core.data_models import (
    DirectorInstruction,
    ModelSpecificTTSInstruction,
    Segment,
)
from src_next.critic.attribute_result import AttributeAwareCriticResult
from src_next.critic.prompts.attribute_critic_prompt import (
    build_attribute_critic_prompt,
)
from src_next.critic.qwen3omni_critic import _parse_scoring_json


class AttributeAwareQwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频（属性提取 + 一致性 + 5 维评分）。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        timeout: int = 120,
        bypass_proxy: bool = True,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
        self._proxies = {"http": None, "https": None} if bypass_proxy else None

    def evaluate(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
        director_instruction: DirectorInstruction,
    ) -> AttributeAwareCriticResult:
        """评估单段音频。失败不抛异常，返回 overall=0.5 中性结果（带 director 渲染）。"""
        try:
            return self._evaluate_inner(
                audio_path, segment, tts_instruction, director_instruction
            )
        except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback
            return AttributeAwareCriticResult.neutral(
                segment_id=segment.segment_id,
                attempt=tts_instruction.attempt,
                director_instruction=director_instruction,
                err_msg=str(exc),
            )

    def _evaluate_inner(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
        director_instruction: DirectorInstruction,
    ) -> AttributeAwareCriticResult:
        prompt_text = build_attribute_critic_prompt(
            segment, tts_instruction, director_instruction
        )
        audio_b64 = base64.b64encode(Path(audio_path).read_bytes()).decode("ascii")
        payload = {
            "audio": audio_b64,
            "text": prompt_text,
            "return_audio": False,
            "max_new_tokens": 1024,
        }
        url = f"{self.base_url}/v1/omni/chat"
        resp = requests.post(
            url,
            json=payload,
            proxies=self._proxies,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"omni/chat returned HTTP {resp.status_code}: {resp.text[:200]!r}"
            )
        data = resp.json()
        raw_text = str(data.get("text", ""))
        if not raw_text:
            raise RuntimeError("omni/chat returned empty text field")
        scoring = _parse_scoring_json(raw_text)
        return AttributeAwareCriticResult.from_json(
            raw_llm_output=scoring,
            director_instruction=director_instruction,
            segment_id=segment.segment_id,
            attempt=tts_instruction.attempt,
        )
