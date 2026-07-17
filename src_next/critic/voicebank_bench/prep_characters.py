"""src_next/critic/voicebank_bench/prep_characters.py

对 audiobench_zh 测试集的 30 个故事跑 pipeline stage 1-5，
产出 characters.json 及上游中间产物，供 voicebank bench 使用。

调用方式（从项目根目录）：
    python -m src_next.critic.voicebank_bench.prep_characters \
        --profile src_next/profiles/yellow_voxcpm2_cosyvoicehttp.yaml \
        [--skip-existing] [--cases basic_children_01,basic_children_02]

产物目录：
    tests/audiobench_zh/_prep_characters/
    ├── basic_children_01/
    │   ├── segments_raw.json
    │   ├── segments_after_quote_merge.json
    │   ├── quote_classifications.json
    │   ├── resolved_segments.json
    │   └── characters.json
    └── ...
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from dataclasses import asdict, fields as dataclass_fields, is_dataclass
from pathlib import Path
from typing import Any

# Windows UTF-8 输出（中文角色名/故事文本）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import yaml

from src_next.analysis.character_analyzer import analyze_characters
from src_next.analysis.quote_classifier import classify_and_merge_quotes
from src_next.analysis.story_resolver import resolve_speakers
from src_next.core.data_models import CharacterProfile, Segment, StoryInput
from src_next.core.segment_builder import build_segments
from src_next.llm.registry import create_llm_client


# ─────────────────────────────────────────────────────────────────────────────
# 序列化工具（复用 pipeline 的模式）
# ─────────────────────────────────────────────────────────────────────────────

def _serialize(obj: Any) -> Any:
    """递归序列化 dataclass / Path / 其他类型为 JSON 兼容格式。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return _serialize(asdict(obj))
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def _save_json(obj: Any, path: Path) -> None:
    """保存为 UTF-8 JSON（缩进 2，保留中文）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_serialize(obj), f, ensure_ascii=False, indent=2)


def _dataclass_from_list(path: Path, cls: type) -> list[Any]:
    """从 JSON list 还原 dataclass 列表，过滤未知字段。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    allowed = {f.name for f in dataclass_fields(cls)}
    out: list[Any] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kwargs = {k: v for k, v in item.items() if k in allowed}
        out.append(cls(**kwargs))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Profile 加载（复用 pipeline 的逻辑）
# ─────────────────────────────────────────────────────────────────────────────

