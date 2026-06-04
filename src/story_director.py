"""故事导演层：为每个 segment 生成情绪、语速、停顿等表演指导。

输出模型无关的语义标签，不直接涉及 TTS 参数或音频文件选择。
"""

import json
import os
from pathlib import Path
from typing import Dict

import requests

_SYSTEM_PROMPT = """你是一个有声书导演。根据故事内容、角色特征和每个文本片段的语境，生成表演指导。

严格输出JSON，不要输出其他内容。结构如下：

{
  "overall_style": {
    "genre": "故事类型（如散文/寓言/童话/历史故事）",
    "tone": "整体基调（如温暖怀旧/紧张激烈/轻松幽默）",
    "pace": "整体节奏（如舒缓/适中/紧凑）",
    "summary": "一句话概括故事氛围"
  },
  "characters_direction": {
    "角色名": {
      "voice_direction": "对这个角色声音表现的指导",
      "performance_note": "表演要点，角色性格在台词中的体现"
    }
  },
  "segment_directions": [
    {
      "segment_id": 1,
      "emotion": "情绪（平静/温馨/担忧/兴奋/急切/坚定/伤感/惊讶/愤怒/恐惧）",
      "intensity": "强度（轻/中/强）",
      "pace": "语速（慢/稍慢/正常/稍快/快）",
      "delivery_note": "一句话表演指导，具体到语气和重读建议",
      "emphasis_words": ["需要重读的词"],
      "pause_after_ms": 500,
      "needs_review": false
    }
  ]
}

判断依据：
- 旁白：回忆性叙述偏柔和温慢，描写性叙述偏平静，转折处要有变化
- 对白：根据角色性格和台词内容判断情绪和语气
- 停顿：段落结尾长停（500-800ms），段内短停（200-400ms），戏剧性时刻可到1000ms
- emphasis_words：只选1-3个真正需要重读的词，不要多选
- needs_review：当情绪判断不确定或文本有歧义时标记为true

重要：segment_directions 必须覆盖输入的每一个 segment，不能遗漏。"""


def direct_story(
    segments: Dict,
    characters: Dict,
    story_text: str = "",
) -> Dict:
    """生成完整导演计划。

    Args:
        segments: segment_builder.build_segments() 的输出
        characters: character_analyzer.analyze_characters() 的输出
        story_text: 故事全文（提供给 LLM 作为上下文）

    Returns:
        包含 overall_style、characters_direction、segment_directions 的字典
    """
    user_prompt = _build_user_prompt(segments, characters, story_text)
    env = _load_env()
    raw = _call_llm(_SYSTEM_PROMPT, user_prompt, env)
    directing = _parse_response(raw)
    directing = _validate_and_fill(directing, segments)

    return directing


def _build_user_prompt(
    segments: Dict, characters: Dict, story_text: str
) -> str:
    """构建 LLM 的 user prompt。"""
    parts = []

    if story_text:
        parts.append("## 故事全文\n\n" + story_text)

    parts.append("\n## 角色信息\n")
    n = characters["narrator"]
    parts.append(f"- narrator: {n['gender']}, {n['age']}, {n['timbre']}")
    for c in characters.get("characters", []):
        parts.append(f"- {c['speaker']}: {c['gender']}, {c['age']}, {c['timbre']} ({c['role_type']})")

    parts.append("\n## 需要指导的片段\n")
    for seg in segments["segments"]:
        parts.append(f"[seg_{seg['segment_id']}] ({seg['speaker']}, {seg['type']}) {seg['text']}")

    parts.append("\n请为以上每个片段生成表演指导，严格输出JSON。")
    return "\n".join(parts)


