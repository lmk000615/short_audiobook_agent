"""src_next/critic/voicebank_bench/test_qwen3omni_vb_critic.py

最小验证测试：Qwen3-Omni 能否"听"一段 voicebank 参考音色 wav 并返回有效评分。

验证点：
  1. Qwen3-Omni 服务是否可达
  2. base64 音频能否被正确接收
  3. 返回的文本中是否包含可解析的 JSON
  4. 评分是否合理（不是全 0.5 中性分）

调用方式（从项目根目录）：
    # 指定 wav 文件
    python -m src_next.critic.voicebank_bench.test_qwen3omni_vb_critic \
        --wav path/to/narrator.wav

    # 不指定 wav，自动从 _voicebank_results/ 找一个
    python -m src_next.critic.voicebank_bench.test_qwen3omni_vb_critic

    # 指定服务地址
    python -m src_next.critic.voicebank_bench.test_qwen3omni_vb_critic \
        --wav path/to/narrator.wav \
        --base-url http://10.50.121.102:8011

注意：此脚本的 prompt 是临时验证用，不是正式的 voicebank critic prompt。
正式的评分体系设计由用户后续提供。
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Windows UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# 临时验证用 prompt（非正式设计）
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
你是一位专业的语音音色质量审核员。你将听到一段角色音色参考音频。
请根据你听到的实际音色，评估该音频与角色设定的匹配程度。"""

_USER_PROMPT_TEMPLATE = """\
请仔细听这段角色音色参考音频，并评估其与角色设定的匹配度。

## 角色设定

- **角色名**：{speaker_name}
- **设定性别**：{gender}
- **设定年龄/风格**：{age_style}
- **音色描述（voice_prompt）**：{voice_prompt}

## 评估要求

请从以下 4 个维度评分（0.0-1.0）：

1. **gender_match**（性别匹配度）：音频中的声音性别是否与设定一致？
2. **age_match**（年龄匹配度）：声音的年龄感是否与设定一致？
3. **timbre_match**（音色匹配度）：音色特征（清亮/低沉/沙哑/温柔等）是否与 voice_prompt 描述一致？
4. **clarity**（清晰度）：音频是否清晰、无噪声、无截断？

## 输出格式

只输出一个 JSON 对象，不要加任何其他文字：
```json
{{
  "gender_match_score": 0.0-1.0,
  "age_match_score": 0.0-1.0,
  "timbre_match_score": 0.0-1.0,
  "clarity_score": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "issues": ["具体问题描述"],
  "suggestion": "改进建议"
}}
```"""


# ─────────────────────────────────────────────────────────────────────────────
# 音频编码（参考 long_audio_critic.py）
# ─────────────────────────────────────────────────────────────────────────────

def _encode_audio_as_data_uri(audio_path: Path) -> str:
    """将音频文件编码为 data URI（base64）。"""
    mime_type, _ = mimetypes.guess_type(str(audio_path))
    if not mime_type:
        mime_type = "audio/wav"
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