def _load_pipeline_profile(path: str | Path) -> dict[str, Any]:
    """yaml.safe_load + 5 块校验。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"profile 不存在: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"profile 顶层不是 dict: {p}")
    for block in ("llm", "voicebank", "tts", "output", "pipeline"):
        if block not in data:
            raise ValueError(f"profile 缺块: {block!r}（file={p}）")
    return data


def _split_backend_block(profile: dict[str, Any], block: str) -> tuple[str, dict[str, Any]]:
    """从 profile[block] pop 出 backend，返回 (backend, 剩余 config 字典)。"""
    block_dict = dict(profile[block])
    backend = block_dict.pop("backend")
    return backend, block_dict


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────

# 产物统一存放在 tests/audiobench_zh/ 下
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src_next/critic/voicebank_bench/ → 项目根
BENCH_DIR = _PROJECT_ROOT / "tests" / "audiobench_zh"
CASES_DIR = BENCH_DIR / "cases"
OUTPUT_DIR = BENCH_DIR / "_prep_characters"


def _discover_cases() -> list[str]:
    """扫描 cases/ 目录，返回所有 case id（按文件名排序）。"""
    ids: list[str] = []
    for txt in sorted(CASES_DIR.glob("*.txt")):
        ids.append(txt.stem)
    return ids


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="audiobench_zh: 预处理 stage 1-5，生成 characters.json",
    )
    parser.add_argument(
        "--profile", required=True,
        help="profile yaml 路径（用于创建 LLM 客户端）",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="已有 characters.json 的 case 跳过",
    )
    parser.add_argument(
        "--cases", default="",
        help="逗号分隔的 case id 列表（为空则跑全部 30 个）",
    )
    return parser.parse_args()


def _process_one_case(
    case_id: str,
    llm_client: Any,
    *,
    skip_existing: bool,
) -> dict[str, Any]:
    """处理单个 case，返回结果摘要字典。"""
    case_dir = OUTPUT_DIR / case_id
    characters_path = case_dir / "characters.json"

    # 检查是否跳过
    if skip_existing and characters_path.exists():
        chars = _dataclass_from_list(characters_path, CharacterProfile)
        return {
            "case_id": case_id,
            "status": "skipped",
            "n_characters": len(chars),
            "elapsed_sec": 0.0,
        }

    # 读取故事文本
    txt_path = CASES_DIR / f"{case_id}.txt"
    if not txt_path.exists():
        return {"case_id": case_id, "status": "error", "error": "txt 不存在", "elapsed_sec": 0.0}

    text = txt_path.read_text(encoding="utf-8-sig")
    story_name = case_id

    t0 = time.time()

    try:
        # Stage 1: build_segments
        story_input = StoryInput(story_name=story_name, text=text, source_path=str(txt_path))
        segments_raw = build_segments(story_input)
        _save_json(segments_raw, case_dir / "segments_raw.json")

        # Stage 3: quote_classifier
        quote_debug_path = case_dir / "quote_classifications.json"
        segments_merged = classify_and_merge_quotes(
            segments_raw, llm_client,
            story_context=story_name,
            output_debug_path=str(quote_debug_path),
        )
        _save_json(segments_merged, case_dir / "segments_after_quote_merge.json")

        # Stage 4: story_resolver
        resolved = resolve_speakers(
            segments_merged, llm_client,
            story_context=text,
        )
        _save_json(resolved, case_dir / "resolved_segments.json")

        # Stage 5: character_analyzer
        characters = analyze_characters(
            resolved, llm_client,
            story_context=text,
        )
        _save_json(characters, case_dir / "characters.json")

        elapsed = time.time() - t0
        return {
            "case_id": case_id,
            "status": "ok",
            "n_segments_raw": len(segments_raw),
            "n_segments_merged": len(segments_merged),
            "n_characters": len(characters),
            "elapsed_sec": round(elapsed, 2),
        }

    except Exception as err:
        elapsed = time.time() - t0
        return {
            "case_id": case_id,
            "status": "error",
            "error": f"{type(err).__name__}: {err}",
            "elapsed_sec": round(elapsed, 2),
        }


def main() -> int:
    args = _parse_args()

    # 加载 profile，创建 LLM 客户端
    profile = _load_pipeline_profile(args.profile)
    llm_backend, llm_cfg = _split_backend_block(profile, "llm")
    llm_client = create_llm_client(llm_backend, **llm_cfg)
    print(f"[prep] LLM backend={llm_backend}")

    # 确定 case 列表
    all_ids = _discover_cases()
    if args.cases:
        requested = set(args.cases.split(","))
        case_ids = [cid for cid in all_ids if cid in requested]
        unknown = requested - set(case_ids)
        if unknown:
            print(f"[prep] ⚠️ 未知 case id: {', '.join(sorted(unknown))}")
    else:
        case_ids = all_ids

    print(f"[prep] cases={len(case_ids)}, skip_existing={args.skip_existing}")
    print(f"[prep] output={OUTPUT_DIR}")
    print("=" * 70)

    # 逐 case 处理
    results: list[dict[str, Any]] = []
    for i, case_id in enumerate(case_ids, 1):
        result = _process_one_case(case_id, llm_client, skip_existing=args.skip_existing)
        results.append(result)
        status = result["status"]
        n_chars = result.get("n_characters", "?")
        elapsed = result.get("elapsed_sec", 0)
        tag = f"[{i}/{len(case_ids)}]"
        if status == "ok":
            print(f"{tag} {case_id:<28s} OK   chars={n_chars}  {elapsed:.1f}s")
        elif status == "skipped":
            print(f"{tag} {case_id:<28s} SKIP chars={n_chars}")
        else:
            err = result.get("error", "unknown")
            print(f"{tag} {case_id:<28s} ERR  {err}")

    # 汇总
    print("=" * 70)
    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skipped")
    n_err = sum(1 for r in results if r["status"] == "error")
    total_time = sum(r.get("elapsed_sec", 0) for r in results)
    print(f"[summary] ok={n_ok}  skipped={n_skip}  error={n_err}  total_time={total_time:.1f}s")

    if n_err > 0:
        print("\n[errors]")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['case_id']}: {r.get('error', 'unknown')}")

    return 1 if n_err > 0 else 0


if __name__ == "__main__":
    sys.exit(main())