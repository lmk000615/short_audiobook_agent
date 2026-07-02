"""src_next/utils/yaml_utils.py:load_backends_yaml 单元测试。

依赖 PyYAML。蓝区若未装则自动跳过（pytest.importorskip），黄区正常跑。
"""
from __future__ import annotations

import pytest

# 蓝区可能未装 PyYAML；这里跳过整文件。黄区正常跑。
yaml = pytest.importorskip("yaml")

from pathlib import Path  # noqa: E402

from src_next.utils.yaml_utils import load_backends_yaml  # noqa: E402


def test_load_backends_yaml_returns_dict_with_required_keys():
    data = load_backends_yaml()
    assert "enabled_backends" in data
    assert "backends" in data
    assert "default_model" in data


def test_load_backends_yaml_enabled_backends_is_list():
    data = load_backends_yaml()
    assert isinstance(data["enabled_backends"], list)
    assert len(data["enabled_backends"]) >= 1


def test_load_backends_yaml_backends_have_base_url():
    data = load_backends_yaml()
    for backend_name in data["enabled_backends"]:
        assert backend_name in data["backends"], (
            f"enabled backend {backend_name!r} 不在 backends dict 里"
        )
        backend_cfg = data["backends"][backend_name]
        assert "base_url" in backend_cfg, f"backend {backend_name!r} 缺 base_url"


def test_load_backends_yaml_default_model_is_valid():
    """default_model 必须是某个 model_configs/*.json 的 name。"""
    from src_next.utils.model_config_loader import load_all_model_configs

    data = load_backends_yaml()
    all_model_names = set(load_all_model_configs().keys())
    assert data["default_model"] in all_model_names, (
        f"default_model {data['default_model']!r} 不在 model_configs names {all_model_names} 里"
    )


def test_load_backends_yaml_enabled_backends_subset_of_backends_dict():
    """每个 enabled backend 必须在 backends dict 里有对应条目。"""
    data = load_backends_yaml()
    backends_dict_keys = set(data["backends"].keys())
    enabled_set = set(data["enabled_backends"])
    assert enabled_set.issubset(backends_dict_keys), (
        f"enabled_backends 含 backends dict 里没有的 key：{enabled_set - backends_dict_keys}"
    )


def test_load_backends_yaml_enabled_backends_have_model_configs():
    """每个 enabled backend 必须能通过 backend 字段对应到 model_config。"""
    from src_next.utils.model_config_loader import load_all_model_configs

    data = load_backends_yaml()
    all_configs = load_all_model_configs()
    backend_to_name = {cfg["backend"]: name for name, cfg in all_configs.items()}

    for backend in data["enabled_backends"]:
        assert backend in backend_to_name, (
            f"enabled backend {backend!r} 没有对应的 model_config"
        )


def test_load_backends_yaml_custom_path(tmp_path):
    """loader 应支持 path override（用于测试）。"""
    custom = tmp_path / "custom_backends.yaml"
    custom.write_text(
        """
enabled_backends: [mock_backend]
backends:
  mock_backend:
    base_url: http://mock:9999
default_model: MockModel
""",
        encoding="utf-8",
    )
    data = load_backends_yaml(path=custom)
    assert data["enabled_backends"] == ["mock_backend"]
    assert data["default_model"] == "MockModel"


def test_load_backends_yaml_raises_on_missing_required_key(tmp_path):
    """缺必填 key 时报错。"""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "enabled_backends: [foo]\n",  # 缺 backends + default_model
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="缺必填 key"):
        load_backends_yaml(path=broken)


def test_load_backends_yaml_raises_when_enabled_not_subset(tmp_path):
    """enabled_backends 引用 backends dict 里没有的 key 时报错。"""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        """
enabled_backends: [foo, bar]
backends:
  foo:
    base_url: http://foo:1
default_model: SomeModel
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bar"):
        load_backends_yaml(path=broken)


def test_load_backends_yaml_raises_when_backend_missing_base_url(tmp_path):
    """backend 缺 base_url 时报错。"""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        """
enabled_backends: [foo]
backends:
  foo:
    extra_args: {}
default_model: SomeModel
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="base_url"):
        load_backends_yaml(path=broken)
