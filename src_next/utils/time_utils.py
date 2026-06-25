"""src_next/utils/time_utils.py

时间相关纯函数。
"""

from __future__ import annotations

from datetime import datetime


def now_timestamp() -> str:
    """当前时间戳，形如 ``20260625_143022``。

    用途：WebUI 任务目录的 ``task_id``；同秒冲突由调用方追加随机后缀。
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_seconds(seconds: float) -> str:
    """把秒数格式化成简短可读字符串。

    Examples:
        >>> format_seconds(0.1)
        '0.1s'
        >>> format_seconds(45)
        '45s'
        >>> format_seconds(83)
        '1m 23s'
        >>> format_seconds(3600)
        '1h 0m'
    """
    if seconds < 60:
        return f"{seconds:.1f}s" if seconds < 10 else f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"
