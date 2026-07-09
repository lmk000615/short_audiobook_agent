"""src_next/analysis/character_analyzer.py

角色档案生成（CharacterProfile 列表）。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..core.data_models import CharacterProfile, Segment
from ..llm.base import BaseLLMClient, LLMError

# ── narrator 固定档案 ──────────────────────────────────────────────────────

_NARRATOR_VOICE_PROMPT = "音色柔和温暖的青年女性声音，语速平稳，吐字清晰，气息较轻"


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


# ── 安全称谓后缀（fallback 用） ─────────────────────────────────────────────

_SAFE_TITLES = (
    "先生", "女士", "老师", "师傅", "同志", "小姐",
    "大叔", "阿姨", "爷爷", "奶奶",
)


# ── LLM prompt ─────────────────────────────────────────────────────────────

_NARRATOR_SYSTEM_PROMPT = """你是一个中文有声书旁白音色分析师。基于故事全文判断文体风格，推荐最合适的旁白音色。

严格输出 JSON，结构如下：

{
  "gender": "male / female",
  "age_style": "young / middle_aged / elderly",
  "personality": "一句话描述朗读风格",
  "voice_prompt": "声学物理维度描述性短语",
  "genre": "fairy_tale / wuxia / romance / mystery / essay / knowledge / other",
  "confidence": 0.0~1.0
}

文体风格 → 旁白音色参考：

- **fairy_tale**（童话 / 儿童故事 / 寓言）：音色柔和温暖、中音区偏暖、气息较轻的青年女性声音，语速平稳，吐字清晰
- **wuxia**（武侠 / 历史 / 古风）：音色低沉浑厚、中低音区饱满的中年男性声音，语速偏慢，吐字沉稳有力
- **romance**（都市言情 / 言情）：音色纤细柔和、高音区偏暖的青年女性声音，语速适中，气息绵长
- **mystery**（悬疑 / 推理 / 恐怖）：音色低沉干涩、中低音区偏冷的青年或中年男性声音，语速平稳克制
- **essay**（散文 / 抒情 / 随笔）：音色清澈圆润、中音区偏暖的青年女性声音，语速舒缓，气息平稳
- **knowledge**（科普 / 说明 / 教程）：音色清晰明亮、中音区偏干的青年声音，吐字准确，逻辑感强
- **other**：根据文本整体基调灵活判断

voice_prompt 字段要求（**非常重要**）：

- 必须是 Qwen3-TTS VoiceDesign 期望的自然语言描述性短语（**不是「用...说」格式**），长度 15~50 字
- **每个词都必须对应音频模型能理解的声学物理维度**，禁止出现用途性/文学性描述
- 必须明确包含以下 4 个维度：
  * **性别**（男 / 女）
  * **年龄感**（童 / 青年 / 中年 / 老年）
  * **音色物理特征**（必须从以下词中选至少一个：柔和 / 低沉 / 高亢 / 清亮 / 沙哑 / 浑厚 / 纤细 / 圆润 / 干涩 / 苍老 / 清脆 / 饱满 / 气息感 / 鼻音 / 磁性 / 明亮 / 温暖 / 偏冷 / 偏暖）
  * **语气节奏**（平稳 / 缓慢 / 适中 / 偏快 / 克制 / 舒缓 / 有力 / 轻快）
- **禁止**出现以下类型词汇：
  * 用途性描述：「适合讲述XX」「富有XX感」「适合XX叙事」
  * 文学性描述：「灵动」「富有感染力」「画面感」「沧桑感」「智慧感」
  * 「用...说」格式
- 参考写法（声学物理维度版本）：
  * "音色柔和温暖的青年女性声音，语速平稳，吐字清晰，气息较轻"
  * "音色低沉浑厚的中年男性声音，语速缓慢，中低音区饱满"
  * "音色干涩偏冷的中年男性声音，语调平稳克制，吐字清晰"
"""


_CHARACTER_SYSTEM_PROMPT = """你是一个中文故事角色声音分析师。根据故事全文和每个角色的台词，为角色生成声音档案，并合并指代同一角色的别名。

严格输出 JSON，结构如下：

{
  "characters": [
    {
      "name": "canonical 角色名（优先采用原文首次出现且稳定的称呼）",
      "aliases": ["别名1", "别名2"],
      "gender": "male / female",
      "age_style": "child / young / middle_aged / elderly",
      "personality": "一句话描述角色性格",
      "voice_prompt": "声学物理维度描述性短语（15~50字）",
      "confidence": 0.0~1.0
    }
  ],
  "alias_map": {
    "别名": "canonical 名"
  }
}

