"""servers/api_server_indextts.py

外部部署用：把 IndexTTS-2 包成 HTTP 服务，
契约对齐 src_next/tts/indextts_http.py（client）与 usage_guide_indextts.md。

端点：
    GET  /health                → {"status":"ok","model":"IndexTTS 2 (Full)",...}
    GET  /v1/tts/config          → 运行配置
    POST /v1/tts/synthesize      → body {text, reference_audio_base64|reference_audio_path,
                                          emotion_vector, emotion_alpha, emotion_text,
                                          use_random, temperature, top_p, top_k, num_beams,
                                          max_mel_tokens, max_text_tokens, interval_silence}
                                   返回 wav 字节流

字段映射（payload → IndexTTS2.infer）：
    reference_audio_base64/path → spk_audio_prompt（音色参考）
    text                        → text
    emotion_vector              → emo_vector（8 维）
    emotion_alpha               → emo_alpha
    emotion_text                → emo_text（+ use_emo_text=True）
    use_random                  → use_random
    max_text_tokens             → max_text_tokens_per_sentence
    interval_silence            → interval_silence
    temperature/top_p/top_k/num_beams/max_mel_tokens → generation kwargs（best-effort，
        infer 签名不接受时自动去掉重试）

模型调用：from indextts.infer_v2 import IndexTTS2; tts.infer(spk, text, out_path, ...)
infer 自己把 wav 写到 out_path（native SR），server 读回字节返回。

运行环境：index-tts 官方 env（clone 仓库后 pip install -e .）。本脚本不 import src_next。

启动示例（在 /root/autodl-tmp/index-tts 下）：
    python /root/autodl-tmp/api_server_indextts.py --port 8009 --model-dir checkpoints
"""

from __future__ import annotations

import argparse
import base64
import os
import tempfile
import threading
import time
import traceback


_MODEL = None
_MODEL_DIR = ""
_INFER_LOCK = threading.Lock()


def _load_model(model_dir: str, cfg_path: str, use_fp16: bool) -> None:
    global _MODEL, _MODEL_DIR
    _MODEL_DIR = model_dir
    from indextts.infer_v2 import IndexTTS2
    print(f"[indextts] loading model_dir={model_dir} cfg={cfg_path} fp16={use_fp16} ...", flush=True)
    t0 = time.time()
    _MODEL = IndexTTS2(
        cfg_path=cfg_path,
        model_dir=model_dir,
        use_fp16=use_fp16,
        use_cuda_kernel=False,
        use_deepspeed=False,
    )
    print(f"[indextts] model loaded in {time.time()-t0:.1f}s", flush=True)


def _resolve_spk(body: dict) -> tuple[str, bool]:
    """返回 (spk_audio_path, is_temp)。优先 base64，其次 path。"""
    b64 = body.get("reference_audio_base64")
    if b64:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(base64.b64decode(b64))
        return tmp, True
    path = body.get("reference_audio_path")
    if path and os.path.exists(path):
        return path, False
    raise ValueError("missing reference_audio_base64 / reference_audio_path")


def _synthesize(body: dict) -> bytes:
    text = body.get("text", "")
    if not text:
        raise ValueError("missing text")

    spk_path, spk_is_tmp = _resolve_spk(body)
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    # 核心情感/随机参数
    core: dict = {"verbose": False}
    if body.get("emotion_vector") is not None:
        core["emo_vector"] = list(body["emotion_vector"])
    if body.get("emotion_alpha") is not None:
        core["emo_alpha"] = float(body["emotion_alpha"])
    if body.get("emotion_text"):
        core["emo_text"] = str(body["emotion_text"])
        core["use_emo_text"] = True
    if body.get("use_random") is not None:
        core["use_random"] = bool(body["use_random"])

    # 可选的时长/生成参数（best-effort）
    extra: dict = {}
    if body.get("max_text_tokens") is not None:
        extra["max_text_tokens_per_sentence"] = int(body["max_text_tokens"])
    if body.get("interval_silence") is not None:
        extra["interval_silence"] = int(body["interval_silence"])
    for k in ("temperature", "top_p", "top_k", "num_beams",
              "max_mel_tokens", "repetition_penalty"):
        if body.get(k) is not None:
            extra[k] = body[k]

    try:
        try:
            with _INFER_LOCK:
                _MODEL.infer(spk_path, text, out_path, **core, **extra)
        except TypeError:
            # infer 不接受某些可选 kwargs → 只用核心参数重试
            with _INFER_LOCK:
                _MODEL.infer(spk_path, text, out_path, **core)

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p, is_tmp in ((spk_path, spk_is_tmp), (out_path, True)):
            if is_tmp:
                try:
                    os.remove(p)
                except OSError:
                    pass


def _build_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response

    app = FastAPI(title="IndexTTS-2 Server")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok" if _MODEL is not None else "loading",
                             "model": "IndexTTS 2 (Full)", "sampling_rate": 22050})

    @app.get("/v1/tts/config")
    def config():
        return JSONResponse({"model_dir": _MODEL_DIR, "sampling_rate": 22050})

    @app.post("/v1/tts/synthesize")
    async def synthesize(request: Request):
        if _MODEL is None:
            return JSONResponse({"error": "model not loaded"}, status_code=503)
        body = await request.json()
        t0 = time.time()
        try:
            wav_bytes = _synthesize(body)
        except ValueError as err:
            return JSONResponse({"error": str(err)}, status_code=400)
        except Exception as err:  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)
        print(f"[indextts] len={len(body.get('text',''))}chars -> {len(wav_bytes)}B "
              f"in {time.time()-t0:.1f}s", flush=True)
        return Response(content=wav_bytes, media_type="audio/wav")

    return app


def main() -> int:
    p = argparse.ArgumentParser(description="IndexTTS-2 HTTP server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8009)
    p.add_argument("--model-dir", default="checkpoints")
    p.add_argument("--cfg-path", default=None, help="默认 <model-dir>/config.yaml")
    p.add_argument("--fp16", action="store_true", help="用 fp16 加载（省显存）")
    args = p.parse_args()

    cfg_path = args.cfg_path or os.path.join(args.model_dir, "config.yaml")
    _load_model(args.model_dir, cfg_path, args.fp16)

    import uvicorn
    print(f"[indextts] serving on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(_build_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
