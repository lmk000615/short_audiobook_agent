"""src_next/critic/voicebank_bench/run_voicebank_bench.py

Voicebank + Voicebank Critic 基准测试脚本。

从 _prep_characters/ 加载 characters.json，对每个 case 跑 voicebank 生成
+ critic 评分，产物按 profile name 分目录存放，支持多 profile 对比。

调用方式（从项目根目录）：
    # 完整测试（voicebank + critic）
    python -m src_next.critic.voicebank_bench.run_voicebank_bench \
        --profile src_next/profiles/yellow_voxcpm2_cosyvoicehttp.yaml

    # 只跑 voicebank，不跑 critic
    python -m src_next.critic.voicebank_bench.run_voicebank_bench \
        --profile src_next/profiles/yellow_voxcpm2_cosyvoicehttp.yaml --no-critic

    # 只对已有 wav 重跑 critic
    python -m src_next.critic.voicebank_bench.run_voicebank_bench \
        --profile src_next/profiles/yellow_voxcpm2_cosyvoicehttp.yaml --critic-only

    # 指定 case + 跳过已有
    python -m src_next.critic.voicebank_bench.run_voicebank_bench \
        --profile src_next/profiles/yellow_voxcpm2_cosyvoicehttp.yaml \
        --cases basic_children_01,basic_children_02 --skip-existing

产物目录：
    tests/audiobench_zh/_voicebank_results/
    ├── voxcpm2_cosyvoice/           # profile name
    │   ├── basic_children_01/
    │   │   ├── voicebank_result.json
    │   │   ├── voicebank_critic_result.json
    │   │   ├── voicebank_critic_regen_history.json
    │   │   ├── voicebank/
    │   │   │   ├── narrator.wav
    │   │   │   └── critic.log
    │   │   └── bench_summary.json
    │   └── ...
    └── _bench_report.json           # 全量汇总
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

# Windows UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import yaml

from src_next.core.data_models import CharacterProfile, VoicebankCriticResult, VoicebankResult
from src_next.llm.registry import create_llm_client
from src_next.voicebank.registry import create_voicebank_adapter
from src_next.voicebank.voicebank_critic import run_voicebank_critic


# ─────────────────────────────────────────────────────────────────────────────
# 序列化工具
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


def _load_voicebank_result(path: Path) -> VoicebankResult:
    """从 JSON 还原 VoicebankResult。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {f.name for f in dataclass_fields(VoicebankResult)}
    kwargs = {k: v for k, v in raw.items() if k in allowed} if isinstance(raw, dict) else {}
    return VoicebankResult(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Profile 加载
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
# 常量
# ─────────────────────────────────────────────────────────────────────────────

# 产物统一存放在 tests/audiobench_zh/ 下
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src_next/critic/voicebank_bench/ → 项目根
BENCH_DIR = _PROJECT_ROOT / "tests" / "audiobench_zh"
PREP_DIR = BENCH_DIR / "_prep_characters"
RESULTS_ROOT = BENCH_DIR / "_voicebank_results"


def _discover_prep_cases() -> list[str]:
    """扫描 _prep_characters/ 目录，返回有 characters.json 的 case id。"""
    ids: list[str] = []
    for d in sorted(PREP_DIR.iterdir()):
        if d.is_dir() and (d / "characters.json").exists():
            ids.append(d.name)
    return ids


def _profile_label(profile: dict[str, Any]) -> str:
    """从 profile 生成简短标签用作目录名。"""
    name = profile.get("name", "")
    if name:
        return name
    # 兜底：voicebank backend + tts backend
    vb = profile.get("voicebank", {}).get("backend", "unknown")
    tts = profile.get("tts", {}).get("backend", "unknown")
    return f"{vb}_{tts}"


# ─────────────────────────────────────────────────────────────────────────────
# 单 case 处理
# ─────────────────────────────────────────────────────────────────────────────

def _process_one_case(
    case_id: str,
    *,
    profile: dict[str, Any],
    llm_client: Any,
    vb_adapter: Any,
    profile_label: str,
    no_critic: bool,
    critic_only: bool,
    skip_existing: bool,
) -> dict[str, Any]:
    """处理单个 case，返回结果摘要。"""
    case_dir = RESULTS_ROOT / profile_label / case_id
    vb_result_path = case_dir / "voicebank_result.json"

    # 加载 characters
    chars_path = PREP_DIR / case_id / "characters.json"
    if not chars_path.exists():
        return {"case_id": case_id, "status": "error", "error": "characters.json 不存在，先跑 prep_characters"}

    characters = _dataclass_from_list(chars_path, CharacterProfile)

    # ── critic-only 模式 ──────────────────────────────────────
    if critic_only:
        if not vb_result_path.exists():
            return {"case_id": case_id, "status": "error", "error": "critic-only 但 voicebank_result.json 不存在"}
        return _run_critic_only(
            case_id, case_dir, characters, profile, llm_client, vb_adapter,
        )

    # ── 跳过已有 ──────────────────────────────────────────────
    if skip_existing and vb_result_path.exists():
        vb_result = _load_voicebank_result(vb_result_path)
        return {
            "case_id": case_id,
            "status": "skipped",
            "n_characters": len(characters),
            "n_voices": len(vb_result.speaker_to_voice),
            "elapsed_sec": 0.0,
        }

    # ── 正常流程：voicebank + 可选 critic ─────────────────────
    t0 = time.time()
    try:
        # Stage 6: voicebank
        voicebank_result = vb_adapter.prepare_voicebank(characters, str(case_dir))
        _save_json(voicebank_result, vb_result_path)

        # Stage 6b: voicebank_critic（可选）
        critic_result = None
        critic_config = profile.get("pipeline", {}).get("voicebank_critic", {})
        critic_enabled = bool(critic_config.get("enabled", False)) and not no_critic

        if critic_enabled:
            critic_result = run_voicebank_critic(
                characters=characters,
                voicebank_result=voicebank_result,
                llm_client=llm_client,
                vb_adapter=vb_adapter,
                output_dir=str(case_dir),
                critic_config=critic_config,
            )
            # 落盘 critic 结果
            _save_json(critic_result, case_dir / "voicebank_critic_result.json")
            if critic_result.regen_history:
                _save_json(critic_result.regen_history, case_dir / "voicebank_critic_regen_history.json")
            # 更新 voicebank_result（critic 可能就地更新了 speaker_to_voice）
            _save_json(voicebank_result, vb_result_path)

        elapsed = time.time() - t0

        # 生成 bench_summary.json
        summary = _build_bench_summary(
            case_id, characters, voicebank_result, critic_result, elapsed,
        )
        _save_json(summary, case_dir / "bench_summary.json")

        return {
            "case_id": case_id,
            "status": "ok",
            "n_characters": len(characters),
            "n_voices": len(voicebank_result.speaker_to_voice),
            "critic_enabled": critic_enabled,
            "elapsed_sec": round(elapsed, 2),
            "critic_summary": _format_critic_brief(critic_result) if critic_result else None,
        }

    except Exception as err:
        elapsed = time.time() - t0
        return {
            "case_id": case_id,
            "status": "error",
            "error": f"{type(err).__name__}: {err}",
            "elapsed_sec": round(elapsed, 2),
        }


def _run_critic_only(
    case_id: str,
    case_dir: Path,
    characters: list[CharacterProfile],
    profile: dict[str, Any],
    llm_client: Any,
    vb_adapter: Any,
) -> dict[str, Any]:
    """critic-only 模式：对已有 voicebank 产物重跑 critic。"""
    t0 = time.time()
    try:
        voicebank_result = _load_voicebank_result(case_dir / "voicebank_result.json")
        critic_config = profile.get("pipeline", {}).get("voicebank_critic", {})

        # 强制启用 critic
        critic_config = dict(critic_config)
        critic_config["enabled"] = True

        critic_result = run_voicebank_critic(
            characters=characters,
            voicebank_result=voicebank_result,
            llm_client=llm_client,
            vb_adapter=vb_adapter,
            output_dir=str(case_dir),
            critic_config=critic_config,
        )
        _save_json(critic_result, case_dir / "voicebank_critic_result.json")
        if critic_result.regen_history:
            _save_json(critic_result.regen_history, case_dir / "voicebank_critic_regen_history.json")
        _save_json(voicebank_result, case_dir / "voicebank_result.json")

        elapsed = time.time() - t0
        summary = _build_bench_summary(case_id, characters, voicebank_result, critic_result, elapsed)
        _save_json(summary, case_dir / "bench_summary.json")

        return {
            "case_id": case_id,
            "status": "ok",
            "n_characters": len(characters),
            "n_voices": len(voicebank_result.speaker_to_voice),
            "critic_enabled": True,
            "elapsed_sec": round(elapsed, 2),
            "critic_summary": _format_critic_brief(critic_result),
        }

    except Exception as err:
        elapsed = time.time() - t0
        return {
            "case_id": case_id,
            "status": "error",
            "error": f"{type(err).__name__}: {err}",
            "elapsed_sec": round(elapsed, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 汇总格式化
# ─────────────────────────────────────────────────────────────────────────────

def _build_bench_summary(
    case_id: str,
    characters: list[CharacterProfile],
    voicebank_result: VoicebankResult,
    critic_result: VoicebankCriticResult | None,
    elapsed_sec: float,
) -> dict[str, Any]:
    """构建单 case 的 bench_summary.json。"""
    speaker_scores: list[dict[str, Any]] = []

    if critic_result:
        # 按 speaker 取最终轮结果
        by_speaker: dict[str, Any] = {}
        for r in critic_result.speaker_results:
            by_speaker[r.speaker] = r  # 后出现的覆盖前面的
        for spk, result in by_speaker.items():
            speaker_scores.append({
                "speaker": spk,
                "overall_score": round(result.overall_score, 3),
                "gender_match_score": round(result.gender_match_score, 3),
                "age_match_score": round(result.age_match_score, 3),
                "timbre_match_score": round(result.timbre_match_score, 3),
                "clarity_score": round(result.clarity_score, 3),
                "should_regen": result.should_regen,
                "round_index": result.round_index,
            })

    return {
        "case_id": case_id,
        "n_characters": len(characters),
        "n_voices": len(voicebank_result.speaker_to_voice),
        "voicebank_backend": voicebank_result.backend,
        "critic_enabled": critic_result is not None and critic_result.enabled,
        "elapsed_sec": round(elapsed_sec, 2),
        "speaker_scores": speaker_scores,
        "critic_meta": {
            "speakers_regen": critic_result.speakers_regen if critic_result else 0,
            "speakers_improved": critic_result.speakers_improved if critic_result else 0,
            "total_rounds": critic_result.total_rounds if critic_result else 0,
        } if critic_result else None,
    }


def _format_critic_brief(critic_result: VoicebankCriticResult | None) -> str | None:
    """将 critic 结果格式化为简短摘要行。"""
    if not critic_result or not critic_result.speaker_results:
        return None
    by_speaker: dict[str, Any] = {}
    for r in critic_result.speaker_results:
        by_speaker[r.speaker] = r
    parts: list[str] = []
    for spk, r in by_speaker.items():
        verdict = "REGEN" if r.should_regen else "PASS"
        parts.append(f"{spk}={r.overall_score:.2f}({verdict})")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="audiobench_zh: voicebank + critic 基准测试",
    )
    parser.add_argument(
        "--profile", required=True,
        help="profile yaml 路径",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="已有 voicebank_result.json 的 case 跳过",
    )
    parser.add_argument(
        "--cases", default="",
        help="逗号分隔的 case id 列表（为空则跑全部）",
    )
    parser.add_argument(
        "--no-critic", action="store_true",
        help="只跑 voicebank，不跑 critic",
    )
    parser.add_argument(
        "--critic-only", action="store_true",
        help="跳过 voicebank 生成，只对已有 wav 跑 critic",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.no_critic and args.critic_only:
        print("[bench] ❌ --no-critic 和 --critic-only 不能同时使用")
        return 2

    # 加载 profile
    profile = _load_pipeline_profile(args.profile)
    profile_label = _profile_label(profile)

    # 创建客户端
    llm_backend, llm_cfg = _split_backend_block(profile, "llm")
    llm_client = create_llm_client(llm_backend, **llm_cfg)
    print(f"[bench] LLM backend={llm_backend}")

    vb_backend, vb_cfg = _split_backend_block(profile, "voicebank")
    vb_adapter = create_voicebank_adapter(vb_backend, **vb_cfg)
    print(f"[bench] voicebank backend={vb_backend}")

    # 确定 case 列表
    all_ids = _discover_prep_cases()
    if not all_ids:
        print(f"[bench] ❌ _prep_characters/ 下没有找到 characters.json，先跑 prep_characters")
        return 2

    if args.cases:
        requested = set(args.cases.split(","))
        case_ids = [cid for cid in all_ids if cid in requested]
        unknown = requested - set(case_ids)
        if unknown:
            print(f"[bench] ⚠️ 未知 case id: {', '.join(sorted(unknown))}")
    else:
        case_ids = all_ids

    critic_config = profile.get("pipeline", {}).get("voicebank_critic", {})
    critic_enabled_by_profile = bool(critic_config.get("enabled", False))

    mode = "voicebank+critic" if (critic_enabled_by_profile and not args.no_critic) else "voicebank"
    if args.critic_only:
        mode = "critic-only"

    print(f"[bench] profile_label={profile_label}")
    print(f"[bench] cases={len(case_ids)}, mode={mode}, skip_existing={args.skip_existing}")
    print(f"[bench] output={RESULTS_ROOT / profile_label}")
    print("=" * 70)

    # 逐 case 处理
    results: list[dict[str, Any]] = []
    for i, case_id in enumerate(case_ids, 1):
        result = _process_one_case(
            case_id,
            profile=profile,
            llm_client=llm_client,
            vb_adapter=vb_adapter,
            profile_label=profile_label,
            no_critic=args.no_critic,
            critic_only=args.critic_only,
            skip_existing=args.skip_existing,
        )
        results.append(result)

        # 实时输出
        status = result["status"]
        n_chars = result.get("n_characters", "?")
        n_voices = result.get("n_voices", "?")
        elapsed = result.get("elapsed_sec", 0)
        tag = f"[{i}/{len(case_ids)}]"

        if status == "ok":
            critic_brief = result.get("critic_summary") or ""
            print(f"{tag} {case_id:<28s} OK   chars={n_chars} voices={n_voices}  {elapsed:.1f}s  {critic_brief}")
        elif status == "skipped":
            print(f"{tag} {case_id:<28s} SKIP chars={n_chars} voices={n_voices}")
        else:
            err = result.get("error", "unknown")
            print(f"{tag} {case_id:<28s} ERR  {err}")

    # ── 全量汇总报告 ──────────────────────────────────────────
    report = {
        "profile_label": profile_label,
        "mode": mode,
        "total_cases": len(case_ids),
        "n_ok": sum(1 for r in results if r["status"] == "ok"),
        "n_skipped": sum(1 for r in results if r["status"] == "skipped"),
        "n_error": sum(1 for r in results if r["status"] == "error"),
        "total_elapsed_sec": round(sum(r.get("elapsed_sec", 0) for r in results), 2),
        "cases": results,
    }
    _save_json(report, RESULTS_ROOT / "_bench_report.json")

    # ── 汇总表 ────────────────────────────────────────────────
    print("=" * 70)
    print(f"[summary] ok={report['n_ok']}  skipped={report['n_skipped']}  error={report['n_error']}  time={report['total_elapsed_sec']:.1f}s")

    # 评分汇总表（仅 critic 模式）
    if mode in ("voicebank+critic", "critic-only"):
        print()
        print(f"{'case_id':<28s} {'chars':>5s} {'voices':>6s}  {'critic_detail':<60s}")
        print("-" * 105)
        for r in results:
            if r["status"] != "ok":
                continue
            cid = r["case_id"]
            nc = r.get("n_characters", "?")
            nv = r.get("n_voices", "?")
            brief = r.get("critic_summary") or "N/A"
            print(f"{cid:<28s} {nc:>5} {nv:>6}  {brief}")

    if report["n_error"] > 0:
        print("\n[errors]")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['case_id']}: {r.get('error', 'unknown')}")

    return 1 if report["n_error"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())