归并规则（**非常重要**）：
1. 同同一个角色的不同称呼必须合并到一条 character 记录中，canonical 名优先采用原文首次出现且稳定的称呼（优先级：人名 > 职务 > 代词）。
2. aliases 数组列出所有指代该角色的别名（不含 canonical 本身）。
3. alias_map 必须把每个别名映射到 canonical 名；alias_map 的 value 必须出现在 characters[].name 中。
4. 不要凭常识替换原文称呼：原文叫"小明"就不要 canonical 改成"明"；原文叫"豆豆"就不要改成"小豆豆"。
5. 不同角色不得合并：父子关系（"小明" vs "小明爸爸"）、主仆关系、人和动物均不得当作同一角色。
6. narrator 永远独立，不在 characters 数组中。

## voice_prompt 字段要求（**非常重要，必须严格遵守**）

voice_prompt 是供语音合成模型（Qwen3-TTS VoiceDesign / CosyVoice3）消费的音色描述，模型只能理解**声学物理维度**，不理解文学概念。

### 格式要求
- 自然语言描述性短语，长度 15~50 字
- **禁止**「用...说」格式
- **禁止**「用...嗓音说」格式

### 必须包含的 4 个维度（缺一不可）
1. **性别**：男 / 女
2. **年龄感**：童 / 青年 / 中年 / 老年
3. **音色物理特征**：必须从以下词中选至少一个：
   - 音高维度：高亢 / 低沉 / 中音区
   - 音色质感：清亮 / 沙哑 / 浑厚 / 纤细 / 圆润 / 干涩 / 苍老 / 清脆 / 饱满 / 明亮
   - 音色色调：柔和 / 磁性 / 温暖 / 偏冷 / 偏暖
   - 发声特征：气息感 / 鼻音 / 喉音
4. **语气节奏**：平稳 / 缓慢 / 适中 / 偏快 / 克制 / 舒缓 / 有力 / 轻快 / 急促

### 动物角色映射规则（**极其重要**）
语音合成模型只能生成**人类语音**，不理解"动物声音"是什么。所有动物角色必须映射为等价的人类声音描述：
- **禁止**在 voice_prompt 中出现"动物""兽""猴""鹿""兔""狐"等物种词
- 映射原则：根据角色在故事中的**性格和年龄定位**，选择最接近的人类声音
- 映射示例：
  * 小猴（活泼机灵）→ 清亮高亢的少年男孩声音
  * 小鹿（骄傲急躁）→ 音色清脆的少年男孩声音
  * 老山羊（睿智稳重）→ 音色苍老沙哑的老年男性声音
  * 小兔（胆小天真）→ 音色纤细清亮的小女孩声音
  * 狐狸（狡猾阴险）→ 音色低沉偏冷的中年男性声音
  * 大熊（憨厚老实）→ 音色浑厚低沉的中年男性声音
- 关键：映射依据是**角色性格和年龄**，不是动物体型或叫声特征

### 禁止出现的词汇类型
- ❌ 用途性描述：「适合讲述XX」「富有XX感」「适合XX叙事」「适合XX风格」
- ❌ 文学性描述：「灵动」「富有感染力」「画面感」「沧桑感」「智慧感」「故事感」
- ❌ 物种描述：「动物声音」「兽音」「猴叫」
- ❌ 「用...说」格式

### 其他字段要求
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

