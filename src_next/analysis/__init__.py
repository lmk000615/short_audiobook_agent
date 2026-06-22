"""Analysis layer for src_next.

Submodules（按需 import，不在 package init 阶段加载）：

- ``story_resolver``      segments → resolved segments（speaker / segment_type）
- ``character_analyzer``  resolved segments → CharacterProfile 列表
- ``story_director``      resolved segments + characters → DirectorInstruction 列表

调用方式：

    from src_next.analysis.story_resolver import resolve_speakers
    from src_next.analysis.character_analyzer import analyze_characters
    from src_next.analysis.story_director import generate_director_plan

本层只依赖 ``src_next.core.data_models`` 和 ``src_next.llm.base.BaseLLMClient``，
不 import 具体的 LLM 后端（QwenHTTPClient / Gemma4HTTPClient）。
"""
