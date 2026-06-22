"""src_next/analysis/character_analyzer.py

角色档案生成（CharacterProfile 列表）。

数据流位置：
    Segment[]（已 resolve_speakers 处理过）
        → analyze_characters(segments, llm_client)
        → CharacterProfile[]（narrator 必在 index=0）

策略（v1 简化版）：
    1. 永远先放 narrator：用稳定 voice_prompt（参考旧 src/character_analyzer.py 的
       ``_NARRATOR_PROFILE``，精简成一句自然语言描述，供 Qwen VoiceGenerator 消费）。
    2. 从 segments 里按首次出现顺序收集所有非 narrator / 非 unknown 的 speaker。
    3. 把这些 speaker 一次性丢给 LLM 生成档案。
    4. LLM 返回结构异常（包括 MockLLM 的占位 dict）→ 每个 speaker 走 fallback
       （根据名字关键词猜动物 / 老人 / 儿童，给一个低 confidence 档案）。
    5. 单角色失败不阻塞其他角色。

参考旧 src/character_analyzer.py：
- narrator 硬编码，不走 LLM；
- voice_instruction 用自然语言一句话描述，便于后续 TTS 直接消费；
- 角色 prompt 列出 gender / age / timbre / role_type / confidence 字段。

本层与旧 src 的差异：
- 字段从旧版 dict 改为 ``src_next.core.data_models.CharacterProfile`` dataclass；
- ``timbre`` 字段并入 voice_prompt 自然语言描述，不再单独保留；
- ``voice_prompt`` 强约束 ``用...说`` 格式，便于透传到 Qwen VoiceGenerator 的 ``--instruct``；
- 不再生成 ``reason`` 字段（debug 时看 LLM 原始日志即可）。
"""

from __future__ import annotations

from typing import Any

from ..core.data_models import CharacterProfile, Segment
from ..llm.base import BaseLLMClient, LLMError


# ── narrator 固定档案 ──────────────────────────────────────────────────────

_NARRATOR_VOICE_PROMPT = "用温柔亲切的年轻女声说书人嗓音说"


def _default_narrator() -> CharacterProfile:
    return CharacterProfile(
        name="narrator",
        role_type="narrator",
        gender="female",
        age_style="young",
        personality="温柔亲切，平稳客观",
        voice_prompt=_NARRATOR_VOICE_PROMPT,
        confidence=0.95,
    )


# ── LLM prompt ─────────────────────────────────────────────────────────────

_CHARACTER_SYSTEM_PROMPT = """你是一个中文故事角色声音分析师。根据每个角色的台词和故事上下文，为角色生成声音档案。

严格输出 JSON，结构如下：

{
  "characters": [
    {
      "name": "角色名",
      "gender": "male / female",
      "age_style": "child / young / middle_aged / elderly",
      "personality": "一句话描述角色性格",
      "voice_prompt": "用...的嗓音说（开头必须是'用'，结尾必须是'说'）",
      "confidence": 0.0~1.0
    }
  ]
}

要求：
- characters 数组长度必须等于输入的角色数
- voice_prompt 必须以 "用" 开头、以 "说" 结尾，长度 10~30 个汉字
- voice_prompt 必须包含性别 + 年龄感 + 音色特征，便于 Qwen3-TTS VoiceDesign 直接作为 --instruct 参数
- 性别不确定时优先标 confidence<0.6
- 不能确定的角色也必须输出（confidence 标低），不能省略
"""


# ── 动物 / 老人 / 儿童 关键词（fallback 用） ────────────────────────────────

_ANIMAL_KEYWORDS = (
    "松鼠", "兔子", "狐狸", "猫", "狗", "熊", "虎", "狮", "狼", "鹿",
    "猴", "鸡", "鸭", "鹅", "鱼", "龟", "乌鸦", "鸟", "蚱蜢", "蚂蚁",
    "蝴蝶", "蜜蜂", "龙", "蛇", "马", "牛", "羊", "猪", "鼠", "大象",
    "老鼠", "乌龟", "鹦鹉", "燕子", "麻雀", "喜鹊", "青蛙", "螃蟹",
)

