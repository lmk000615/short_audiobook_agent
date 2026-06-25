"""src_next/core/logging_utils.py

STAGE 级日志工具。

两类 API：

1. 旧版独立函数（``log_stage_start`` / ``log_stage_done`` / ``log_item``）
   mock pipeline 用；只 print 到 stdout，使用 ▶ / ✓ / ├─ 装饰符。

2. ``StageLogger`` 类（NEW，给真实 pipeline + WebUI 用）
   三合一：终端 print + 文件落盘 + 内存累积；支持 WebUI 取 ``get_full_text()``
   实时显示。格式和 ``audiobook_pipeline._log_*`` 助手保持一致，方便平滑替换。
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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


# ─────────────────────────────────────────────────────────────────────────────
# StageLogger（NEW）
# ─────────────────────────────────────────────────────────────────────────────


class StageLogger:
    """三合一 stage 级日志：终端 print + 文件落盘 + 内存累积。

    用法：
        logger = StageLogger(output_dir=task_dir)
        logger.pipeline_header(input_path, profile_path, output_dir)
        logger.stage_start("1/10", "build_segments")
        ...
        logger.stage_done("1/10", "build_segments", 0.02, extra="segments=21")
        ...
        logger.summary(success=True, total_time=223.1, ...)
        text = logger.get_full_text()       # 给 WebUI 实时显示
        tail = logger.get_summary(n=30)     # 给 WebUI 摘要框

    文件输出：``<output_dir>/logs/pipeline.log``，UTF-8 编码，每行 ISO 时间戳前缀。
    文件在首次写入时 lazy 打开（避免 mock / 测试场景下创建无意义目录）。

    Note:
        ``also_print=True`` 时复制一份到 stdout（flush=True），方便 CLI / 服务器
        tail -f webui.log。WebUI 内部跑生成器时可以传 ``also_print=False`` 避免
        双重输出（但通常保留以便排错）。
    """

    def __init__(
        self,
        output_dir: str | Path | None = None,
        *,
        also_print: bool = True,
    ) -> None:
        self._also_print = also_print
        self._lines: list[str] = []
        self._file_path: Path | None = None
        self._file = None
        if output_dir is not None:
            log_dir = Path(output_dir).expanduser().resolve() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._file_path = log_dir / "pipeline.log"

    # ── internal helpers ────────────────────────────────────────────────

    def _emit(self, line: str) -> None:
        """把一行写到内存 + 文件 + stdout。"""
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        formatted = f"{ts} {line}" if line else ts
        self._lines.append(formatted)
        if self._file_path is not None:
            if self._file is None:
                self._file = open(self._file_path, "a", encoding="utf-8")
            self._file.write(formatted + "\n")
            self._file.flush()
        if self._also_print:
            print(formatted, flush=True)

    # ── generic levels ──────────────────────────────────────────────────

    def info(self, message: str) -> None:
        self._emit(f"[INFO] {message}")

    def warning(self, message: str) -> None:
        self._emit(f"[WARN] {message}")

    def error(self, message: str) -> None:
        self._emit(f"[ERROR] {message}")

    def blank(self) -> None:
        """输出空行（用于段落分隔）。"""
        self._emit("")

    # ── pipeline header / footer ────────────────────────────────────────

    def pipeline_header(
        self,
        input_path: str,
        profile_path: str | None,
        output_dir: str,
    ) -> None:
        """镜像 audiobook_pipeline._log_pipeline_header 格式。"""
        self._emit(f"[Pipeline] input={input_path}")
        if profile_path:
            self._emit(f"[Pipeline] profile={profile_path}")
        self._emit(f"[Pipeline] output={output_dir}")
        self.blank()

    def summary(self, **kwargs: Any) -> None:
        """镜像 audiobook_pipeline._log_summary 字段。

        Expected kwargs (all optional except success/total_time):
            success, total_time, analysis_time, voicebank_time,
            tts_time, merge_time, final_audio_duration (None ok),
            rtf (None ok), output_dir, final_audio, error=""
        """
        self.blank()
        self._emit("[Summary]")
        self._emit(f"success={'true' if kwargs.get('success') else 'false'}")
        total = kwargs.get("total_time")
        if total is not None:
            self._emit(f"total_time={total:.2f}s")
        for k in ("analysis_time", "voicebank_time", "tts_time", "merge_time"):
            v = kwargs.get(k)
            if v is not None:
                self._emit(f"{k}={v:.2f}s")
        fa_dur = kwargs.get("final_audio_duration")
        if fa_dur is None:
            self._emit("final_audio_duration=null")
        else:
            self._emit(f"final_audio_duration={fa_dur:.2f}s")
        rtf = kwargs.get("rtf")
        if rtf is None:
            self._emit("rtf=null")
        else:
            self._emit(f"rtf={rtf:.2f}")
        out = kwargs.get("output_dir")
        if out is not None:
            self._emit(f"output_dir={out}")
        fa = kwargs.get("final_audio")
        self._emit(f"final_audio={fa or ''}")
        err = kwargs.get("error")
        if err:
            self._emit(f"error={err}")

    # ── stage lifecycle ─────────────────────────────────────────────────

    def stage_start(self, step: str, name: str) -> None:
        self._emit(f"[{step}] {name} ...")

    def stage_done(
        self,
        step: str,
        name: str,
        elapsed: float,
        extra: str = "",
    ) -> None:
        suffix = f", {extra}" if extra else ""
        self._emit(f"[{step}] {name} ... done in {elapsed:.2f}s{suffix}")

    def stage_reused(
        self,
        step: str,
        name: str,
        src: str,
        elapsed: float,
    ) -> None:
        self._emit(
            f"[{step}] {name} ... reused, loaded from {src}, {elapsed:.2f}s"
        )

    def stage_failed(
        self,
        step: str,
        name: str,
        elapsed: float,
        err: str,
    ) -> None:
        self._emit(f"[{step}] {name} ... failed in {elapsed:.2f}s — {err}")

    # ── retrieval ───────────────────────────────────────────────────────

    def get_full_text(self) -> str:
        """返回从 logger 创建以来的全部日志文本。"""
        return "\n".join(self._lines)

    def get_summary(self, n: int = 30) -> str:
        """返回最后 N 行 + 完整 [Summary] 块。

        找到 ``[Summary]`` 行位置；从该位置到末尾的全部行 + 末尾 n 行（去重）。
        如果没有 [Summary] 块（pipeline 中途失败），就只返回最后 n 行。
        """
        if not self._lines:
            return ""
        summary_start = -1
        for i, line in enumerate(self._lines):
            if line.endswith("[Summary]"):
                summary_start = i
                break
        if summary_start >= 0:
            tail_n = self._lines[-n:] if n > 0 else []
            combined = self._lines[summary_start:] + [
                ln for ln in tail_n if ln not in self._lines[summary_start:]
            ]
            return "\n".join(combined)
        return "\n".join(self._lines[-n:])

    def close(self) -> None:
        """显式关闭文件句柄；进程退出时也会自动关闭，通常不需要手动调。"""
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

