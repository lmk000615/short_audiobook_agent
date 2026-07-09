"""Pytest fixtures for Qwen3OmniCritic integration tests.

⚠️ Integration tests must run SERIALLY (no -n auto / no pytest-xdist) because
Qwen3-Omni service has an infer_lock — concurrent requests will queue and timeout.

⚠️ Integration tests are skip-marked by default — see KNOWN_ISSUES.md.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def real_critic():
    """Real Qwen3OmniCritic pointing at the yellow-zone service. Session-scoped to amortize."""
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    return Qwen3OmniCritic(base_url="http://10.50.121.102:8011")


def _audio_path(filename: str) -> str:
    """Resolve a fixture audio path. Server-side override via env var."""
    root = os.environ.get("CRITIC_FIXTURES_ROOT")
    if root:
        # Server-side absolute path (e.g., /data/.../critic-fixtures/good_narration.wav)
        return str(Path(root) / filename)
    # Local fallback — only works if you're on the same host as the Qwen3-Omni service
    return str(FIXTURES_DIR / filename)


@pytest.fixture(scope="session")
def good_narration_wav():
    return _audio_path("good_narration.wav")


@pytest.fixture(scope="session")
def bad_clipping_wav():
    return _audio_path("bad_clipping.wav")


@pytest.fixture(scope="session")
def emotion_mismatch_wav():
    return _audio_path("emotion_mismatch.wav")


@pytest.fixture(scope="session")
def real_llm():
    """Real LLM client via the project's standard profile mechanism.

    Skips if no profile is available (CI without LLM access).
    See KNOWN_ISSUES.md §1 for activation steps.
    """
    try:
        from src_next.llm.qwen_http import QwenHTTPClient  # noqa: F401
    except ImportError:
        pytest.skip("LLM backend not importable — skipping integration test")

    profile_path = os.environ.get("CRITIC_TEST_LLM_PROFILE")
    if not profile_path:
        pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set — skipping real-LLM integration test")

    # Lazy import — only needed when actually running
    import yaml
    from src_next.llm.qwen_http import QwenHTTPClient
    from src_next.llm.gemma4_http import Gemma4HTTPClient

    with open(profile_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    llm_cfg = cfg.get("llm", cfg)
    backend = llm_cfg.get("type", "qwen_http").lower()
    if backend in ("gemma4", "gemma4_http"):
        return Gemma4HTTPClient(base_url=llm_cfg["base_url"])
    return QwenHTTPClient(base_url=llm_cfg["base_url"])
