"""Pipeline runner — orchestrates step1/2/3/4 end to end.

Usage:
    python run_pipeline.py --input path/to/story.txt [--vd-model qwen3|moss] [--tts-model cosyvoice|indextts]
    python run_pipeline.py --input test_story.txt --vd-model moss
    python run_pipeline.py --input test_story.txt --tts-model indextts
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Allow direct execution from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import config, tts_client


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input).resolve()
    vd_model = args.vd_model or "qwen3"
    tts_model = args.tts_model or config.CLONE_MODEL

    print("=" * 60)
    print(f"TTS Pipeline — vd_model={vd_model}, tts_model={tts_model}")
    print(f"Input: {input_path}")
    print("=" * 60)

    # Check service health
    print("\n[health] checking TTS services ...")
    health = tts_client.health_checks()
    for svc, ok in health.items():
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {svc}")

    # Check voice design model service
    vd_key = f"{vd_model}_voicedesign"
    if vd_key not in health:
        print(f"[error] unknown --vd-model: {vd_model} (available: qwen3, moss)", file=sys.stderr)
        return 1
    if not health[vd_key]:
        print(f"[error] {vd_model} voice design service is not available", file=sys.stderr)
        return 1

    # Check TTS model service
    if tts_model not in ("cosyvoice", "indextts"):
        print(f"[error] invalid --tts-model: {tts_model} (available: cosyvoice, indextts)", file=sys.stderr)
        return 1

    # Build step commands
    step1_cmd = ["python", "step1_split.py", "--input", str(input_path), "--tts-model", tts_model]
    step2_cmd = ["python", "step2_design.py", "--input", str(input_path), "--model", vd_model]
    step3_cmd = ["python", "step3_clone.py", "--input", str(input_path), "--tts-model", tts_model]
    step4_cmd = ["python", "step4_merge.py", "--input", str(input_path)]

    steps = [
        ("step1", "Text splitting", step1_cmd),
        ("step2", "Voice design", step2_cmd),
        ("step3", "Voice clone", step3_cmd),
        ("step4", "Merge audio", step4_cmd),
    ]

    total_start = time.time()
    stage_times = {}

    for step_id, step_name, cmd in steps:
        print(f"\n[run] === Stage {step_id}: {step_name} ===")
        stage_start = time.time()
        result = subprocess.run(cmd, cwd=Path(__file__).resolve().parent)
        stage_elapsed = time.time() - stage_start
        stage_times[step_id] = stage_elapsed
        print(f"[timing] {step_id} took {stage_elapsed:.2f}s")
        if result.returncode != 0:
            print(f"\n[error] step {step_id} failed with code {result.returncode}", file=sys.stderr)
            return result.returncode

    total_elapsed = time.time() - total_start

    final_path = config.story_output_dir(input_path) / "final.wav"
    print("\n" + "=" * 60)
    print(f"Done: {final_path}")
    print("=" * 60)
    print("\n[timing] === Stage breakdown ===")
    for step_id, elapsed in stage_times.items():
        print(f"  {step_id}: {elapsed:.2f}s")
    print(f"  Total: {total_elapsed:.2f}s")
    print("=" * 60)
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="End-to-end TTS pipeline: split -> design -> clone -> merge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_pipeline.py --input test_story.txt
    python run_pipeline.py --input test_story.txt --vd-model moss
    python run_pipeline.py --input test_story.txt --tts-model indextts
    python run_pipeline.py --input test_story.txt --vd-model qwen3 --tts-model indextts
        """,
    )
    p.add_argument("--input", required=True,
                   help="path to source .txt story file")
    p.add_argument("--vd-model", choices=["qwen3", "moss"],
                   help="Voice design model (default: qwen3)")
    p.add_argument("--tts-model", choices=["cosyvoice", "indextts"],
                   help=f"TTS model for cloning (default: {config.CLONE_MODEL})")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())