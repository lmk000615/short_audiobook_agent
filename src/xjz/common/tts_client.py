"""HTTP clients for the two TTS services used in this workflow.

Both endpoints live behind the same proxy-restricted network, so we explicitly
disable proxies on every request (see usage_guide_*.md in dataset/).
"""

from pathlib import Path

import requests

from . import config

_NO_PROXY = {"http": None, "https": None}


def health_checks() -> dict[str, bool]:
    """Ping all services. Returns a dict of service_name -> reachable."""
    results = {}
    for name, url in (("qwen3_voicedesign", config.QWEN3_VD_URL),
                      ("moss_voicedesign", config.MOSS_VD_URL),
                      ("cosyvoice", config.COSYVOICE_URL),
                      ("indextts", config.INDEXTTS_URL)):
        try:
            r = requests.get(f"{url}/health",
                             proxies=_NO_PROXY,
                             timeout=config.HTTP_TIMEOUT)
            results[name] = r.status_code == 200
        except requests.RequestException:
            results[name] = False
    return results


def qwen3_voicedesign(text: str, instruction: str, language: str) -> bytes:
    """Call Qwen3-TTS VoiceDesign. Returns raw WAV bytes."""
    resp = requests.post(
        f"{config.QWEN3_VD_URL}/v1/voicedesign/generate",
        json={
            "text": text,
            "instruction": instruction,
            "language": language,
        },
        proxies=_NO_PROXY,
        timeout=config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def moss_voicedesign(text: str, instruction: str) -> bytes:
    """Call MOSS-VoiceGenerator. Returns raw WAV bytes."""
    resp = requests.post(
        f"{config.MOSS_VD_URL}/v1/voicegen/generate",
        json={
            "text": text,
            "instruction": instruction,
        },
        proxies=_NO_PROXY,
        timeout=config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def cosyvoice_generate(
    text: str,
    prompt_text: str,
    prompt_audio_b64: str,
    mode: str,
) -> bytes:
    """Call Fun-CosyVoice3 in zero_shot/instruct/cross_lingual mode."""
    resp = requests.post(
        f"{config.COSYVOICE_URL}/v1/cosyvoice/generate",
        json={
            "text": text,
            "prompt_text": prompt_text,
            "prompt_audio": prompt_audio_b64,
            "mode": mode,
            "stream": False,
        },
        proxies=_NO_PROXY,
        timeout=config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def wav_to_b64(path: str | Path) -> str:
    """Read a wav file and return its base64-encoded payload as str."""
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def indextts_generate(
    text: str,
    reference_audio_b64: str,
    *,
    emotion_vector: list[float] | None = None,
    emotion_audio_b64: str | None = None,
    emotion_alpha: float = 1.0,
    emotion_text: str | None = None,
    use_random: bool = False,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    num_beams: int | None = None,
    repetition_penalty: float | None = None,
    max_text_tokens: int | None = None,
    max_mel_tokens: int | None = None,
    interval_silence: int | None = None,
    verbose: bool = False,
) -> bytes:
    """Call IndexTTS-2 for voice cloning with optional emotion control.

    Args:
        text: Text to synthesize
        reference_audio_b64: Base64-encoded reference audio for voice cloning
        emotion_vector: 8-dim emotion vector [happy, angry, sad, afraid,
            disgusted, melancholic, surprised, calm]
        emotion_audio_b64: Base64-encoded audio for emotion reference
        emotion_alpha: Emotion intensity 0.0-1.0
        emotion_text: Text description for auto emotion generation
        use_random: Enable random variation (lower fidelity)
        temperature: Sampling temperature
        top_p: Nucleus sampling cutoff
        top_k: Top-k sampling
        num_beams: Beam search count
        repetition_penalty: Repetition penalty
        max_text_tokens: Max text tokens per segment
        max_mel_tokens: Max mel tokens (controls duration)
        interval_silence: Silence between segments in ms
        verbose: Enable verbose output

    Returns:
        Raw WAV bytes
    """
    payload: dict = {
        "text": text,
        "reference_audio_base64": reference_audio_b64,
    }

    # Optional emotion controls
    if emotion_vector is not None:
        payload["emotion_vector"] = emotion_vector
    if emotion_audio_b64 is not None:
        payload["emotion_audio_base64"] = emotion_audio_b64
    if emotion_alpha != 1.0:
        payload["emotion_alpha"] = emotion_alpha
    if emotion_text is not None:
        payload["emotion_text"] = emotion_text
    if use_random:
        payload["use_random"] = True

    # Optional sampling params
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None:
        payload["top_k"] = top_k
    if num_beams is not None:
        payload["num_beams"] = num_beams
    if repetition_penalty is not None:
        payload["repetition_penalty"] = repetition_penalty
    if max_text_tokens is not None:
        payload["max_text_tokens"] = max_text_tokens
    if max_mel_tokens is not None:
        payload["max_mel_tokens"] = max_mel_tokens
    if interval_silence is not None:
        payload["interval_silence"] = interval_silence
    if verbose:
        payload["verbose"] = True

    resp = requests.post(
        f"{config.INDEXTTS_URL}/v1/tts/synthesize",
        json=payload,
        proxies=_NO_PROXY,
        timeout=config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content
