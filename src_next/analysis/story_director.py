"""src_next/analysis/story_director.py

导演计划生成（每段一个 DirectorInstruction）。

数据流位置：
    Segment[] + CharacterProfile[]
        → generate_director_plan(segments, characters, llm_client)
        → DirectorInstruction[]（和 segments 一一对应，顺序一致）

策略（v1 简化版）：
    1. 一次性把所有 segment + 角色档案打包丢给 LLM。
    2. LLM 返回 ``segment_directions`` 列表。
    3. 缺失字段 / 缺失 segment → 走 fallback：
       * narrator 段：emotion=calm / pace=0.95 / tone=warm / pause=0.6s
       * dialogue 段：根据末尾标点给情绪（？→ surprised，！→ excited，。→ calm）
    4. 单段失败不阻塞。

参考旧 src/story_director.py：
- overall_style + segment_directions 双层结构；
- emphasis_words / pause_after_ms / needs_review 等字段；
- 解析失败时保存 raw 文本到 ``output/debug`` 便于排错。

本层 v1 简化：
- 不再生成 overall_style（v1 每段独立判断，不做整体基调推断）；
- 不再生成 emphasis_words / needs_review（v1 只要 5 个字段，保持和
  ``src_next.core.data_models.DirectorInstruction`` 字段一致）；
- ``pause_after_ms`` 改为 ``pause_hint``（秒，浮点）。
"""

from __future__ import annotations

from typing import Any

from ..core.data_models import CharacterProfile, DirectorInstruction, Segment
from ..llm.base import BaseLLMClient, LLMError


# ── LLM prompt ─────────────────────────────────────────────────────────────

_DIRECTOR_SYSTEM_PROMPT = """你是一个中文有声书导演。根据每个文本片段的内容、说话人、角色档案，生成朗读指导。

严格输出 JSON，结构如下：

{
  "segment_directions": [
    {
      "segment_id": "seg_001",
      "emotion": "情绪关键词：neutral / warm / happy / sad / angry / fearful / surprised / disgusted / excited / calm",
      "pace": 1.0,
      "tone": "normal / warm / sharp / soft / deep / bright",
      "pause_hint": 0.5,
      "delivery_instruction": "一句话朗读指导"
    }
  ]
}

要求：
- segment_directions 数量必须等于输入 segment 数量
- 每个 segment_id 都必须出现且唯一
- pace 范围 0.8~1.2，1.0 为正常速
- pause_hint 范围 0.0~2.0，单位秒
- emotion 必须是上面列出的有效情绪词
- delivery_instruction 不超过 30 个汉字

判断依据：
- narrator 段：回忆性叙述偏 warm + 慢；描写性叙述偏 calm + 正常速；转折处可加快
- dialogue 段：根据角色性格 + 标点 + 上下文判断情绪
- 段尾长停（0.5~1.0s），段内戏剧性时刻可加停顿
"""


# ── 入口函数 ────────────────────────────────────────────────────────────────

