# analysis/ 语义分析层

> 本层是 `src_next/`` 重构架构中的语义理解层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图看懂 src_next」。

## 一、这一层负责什么

把 core 层切出来的纯文本 segments，经过 LLM 分析，产出后续 voicebank / tts / audio 层需要的语义结构：

- **说话人识别**：判断每段是 narrator 还是对白，对白归属哪个角色。
- **角色档案生成**：从故事中提取角色清单，为每个角色生成 gender / age_style / personality / voice_prompt。
- **导演计划生成**：为每个 segment 生成 emotion / pace / tone / pause_hint / delivery_instruction。
- **结构稳定性**：把 LLM 的随机输出清洗成符合 `src_next.core.data_models` 的 dataclass 实例。

## 二、这一层不负责什么

- **不直接发 HTTP**：所有 LLM 调用通过 `BaseLLMClient.generate_json`。
- **不绑定具体后端**：不 import `QwenHTTPClient` / `Gemma4HTTPClient`，切换后端零改动。
- **不生成音频**：TTS / voicebank / audio_merger 都不在本层。
- **不读 .env / 不读 profile yaml**：环境配置由上层注入。
- **不写文件**：中间产物持久化由 core pipeline 负责。
- **不做整体风格分析（v1 简化）**：旧 src 的 overall_style / genre 推断暂未搬过来。

## 三、三个文件的输入输出

### 3.1 `story_resolver.py`

```python
def resolve_speakers(
    segments: list[Segment],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[Segment]:
```

- **输入**：`core.segment_builder.build_segments()` 输出的原始 Segment 列表（所有段默认 `speaker=narrator`, `segment_type=narration`）。
- **输出**：新的 Segment 列表（深拷贝，入参不变），每段的 `speaker` 和 `segment_type` 已更新。
- **segment_type 取值**：`narration` / `dialogue` / `unknown`（unknown 会在函数返回前全部转成 narration）。

策略：

1. **规则识别优先**：正则匹配 `X + 状态副词 + 说/问/道 + 标点/引号` 模式，命中即标 `dialogue` + `speaker=X`。
2. **无引号无动词** → `narration` + `narrator`。
3. **有引号但规则没识别出来** → 暂标 `unknown`，留给 LLM 批量兜底。
4. **LLM 失败 / 结构异常** → 全部 fallback 成 `narrator`。

### 3.2 `character_analyzer.py`

```python
def analyze_characters(
    segments: list[Segment],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[CharacterProfile]:
```

- **输入**：resolved segments（speaker 已识别）。
- **输出**：`CharacterProfile` 列表。`index=0` 永远是 narrator，其余按 speaker 首次出现顺序。

字段约束：

- **narrator** 走固定档案：`female / young / voice_prompt="用温柔亲切的年轻女声说书人嗓音说" / confidence=0.95`。
- **普通角色** 由 LLM 生成；`voice_prompt` 必须以 "用" 开头、以 "说" 结尾，长度 10~60 字符。
- **LLM 失败时** 根据角色名关键词（动物 / 老人 / 儿童）走 fallback，confidence 标低（0.3~0.4）。

### 3.3 `story_director.py`

```python
def generate_director_plan(
    segments: list[Segment],
    characters: list[CharacterProfile],
    llm_client: BaseLLMClient,
    *,
    story_context: str = "",
) -> list[DirectorInstruction]:
```

- **输入**：resolved segments + characters 列表。
- **输出**：`DirectorInstruction` 列表，长度严格等于 segments，按 segment 顺序排列。

字段约束：

- `emotion`：必须是 `neutral / warm / happy / sad / angry / fearful / surprised / disgusted / excited / calm` 之一。
- `pace`：0.8~1.2，1.0 为正常速。
- `tone`：`normal / warm / sharp / soft / deep / bright` 之一。
- `pause_hint`：0.0~2.0 秒。
- `delivery_instruction`：不超过 60 字符。

## 四、为什么只能依赖 BaseLLMClient

- analysis 层是「业务逻辑」层，应该和具体的 LLM 后端（Qwen / Gemma4 / 本地模型）解耦。
- 切换后端只需要在 app 层换一个 `BaseLLMClient` 实例，analysis 层代码零改动。
- `MockLLMClient` 可以在不访问网络的情况下验证 analysis 数据流（CI / 本地无 GPU 环境），直接 `llm = MockLLMClient()` 即可，不需要 `.env` 配置。
- 三个函数都做了 MockLLM 返回结构（默认占位 dict）的兼容：检测到不匹配的形状时走 fallback，不会抛异常。

## 五、和其他层的交互

```text
                ┌─────────────────────────────┐
                │   core/segment_builder.py   │
                └─────────────┬───────────────┘
                              │ Segment[]
                              ▼
              ┌─────────────────────────────────┐
              │  analysis/story_resolver.py     │
              └─────────────┬───────────────────┘
                            │ Segment[] (resolved)
              ┌─────────────┴───────────────────┐
              ▼                                 ▼
  ┌──────────────────────────┐    ┌─────────────────────────────┐
  │ analysis/                │    │  analysis/                  │
  │ character_analyzer.py    │    │  story_director.py          │
  └─────────────┬────────────┘    └─────────────┬───────────────┘
                │ CharacterProfile[]             │ DirectorInstruction[]
                ▼                                ▼
       voicebank/                       core/tts_instruction_builder.py
       (prepare_voicebank)              (build_tts_instructions)
```

- **上游**：`core/segment_builder.py`（提供 `Segment[]`）。
- **下游**：
  - `CharacterProfile[]` → `voicebank/`（生成参考音频）。
  - `DirectorInstruction[]` → `core/tts_instruction_builder.py`（合成 TTS 指令）。
- **同级依赖**：`llm/`（只通过 `BaseLLMClient` 接口）。

## 六、参考旧 `src` 的地方

| 旧 src 文件 | 借鉴点 | 改动点 |
|---|---|---|
| `src/llm_story_resolver.py` | speaker 识别的 prompt 设计；JSON 解析容错思路 | 不再做「段落 → part」二级切分；规则识别用正则；不再发 HTTP |
| `src/character_analyzer.py` | narrator 硬编码 + voice_instruction 一句话描述 | 字段改为 `CharacterProfile` dataclass；`timbre` 并入 `voice_prompt`；voice_prompt 强约束「用...说」格式 |
| `src/story_director.py` | segment_directions 一一对应；fallback 兜底 | 去掉 `overall_style` / `emphasis_words` / `needs_review`；字段精简到 5 个；`pause_after_ms` → `pause_hint`（秒） |
| `src/segment_builder.py` | — | 不参考；`src_next/core/segment_builder.py` 已重写 |
| `src/tts_instruction_generator.py` | — | 不参考；属于 tts 层职责 |

## 七、v1 简化实现

下列点 v1 不做，后续按需补齐：

1. **不做 overall_style**：旧 src 会先推断故事类型 / 整体基调。v1 每段独立判断。
2. **不做 emphasis_words**：旧 src 会标注重读词。v1 只有 `delivery_instruction` 一句话。
3. **不做 needs_review**：旧 src 会标记低置信度段。v1 用 `DirectorInstruction` 字段表达不出「需复核」，未来可加。
4. **规则识别覆盖有限**：speaker 正则只匹配 `X + 动词 + 标点` 模式；复杂结构（倒装、省略主语等）都丢给 LLM。
5. **无 incremental 分析**：本层假设每次调用都是从头分析；不支持「已有角色档案，只增量分析新角色」。
6. **LLM 一次性调用**：每层（resolver / character / director）只调一次 LLM；不做 retry / 分块 / 流式。
7. **不带 debug 落盘**：旧 src 解析失败会把 raw 文本写到 `output/debug/`。v1 不做，由 core pipeline 统一负责中间产物持久化。

## 八、最小调用示例

```python
from src_next.core.data_models import StoryInput
from src_next.core.segment_builder import build_segments
from src_next.llm.mock_llm import MockLLMClient
from src_next.analysis.story_resolver import resolve_speakers
from src_next.analysis.character_analyzer import analyze_characters
from src_next.analysis.story_director import generate_director_plan

story = StoryInput(story_name="test", text="从前有一只小松鼠。\n小松鼠说：我要去找松果。")
segments = build_segments(story)

llm = MockLLMClient()  # 离线无网络也能跑通
resolved = resolve_speakers(segments, llm)
characters = analyze_characters(resolved, llm)
plan = generate_director_plan(resolved, characters, llm)
```

切换到真实 Qwen 后端只需把 `MockLLMClient()` 换成 `QwenHTTPClient()`，其余代码不动。