_ANIMAL_VOICE_MAP: dict[str, tuple[str, str, str]] = {
    "猴": ("male", "child", "音色清亮高亢的少年男孩声音，语速偏快，气息轻快"),
    "松鼠": ("male", "child", "音色清亮急促的少年男孩声音，语速偏快，语气活泼"),
    "兔": ("female", "child", "音色纤细清亮的小女孩声音，语速适中，语气天真"),
    "鹿": ("male", "young", "音色清脆明亮的少年男孩声音，语速适中，吐字有力"),
    "马": ("male", "young", "音色浑厚明亮的青年男性声音，语速适中，吐字沉稳"),
    "狐": ("male", "middle_aged", "音色低沉偏冷的中年男性声音，语速缓慢，语气克制"),
    "蛇": ("male", "middle_aged", "音色低沉干涩的中年男性声音，语速缓慢，气息绵长"),
    "熊": ("male", "middle_aged", "音色浑厚低沉的中年男性声音，语速缓慢，吐字沉稳"),
    "牛": ("male", "middle_aged", "音色浑厚饱满的中年男性声音，语速偏慢，语气沉稳"),
    "羊": ("male", "elderly", "音色苍老沙哑的老年男性声音，语速缓慢，气息较重"),
    "龟": ("male", "elderly", "音色苍老干涩的老年男性声音，语速缓慢，吐字沉稳"),
    "鸟": ("female", "child", "音色清脆高亢的小女孩声音，语速偏快，气息轻快"),
    "燕": ("female", "child", "音色清脆明亮的小女孩声音，语速偏快，语气活泼"),
    "猫": ("female", "child", "音色纤细柔和的小女孩声音，语速适中，语气慵懒"),
    "狗": ("male", "young", "音色清亮明亮的青年男性声音，语速适中，语气忠诚"),
}


# ── 入口函数 ────────────────────────────────────────────────────────────────

def analyze_characters(
    segments: list[Segment],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[CharacterProfile]:
    """从 resolved segments 生成 CharacterProfile 列表（含别名归并）。"""
    narrator = _analyze_narrator_via_llm(story_context, llm_client) or _default_narrator()

    unique_speakers = _extract_unique_speakers(segments)
    if not unique_speakers:
        return [narrator]

    profiles, alias_map = _analyze_via_llm(
        unique_speakers, segments, llm_client, story_context,
    )

    if not alias_map:
        alias_map = _build_alias_map_from_safe_rules(unique_speakers)

    merged = _merge_speakers(unique_speakers, alias_map, profiles)
    ordered = _sort_by_first_appearance(merged, segments)
    return [narrator] + ordered


# ── 内部工具 ────────────────────────────────────────────────────────────────

def _extract_unique_speakers(segments: list[Segment]) -> list[str]:
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
) -> tuple[dict[str, CharacterProfile], dict[str, str]]:
    if not speakers:
        return {}, {}

    prompt = _build_character_prompt(speakers, segments, story_context)
    try:
        result = llm_client.generate_json(
            prompt, system_prompt=_CHARACTER_SYSTEM_PROMPT
        )
    except (LLMError, Exception):
        return {}, {}

    return _extract_character_profiles(result)


def _build_character_prompt(
    speakers: list[str],
    segments: list[Segment],
    story_context: str,
) -> str:
    parts: list[str] = []
    if story_context:
        parts.append(f"## 故事全文（请通读后再判断角色合并）\n\n{story_context}")

    lines_by_speaker: dict[str, list[str]] = {name: [] for name in speakers}
    for seg in segments:
        name = (seg.speaker or "").strip()
        if name in lines_by_speaker and len(lines_by_speaker[name]) < 3:
            lines_by_speaker[name].append(seg.text)

    parts.append("\n## 角色与台词（按首次出现顺序）\n")
    for name in speakers:
        parts.append(f"### {name}")
        for line in lines_by_speaker[name]:
            parts.append(f"- {line}")
        if not lines_by_speaker[name]:
            parts.append("- （无对白）")

    parts.append(
        "\n请基于全文判断 speaker 之间是否存在别名关系，"
        "把指代同一角色的 speaker 合并到 canonical 名（characters[].name），"
        "并在 alias_map 中列出「别名 → canonical 名」映射。"
        "\n\n**再次提醒**：voice_prompt 必须使用声学物理维度描述，"
        "动物角色必须映射为等价的人类声音描述，"
        "禁止出现「动物」「适合」「富有XX感」等非声学维度词汇。"
    )
    return "\n".join(parts)


def _extract_character_profiles(
    result: Any,
) -> tuple[dict[str, CharacterProfile], dict[str, str]]:
    raw_list, alias_map = _parse_llm_output(result)

    profiles: dict[str, CharacterProfile] = {}
    for raw in raw_list:
        name = str(raw.get("name") or "").strip()
        if not name or name == "narrator":
            continue
        profiles[name] = _build_profile_from_llm(name, raw)
    return profiles, alias_map


