"""src_next/voicebank/scripts/run_voicedesign_srcnext.py

src_next 自己维护的 Qwen3-TTS VoiceDesign wrapper。

和外部 F:/akoasm/TTS-test/pipeline/run_voicedesign.py 的差异：
* 不再硬编码 attn_implementation="flash_attention_2"；
* 新增 --attn-implementation CLI 参数，默认 "sdpa"（PyTorch 原生，不需要
  flash-attn 包）；可选 "sdpa" / "flash_attention_2" / "eager"；
* 启动时打印关键配置（model_dir / device / language / attn / output），
  方便 adapter 的 .log 文件排查；
* 模型加载失败时抛出清晰异常，并在异常里点出可能原因（如选了
  flash_attention_2 但 venv 没装 flash_attn）。

CLI 接口（和原脚本完全兼容，adapter 不用改逻辑）：
    --text              要合成的文本（默认测试句）
    --instruct          音色描述（voicedesign 核心参数）
    --output            wav 输出路径
    --model-dir         本地模型目录（不传则从 HuggingFace 拉）
    --language          Chinese / English / Japanese / ...
    --device            cuda:0 / cpu / ...
    --attn-implementation  sdpa / flash_attention_2 / eager  （新增，默认 sdpa）
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


_SUPPORTED_ATTN = ("sdpa", "flash_attention_2", "eager")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="src_next Qwen3-TTS VoiceDesign wrapper (sdpa-default)"
    )
    parser.add_argument(
        "--text",
        type=str,
        default="你好，欢迎使用语音设计功能，这是一个测试句子。",
        help="Text to synthesize",
    )
    parser.add_argument(
        "--instruct",
        type=str,
        default="用温柔甜美的女声说",
        help="Voice design instruction",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="Chinese",
        help="Language (Chinese / English / Japanese / ...)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_voicedesign.wav",
        help="Output wav path",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Local model directory (default: auto-download from HF)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda:0",
        help="Device (cuda:0 / cpu / ...)",
    )
    parser.add_argument(
        "--attn-implementation",
        type=str,
        default="sdpa",
        choices=_SUPPORTED_ATTN,
        help=(
            "Attention implementation. "
            "'sdpa' = PyTorch native (no extra deps, default). "
            "'flash_attention_2' = requires `pip install flash-attn`. "
            "'eager' = pure PyTorch fallback (slowest)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # 延迟 import：让 --help 不依赖 torch / qwen_tts
    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel
    except ImportError as err:
        print(
            f"[srcnext-voicedesign] 依赖缺失: {type(err).__name__}: {err}\n"
            "请检查 venv 是否安装了 torch / soundfile / qwen-tts。",
            file=sys.stderr,
            flush=True,
        )
        return 2

    model_id = args.model_dir or "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60, flush=True)
    print("[srcnext-voicedesign] 配置:", flush=True)
    print(f"  model_dir           = {model_id}", flush=True)
    print(f"  device              = {args.device}", flush=True)
    print(f"  language            = {args.language}", flush=True)
    print(f"  attn_implementation = {args.attn_implementation}", flush=True)
    print(f"  output              = {output_path}", flush=True)
    print(f"  text                = {args.text!r}", flush=True)
    print(f"  instruct            = {args.instruct!r}", flush=True)
    print("=" * 60, flush=True)

    print(f"[srcnext-voicedesign] 加载模型 ...", flush=True)
    try:
        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=args.device,
            dtype=torch.bfloat16,
            attn_implementation=args.attn_implementation,
        )
    except Exception as err:
        # 重点提示：选了 flash_attention_2 但 venv 缺 flash_attn 的情况
        if args.attn_implementation == "flash_attention_2":
            print(
                f"[srcnext-voicedesign] 模型加载失败: {type(err).__name__}: {err}\n"
                "提示：你选了 --attn-implementation flash_attention_2，"
                "但当前 venv 似乎没装 flash_attn 包。\n"
                "可选解决方案：\n"
                "  1) 改用 --attn-implementation sdpa（推荐，无需额外依赖）；\n"
                "  2) pip install flash-attn --no-build-isolation（需要 nvcc，"
                "编译耗时较长）。",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                f"[srcnext-voicedesign] 模型加载失败: {type(err).__name__}: {err}",
                file=sys.stderr,
                flush=True,
            )
        traceback.print_exc()
        return 3

    print("[srcnext-voicedesign] 生成语音 ...", flush=True)
    try:
        wavs, sr = model.generate_voice_design(
            text=args.text,
            instruct=args.instruct,
            language=args.language,
        )
    except Exception as err:
        print(
            f"[srcnext-voicedesign] 生成失败: {type(err).__name__}: {err}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc()
        return 4

    if not wavs:
        print(
            "[srcnext-voicedesign] 模型返回空音频列表，未写出 wav。",
            file=sys.stderr,
            flush=True,
        )
        return 5

    sf.write(str(output_path), wavs[0], sr)
    print(
        f"[srcnext-voicedesign] 已写出: {output_path} (sr={sr})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
