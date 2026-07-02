"""src_next/utils/model_config_loader.py 的单元测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_next.utils.model_config_loader import (
    get_backend_for_model,
    get_default_parameters,
    load_all_model_configs,
    load_model_config,
    ModelConfigError,
)


def test_load_model_config_returns_dict():
    cfg = load_model_config("S2Pro")
    assert cfg["name"] == "S2Pro"
    assert cfg["backend"] == "s2pro_http"
    assert "parameters" in cfg
    assert "instruction" in cfg["parameters"]


def test_load_model_config_unknown_name_raises():
    with pytest.raises(ModelConfigError, match="Unknown model name"):
        load_model_config("NonExistentModel")


def test_load_all_model_configs_returns_dict_keyed_by_name():
    all_configs = load_all_model_configs()
    assert "CosyVoice3" in all_configs
    assert "S2Pro" in all_configs
    assert "IndexTTS2" in all_configs
    assert len(all_configs) >= 3


def test_get_backend_for_model():
    assert get_backend_for_model("S2Pro") == "s2pro_http"
    assert get_backend_for_model("CosyVoice3") == "cosyvoice_http"
    assert get_backend_for_model("IndexTTS2") == "indextts_http"


def test_get_backend_for_model_unknown_raises():
    with pytest.raises(ModelConfigError):
        get_backend_for_model("Unknown")


def test_get_default_parameters_returns_all_defaults():
    defaults = get_default_parameters("S2Pro")
    assert "instruction" in defaults
    assert defaults["instruction"] == ""
    assert defaults["enable_reference_audio"] is True
    assert defaults["temperature"] == 1.0


def test_get_default_parameters_unknown_raises():
    with pytest.raises(ModelConfigError):
        get_default_parameters("Unknown")
