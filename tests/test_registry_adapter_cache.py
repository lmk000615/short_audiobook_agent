"""src_next/tts/registry.py:create_adapter_for_backend 单元测试。"""
from __future__ import annotations

import pytest

from src_next.tts.base import TTSError
from src_next.tts.registry import clear_adapter_cache, create_adapter_for_backend


def test_create_adapter_for_backend_returns_adapter():
    adapter = create_adapter_for_backend(
        "cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments"
    )
    assert adapter is not None


def test_create_adapter_for_backend_caches_per_backend_and_config():
    """相同 backend + 相同 config 应返回相同实例。"""
    clear_adapter_cache()
    a1 = create_adapter_for_backend(
        "cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments"
    )
    a2 = create_adapter_for_backend(
        "cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments"
    )
    assert a1 is a2, "相同 backend+config 应返回缓存实例"


def test_create_adapter_for_backend_different_config_returns_new_instance():
    """不同 config 应产生不同实例。"""
    clear_adapter_cache()
    a1 = create_adapter_for_backend(
        "cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments"
    )
    a2 = create_adapter_for_backend(
        "cosyvoice_http", base_url="http://mock:9999", output_subdir="audio_segments"
    )
    assert a1 is not a2, "不同 config 应返回新实例"


def test_create_adapter_for_backend_unknown_backend_raises():
    """未知 backend 报错（沿用现有 create_tts_adapter 的 TTSError 约定）。"""
    with pytest.raises(TTSError, match="未知"):
        create_adapter_for_backend("totally_made_up_backend", base_url="http://x")


def test_create_adapter_for_backend_extra_args_in_config_keyed_distinctly():
    """extra_args 内容不同也视为不同 config，应返回新实例。"""
    clear_adapter_cache()
    a1 = create_adapter_for_backend(
        "cosyvoice_http",
        base_url="http://mock:8005",
        output_subdir="audio_segments",
        extra_args={"max_workers": 4},
    )
    a2 = create_adapter_for_backend(
        "cosyvoice_http",
        base_url="http://mock:8005",
        output_subdir="audio_segments",
        extra_args={"max_workers": 8},  # 不同
    )
    assert a1 is not a2, "extra_args 内容不同应触发新实例"