def _parse_llm_output(result: Any) -> tuple[list[dict[str, Any]], dict[str, str]]:
    raw_list: list[dict[str, Any]] = []
    alias_map: dict[str, str] = {}

    if isinstance(result, dict):
        chars = result.get("characters")
        if isinstance(chars, list):
            raw_list = [c for c in chars if isinstance(c, dict)]
        elif "name" in result:
            raw_list = [result]
        am = result.get("alias_map")
        if isinstance(am, dict):
            alias_map = {
                str(k): str(v)
                for k, v in am.items()
                if isinstance(k, str) and isinstance(v, str)
                and str(k).strip() and str(v).strip()
            }
    elif isinstance(result, list):
        raw_list = [c for c in result if isinstance(c, dict)]

    return raw_list, alias_map


def _build_profile_from_llm(name: str, raw: dict[str, Any]) -> CharacterProfile:
    gender = _clean_str(raw.get("gender"), valid={"male", "female"})
    age_style = _clean_str(
        raw.get("age_style"),
        valid={"child", "young", "middle_aged", "elderly"},
    )
    personality = str(raw.get("personality") or "").strip() or None
    voice_prompt = _clean_voice_prompt(raw.get("voice_prompt"), name)
    confidence = _clean_confidence(raw.get("confidence"), default=0.6)

    aliases_raw = raw.get("aliases") or []
    aliases_clean: list[str] = []
    seen: set[str] = set()
    for a in aliases_raw:
        if not isinstance(a, str):
            continue
        a_str = a.strip()
        if not a_str or a_str == name or a_str in seen:
            continue
        seen.add(a_str)
        aliases_clean.append(a_str)

    return CharacterProfile(
        name=name,
        role_type="character",
        gender=gender,
        age_style=age_style,
        personality=personality,
        voice_prompt=voice_prompt,
        confidence=confidence,
        aliases=aliases_clean,
    )


_FORBIDDEN_VOICE_PROMPT_PATTERNS = (
    "动物", "兽", "适合讲述", "适合叙事", "富有", "画面感",
    "感染力", "灵动", "沧桑感", "智慧感", "故事感",
)


def _clean_voice_prompt(raw: Any, name: str) -> str:
    """voice_prompt 校验与安全规整：必须是声学物理维度描述性短语，长度 15~50 字。"""
    s = str(raw or "").strip()

    # 基础过滤检测
    if s.startswith("用") and s.endswith("说"):
        return _fallback_voice_prompt(name)

    for pattern in _FORBIDDEN_VOICE_PROMPT_PATTERNS:
        if pattern in s:
            return _fallback_voice_prompt(name)

    # 长度策略柔性控制：对稍微超长（50-60字）的文本进行右端安全截断，避免直接触发降级
    if 15 <= len(s) <= 50:
        return s
    elif 50 < len(s) <= 60:
        return s[:50]
    else:
        return _fallback_voice_prompt(name)


def _fallback_voice_prompt(name: str) -> str:
    if any(kw in name for kw in _ELDERLY_KEYWORDS):
        return "音色苍老沙哑的老年男性声音，语速缓慢，气息较重"
    if any(kw in name for kw in _CHILD_KEYWORDS):
        return "音色清亮活泼的童声，语速适中，气息轻快"
    for animal_kw, (_g, _a, vp) in _ANIMAL_VOICE_MAP.items():
        if animal_kw in name:
            return vp
    if any(kw in name for kw in _ANIMAL_KEYWORDS):
        return "音色清亮明亮的少年男孩声音，语速适中，吐字清晰"
    return "音色自然清晰的中年声音，语速平稳，吐字准确"


def _analyze_narrator_via_llm(
    story_context: str,
    llm_client: BaseLLMClient,
) -> CharacterProfile | None:
    if not story_context or len(story_context.strip()) < 20:
        return None

    prompt = (
        f"## 故事全文\n\n{story_context}\n\n"
        "请基于全文判断文体风格，推荐最合适的旁白音色。"
        "voice_prompt 必须使用声学物理维度描述，"
        "禁止出现「适合讲述XX」「富有XX感」等非声学维度词汇。"
    )
    try:
        result = llm_client.generate_json(
            prompt, system_prompt=_NARRATOR_SYSTEM_PROMPT
        )
    except (LLMError, Exception):
        return None

    if not isinstance(result, dict):
        return None

    gender = _clean_str(result.get("gender"), valid={"male", "female"})
    age_style = _clean_str(
        result.get("age_style"),
        valid={"child", "young", "middle_aged", "elderly"},
    )
    personality = str(result.get("personality") or "").strip() or None
    voice_prompt = _clean_voice_prompt(result.get("voice_prompt"), "narrator")
    confidence = _clean_confidence(result.get("confidence"), default=0.7)

    return CharacterProfile(
        name="narrator",
        role_type="narrator",
        gender=gender or "female",
        age_style=age_style or "young",
        personality=personality or "温柔亲切，平稳客观",
        voice_prompt=voice_prompt,
        confidence=confidence,
    )


