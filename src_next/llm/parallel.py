"""src_next/llm/parallel.py

LLM batch 并发工具。

不依赖具体模型：Qwen / Gemma4 / Mock 都可以复用。
基于 ThreadPoolExecutor（IO 密集型并发，不需要 ProcessPool）。

设计要点：
* 每个 batch 单独 try/except，单个失败不影响其他；
* 返回结果保持原始顺序（按输入的 batch_index 排列，不是按完成时间）；
* BatchResult 同时带 success / result / error / elapsed_seconds，方便上层做
  统计和失败重试。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar


T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchResult:
    """单个 batch 的执行结果。

    Attributes:
        batch_index: 在原始 batch_inputs 列表中的下标（0-based）。
        success:     该 batch 是否成功完成（未抛异常）。
        result:      worker_fn 的返回值（失败时为 None）。
        error:       失败时的异常描述，格式 "{ExcTypeName}: {message}"。
        elapsed_seconds: 该 batch 实际耗时（秒）。
    """

    batch_index: int
    success: bool
    result: Any = None
    error: str = ""
    elapsed_seconds: float = 0.0


def run_batches_parallel(
    batch_inputs: list[T],
    worker_fn: Callable[[T], R],
    max_workers: int = 3,
) -> list[BatchResult]:
    """并发执行多个 batch，保持原始顺序。

    Args:
        batch_inputs: 每个 batch 的输入（任意类型，通常是 prompt 或 prompt+context）。
        worker_fn:    处理单个 batch 的函数，签名 (input) -> result。
                      内部应自行调用 LLM 客户端；本工具不关心具体调用哪个后端。
        max_workers:  最大并发数。实际并发会被 clamp 到 [1, len(batch_inputs)]。

    Returns:
        与 batch_inputs 等长、同序的 BatchResult 列表。
        即使某个 batch 抛异常，对应位置也只是 success=False，不影响其他 batch。
    """
    total = len(batch_inputs)
    if total == 0:
        return []

    results: list[BatchResult | None] = [None] * total

    def _run(index: int, payload: T) -> tuple[int, BatchResult]:
        start = time.time()
        try:
            value = worker_fn(payload)
            elapsed = time.time() - start
            return index, BatchResult(
                batch_index=index,
                success=True,
                result=value,
                elapsed_seconds=elapsed,
            )
        except Exception as err:  # noqa: BLE001 - 故意宽，单个 batch 不能拖垮整体
            elapsed = time.time() - start
            return index, BatchResult(
                batch_index=index,
                success=False,
                error=f"{type(err).__name__}: {err}",
                elapsed_seconds=elapsed,
            )

    worker_count = max(1, min(max_workers, total))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [
            pool.submit(_run, i, payload) for i, payload in enumerate(batch_inputs)
        ]
        for future in futures:
            index, batch_result = future.result()
            results[index] = batch_result

    # 理论上所有位置都应已填充；防御性兜底
    final: list[BatchResult] = []
    for i, r in enumerate(results):
        if r is None:
            r = BatchResult(
                batch_index=i,
                success=False,
                error="worker did not produce a result (unexpected)",
            )
        final.append(r)
    return final
