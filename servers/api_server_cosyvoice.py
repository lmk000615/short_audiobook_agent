"""servers/api_server_cosyvoice.py

外部部署用：把 Fun-CosyVoice3-0.5B 包成 HTTP 服务，
契约对齐 src_next/tts/cosyvoice_http.py（client）与 usage_guide_cosyvoice.md。

端点：
    GET  /health                   → {"status":"ok","model":"Fun-CosyVoice3-0.5B"}
    GET  /v1/cosyvoice/config       → {"sampling_rate":24000,"supported_modes":[...]}
    POST /v1/cosyvoice/generate     → body {text, prompt_text, prompt_audio, mode, stream}
                                      返回 wav 字节流（PCM_16）

字段映射（payload → CosyVoice AutoModel）：
    mode=instruct       : inference_instruct2(text=text, instruct_text=prompt_text, prompt_speech_16k=ref)
    mode=zero_shot      : inference_zero_shot(text=text, instruct_text=prompt_text, prompt_speech_16k=ref)
    mode=cross_lingual  : inference_cross_lingual(instruct_text=text, prompt_speech_16k=ref)
    prompt_audio        : 本地路径（新链路，直接用）或 base64（老链路，解码写临时文件）
                          → load_wav(path, 16000) 得到 16k 参考音频张量

运行环境：CosyVoice 官方 conda env（python 3.10 + requirements.txt）。
必须能 import cosyvoice；本脚本会把 CosyVoice 仓库根目录 + third_party/Matcha-TTS
插入 sys.path。默认仓库根 = 当前工作目录（在 CosyVoice/ 下启动），或用 --cosyvoice-root 指定。

启动示例（在 /root/autodl-tmp/CosyVoice 下）：
    python /root/autodl-tmp/api_server_cosyvoice.py \
        --port 8005 --device cuda:0 \
        --model-dir pretrained_models/Fun-CosyVoice3-0.5B \
        --cosyvoice-root /root/autodl-tmp/CosyVoice
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import sys
import tempfile
import threading
import time
import traceback


_MODEL = None
_SR = 24000
_MODEL_DIR = ""
_INFER_LOCK = threading.Lock()
_load_wav = None  # cosyvoice.utils.file_utils.load_wav，加载模型时填充


def _setup_paths(cosyvoice_root: str) -> None:
    root = os.path.abspath(cosyvoice_root)
    matcha = os.path.join(root, "third_party", "Matcha-TTS")
    for p in (matcha, root):
        if p not in sys.path:
            sys.path.insert(0, p)


def _load_model(model_dir: str, cosyvoice_root: str) -> None:
    global _MODEL, _SR, _MODEL_DIR, _load_wav
    _setup_paths(cosyvoice_root)
    _MODEL_DIR = model_dir

    from cosyvoice.cli.cosyvoice import AutoModel
    from cosyvoice.utils.file_utils import load_wav

    _load_wav = load_wav
    print(f"[cosyvoice] loading model_dir={model_dir} ...", flush=True)
    t0 = time.time()
    _MODEL = AutoModel(model_dir=model_dir)
    _SR = int(getattr(_MODEL, "sample_rate", 24000))
    print(f"[cosyvoice] model loaded in {time.time()-t0:.1f}s (sr={_SR})", flush=True)


def _resolve_ref_path(prompt_audio: str) -> str:
    """prompt_audio 是本地路径就直接用；否则当 base64 解码写临时文件。"""
    if prompt_audio and os.path.exists(prompt_audio):
        return prompt_audio
    raw = base64.b64decode(prompt_audio)
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return tmp


def _synthesize(text: str, prompt_text: str, prompt_audio: str, mode: str) -> bytes:
    import numpy as np
    import soundfile as sf
    import torch

    ref_path = _resolve_ref_path(prompt_audio)
    tmp_created = ref_path != prompt_audio
    try:
        prompt_16k = _load_wav(ref_path, 16000)

        if mode == "cross_lingual":
            gen = _MODEL.inference_cross_lingual(
                instruct_text=text, prompt_speech_16k=prompt_16k, stream=False)
        elif mode == "zero_shot":
            gen = _MODEL.inference_zero_shot(
                text=text, instruct_text=prompt_text,
                prompt_speech_16k=prompt_16k, stream=False)
        else:  # instruct（默认）
            gen = _MODEL.inference_instruct2(
                text=text, instruct_text=prompt_text,
                prompt_speech_16k=prompt_16k, stream=False)

        chunks = [j["tts_speech"] for j in gen]
        if not chunks:
            raise RuntimeError("model yielded no tts_speech")
        audio = torch.cat(chunks, dim=1).squeeze(0).cpu().numpy()
        audio = np.clip(audio, -1.0, 1.0)

        buf = io.BytesIO()
        sf.write(buf, audio, _SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
    finally:
        if tmp_created:
            try:
                os.remove(ref_path)
            except OSError:
                pass


def _build_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response

    app = FastAPI(title="Fun-CosyVoice3 Server")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok" if _MODEL is not None else "loading",
                             "model": "Fun-CosyVoice3-0.5B"})

    @app.get("/v1/cosyvoice/config")
    def config():
        return JSONResponse({"sampling_rate": _SR,
                             "supported_modes": ["instruct", "zero_shot", "cross_lingual"],
                             "model_dir": _MODEL_DIR})

    @app.post("/v1/cosyvoice/generate")
    async def generate(request: Request):
        if _MODEL is None:
            return JSONResponse({"error": "model not loaded"}, status_code=503)
        body = await request.json()
        text = body.get("text", "")
        prompt_text = body.get("prompt_text", "")
        prompt_audio = body.get("prompt_audio", "")
        mode = body.get("mode", "instruct")
        if not text:
            return JSONResponse({"error": "missing text"}, status_code=400)
        if not prompt_audio:
            return JSONResponse({"error": "missing prompt_audio"}, status_code=400)
        t0 = time.time()
        try:
            with _INFER_LOCK:
                wav_bytes = _synthesize(text, prompt_text, prompt_audio, mode)
        except Exception as err:  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)
        print(f"[cosyvoice] mode={mode} len={len(text)}chars -> {len(wav_bytes)}B "
              f"in {time.time()-t0:.1f}s", flush=True)
        return Response(content=wav_bytes, media_type="audio/wav")

    return app


def main() -> int:
    p = argparse.ArgumentParser(description="Fun-CosyVoice3 HTTP server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8005)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--model-dir", default="pretrained_models/Fun-CosyVoice3-0.5B")
    p.add_argument("--cosyvoice-root", default=os.getcwd(),
                   help="CosyVoice 仓库根目录（默认当前工作目录）")
    args = p.parse_args()

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", args.device.split(":")[-1]
                          if args.device.startswith("cuda") else "")

    _load_model(args.model_dir, args.cosyvoice_root)

    import uvicorn
    app = _build_app()
    print(f"[cosyvoice] serving on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
