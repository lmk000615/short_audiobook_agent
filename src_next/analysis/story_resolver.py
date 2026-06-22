"""src_next/analysis/story_resolver.py

说话人识别 / 段落类型识别（产出 resolved segments）。

数据流位置：
    Segment[]（来自 core.segment_builder）
        → resolve_speakers(segments, llm_client)
        → Segment[]（speaker / segment_type 已更新的深拷贝）

策略（v1 简化版）：
    1. 规则识别优先：每个 segment 用正则匹配 ``X + 状态副词 + 说/问/道 + 标点`` 模式。
       命中 → speaker=X, segment_type=dialogue。
    2. 无引号 + 无动词模式 → speaker=narrator, segment_type=narration。
    3. 有引号但规则没识别出归属 → 暂时标 speaker=unknown, segment_type=unknown，
       留给 LLM 兜底。
    4. 所有 unknown 段批量打包丢给 LLM。
    5. LLM 失败 / 返回结构异常 → unknown 全部 fallback 成 narrator。
    6. 单段失败不阻塞其他段。

参考旧 src/llm_story_resolver.py：
- 引号类型 + 说话人的 prompt 设计思路；
- ```` ```json ```` 代码块剥离 / 多余解释文字剔除的容错由 BaseLLMClient 兜底，
  本层不再自己写 regex 抠 JSON。

本文件不做的事：
- 不发 HTTP 请求；
- 不读 .env；
- 不 import QwenHTTPClient / Gemma4HTTPClient；
- 不再做 ``段落 → part`` 的二级切分（旧 src 有，src_next 已经按段处理）。
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from ..core.data_models import Segment
from ..llm.base import BaseLLMClient, LLMError


# ── 常量 ────────────────────────────────────────────────────────────────────
#
# 用 \u 转义书写所有非 ASCII 引号 / 标点，避免和 Python 字符串字面量定界符冲突：
#   “  "  LEFT DOUBLE QUOTATION MARK
#   ”  "  RIGHT DOUBLE QUOTATION MARK
#   ‘  '  LEFT SINGLE QUOTATION MARK
#   ’  '  RIGHT SINGLE QUOTATION MARK
#   「  「
#   」  」
#   『  『
#   』  』
#   ：  ：
#   ，  ，
#   。  。
#   ！  ！
#   ？  ？
#   、  、
#   ；  ；

_SMART_QUOTES = "“”‘’「」『』"

# speaker 名字里不允许出现的字符：空白 + 中英文标点 + 各类引号
# （用 \u 转义拼接，避免在源码里出现裸的 " ' 导致 Python lexer 误解）
_SPEAKER_FORBIDDEN = (
    " \t\n\r"
    "：:,，。！？、；;."
    "“”‘’「」『』"
    "\'\""  # ASCII single + double quote
)

# 动词后面允许出现的字符（lookahead）：冒号 / 逗号 / 各类引号
_LOOKAHEAD_CHARS = (
    "：:,，"
    "“”‘’「」『』"
)

# 说话人 + 可选副词 + 动词 + 标点 / 引号（lookahead）
# 副词和动词都按长度从长到短排列，避免 ``说`` 抢先吞掉 ``笑着说``。
_SPEAKER_PATTERN = re.compile(
    r'(?:^|[\n\s，。！？、；])'
    r'([^' + re.escape(_SPEAKER_FORBIDDEN) + r']{1,6}?)'
    r'(?:笑着|哭着|高兴地|伤心地|'
    r'生气地|慢慢地|轻轻地|'
    r'大声|小声|冷冷地|淡淡地)?'
    r'(?:说道|问道|答道|喊道|叫道|'
    r'笑道|回答|询问|说|问|答|道|喊|叫)'
    r'(?=[' + re.escape(_LOOKAHEAD_CHARS) + r'])'
)
# 副词 / 动词的字面对照（便于阅读，不参与运行）：
#   笑着 / 哭着 / 高兴地 / 伤心地 / 生气地 / 慢慢地 / 轻轻地 / 大声 / 小声 / 冷冷地 / 淡淡地
#   说道 / 问道 / 答道 / 喊道 / 叫道 / 笑道 / 回答 / 询问 / 说 / 问 / 答 / 道 / 喊 / 叫


_RESOLVER_SYSTEM_PROMPT = """你是一个中文故事对话分析师。给定若干文本片段，判断每个片段的 segment_id、说话人、段落类型。

严格输出 JSON，结构如下：

{
  "resolutions": [
    {
      "segment_id": "seg_001",
      "speaker": "说话人名称；没有对白时填 narrator",
      "segment_type": "narration / dialogue / unknown",
      "confidence": 0.0~1.0
    }
  ]
}

判断依据：
- 没有引号且没有 "X说/问/道" 模式 → narration，speaker=narrator
- 引号前有明确的 "X说/问/道" → dialogue，speaker=X
- 心理活动（"心想"、"暗想"）→ dialogue，speaker=对应角色
- 无法判断 → unknown，speaker=narrator