# ─────────────────────────────────────────────────────────────────────────────
# JSON 解析（参考 long_audio_critic.py）
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json_from_text(text: str) -> dict[str, Any]:
    """从模型输出中提取第一个完整 JSON 对象。"""
    text = text.strip()
    # 尝试直接解析
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # 去 code fence
    import re
    cleaned = re.sub(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", "", text, flags=re.MULTILINE)
    try:
        obj = json.loads(cleaned.strip())
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # 花括号平衡扫描
    start = text.find("{")
    if start == -1:
        raise ValueError(f"模型输出中没有找到 JSON：\n{text[:300]}")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break
    raise ValueError(f"模型输出中没有找到合法 JSON：\n{text[:500]}")


# ─────────────────────────────────────────────────────────────────────────────
# 核心：调用 Qwen3-Omni
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_voicebank_wav(
    wav_path: str | Path,
    *,
    speaker_name: str = "旁白",
    gender: str = "女性",
    age_style: str = "年轻",
    voice_prompt: str = "平稳亲切的成年女性说书人嗓音",
    base_url: str = "http://10.50.121.102:8011",
    timeout: int = 300,
    bypass_proxy: bool = True,
) -> dict[str, Any]:
    """用 Qwen3-Omni 评估一段 voicebank 参考音色 wav。

    使用 messages 格式（参考 long_audio_critic.py），支持 system prompt 分离。

    注意：Qwen3-Omni 服务有 infer_lock，同一时间只处理一个请求；
    首次推理有 ~30s warm-up，timeout 默认 300s（参考 long_audio_critic.py 的 600s）。

    Returns:
        解析后的评分字典。
    """
    wav_path = Path(wav_path).resolve()
    if not wav_path.is_file():
        raise FileNotFoundError(f"wav 文件不存在: {wav_path}")

    proxies = {"http": None, "https": None} if bypass_proxy else None

    # 健康检查
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        print(f"[test] 健康检查 GET {health_url}")
        hr = requests.get(health_url, proxies=proxies, timeout=10)
        if hr.status_code == 200:
            health = hr.json()
            print(f"[test] ✅ 服务在线: model={health.get('model','?')}, talker={health.get('talker_enabled','?')}")
        else:
            print(f"[test] ⚠️ 健康检查返回 HTTP {hr.status_code}")
    except Exception as e:
        print(f"[test] ⚠️ 健康检查失败: {e}")

    # 编码音频
    audio_data_uri = _encode_audio_as_data_uri(wav_path)

    # 构造 user prompt
    user_text = _USER_PROMPT_TEMPLATE.format(
        speaker_name=speaker_name,
        gender=gender,
        age_style=age_style,
        voice_prompt=voice_prompt,
    )

    # 使用 messages 格式（同 long_audio_critic.py）
    payload = {
        "messages": [
            {
                "role": "system",
                "content": [{"type": "text", "text": _SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "audio", "audio": audio_data_uri},
                ],
            },
        ],
        "return_audio": False,
        "max_new_tokens": 1024,
        "temperature": 0.3,
    }

    url = f"{base_url.rstrip('/')}/v1/omni/chat"
    print(f"[test] POST {url}")
    print(f"[test] wav={wav_path.name} ({wav_path.stat().st_size / 1024:.1f} KB)")
    print(f"[test] timeout={timeout}s（Qwen3-Omni 有 infer_lock，首次推理需 warm-up）")

    t0 = time.perf_counter()
    resp = requests.post(url, json=payload, proxies=proxies, timeout=timeout)
    elapsed = time.perf_counter() - t0
    print(f"[test] HTTP {resp.status_code} in {elapsed:.1f}s")

    if resp.status_code != 200:
        raise RuntimeError(f"omni/chat returned HTTP {resp.status_code}: {resp.text[:300]!r}")

    # 提取文本
    data = resp.json()
    raw_text = ""
    for key in ("text", "response", "content", "output"):
        val = data.get(key)
        if isinstance(val, str):
            raw_text = val
            break
    if not raw_text:
        raw_text = json.dumps(data, ensure_ascii=False)

    print(f"[test] raw response ({len(raw_text)} chars):")
    print(f"  {raw_text[:500]}")

    # 解析 JSON
    scoring = _extract_json_from_text(raw_text)
    return scoring


# ─────────────────────────────────────────────────────────────────────────────
# 自动查找 wav
# ─────────────────────────────────────────────────────────────────────────────

# 项目根目录（src_next/critic/voicebank_bench/ → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BENCH_DIR = _PROJECT_ROOT / "tests" / "audiobench_zh"


def _find_sample_wav() -> Path | None:
    """从 _voicebank_results/ 或 output-src-next/ 找一个 wav 文件。"""
    bench_dir = _BENCH_DIR / "_voicebank_results"
    output_dir = _PROJECT_ROOT / "output-src-next"

    for search_dir in [bench_dir, output_dir]:
        if search_dir.is_dir():
            for wav in sorted(search_dir.rglob("voicebank/*.wav")):
                if wav.stat().st_size > 1000:  # 至少 1KB
                    return wav
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="最小验证：Qwen3-Omni 评估 voicebank 参考音色 wav",
    )
    parser.add_argument(
        "--wav", default="",
        help="wav 文件路径（不指定则自动查找）",
    )
    parser.add_argument(
        "--base-url", default="http://10.50.121.102:8011",
        help="Qwen3-Omni 服务地址",
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="请求超时秒数（默认 300，Qwen3-Omni 有 infer_lock 需排队）",
    )
    parser.add_argument(
        "--speaker-name", default="旁白",
        help="角色名（默认：旁白）",
    )
    parser.add_argument(
        "--gender", default="女性",
        help="设定性别（默认：女性）",
    )
    parser.add_argument(
        "--age-style", default="年轻",
        help="设定年龄/风格（默认：年轻）",
    )
    parser.add_argument(
        "--voice-prompt", default="平稳亲切的成年女性说书人嗓音",
        help="音色描述（默认：平稳亲切的成年女性说书人嗓音）",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # 确定 wav 文件
    if args.wav:
        wav_path = Path(args.wav).resolve()
    else:
        wav_path = _find_sample_wav()
        if wav_path is None:
            print("[test] ❌ 未找到 wav 文件，请用 --wav 指定")
            return 2
        print(f"[test] 自动找到 wav: {wav_path}")

    print("=" * 60)
    print(f"  Qwen3-Omni Voicebank Critic 最小验证测试")
    print(f"  wav:     {wav_path}")
    print(f"  角色:    {args.speaker_name} ({args.gender}, {args.age_style})")
    print(f"  prompt:  {args.voice_prompt}")
    print(f"  服务:    {args.base_url}")
    print("=" * 60)

    try:
        result = evaluate_voicebank_wav(
            wav_path,
            speaker_name=args.speaker_name,
            gender=args.gender,
            age_style=args.age_style,
            voice_prompt=args.voice_prompt,
            base_url=args.base_url,
            timeout=args.timeout,
        )

        print()
        print("=" * 60)
        print("  评分结果")
        print("=" * 60)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 验证评分合理性
        dims = ["gender_match_score", "age_match_score", "timbre_match_score", "clarity_score"]
        all_neutral = all(abs(result.get(d, 0.5) - 0.5) < 0.01 for d in dims)
        if all_neutral:
            print("\n⚠️  所有维度都是 0.5 中性分，可能解析失败或 LLM 未真正听音频")
        else:
            print("\n✅ 评分非中性，Qwen3-Omni 听音频能力验证通过")

        return 0

    except Exception as err:
        print(f"\n❌ 测试失败: {type(err).__name__}: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())