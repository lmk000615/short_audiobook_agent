"""加载 src_next/tts/model_configs/*.json。

这些 JSON 文件描述每个 TTS 模型的能力给 LLM（tts_director）看。
loader 是 fail-fast 的：任何 malformed config 或未知 model 查询都立即
抛 ModelConfigError，pipeline 永远不会带着半加载的 model 注册表运行。

公共 API：
    load_model_config(name) -> dict        # 按 name 取单个 config
    load_all_model_configs() -> dict       # 全部加载，返回 {name: config}
    get_backend_for_model(name) -> str     # name -> backend key（如 "S2Pro" -> "s2pro_http"）
    get_default_parameters(name) -> dict   # 提取所有参数 default 值，扁平 dict
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MODEL_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "tts" / "model_configs"


class ModelConfigError(Exception):
    """model_config 加载失败或 model name 未知时抛出。"""


def load_model_config(name: str, directory: Path | None = None) -> dict[str, Any]:
    """按 model name 加载单份 model_config JSON。

    Args:
        name: 模型名（必须匹配某个 JSON 文件的 ``name`` 字段）。
        directory: 覆盖默认的 model_configs 目录（用于测试）。

    Returns:
        解析后的 JSON dict。

    Raises:
        ModelConfigError: 没有任何 JSON 文件含此 name，或文件解析失败。
    """
    directory = directory or _MODEL_CONFIGS_DIR
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelConfigError(f"Failed to parse {path}: {exc}") from exc
        if cfg.get("name") == name:
            return cfg
    raise ModelConfigError(
        f"Unknown model name: {name!r}. "
        f"Available: {_list_available_names(directory)}"
    )


def load_all_model_configs(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """加载所有 model_configs，返回 {name: config_dict} 映射。

    Args:
        directory: 覆盖默认的 model_configs 目录。

    Returns:
        以 model name 为 key 的 dict。

    Raises:
        ModelConfigError: 任何 JSON 解析失败、缺少 ``name`` 字段、或出现重名 model。
    """
    directory = directory or _MODEL_CONFIGS_DIR
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelConfigError(f"Failed to parse {path}: {exc}") from exc
        if "name" not in cfg:
            raise ModelConfigError(f"{path} missing required 'name' field")
        if cfg["name"] in result:
            raise ModelConfigError(
                f"Duplicate model name {cfg['name']!r} in {path} "
                f"(already defined in another file)"
            )
        result[cfg["name"]] = cfg
    return result


def get_backend_for_model(name: str, directory: Path | None = None) -> str:
    """按 model name 查 backend key（如 's2pro_http'）。

    Raises:
        ModelConfigError: name 未知，或 config 缺 ``backend`` 字段。
    """
    cfg = load_model_config(name, directory=directory)
    if "backend" not in cfg:
        raise ModelConfigError(f"model_config for {name!r} missing 'backend' field")
    return cfg["backend"]


def get_default_parameters(name: str, directory: Path | None = None) -> dict[str, Any]:
    """从 model_config 提取扁平的 {param_name: default_value} dict。

    tts_director fallback 时用：LLM 漏掉某个 segment 或返回无效参数时，
    我们用 model_config 声明的 default 值，不在 Python 里硬编码 fallback。

    没有 ``default`` 字段的参数会被跳过——调用方需要自行决定如何处理。
    """
    cfg = load_model_config(name, directory=directory)
    parameters = cfg.get("parameters", {})
    defaults: dict[str, Any] = {}
    for field_name, spec in parameters.items():
        if "default" not in spec:
            continue
        defaults[field_name] = spec["default"]
    return defaults


def _list_available_names(directory: Path) -> list[str]:
    """列出目录下所有 model name（用于错误信息）。"""
    names: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            if "name" in cfg:
                names.append(cfg["name"])
        except (json.JSONDecodeError, OSError):
            continue
    return names
