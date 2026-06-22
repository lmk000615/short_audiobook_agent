"""src_next/core/segment_builder.py

文本切分：支持三种原始段落格式：

1. 空行分段（如 input/sample_story_01.txt）：
   连续两个 \\n（中间夹空行）作为段落分隔。
2. 段首缩进分段（如 input/不懂就要问.txt）：
   行首有 2+ 空格/制表符缩进表示新段落开始。
3. 行内软换行续行：
   无缩进非空行视为上一段的续行，直接拼接到当前段落。

另外提供 **fallback**：如果结构化模式（空行 / 缩进）把全文压成 1 段、
但原文有多条非空行（典型例子：input/小红帽.txt 每行都是独立段落），
则回退到「每行一段」模式。

逻辑移植自 src/text_loader.py 的 _normalize，区别在于：
- 这里产出 list[Segment] 而非归一化后的纯文本；
- StoryInput.text 已经是读入的字符串，不再做文件 IO；
- 加了单行段落 fallback，处理 text_loader.py 未覆盖的纯单 \\n 格式。
"""

from .data_models import StoryInput, Segment


def _split_structured(text: str) -> list[str]:
    """结构化切分：识别空行 / 段首缩进 / 续行三种信号（移植自 text_loader._normalize）。

    规则：
    - 空行 → 结束当前段落。
    - 行首 2+ 空格/制表符缩进 → 结束当前段落，开始新段落。
    - 无缩进非空行 → 视为续行，拼到当前段落末尾（不加空格，符合中文排版）。
    """
    lines = text.split("\n")
    paragraphs: list[str] = []
    current = ""

    for line in lines:
        stripped = line.lstrip(" \t")
        indent_len = len(line) - len(stripped)

        if indent_len >= 2:
            if current:
                paragraphs.append(current)
            current = stripped
        elif stripped:
            current += stripped
        else:
            if current:
                paragraphs.append(current)
                current = ""

    if current:
        paragraphs.append(current)

    return paragraphs


def _split_single_line(text: str) -> list[str]:
    """单行切分：每个非空行就是独立一段（fallback 模式）。

    用于没有任何空行 / 缩进信号、但每行都是独立段落的文本。
    """
    return [line.strip() for line in text.split("\n") if line.strip()]


def _split_into_paragraphs(text: str) -> list[str]:
    """先尝试结构化切分；若结果只有 1 段但原文有多行，回退到单行模式。

    这样可以同时覆盖：
    - 空行分段（sample_story_01.txt）
    - 段首缩进分段（不懂就要问.txt）
    - 纯单 \\n 分段（小红帽.txt）
    """
    paragraphs = _split_structured(text)

    non_empty_lines = [line for line in text.split("\n") if line.strip()]
    if len(paragraphs) <= 1 and len(non_empty_lines) > 1:
        # 结构化模式把多行文本压成 1 段，说明原文用单 \n 分段
        paragraphs = _split_single_line(text)

    return paragraphs


def build_segments(story_input: StoryInput) -> list[Segment]:
    """按自然段切分文本，生成 segments。

    自动识别三种原始格式 + fallback（详见模块 docstring）。所有段落暂默认：
      * speaker = "narrator"
      * segment_type = "narration"
    segment_id 使用 seg_001 / seg_002 / ... 格式，raw_index 从 1 开始。

    后续 analysis 层接 LLM 后，speaker 和 segment_type 会被更新。
    """
    paragraphs = _split_into_paragraphs(story_input.text)

    segments: list[Segment] = []
    raw_index = 0
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        raw_index += 1
        segments.append(
            Segment(
                segment_id=f"seg_{raw_index:03d}",
                text=paragraph,
                speaker="narrator",
                segment_type="narration",
                raw_index=raw_index,
            )
        )
    return segments
