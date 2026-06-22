"""src_next.core.data_models — 有声书 Agent 核心数据结构

每个 dataclass 代表数据流链路中的一个中间产物。
所有字段尽量简单，可有默认值。
"""

from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# 链路起点
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class StoryInput:
    """
    链路起点：原始文本输入。

    Attributes
    ----------
    story_name : str
        故事名称（从文件名或用户提供提取）。
    text : str
        原始文本全文。
    source_path : str | None
        原始文件路径（可选，无文件时为 None）。
    """

    story_name: str
    text: str
    source_path: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 链路早期产物（segment_builder 输出）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Segment:
    """
    原始文本经过切分后的最小单元。

    出现在数据流的：txt → segments

    Attributes
    ----------
    segment_id : str
        唯一编号，格式为 seg_001, seg_002 ...
    text : str
        该段的文本内容。
    speaker : str
        说话人，默认 narrator，待 analysis 层解析后更新。
    segment_type : str
        段类型，narration / dialogue / unknown。
    raw_index : int
        在原始文本中的段落索引（从 0 开始）。
    """

    segment_id: str
    text: str
    speaker: str = "narrator"
    segment_type: str = "narration"
    raw_index: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# 链路中期产物（analysis 层输出 + voicebank 层输出）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class CharacterProfile:
    """
    角色档案：从文本中提取的角色信息。

    出现在数据流的：resolved_segments → characters

    Attributes
    ----------
    name : str
        角色名称。
    role_type : str
        角色类型，narrator / character。
    gender : str | None
        性别提示（由 LLM 分析生成）。
    age_style : str | None
        年龄/声音风格提示。
    personality : str | None
        性格特点（用于朗读风格指导）。
    voice_prompt : str
        供 voicebank 层使用的音色描述提示词。
    confidence : float
        分析置信度，0.0~1.0。
    """

    name: str
    role_type: str = "character"
    gender: str | None = None
    age_style: str | None = None
    personality: str | None = None
    voice_prompt: str = ""
    confidence: float = 0.8


@dataclass
class DirectorInstruction:
    """
    导演指令：为每个 segment 提供的朗读指导。

    出现在数据流的：characters + resolved_segments → director_plan

    Attributes
    ----------
    segment_id : str
        对应的 segment 编号。
    speaker : str
        说话人。
    emotion : str
        情绪基调（由 LLM 生成，如 紧张 / 温柔 / 平静）。
    pace : float
        语速倍率，1.0 为正常速。
    tone : str
        语调描述。
    pause_hint : float
        段后停顿秒数建议。
    delivery_instruction : str
        综合朗读指导描述。
    """

    segment_id: str
    speaker: str
    emotion: str = "neutral"
    pace: float = 1.0
    tone: str = "normal"
    pause_hint: float = 0.0
    delivery_instruction: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 链路中后段产物（tts 层消费前）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TTSInstruction:
    """
    TTS 合成指令：包含合成单段音频所需的全部信息。

    出现在数据流的：director_plan + voicebank → tts_instructions

    Attributes
    ----------
    segment_id : str
        对应的 segment 编号。
    speaker : str
        说话人。
    text : str
        要合成的文本。
    voice_ref : str | None
        音色参考文件路径（由 voicebank 层填充）。
    emotion : str
        情绪基调（从 director_instruction 复制）。
    pace : float
        语速倍率。
    tone : str
        语调描述。
    instruction : str
        综合朗读指令（供 TTS adapter 参考）。
    """

    segment_id: str
    speaker: str
    text: str
    voice_ref: str | None = None
    emotion: str = "neutral"
    pace: float = 1.0
    tone: str = "normal"
    instruction: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# voicebank 层产物
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class VoicebankResult:
    """
    voicebank 层产出：每个 speaker 对应的音色参考。

    出现在数据流的：characters → voicebank_result

    Attributes
    ----------
    speaker_to_voice : dict[str, str]
        speaker 名称到音色文件路径的映射。
        示例：{"narrator": "voicebank/narrator.wav", "小明": "voicebank/小明.wav"}
    voicebank_dir : str | None
        voicebank 输出目录路径。
    backend : str
        使用的 voicebank backend 名称（如 mock / cosyvoice / indextts）。
    success : bool
        是否全部成功生成。
    """

    speaker_to_voice: dict[str, str] = field(default_factory=dict)
    voicebank_dir: str | None = None
    backend: str = "mock"
    success: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# audio 层产物（tts 层 + audio_merger 层输出）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AudioSegmentResult:
    """
    单个 segment 的音频合成结果。

    出现在数据流的：tts_adapter → audio_segments（内部列表元素）

    Attributes
    ----------
    segment_id : str
        对应的 segment 编号。
    speaker : str
        说话人。
    audio_path : str | None
        生成的音频文件路径（失败时为 None）。
    success : bool
        是否成功合成。
    error : str
        错误信息（成功时为空字符串）。
    """

    segment_id: str
    speaker: str
    audio_path: str | None = None
    success: bool = True
    error: str = ""


@dataclass
class AudioResult:
    """
    音频合并结果：所有 segment 合并后的最终音频。

    出现在数据流的：audio_segments → audio_result → pipeline_result

    Attributes
    ----------
    final_audio : str | None
        合并后的最终音频文件路径。
    audio_segments : list[AudioSegmentResult]
        所有 segment 的单独音频结果。
    duration_seconds : float
        音频总时长（秒）。
    success : bool
        是否成功合并。
    """

    final_audio: str | None = None
    audio_segments: list[AudioSegmentResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    success: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# 链路终点
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PipelineResult:
    """
    完整 pipeline 运行结果：链路终点。

    出现在数据流的：最后汇总

    Attributes
    ----------
    story_name : str
        故事名称。
    output_dir : str
        输出根目录。
    final_audio : str | None
        最终音频文件路径。
    success : bool
        是否完全成功。
    stage_timings : dict[str, float]
        各阶段耗时（秒），键为阶段名称。
    artifacts : dict[str, str]
        中间产物路径映射，如 {"segments": "json/segments.json", ...}
    error : str
        错误信息（成功时为空字符串）。
    """

    story_name: str
    output_dir: str
    final_audio: str | None = None
    success: bool = True
    stage_timings: dict[str, float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str = ""
