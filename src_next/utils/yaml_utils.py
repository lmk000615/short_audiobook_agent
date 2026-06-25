"""src_next/utils/yaml_utils.py

YAML 加载 + profile 发现。无业务依赖。

profile 发现规则见 ``discover_profiles`` docstring。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


# 完整 pipeline profile 必须包含的 5 个顶层块
_REQUIRED_BLOCKS: tuple[str, ...] = ("llm", "voicebank", "tts", "output", "pipeline")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """加载 yaml 文件为 dict。

    Raises:
        FileNotFoundError: 文件不存在。
        yaml.YAMLError: yaml 语法错误。
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"yaml 不存在: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def discover_profiles(
    profiles_dir: str | Path = "src_next/profiles",
) -> list[dict[str, str]]:
    """扫描 ``profiles_dir/*.yaml``，返回适合 WebUI 展示的 profile 列表。

    每项 dict 字段：
        ``path``           — yaml 文件绝对路径字符串
        ``display_name``   — dropdown 显示名
        ``description``    — dropdown 副标题（≤ 200 字符）
        ``region``         — blue / yellow / unknown
        ``filename_stem``  — 文件名（无扩展名），便于排错

    Filter:
        * 跳过 malformed YAML（stderr 打 warning）
        * 跳过缺 ``_REQUIRED_BLOCKS`` 任一块的 yaml
        * 跳过 ``webui.enabled: false`` 的 yaml（默认 true）

    Naming resolution (优先级从高到低)：
        1. ``webui.display_name``
        2. ``display_name``
        3. ``name``
        4. filename stem

    Description resolution (优先级从高到低)：
        1. ``webui.description``
        2. ``description`` (截断到 200 字符)
        3. 自动摘要 (``[region] filename``)

    Collision: display_name 重复时第二项追加 ``(#filename_stem)`` 后缀。

    排序：``(region, display_name)`` 升序，保证 dropdown 顺序稳定。
    """
    profiles_dir = Path(profiles_dir).expanduser().resolve()
    if not profiles_dir.exists():
        return []

    results: list[dict[str, str]] = []
    seen_display_names: dict[str, int] = {}

    for yaml_path in sorted(profiles_dir.glob("*.yaml")):
        try:
            data = load_yaml(yaml_path)
        except yaml.YAMLError as err:
            print(
                f"[yaml_utils] 跳过 malformed yaml: {yaml_path.name} ({err})",
                file=sys.stderr,
            )
            continue
        except Exception as err:
            print(
                f"[yaml_utils] 跳过无法加载的 yaml: {yaml_path.name} ({err})",
                file=sys.stderr,
            )
            continue

        if not isinstance(data, dict):
            continue

        # 必填块校验
        missing = [b for b in _REQUIRED_BLOCKS if not data.get(b)]
        if missing:
            # partial profile（如 blue_indextts.yaml 只有 tts 块）静默跳过，
            # 这些是给 adapter 单测用的，不进 WebUI dropdown
            continue

        # webui.enabled 过滤
        webui_block = data.get("webui") or {}
        if isinstance(webui_block, dict) and webui_block.get("enabled") is False:
            continue

        display_name = _resolve_display_name(data, webui_block, yaml_path.stem)
        description = _resolve_description(data, webui_block, yaml_path.stem)
        region = str(data.get("region") or "unknown")

        # 处理重名：第二次出现追加 (#filename_stem)
        if display_name in seen_display_names:
            display_name = f"{display_name} (#{yaml_path.stem})"
        seen_display_names[display_name] = 1

        results.append({
            "path": str(yaml_path),
            "display_name": display_name,
            "description": description,
            "region": region,
            "filename_stem": yaml_path.stem,
        })

    # 按 (region, display_name) 排序，dropdown 顺序稳定
    results.sort(key=lambda r: (r["region"], r["display_name"]))
    return results


def _resolve_display_name(
    data: dict[str, Any], webui_block: dict[str, Any], filename_stem: str
) -> str:
    """优先级：webui.display_name > display_name > name > filename stem。"""
    for key in ("display_name",):
        val = webui_block.get(key)
        if val and isinstance(val, str):
            return val.strip()
    val = data.get("display_name")
    if val and isinstance(val, str):
        return val.strip()
    val = data.get("name")
    if val and isinstance(val, str):
        return val.strip()
    return filename_stem


def _resolve_description(
    data: dict[str, Any], webui_block: dict[str, Any], filename_stem: str
) -> str:
    """优先级：webui.description > description > 自动摘要。

    多行 description 取第一段非空行，截断到 200 字符。
    """
    val = webui_block.get("description")
    if val and isinstance(val, str):
        return _truncate_desc(val)

    val = data.get("description")
    if val and isinstance(val, str):
        return _truncate_desc(val)

    region = data.get("region") or "unknown"
    return f"[{region}] {filename_stem}"


def _truncate_desc(text: str, *, max_chars: int = 200) -> str:
    """多行描述取第一段非空行，截断到 max_chars。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    joined = " ".join(lines)
    if len(joined) <= max_chars:
        return joined
    return joined[: max_chars - 1] + "…"