def _load_env() -> Dict[str, str]:
    """从 .env 文件加载配置。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def _call_llm(system_prompt: str, user_prompt: str, env: Dict[str, str]) -> str:
    """调用 LLM API（Anthropic Messages 格式）。"""
    base_url = env.get("LLM_BASE_URL", os.environ.get("LLM_BASE_URL", ""))
    api_key = env.get("LLM_API_KEY", os.environ.get("LLM_API_KEY", ""))
    model = env.get("LLM_MODEL", os.environ.get("LLM_MODEL", "qwen3.6-plus"))

    if not base_url or not api_key:
        raise ValueError("缺少 LLM 配置。请在 .env 文件中设置 LLM_BASE_URL 和 LLM_API_KEY。")

    base = base_url.rstrip("/")
    url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.2,
    }

    response = requests.post(
        url, headers=headers, json=payload, timeout=(10, 180), verify=False
    )
    response.raise_for_status()

    data = response.json()
    for block in data["content"]:
        if block.get("type") == "text":
            return block["text"]
    raise ValueError(f"LLM 响应中没有 text block: {data}")


def _parse_response(raw: str) -> Dict:
    """解析 LLM 返回的 JSON。"""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def _validate_and_fill(directing: Dict, segments: Dict) -> Dict:
    """校验 LLM 输出，补全缺失字段，确保每个 segment 都有 direction。"""
    if "overall_style" not in directing:
        directing["overall_style"] = {
            "genre": "未知", "tone": "中性", "pace": "适中", "summary": "",
        }

    if "characters_direction" not in directing:
        directing["characters_direction"] = {}

    if "narrator" not in directing["characters_direction"]:
        directing["characters_direction"]["narrator"] = {
            "voice_direction": "平稳自然的旁白",
            "performance_note": "",
        }

    seg_dirs = directing.get("segment_directions", [])
    dir_map = {d["segment_id"]: d for d in seg_dirs}

    filled = []
    for seg in segments["segments"]:
        sid = seg["segment_id"]
        if sid in dir_map:
            d = dir_map[sid]
            d.setdefault("emotion", "平静")
            d.setdefault("intensity", "轻")
            d.setdefault("pace", "正常")
            d.setdefault("delivery_note", "")
            d.setdefault("emphasis_words", [])
            d.setdefault("pause_after_ms", 400)
            d.setdefault("needs_review", False)
        else:
            d = {
                "segment_id": sid,
                "emotion": "平静",
                "intensity": "轻",
                "pace": "正常",
                "delivery_note": "",
                "emphasis_words": [],
                "pause_after_ms": 400,
                "needs_review": True,
            }
        d["speaker"] = seg["speaker"]
        d["text"] = seg["text"]
        filled.append(d)

    directing["segment_directions"] = filled
    return directing


def generate_markdown(directing: Dict) -> str:
    """生成人类可读的 MD 报告。"""
    lines = ["# 导演计划\n"]

    style = directing.get("overall_style", {})
    lines.append("## 整体风格")
    lines.append(f"- 类型：{style.get('genre', '')}")
    lines.append(f"- 基调：{style.get('tone', '')}")
    lines.append(f"- 节奏：{style.get('pace', '')}")
    lines.append(f"- 概述：{style.get('summary', '')}\n")

    chars = directing.get("characters_direction", {})
    if chars:
        lines.append("## 角色表演指导\n")
        for name, direction in chars.items():
            lines.append(f"### {name}")
            lines.append(f"- 声音指导：{direction.get('voice_direction', '')}")
            lines.append(f"- 表演要点：{direction.get('performance_note', '')}\n")

    seg_dirs = directing.get("segment_directions", [])
    if seg_dirs:
        lines.append("## 逐段表演指导\n")
        for d in seg_dirs:
            review_tag = " [需复核]" if d.get("needs_review") else ""
            lines.append(f"### seg_{d['segment_id']} — {d['speaker']}{review_tag}")
            lines.append(f"> {d['text']}")
            lines.append(f"- 情绪：{d['emotion']}（{d['intensity']}）")
            lines.append(f"- 语速：{d['pace']}")
            lines.append(f"- 指导：{d['delivery_note']}")
            if d.get("emphasis_words"):
                lines.append(f"- 重读：{'、'.join(d['emphasis_words'])}")
            lines.append(f"- 停顿：{d['pause_after_ms']}ms\n")

    return "\n".join(lines)
