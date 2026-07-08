"""servers/api_server_qwen3_voicedesign.py

外部部署用：把 Qwen3-TTS-12Hz-1.7B-VoiceDesign 包成 HTTP 服务，
契约对齐 src_next/voicebank/qwen3_http.py（client）与 usage_guide_qwen3.md。

端点：
    GET  /health                      → {"status":"ok","model":"Qwen3-TTS-VoiceDesign"}
    GET  /v1/voicedesign/config       → 运行配置
    POST /v1/voicedesign/generate     → body {text, instruction, language, [max_new_tokens]}
                                         返回 wav 字节流（PCM_16）

模型调用方式来自 src_next/voicebank/scripts/run_voicedesign_srcnext.py：
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(model_id, dtype=bfloat16, attn_implementation="sdpa")
    wavs, sr = model.generate_voice_design(text=..., instruct=..., language=...)

运行环境：模型自己的 conda env（Python 3.10，装 torch / soundfile / qwen-tts /
fastapi / uvicorn）。本脚本**不 import src_next**，可独立部署到 GPU 机器。

启动示例：
    python servers/api_server_qwen3_voicedesign.py --port 8007 --device cuda:0

说明：
* 本服务显存占用小（1.7B bf16 ~5-7GB），常驻 GPU 即可；GPU 分时复用（offload）
  由更大的 TTS 服务负责，voicebank 与"当前活动的单个 TTS"共存（~6+12≈18GB < 24GB）。
* 单 GPU 上 generate 用锁串行，避免并发 generate 争用/OOM；因此 client 侧
  （profile 的 voicebank.extra_args）应给足 timeout_per_char（建议 300+）。
"""

from __future__ import annotations

import argparse
import io
import threading
import time
import traceback

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel


_DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

# ── 全局状态（启动时填充） ─────────────────────────────────────────────
_MODEL = None
_DEVICE = "cuda:0"
_MODEL_ID = _DEFAULT_MODEL_ID
_ATTN = "sdpa"
_INFER_LOCK = threading.Lock()  # 单 GPU：串行 generate，避免并发争用


class GenerateRequest(BaseModel):
    text: str
    instruction: str = ""
    language: str = "Chinese"
    max_new_tokens: int | None = None


app = FastAPI(title="Qwen3-TTS VoiceDesign Server")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok" if _MODEL is not None else "loading",
            "model": "Qwen3-TTS-VoiceDesign",
            "device": _DEVICE,
        }
    )


@app.get("/v1/voicedesign/config")
def config() -> JSONResponse:
    return JSONResponse(
        {
            "model_id": _MODEL_ID,
            "device": _DEVICE,
            "attn_implementation": _ATTN,
            "dtype": "bfloat16",
        }
    )


@app.post("/v1/voicedesign/generate")
def generate(req: GenerateRequest) -> Response:
    if _MODEL is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)

    instruct = (req.instruction or "").strip()
    if not instruct:
        instruct = "用自然平和的语气说"

    kwargs = {
        "text": req.text,
        "instruct": instruct,
        "language": req.language or "Chinese",
    }
    if req.max_new_tokens is not None:
        kwargs["max_new_tokens"] = int(req.max_new_tokens)

    t0 = time.time()
    try:
        with _INFER_LOCK:
            wavs, sr = _MODEL.generate_voice_design(**kwargs)
    except TypeError:
        # 某些版本 generate_voice_design 不接受 max_new_tokens：去掉重试
        kwargs.pop("max_new_tokens", None)
        try:
            with _INFER_LOCK:
                wavs, sr = _MODEL.generate_voice_design(**kwargs)
        except Exception as err:  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)
    except Exception as err:  # noqa: BLE001
        traceback.print_exc()
        return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)

    if not wavs:
        return JSONResponse({"error": "model returned empty wav list"}, status_code=500)

    # float 波形 → PCM_16 wav 字节（client 会校验 len>=44）
    buf = io.BytesIO()
    sf.write(buf, wavs[0], int(sr), format="WAV", subtype="PCM_16")
    wav_bytes = buf.getvalue()

    elapsed = time.time() - t0
    print(
        f"[voicedesign] instruct={instruct!r} lang={req.language} "
        f"len={len(req.text)}chars -> {len(wav_bytes)}B sr={sr} in {elapsed:.1f}s",
        flush=True,
    )
    return Response(content=wav_bytes, media_type="audio/wav")


def _load_model(model_id: str, device: str, attn: str) -> None:
    global _MODEL, _DEVICE, _MODEL_ID, _ATTN
    _DEVICE, _MODEL_ID, _ATTN = device, model_id, attn

    from qwen_tts import Qwen3TTSModel  # 延迟 import，避免 --help 依赖 torch

    print(f"[voicedesign] loading {model_id} onto {device} (attn={attn}) ...", flush=True)
    t0 = time.time()
    _MODEL = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device,
        dtype=torch.bfloat16,
        attn_implementation=attn,
    )
    print(f"[voicedesign] model loaded in {time.time() - t0:.1f}s", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen3-TTS VoiceDesign HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8007)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--model-dir",
        default=_DEFAULT_MODEL_ID,
        help="本地权重目录，或 HF 模型 id（默认从 HF 拉）",
    )
    parser.add_argument(
        "--attn-implementation",
        default="sdpa",
        choices=("sdpa", "flash_attention_2", "eager"),
    )
    args = parser.parse_args()

    _load_model(args.model_dir, args.device, args.attn_implementation)
    print(f"[voicedesign] serving on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
