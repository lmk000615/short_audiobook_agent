"""Qwen3OmniCritic unit tests.

Integration tests (real Qwen3-Omni service) are written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness tests run by default.
"""
from __future__ import annotations

import pytest

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


def test_critic_can_be_constructed_with_defaults():
    """Qwen3OmniCritic should construct with the documented default base_url."""
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic

    critic = Qwen3OmniCritic()
    assert critic.base_url == "http://10.50.121.102:8011"
    assert critic.timeout == 120
    assert critic.bypass_proxy is True