def generate_director_plan(
    segments: list[Segment],
    characters: list[CharacterProfile],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[DirectorInstruction]:
    """为每个 segment 生成一条 DirectorInstruction。

    Args:
        segments: resolved segments。
        characters: ``analyze_characters`` 的输出（含 narrator）。
        llm_client: 任意 ``BaseLLMClient`` 实现。
        story_context: 故事上下文（可选）。

    Returns:
        DirectorInstruction 列表，长度严格等于 segments，按 segment 顺序排列。
    """
    if not segments:
        return []

    char_map = {c.name: c for c in characters}
    llm_dirs = _direct_via_llm(segments, characters, llm_client, story_context)
    id_to_dir = {d["segment_id"]: d for d in llm_dirs}

    plan: list[DirectorInstruction] = []
    for seg in segments:
        raw = id_to_dir.get(seg.segment_id)
        if raw:
            plan.append(_build_instruction_from_llm(seg, raw))
        else:
            plan.append(_fallback_instruction(seg, char_map.get(seg.speaker)))
    return plan


# ── LLM 调用 ────────────────────────────────────────────────────────────────

def _direct_via_llm(
    segments: list[Segment],
    characters: list[CharacterProfile],
    llm_client: BaseLLMClient,
    story_context: str,
) -> list[dict[str, Any]]:
    if not segments:
        return []

    prompt = _build_director_prompt(segments, characters, story_context)
    try:
        result = llm_client.generate_json(
            prompt, system_prompt=_DIRECTOR_SYSTEM_PROMPT
        )
    except LLMError:
        return []
    except Exception:  # noqa: BLE001
        return []

    return _extract_directions(result, expected_ids=[s.segment_id for s in segments])


def _build_director_prompt(
    segments: list[Segment],
    characters: list[CharacterProfile],
    story_context: str,
) -> str:
    parts: list[str] = []
    if story_context:
        parts.append(f"## 故事上下文\n\n{story_context}")

    parts.append("\n## 角色档案\n")
    for c in characters:
        parts.append(
            f"- {c.name} ({c.role_type}/{c.gender or '?'}/{c.age_style or '?'}): "
            f"{c.personality or '无描述'}"
        )

    parts.append("\n## 需要指导的片段\n")
    for seg in segments:
        parts.append(
            f"- [{seg.segment_id}] speaker={seg.speaker}, type={seg.segment_type}\n"
            f"  text={seg.text}"
        )

    parts.append(
        "\n请为以上每个片段输出 segment_directions，数量必须等于输入片段数。"
    )
    return "\n".join(parts)


def _extract_directions(
    result: Any,
    *,
    expected_ids: list[str],
) -> list[dict[str, Any]]:
    """从 LLM 返回里抠出 segment_directions。

    兼容多种形状；只保留 segment_id 在 expected_ids 里的项。
    """
    raw_list: list[dict[str, Any]] = []
    if isinstance(result, dict):
        dirs = result.get("segment_directions")
        if isinstance(dirs, list):
            raw_list = [d for d in dirs if isinstance(d, dict)]
        elif "segment_id" in result:
            raw_list = [result]
    elif isinstance(result, list):
        raw_list = [d for d in result if isinstance(d, dict)]

    expected = set(expected_ids)
    return [d for d in raw_list if str(d.get("segment_id") or "") in expected]


def _build_instruction_from_llm(
    seg: Segment, raw: dict[str, Any]
) -> DirectorInstruction:
    return DirectorInstruction(
        segment_id=seg.segment_id,
        speaker=seg.speaker,
        emotion=_clean_emotion(raw.get("emotion")),
        pace=_clean_pace(raw.get("pace")),
        tone=_clean_tone(raw.get("tone")),
        pause_hint=_clean_pause(raw.get("pause_hint")),
        delivery_instruction=_clean_delivery(raw.get("delivery_instruction")),
    )


# ── Fallback ───────────────────────────────────────────────────────────────

# 末尾标点 → 情绪（dialogue 段没有 LLM 结果时的兜底）
_PUNCT_EMOTION_MAP = (
    ("？", "surprised"),
    ("?", "surprised"),
    ("！", "excited"),
    ("!", "excited"),
    ("…", "sad"),
    ("。", "calm"),
)


def _fallback_instruction(
    seg: Segment, char: CharacterProfile | None
) -> DirectorInstruction:
    """LLM 没覆盖到该 segment 时的兜底。

    按用户规格：
        narrator / narration → neutral / 1.0 / normal
        dialogue             → 根据末尾标点给情绪
    """
    if seg.segment_type == "dialogue":
        emotion = "neutral"
        for pc, emo in _PUNCT_EMOTION_MAP:
            if pc in seg.text:
                emotion = emo
                break
        pace = 1.0
        tone = "normal"
        pause_hint = 0.4
        delivery = "自然对白语气"
    else:
        # narration / narrator：按 spec 用 neutral / 1.0 / normal
        emotion = "neutral"
        pace = 1.0
        tone = "normal"
        pause_hint = 0.6
        delivery = "平稳叙述"

    return DirectorInstruction(
        segment_id=seg.segment_id,
        speaker=seg.speaker,
        emotion=emotion,
        pace=pace,
        tone=tone,
        pause_hint=pause_hint,
        delivery_instruction=delivery,
    )


# ── 字段清洗 ────────────────────────────────────────────────────────────────

_VALID_EMOTIONS = {
    "neutral", "warm", "happy", "sad", "angry",
    "fearful", "surprised", "disgusted", "excited", "calm",
}

_VALID_TONES = {"normal", "warm", "sharp", "soft", "deep", "bright"}


def _clean_emotion(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    return s if s in _VALID_EMOTIONS else "neutral"


def _clean_tone(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    return s if s in _VALID_TONES else "normal"


def _clean_pace(raw: Any) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if v < 0.8:
        return 0.8
    if v > 1.2:
        return 1.2
    return v


def _clean_pause(raw: Any) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.4
    if v < 0.0:
        return 0.0
    if v > 2.0:
        return 2.0
    return v


def _clean_delivery(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if len(s) > 60:
        s = s[:60]
    return s
