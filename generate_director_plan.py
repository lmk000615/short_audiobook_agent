"""生成导演计划：输入故事文本，输出角色分析和导演计划（JSON + MD）。

用法：
    python -X utf8 generate_director_plan.py input/将相和.txt
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from text_loader import load_text
from story_parser import parse_text
from llm_story_resolver import resolve_quotes
from segment_builder import build_segments
from character_analyzer import analyze_characters
from story_director import direct_story, generate_markdown


def save_json(data, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="生成有声书导演计划")
    parser.add_argument("input_file", nargs="?", default="input/将相和.txt", help="输入文本文件路径")
    args = parser.parse_args()

    t_start = time.perf_counter()
    story_name = Path(args.input_file).stem
    analysis_dir = Path("output/analysis")

    print(f"\n{'='*50}")
    print(f"正在处理：{args.input_file}")
    print(f"{'='*50}\n")

    # 1. 读取文本
    print("[1/6] 读取文本...", end=" ", flush=True)
    text = load_text(args.input_file)
    print(f"完成，共 {len(text)} 字")

    # 2. 解析段落结构
    print("[2/6] 解析段落结构...", end=" ", flush=True)
    parsed = parse_text(text)
    print(f"完成，共 {parsed['total_paragraphs']} 个段落")

    # 3. LLM 语义判断
    print("[3/6] LLM 语义判断...", end=" ", flush=True)
    resolved = resolve_quotes(parsed)
    print(f"完成，共判断 {resolved['total_resolved']} 个引号")

    # 4. 构建 segments
    print("[4/6] 构建 segments...", end=" ", flush=True)
    segments = build_segments(parsed, resolved)
    print(f"完成，共 {segments['total_segments']} 个 segment")

    # 5. 分析角色
    print("[5/6] 分析角色声音特征...", end=" ", flush=True)
    characters = analyze_characters(segments, text)
    save_json(characters, analysis_dir / f"{story_name}_characters.json")
    char_names = [c["speaker"] for c in characters["characters"]]
    print(f"完成，角色：{', '.join(char_names) if char_names else '无'} + narrator")

    # 6. 生成导演计划
    print("[6/6] 生成导演计划...", end=" ", flush=True)
    directing = direct_story(segments, characters, text)
    save_json(directing, analysis_dir / f"{story_name}_director_plan.json")
    md = generate_markdown(directing)
    (analysis_dir / f"{story_name}_director_plan.md").write_text(md, encoding="utf-8")
    print("完成")

    # 摘要
    elapsed = time.perf_counter() - t_start
    style = directing.get("overall_style", {})
    seg_count = len(directing.get("segment_directions", []))

    print(f"\n{'='*50}")
    print(f"完成！耗时 {elapsed:.1f}s")
    print(f"  故事类型：{style.get('genre', '')}")
    print(f"  整体基调：{style.get('tone', '')}")
    print(f"  角色：{', '.join(char_names) + ' + narrator' if char_names else 'narrator'}")
    print(f"  导演计划：{seg_count} 个 segment")
    print(f"  输出：{analysis_dir}/{story_name}_director_plan.json")
    print(f"        {analysis_dir}/{story_name}_director_plan.md")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
