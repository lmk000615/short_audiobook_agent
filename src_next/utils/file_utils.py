"""src_next/utils/file_utils.py

文件读写 + 路径管理纯函数。无业务依赖，可被任何层调用。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在；返回 Path 对象。parents=True, exist_ok=True。"""
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_text(content: str, path: str | Path, *, encoding: str = "utf-8") -> Path:
    """写文本文件；父目录自动创建。返回 Path 对象。"""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)
    return p


def save_json_file(obj: Any, path: str | Path, *, indent: int = 2) -> Path:
    """写 JSON 文件；ensure_ascii=False；父目录自动创建。"""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=indent, default=str),
        encoding="utf-8",
    )
    return p


def read_text_with_encoding(
    path: str | Path,
    *,
    encodings: tuple[str, ...] = ("utf-8-sig", "utf-8", "gbk"),
) -> tuple[str, str | None]:
    """按给定编码顺序尝试读文本；返回 (content, error)。

    Args:
        path: 文件路径。
        encodings: 尝试顺序；默认先 UTF-8-sig（带 BOM）→ UTF-8 → GBK。

    Returns:
        (content, None) 成功；
        ("", error_message) 全部编码都失败。
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return "", f"文件不存在: {p}"
    for enc in encodings:
        try:
            return p.read_text(encoding=enc), None
        except UnicodeDecodeError:
            continue
        except Exception as err:
            return "", f"{type(err).__name__}: {err}"
    return "", f"未知编码（尝试过 {', '.join(encodings)}）"


def file_size_ok(path: str | Path, max_bytes: int) -> bool:
    """文件大小是否在 max_bytes 以内。文件不存在返回 False。"""
    p = Path(path)
    if not p.exists():
        return False
    return p.stat().st_size <= max_bytes


# 安全 story_name 字符白名单：中文字符 + 字母数字 + 下划线 + 连字符
_SAFE_NAME_PATTERN = re.compile(r"[^一-鿿A-Za-z0-9_\-]")


def safe_story_name(name: str, *, max_len: int = 60) -> str:
    """把任意字符串清理成可作目录名的安全形式。

    策略：
        1. strip 首尾空白；
        2. 把非 [中文/字母/数字/_/-] 字符替换为 ``_``；
        3. 截断到 max_len；
        4. 空字符串兜底为 ``unnamed``。

    Examples:
        >>> safe_story_name("小红帽")
        '小红帽'
        >>> safe_story_name("小红帽/测试?.txt")
        '小红帽_测试_.txt'
        >>> safe_story_name("")
        'unnamed'
    """
    s = (name or "").strip()
    s = _SAFE_NAME_PATTERN.sub("_", s)
    s = s.strip("._-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("._-")
    return s or "unnamed"
