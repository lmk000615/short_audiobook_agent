"""Qwen3-Omni 音频评估客户端。

调 Qwen3-Omni 服务的 /v1/omni/audio_analysis 端点（黄区 10.50.121.102:8011），
让模型"听"一段 TTS 合成音频，输出 5 维评分 + 修复建议。

⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。

⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
如果服务返回的不是评分 JSON，按 KNOWN_ISSUES.md §2 切换到 /v1/omni/chat。
"""
from __future__ import annotations

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


class Qwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频质量。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        timeout: int = 120,
        bypass_proxy: bool = True,
    ) -> None:
        """
        Args:
            base_url: Qwen3-Omni 服务地址（默认黄区 8011）。
            timeout: 单次评估超时（秒）。Qwen3-Omni 单请求较慢，建议 120s+。
            bypass_proxy: 是否绕过系统代理（黄区内网 true）。
        """
        self.base_url = base_url
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