def _fallback_character_profile(name: str) -> CharacterProfile:
    if any(kw in name for kw in _ELDERLY_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="male",
            age_style="elderly",
            personality="沉稳",
            voice_prompt="音色苍老沙哑的老年男性声音，语速缓慢，气息较重",
            confidence=0.4,
        )
    if any(kw in name for kw in _CHILD_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="female",
            age_style="child",
            personality="天真",
            voice_prompt="音色清亮活泼的童声，语速适中，气息轻快",
            confidence=0.4,
        )
    for animal_kw, (g, a, vp) in _ANIMAL_VOICE_MAP.items():
        if animal_kw in name:
            return CharacterProfile(
                name=name,
                role_type="character",
                gender=g,
                age_style=a,
                personality="活泼",
                voice_prompt=vp,
                confidence=0.4,
            )
    if any(kw in name for kw in _ANIMAL_KEYWORDS):
        return CharacterProfile(
            name=name,
            role_type="character",
            gender="male",
            age_style="child",
            personality="活泼",
            voice_prompt="音色清亮明亮的少年男孩声音，语速适中，吐字清晰",
            confidence=0.4,
        )
    return CharacterProfile(
        name=name,
        role_type="character",
        gender=None,
        age_style=None,
        personality=None,
        voice_prompt="音色自然清晰的中年声音，语速平稳，吐字准确",
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
    return max(0.0, min(1.0, v))


def _merge_speakers(
    speakers: list[str],
    alias_map: dict[str, str],
    profiles: dict[str, CharacterProfile],
) -> list[CharacterProfile]:
    canonical_to_speakers: dict[str, list[str]] = defaultdict(list)
    for sp in speakers:
        canon = alias_map.get(sp, sp)
        canonical_to_speakers[canon].append(sp)

    result: list[CharacterProfile] = []
    for canon, sp_list in canonical_to_speakers.items():
        if canon == "narrator":
            continue

        prof = profiles.get(canon)
        if prof is None:
            for sp in sp_list:
                if sp in profiles:
                    prof = profiles[sp]
                    break
        if prof is None:
            prof = _fallback_character_profile(canon)

        all_aliases: list[str] = []
        seen: set[str] = set()
        for a in (prof.aliases or []):
            if a != canon and a not in seen:
                seen.add(a)
                all_aliases.append(a)
        for sp in sp_list:
            if sp != canon and sp not in seen:
                seen.add(sp)
                all_aliases.append(sp)

        prof.aliases = all_aliases
        prof.name = canon
        result.append(prof)

    return result


def _sort_by_first_appearance(
    profiles: list[CharacterProfile],
    segments: list[Segment],
) -> list[CharacterProfile]:
    """按 canonical name 在 segments 中首次出现位置排序（引入计数器兜底机制）。"""
    first_idx: dict[str, tuple[int, int]] = {}
    
    # 局部自增自增计数，防御 seg.raw_index 缺失或重复导致的乱序风险
    for fallback_seq, seg in enumerate(segments):
        spk = (seg.speaker or "").strip()
        if not spk:
            continue
        for p in profiles:
            if spk == p.name or spk in (p.aliases or []):
                if p.name not in first_idx:
                    primary_index = seg.raw_index if isinstance(seg.raw_index, int) else fallback_seq
                    first_idx[p.name] = (primary_index, fallback_seq)

    def key(p: CharacterProfile) -> tuple[float, float]:
        return first_idx.get(p.name, (float('inf'), float('inf')))

    return sorted(profiles, key=key)


def _build_alias_map_from_safe_rules(speakers: list[str]) -> dict[str, str]:
    if not speakers:
        return {}

    known = set(speakers)
    am: dict[str, str] = {}
    for sp in speakers:
        for title in _SAFE_TITLES:
            if sp.endswith(title) and len(sp) > len(title):
                core = sp[:-len(title)]
                if len(core) >= 2 and core in known and core != sp:
                    am[sp] = core
                    break
    return am