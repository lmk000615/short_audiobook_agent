"""Stage 4 — Merge per-segment wavs into a single final wav.

Concatenates all `segments/*.wav` in filename order, inserting N ms of silence
between consecutive segments. Uses soundfile for format-agnostic WAV handling.

Usage:
    python step4_merge.py --input path/to/story.txt [--silence-ms N]
"""

import argparse
import sys
import soundfile as sf
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import config


def main() -> int:
    args = _parse_args()
    silence_ms = args.silence_ms if args.silence_ms is not None else config.SILENCE_BETWEEN_SEGMENTS_MS

    out_dir = config.story_output_dir(args.input)
    segments_dir = out_dir / "segments"
    if not segments_dir.is_dir():
        print(f"[error] {segments_dir} not found — run step3_clone.py first",
              file=sys.stderr)
        return 1

    segment_paths = sorted(segments_dir.glob("*.wav"))
    if not segment_paths:
        print(f"[error] no wavs under {segments_dir}", file=sys.stderr)
        return 1

    final_path = out_dir / "final.wav"

    # Read first file to get sample rate and channels
    first_data, samplerate = sf.read(str(segment_paths[0]))
    if len(first_data.shape) == 1:
        channels = 1
    else:
        channels = first_data.shape[1]

    # Generate silence
    silence_frames = int(samplerate * silence_ms / 1000)
    silence = np.zeros((silence_frames, channels) if channels > 1 else silence_frames, dtype=first_data.dtype)

    # Concatenate all segments with silence
    all_data = first_data
    for i, p in enumerate(segment_paths[1:], start=1):
        data, _ = sf.read(str(p))
        all_data = np.concatenate([all_data, silence, data])

    # Write output (convert to PCM_16 for compatibility)
    sf.write(str(final_path), all_data, samplerate, subtype='PCM_16')

    print(f"[step4] merged {len(segment_paths)} segments "
          f"({silence_ms}ms silence between) -> {final_path}")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage 4: concatenate segment wavs")
    p.add_argument("--input", required=True,
                   help="path to source .txt (used to locate outputs/<stem>/)")
    p.add_argument("--silence-ms", type=int, default=None,
                   help="silence between segments in ms (default 300; set 0 to disable)")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
