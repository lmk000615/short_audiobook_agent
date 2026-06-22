"""src_next/core/logging_utils.py

STAGE 级日志工具。格式示例：

    ▶ STAGE 1/8｜文本切分｜进行中
    ✓ STAGE 1/8｜文本切分｜完成
      ├─ ITEM 生成 12 个 segments

暂不接 WebUI progress event，只 print 到 stdout。
"""

import sys

# Windows 控制台默认 GBK 编码，无法输出 ▶ / ✓ / ├─ 等字符。
# 导入本模块时尝试把 stdout 切到 UTF-8（Python 3.7+）。
# 在已经是大 UTF-8 的环境（Linux / 现代终端）是 no-op。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (OSError, ValueError):
    pass


def log_stage_start(step: str, label: str) -> None:
    """打印 stage 开始日志，例如 ▶ STAGE 1/8｜文本切分｜进行中。"""
    print(f"▶ STAGE {step}｜{label}｜进行中")


def log_stage_done(step: str, label: str) -> None:
    """打印 stage 完成日志，例如 ✓ STAGE 1/8｜文本切分｜完成。"""
    print(f"✓ STAGE {step}｜{label}｜完成")


def log_item(message: str) -> None:
    """打印一条 item 日志，缩进显示在 stage 下面。"""
    print(f"  ├─ ITEM {message}")
