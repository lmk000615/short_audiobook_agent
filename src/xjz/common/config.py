"""Central configuration for the TTS workflow.

Loads LLM credentials from environment variables and exposes service URLs /
workflow constants. Tweakable defaults (CLONE_MODE, SILENCE_BETWEEN_SEGMENTS_MS)
live here so all step scripts read from a single source of truth.
"""

import os
from pathlib import Path

# Load .env file if present (for direct script execution)
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.is_file():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

# --- LLM (DashScope Anthropic-compatible endpoint) ---
LLM_BASE_URL = os.environ["LLM_BASE_URL"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.6-plus")
LLM_MAX_TOKENS = 8192

# --- TTS services ---
QWEN3_VD_URL = "http://10.154.39.97:8007"   # Qwen3-TTS VoiceDesign
COSYVOICE_URL = "http://10.154.39.97:8005"  # Fun-CosyVoice3
MOSS_VD_URL = "http://10.154.39.97:8003"    # MOSS-VoiceGenerator
INDEXTTS_URL = "http://10.154.39.97:8009"   # IndexTTS-2

# --- Workflow constants ---
LANGUAGE = "Chinese"
NEUTRAL_SAMPLE_TEXT = "大家好，今天我来跟你们说几句话。"
CONTROL_RULE = "保持音色稳定，仅按当前语气调整情绪、语速和语调"

CLONE_MODE = "zero_shot"  # zero_shot | instruct
CLONE_MODEL = "cosyvoice"  # cosyvoice | indextts
SILENCE_BETWEEN_SEGMENTS_MS = 300
HTTP_TIMEOUT = 300

# --- IndexTTS defaults ---
INDEXTTS_TEMPERATURE = 0.8
INDEXTTS_TOP_P = 0.8
INDEXTTS_TOP_K = 30
INDEXTTS_NUM_BEAMS = 3
INDEXTTS_REPETITION_PENALTY = 10.0
INDEXTTS_MAX_TEXT_TOKENS = 120
INDEXTTS_MAX_MEL_TOKENS = 1500
INDEXTTS_INTERVAL_SILENCE = 200

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # src/xjz
OUTPUT_ROOT = PROJECT_ROOT.parent.parent / "output" / "xjz_output"  # D:/short_audiobook_agent/output/xjz_output
PROMPTS_DIR = PROJECT_ROOT / "prompts"  # src/xjz/prompts


def story_output_dir(input_txt_path: str | Path) -> Path:
    """Return output directory named as '{stem}'.

    e.g. `sample_story_02.txt` -> `output/xjz_output/sample_story_02/`
    """
    stem = Path(input_txt_path).stem
    return OUTPUT_ROOT / stem
