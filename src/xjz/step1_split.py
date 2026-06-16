"""Stage 1 — Text splitting via LLM.

Reads a .txt story, makes two LLM calls (character extraction, then segment
splitting), and writes `voice_design.json` + `voice_clone.json` into the
story's output directory.

Supports two TTS backends:
    - cosyvoice: Fun-CosyVoice3 (default)
    - indextts:  IndexTTS-2 (with emotion control)

Usage:
    python step1_split.py --input path/to/story.txt
    python step1_split.py --input path/to/story.txt --tts-model indextts
"""

import argparse
import json
import sys
from pathlib import Path

# Allow `python step1_split.py` from project root without installation
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import config
from common.llm_client import LLMClient


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input).resolve()
    tts_model = args.tts_model or config.CLONE_MODEL

    if not input_path.is_file():
        print(f"[error] input file not found: {input_path}", file=sys.stderr)
        return 1

    if tts_model not in ("cosyvoice", "indextts"):
        print(f"[error] invalid --tts-model {tts_model!r}", file=sys.stderr)
        return 1

    out_dir = config.story_output_dir(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    design_path = out_dir / "voice_design.json"
    clone_path = out_dir / "voice_clone.json"

    if not args.force and design_path.exists() and clone_path.exists():
        print(f"[skip] {design_path.name} and {clone_path.name} already exist "
              f"(use --force to regenerate)")
        return 0

    story_text = input_path.read_text(encoding="utf-8")
    char_prompt = (config.PROMPTS_DIR / "character_voice_prompt.txt").read_text(encoding="utf-8")

    # Choose segment prompt based on TTS model
    if tts_model == "indextts":
        seg_prompt = (config.PROMPTS_DIR / "segment_split_indextts.txt").read_text(encoding="utf-8")
    else:
        seg_prompt = (config.PROMPTS_DIR / "segment_split.txt").read_text(encoding="utf-8")

    llm = LLMClient()

    print(f"[step1] extracting characters from {input_path.name} ...")
    char_payload = llm.chat_json(char_prompt, story_text)
    characters = char_payload["characters"]
    print(f"[step1] found {len(characters)} character(s): "
          f"{', '.join(c['name'] for c in characters)}")

    print(f"[step1] splitting text into segments (tts_model={tts_model}) ...")
    seg_user_msg = (
        f"已知角色列表：{json.dumps([c['name'] for c in characters], ensure_ascii=False)}\n\n"
        f"原文：\n{story_text}"
    )
    seg_payload = llm.chat_json(seg_prompt, seg_user_msg)
    segments = seg_payload["segments"]
    print(f"[step1] produced {len(segments)} segment(s)")

    voice_design = {
        "source_file": input_path.name,
        "language": config.LANGUAGE,
        "neutral_sample_text": config.NEUTRAL_SAMPLE_TEXT,
        "tts_model": tts_model,
        "characters": [
            {**c, "control_rule": config.CONTROL_RULE} for c in characters
        ],
    }
    design_path.write_text(
        json.dumps(voice_design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    voice_clone = {
        "source_file": input_path.name,
        "language": config.LANGUAGE,
        "tts_model": tts_model,
        "total_segments": len(segments),
        "segments": segments,
    }
    clone_path.write_text(
        json.dumps(voice_clone, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[step1] wrote {design_path}")
    print(f"[step1] wrote {clone_path}")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage 1: LLM-driven text splitting",
        epilog="""
Examples:
    python step1_split.py --input story.txt
    python step1_split.py --input story.txt --tts-model indextts
        """,
    )
    p.add_argument("--input", required=True,
                   help="path to source .txt (e.g. F:/akoasm/dataset/text/sample_story_01.txt)")
    p.add_argument("--tts-model", choices=["cosyvoice", "indextts"],
                   help=f"TTS model for cloning (defaults to config.CLONE_MODEL={config.CLONE_MODEL})")
    p.add_argument("--force", action="store_true",
                   help="regenerate even if outputs already exist")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())