_ELDERLY_KEYWORDS = ("老", "爷爷", "奶奶", "公公", "婆婆", "大叔", "大婶", "先生")

_CHILD_KEYWORDS = ("小宝宝", "宝宝", "孩", "童", "弟弟", "妹妹", "小男孩", "小女孩")


# ── 入口函数 ────────────────────────────────────────────────────────────────

def analyze_characters(
    segments: list[Segment],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[CharacterProfile]:
    """从 resolved segments 生成 CharacterProfile 列表。

    Args:
        segments: 已经跑过 ``resolve_speakers`` 的 Segment 列表（speaker 已填充）。
        llm_client: 实现 ``BaseLLMClient`` 的任意后端。
        story_context: 故事标题 / 章节信息，附加给 LLM。

    Returns:
        CharacterProfile 列表。narrator 永远在 index=0；其余按 speaker 首次出现顺序。
        单角色 LLM 失败时走 fallback，不会丢角色。
    """
    narrator = _default_narrator()
    unique_speakers = _extract_unique_speakers(segments)
    if not unique_speakers:
        return [narrator]

    profiles = _analyze_via_llm(unique_speakers, segments, llm_client, story_context)

    # 用 LLM 结果填充；缺失的角色走 fallback
    characters: list[CharacterProfile] = [narrator]
    for name in unique_speakers:
        profile = profiles.get(name)
        characters.append(profile if profile else _fallback_character_profile(name))
    return characters


# ── 内部工具 ────────────────────────────────────────────────────────────────

def _extract_unique_speakers(segments: list[Segment]) -> list[str]:
    """按首次出现顺序收集 speaker，排除 narrator / unknown / 空。"""
    seen: set[str] = set()
    ordered: list[str] = []
    for seg in segments:
        name = (seg.speaker or "").strip()
        if not name or name in ("narrator", "unknown"):
            continue
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _analyze_via_llm(
    speakers: list[str],
    segments: list[Segment],
    llm_client: BaseLLMClient,
    story_context: str,
) -> dict[str, CharacterProfile]:
    """调用 LLM 一次性分析所有 speaker。

    LLM 失败 / 结构异常时返回空 dict，让上层走 fallback。
    """
    if not speakers:
        return {}

    prompt = _build_character_prompt(speakers, segments, story_context)
    try:
        result = llm_client.generate_json(
            prompt, system_prompt=_CHARACTER_SYSTEM_PROMPT
        )
    except LLMError:
        return {}
    except Exception:  # noqa: BLE001
        return {}

    return _extract_character_profiles(result)


def _build_character_prompt(
    speakers: list[str],
    segments: list[Segment],
    story_context: str,
) -> str:
    parts: list[str] = []
    if story_context:
        parts.append(f"## 故事上下文\n\n{story_context}")

    # 每个 speaker 收集前 3 条代表性台词，给 LLM 判断素材
    lines_by_speaker: dict[str, list[str]] = {name: [] for name in speakers}
    for seg in segments:
        name = (seg.speaker or "").strip()
        if name in lines_by_speaker and len(lines_by_speaker[name]) < 3:
            lines_by_speaker[name].append(seg.text)

    parts.append("\n## 角色与台词\n")
    for name in speakers:
        parts.append(f"### {name}")
        for line in lines_by_speaker[name]:
            parts.append(f"- {line}")
        if not lines_by_speaker[name]:
            parts.append("- （无对白）")

    parts.append(
        "\n请为以上每个角色输出声音档案，characters 数组长度必须等于输入角色数。"
    )
    return "\n".join(parts)


def _extract_character_profiles(result: Any) -> dict[str, CharacterProfile]:
    """从 LLM 返回里抠出 {name: CharacterProfile}。

    兼容：
    * ``{"characters": [...]}``   ← 期望
    * ``[{"name": ...}, ...]``    ← 旧 list 形式
    * ``{"source": "mock", ...}`` ← MockLLMClient 默认 dict，不匹配 → 返回空
    """
    raw_list: list[dict[str, Any]] = []
    if isinstance(result, dict):
        chars = result.get("characters")
        if isinstance(chars, list):
            raw_list = [c for c in chars if isinstance(c, dict)]
        elif "name" in result:
            raw_list = [result]
    elif isinstance(result, list):
        raw_list = [c for c in result if isinstance(c, dict)]

    profiles: dict[str, CharacterProfile] = {}
    for raw in raw_list:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        profiles[name] = _build_profile_from_llm(name, raw)
    return profiles


def _build_profile_from_llm(name: str, raw: dict[str, Any]) -> CharacterProfile:
    """从单条 LLM 输出构造 CharacterProfile，字段缺失时用合理默认。"""
    gender = _clean_str(raw.get("gender"), valid={"male", "female"})
    age_style = _clean_str(
        raw.get("age_style"),
        valid={"child", "young", "middle_aged", "elderly"},
    )
    personality = str(raw.get("personality") or "").strip() or None
    voice_prompt = _clean_voice_prompt(raw.get("voice_prompt"), name)
    confidence = _clean_confidence(raw.get("confidence"), default=0.6)

    return CharacterProfile(
        name=name,
        role_type="character",
        gender=gender,
        age_style=age_style,
        personality=personality,
        voice_prompt=voice_prompt,
        confidence=confidence,
    )


def _clean_voice_prompt(raw: Any, name: str) -> str:
    """voice_prompt 必须是 ``用...说`` 格式；不达标时按 name 走 fallback。"""
    s = str(raw or "").strip()
    if s.startswith("用") and s.endswith("说") and 8 <= len(s) <= 60:
        return s
    return _fallback_voice_prompt(name)


def _fallback_voice_prompt(name: str) -> str:
    """根据名字关键词生成兜底 voice_prompt。

    判断顺序：老人 > 儿童 > 动物 > 默认。
    顺序很关键：``老乌龟`` 同时命中 ``老``（老人）和 ``乌龟``（动物），
    老人优先才能拿到 ``沉稳温暖的老者嗓音说``。
    """
    if any(kw in name for kw in _ELDERLY_KEYWORDS):
        return "用沉稳温暖的老者嗓音说"
    if any(kw in name for kw in _CHILD_KEYWORDS):
        return "用天真可爱的童声说"
    if any(kw in name for kw in _ANIMAL_KEYWORDS):
        # 小动物默认偏儿童感 / female 倾向（儿童故事常见设定）
        return "用清亮活泼的童声说"
    return "用自然真实的人声说"


def _fallback_character_profile(name: str) -> CharacterProfile:
    """LLM 完全没覆盖到该角色时的最终 fallback。

    判断顺序同 ``_fallback_voice_prompt``：老人 > 儿童 > 动物 > 默认。
    """
    if any(kw in name for kw in _ELDERLY_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="male",
            age_style="elderly",
            personality="沉稳",
            voice_prompt="用沉稳温暖的老者嗓音说",
            confidence=0.4,
        )
    if any(kw in name for kw in _CHILD_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="female",
            age_style="child",
            personality="天真",
            voice_prompt="用天真可爱的童声说",
            confidence=0.4,
        )
    if any(kw in name for kw in _ANIMAL_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="female",
            age_style="child",
            personality="活泼",
            voice_prompt="用清亮活泼的童声说",
            confidence=0.4,
        )
    return CharacterProfile(
        name=name,
        role_type="character",
        gender=None,
        age_style=None,
        personality=None,
        voice_prompt="用自然真实的人声说",
        confidence=0.3,
    )


def _clean_str(raw: Any, *, valid: set[str]) -> str | None:
    s = str(raw or "").strip().lower()
    return s if s in valid else None


def _clean_confidence(raw: Any, *, default: float) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v
