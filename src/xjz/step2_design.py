"""Stage 2 — VoiceDesign via Qwen3-TTS.

For each character in `voice_design.json`, calls the Qwen3 VoiceDesign HTTP
API to synthesize a reference wav using a fixed neutral sample text + the
character's voice profile. Writes the wav plus a manifest for Stage 3.

Usage:
    python step2_design.py --input path/to/story.txt
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import config, tts_client


def main() -> int:
    args = _parse_args()
    out_dir = config.story_output_dir(args.input)
    design_path = out_dir / "voice_design.json"
    if not design_path.is_file():
        print(f"[error] {design_path} not found — run step1_split.py first",
              file=sys.stderr)
        return 1

    design = json.loads(design_path.read_text(encoding="utf-8"))
    voices_dir = out_dir / "prompt_voices"
    voices_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict[str, str]] = {}
    sample_text = design["neutral_sample_text"]
    model = args.model

    for char in design["characters"]:
        name = char["name"]
        wav_path = voices_dir / f"{name}.wav"
        if wav_path.exists():
            print(f"[skip] {wav_path.name} already exists")
        else:
            instruction = (
                f"【角色音色】{char['voice_profile']}\n"
                f"【当前语气】{char['emotion_for_design']}\n"
                f"【控制要求】{char['control_rule']}"
            )
            print(f"[step2] designing voice for {name} (model={model}) ...")
            if model == "moss":
                wav_bytes = tts_client.moss_voicedesign(
                    text=sample_text,
                    instruction=instruction,
                )
            else:
                wav_bytes = tts_client.qwen3_voicedesign(
                    text=sample_text,
                    instruction=instruction,
                    language=design.get("language", config.LANGUAGE),
                )
            wav_path.write_bytes(wav_bytes)
            print(f"[step2] wrote {wav_path}")

        manifest[name] = {
            "wav_path": wav_path.relative_to(out_dir).as_posix(),
            "sample_text": sample_text,
        }

    manifest_path = voices_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[step2] wrote {manifest_path}")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage 2: VoiceDesign for each character")
    p.add_argument("--input", required=True,
                   help="path to source .txt (used to locate outputs/<stem>/)")
    p.add_argument("--model", choices=["qwen3", "moss"], default="qwen3",
                   help="选择使用的 TTS 模型 (默认: qwen3)")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