要求：
- resolutions 数量必须等于输入的 segment 数量
- 每个 segment_id 都必须出现且唯一
- speaker 字符串尽量短（角色名 1~6 字），不要包含标点
- confidence 是 0.0~1.0 的浮点数
"""


# ── 入口函数 ────────────────────────────────────────────────────────────────

def resolve_speakers(
    segments: list[Segment],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[Segment]:
    """识别每个 segment 的 speaker 和 segment_type。

    Args:
        segments: ``core.segment_builder.build_segments()`` 输出的 Segment 列表。
        llm_client: 实现 ``BaseLLMClient`` 的任意后端（Mock / Qwen / Gemma4）。
        story_context: 故事标题 / 章节信息 / 已知角色列表，附加给 LLM 提示。

    Returns:
        新的 Segment 列表（深拷贝，入参不变）。每个 segment 的 speaker 和
        segment_type 都被填充；无法判断的统一 fallback 成 narrator / narration。
    """
    if not segments:
        return []

    # 第一遍：规则识别。在副本上改，不动入参。
    resolved: list[Segment] = [deepcopy(seg) for seg in segments]
    for seg in resolved:
        speaker, seg_type = _rule_based_classify(seg.text)
        seg.speaker = speaker
        seg.segment_type = seg_type

    # 第二遍：批量 LLM 兜底 unknown 段。
    unknown_segs = [seg for seg in resolved if seg.segment_type == "unknown"]
    if unknown_segs:
        resolutions = _resolve_via_llm(unknown_segs, llm_client, story_context)
        id_to_res = {r["segment_id"]: r for r in resolutions}
        for seg in unknown_segs:
            res = id_to_res.get(seg.segment_id)
            if res:
                seg.speaker = _clean_speaker(res.get("speaker") or "narrator")
                seg.segment_type = _clean_seg_type(res.get("segment_type"))
            else:
                seg.speaker = "narrator"
                seg.segment_type = "narration"

    # 兜底：所有仍为 unknown 的段（LLM 没覆盖到）→ narrator
    for seg in resolved:
        if seg.segment_type == "unknown" or not seg.speaker:
            seg.speaker = "narrator"
            seg.segment_type = "narration"

    return resolved


# ── 规则识别 ────────────────────────────────────────────────────────────────

def _rule_based_classify(text: str) -> tuple[str, str]:
    """返回 (speaker, segment_type)。

    speaker 可能是 ``unknown``（表示需要 LLM 进一步判断）。
    """
    if not text or not text.strip():
        return ("narrator", "narration")

    # 先找 "X + 状态副词 + 动词 + 标点 / 引号" 模式
    match = _SPEAKER_PATTERN.search(text)
    if match:
        speaker = _clean_speaker(match.group(1))
        if speaker:
            return (speaker, "dialogue")

    # 没匹配到动词 + 标点，但文本里有引号 → 交给 LLM
    if _has_quote(text):
        return ("unknown", "unknown")

    # 纯叙述
    return ("narrator", "narration")


def _has_quote(text: str) -> bool:
    return any(q in text for q in _SMART_QUOTES)


def _clean_speaker(raw: Any) -> str:
    """清洗 speaker 字符串：去空白 / 标点 / 引号；超长截断。"""
    if not raw:
        return ""
    s = str(raw).strip()
    # strip 掉首尾可能残留的标点 / 引号 / 空白
    s = s.strip(_SPEAKER_FORBIDDEN)
    if len(s) > 8:
        s = s[:8]
    return s


def _clean_seg_type(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("narration", "dialogue", "unknown"):
        return s
    return "narration"


# ── LLM 调用 ────────────────────────────────────────────────────────────────

def _resolve_via_llm(
    unknown_segs: list[Segment],
    llm_client: BaseLLMClient,
    story_context: str,
) -> list[dict[str, Any]]:
    """批量调用 LLM 解析 unknown 段。

    失败 / 结构异常时返回空列表（让上层走 narrator 兜底）。
    """
    if not unknown_segs:
        return []

    prompt = _build_resolver_prompt(unknown_segs, story_context)
    try:
        result = llm_client.generate_json(
            prompt, system_prompt=_RESOLVER_SYSTEM_PROMPT
        )
    except LLMError:
        return []
    except Exception:  # noqa: BLE001
        # 任何意外都不能让整条链路挂
        return []

    return _extract_resolutions(result)


def _build_resolver_prompt(segs: list[Segment], story_context: str) -> str:
    parts: list[str] = []
    if story_context:
        parts.append(f"## 故事上下文\n\n{story_context}")

    parts.append("## 待判断的片段\n")
    for seg in segs:
        parts.append(f"- segment_id={seg.segment_id}\n  text={seg.text}")

    parts.append(
        "\n请对以上片段输出 resolutions，"
        "数量必须等于输入片段数，segment_id 必须一一对应。"
    )
    return "\n".join(parts)


def _extract_resolutions(result: Any) -> list[dict[str, Any]]:
    """从 LLM 返回里抠出 resolutions 列表。

    兼容多种形状：
    * ``{"resolutions": [...]}``  ← 期望
    * ``[{segment_id, ...}, ...]``← 旧 list 形式
    * ``{"source": "mock", ...}`` ← MockLLMClient 默认 dict
    * 其他任何异常形状

    MockLLM / 异常形状 → 返回空列表。
    """
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]

    if isinstance(result, dict):
        resolutions = result.get("resolutions")
        if isinstance(resolutions, list):
            return [r for r in resolutions if isinstance(r, dict)]
        # dict 看起来像单条 resolution（有 segment_id / speaker 字段）
        if "segment_id" in result or "speaker" in result:
            return [result]

    return []
