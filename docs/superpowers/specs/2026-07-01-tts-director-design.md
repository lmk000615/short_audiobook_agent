# tts_director 设计文档（Audio-Oscar 方向1）

**Status**: Draft（待用户审核）
**Date**: 2026-07-01
**Owner**: 主开发
**Related**: `refactor_audio_oscar/refactor_plan.md` §4（方向1）+ §8（协作策略）

---

## 1. Background

`src_next/` 当前是 10 阶段线性 pipeline。其中 stage 7（story_director）产出通用 `DirectorInstruction`（11 个语义字段），stage 8（tts_instruction_builder）做 clamp + whitelist 后输出仍是通用的 `TTSInstruction`，最终在 stage 9 的 adapter 里被映射成具体 TTS 后端的模型参数（如 emotion → `[sad]` 标签）。每一步映射都丢失信息，LLM 生成的丰富表演指令被层层削减。

Audio-Oscar 的核心思路：**让 LLM 直接看到模型能力描述（model_configs/*.json），输出模型特定参数，adapter 只透传**。这样消除中间映射层，LLM 可以直接产出 `[sad][speak slowly]望着远方[pause]` 这种位置级标签，而不是抽象的 `emotion: "sad"`。

本次改造合并原 stage 7+8 为新 stage 7（tts_director），并通过 profile 开关 `pipeline.use_tts_director` 控制启用。**开关默认 false，确保 main 行为不变。**

## 2. Goal

- 合并 stage 7（story_director）+ stage 8（tts_instruction_builder）为新 stage 7（tts_director），LLM 直接产出 `ModelSpecificTTSInstruction`（含 model + parameters）。
- LLM 根据文本内容 + 角色档案从可用 TTS 池中**为每个 segment 独立选最优 model**——同一 speaker 的不同段落可以使用不同 model，音色一致性由 voice cloning（同一个 voice_ref）保证。
- adapter 双接口并存：老路径（_synthesize_legacy）保留 mapping 逻辑作 fallback，新路径（_synthesize_model_specific）纯透传。
- 老链路（开关 false）完全不动，main 行为零差异。
- 落盘格式：新链路 stage 7 输出 `tts_instructions.json`（内容是 `ModelSpecificTTSInstruction[]`），不再落 `director_plan.json`。

## 3. Non-goals

- **不动** `core/segment_builder.py` / `analysis/quote_classifier.py` / `analysis/story_resolver.py` / `analysis/character_analyzer.py`（stage 1-5）。
- **不动** `voicebank/`（stage 6）。
- **不动** 老 `story_director.py` 和 `tts_instruction_builder.py`（开关 false 时仍是主链路）。
- **不删** 老 `DirectorInstruction` / `TTSInstruction` dataclass（adapter 老路径还在用）。
- **不实装** Qwen3TTS adapter（C1 不加 qwen3tts.json，等后续单独实装）。
- **不实装** MOSSSoundEffect（C1 不加 mosssoundeffect.json，方向4 启动时由实习生B 加）。
- **不改** stage 9（audio_merger）。
- **不引入** Critic 评估循环（方向3）和 SFX 段间音效（方向4）。

## 4. Architecture

### 4.1 新链路（`pipeline.use_tts_director: true`）

```
Stage 1-6 不变
    ↓
Stage 7 tts_director  ← 新模块，合并老 7+8
    输入：segments + characters + voicebank + available model_configs[]
    LLM 任务：为每个 segment 独立选 model + 输出该 model 的 parameters
    一致性来源：所有 backend 都用同一个 voice_ref 克隆音色，
                speaker 不变 → voice_ref 不变 → 声音一致
    输出：list[ModelSpecificTTSInstruction]（per-segment 可能不同 model）
    落盘：json/tts_instructions.json
    ↓
Stage 8 tts_synthesis  ← 原 stage 9，按 instruction.model 分组调度
    按 model 分组 → 每组 lazy-create adapter → 分别 synthesize
    合并结果按 segment_id 排序
    ↓
Stage 9 audio_merger  ← 原 stage 10
```

### 4.2 老链路（`pipeline.use_tts_director: false`，默认值）

10 stage 完全不动。stage 7 story_director + stage 8 tts_instruction_builder + stage 9 tts_synthesis（单 adapter）+ stage 10 audio_merger 行为不变。

### 4.3 Stage 编号显示

| 开关 | 总数 | 日志格式 | pipeline_result.json stages 数组长度 |
|---|---|---|---|
| false（默认） | 10 | `[1/10]` ... `[10/10]` | 10 |
| true | 9 | `[1/9]` ... `[9/9]` | 9 |

stage 总数变量化：`total_stages = 9 if use_tts_director else 10`。`step = f"{n}/{total_stages}"`。

## 5. Data Contract

### 5.1 `ModelSpecificTTSInstruction`（已在 `core/data_models.py` 落地）

```python
@dataclass
class ModelSpecificTTSInstruction:
    segment_id: str
    speaker: str
    text: str
    model: str                          # 必须出现在 model_configs/*.json 的 name 字段
    parameters: dict[str, Any] = {}     # 模型特定，结构由 model_configs 定义
    voice_ref: str = ""                 # speaker 对应的 voicebank wav 路径
    attempt: int = 1                    # Critic 修复用（方向3），方向1 永远是 1
```

### 5.2 `model_configs/*.json` Schema

```json
{
  "name": "<display name>",            // LLM 输出到 ModelSpecificTTSInstruction.model
  "backend": "<backend key>",           // pipeline 用此值查 adapter（如 "s2pro_http"）
  "short_description": "...",           // ≤30 字，LLM 快速对比
  "description": "...",                 // 详细，明确特色边界
  "strengths": [...],
  "weaknesses": [...],
  "best_for": [...],
  "avoid_for": [...],
  "voice_input": "required_reference" | "optional_reference" | "no_reference",
  "sampling_rate": <int>,
  "output_format": "wav",
  "parameters": {
    "<field>": {
      "type": "string|bool|float|int|list",
      "description": "...",
      "default": ...,
      "required": <bool>,
      ...
    }
  }
}
```

### 5.3 LLM 输出 schema（强制 JSON）

```json
{
  "instructions": [
    {
      "segment_id": "seg_001",
      "model": "S2Pro",
      "parameters": {
        "instruction": "[excited]",
        "inline_tags_text": "[excited]太棒了！[pause]我们成功了！",
        "enable_reference_audio": true,
        "temperature": 0.9
      }
    },
    ...
  ]
}
```

`segment_id` 必须与输入 segments 1:1 对应。缺失的 segment_id 走 fallback。

## 6. File Manifest（按 commit 分组）

### C1: model_configs + tts_director 新模块

| 操作 | 文件 |
|---|---|
| ✅ 已完成 | `src_next/tts/model_configs/cosyvoice3.json` |
| ✅ 已完成 | `src_next/tts/model_configs/s2pro.json` |
| ✅ 已完成 | `src_next/tts/model_configs/indextts2.json` |
| 新增 | `src_next/utils/model_config_loader.py`（加载/校验 model_configs/*.json）|
| 新增 | `src_next/analysis/prompts/__init__.py` |
| 新增 | `src_next/analysis/prompts/tts_director_prompt.py`（system prompt 模板）|
| 新增 | `src_next/analysis/tts_director.py`（`TTSDirectorAgent` 类）|
| 新增 | `tests/test_tts_director_unit.py`（mock LLM，1:1 + fallback + parameters 校验）|
| 新增 | `tests/test_tts_director_integration.py`（真 LLM，`@pytest.mark.integration`）|

### C2: adapter 双接口改造

| 操作 | 文件 |
|---|---|
| 修改 | `src_next/tts/s2pro_adapter.py`（加 `_synthesize_model_specific`）|
| 修改 | `src_next/tts/cosyvoice_http.py`（同上）|
| 修改 | `src_next/tts/indextts_http.py`（同上）|
| 新增 | `tests/test_adapters_model_specific.py`（mock HTTP，验证透传）|

### C3: 全局 TTS registry + pipeline 集成

| 操作 | 文件 |
|---|---|
| 新增 | `src_next/tts/backends.yaml`（全局 TTS backend 注册表，集中所有 TTS 服务地址）|
| 修改 | `src_next/tts/registry.py`（加 `create_adapter_for_backend(backend, **cfg)` + lazy cache）|
| 修改 | `src_next/core/audiobook_pipeline.py`（stage 7 切换 + stage 8 按 model 分组 + 加载 backends.yaml）|
| 修改 | `src_next/utils/yaml_utils.py`（识别 `pipeline.use_tts_director` 开关，开关 true 时跳过 profile.tts 字段校验）|
| 新增 | `tests/test_pipeline_use_tts_director_switch.py`（mock 链路 smoke）|
| 新增 | `tests/test_multi_backend_synthesis.py`（多 adapter 分组调度）|
| 新增 | `tests/test_backends_yaml_loader.py`（backends.yaml 加载 + 校验）|

**现有 3 个 yellow_*.yaml 完全不动**——它们保持原样作为老链路 profile。新链路通过 CLI flag `--use-tts-director` 或在任意 yellow_*.yaml 加一行 `pipeline.use_tts_director: true` 启用，启用后 pipeline 自动加载 `backends.yaml`，忽略 profile.tts 的 backend / base_url / extra_args（只保留 `output_subdir`）。

### C4: docs sync

| 操作 | 文件 |
|---|---|
| 修改 | `src_next_主链路运行及核心模块说明.md`（stage 编号 + backends.yaml 说明 + LLM 选 model 说明）|
| 修改 | `src_next_总体架构说明.md`（架构图说明）|
| 修改 | `CLAUDE.md` §4 表格 + §6 开关说明 + §11 维护表加一行 |
| 修改 | `README.md` 同步 |

### 保留不动

- `src_next/analysis/story_director.py`（老链路 fallback）
- `src_next/core/tts_instruction_builder.py`（老链路 fallback）

## 7. Key Design Decisions

### 7.1 Profile 不变 + 全局 TTS registry

**核心思路**：TTS 服务地址集中维护在 1 处（`backends.yaml`），不在 N 个 profile 里重复。Profile yaml 完全不动。

**`src_next/tts/backends.yaml` 结构**：

```yaml
# 全局 TTS backend 注册表
# use_tts_director=true 时由 pipeline 自动加载
# 加新 TTS 服务只改本文件 + 加 model_configs/<model>.json

# 启用的 backend 列表（LLM 只能从这里选）
# 必须是下面 backends 字典里的 key 子集
enabled_backends:
  - cosyvoice_http
  - s2pro_http
  - indextts_http

# 各 backend 的服务地址 + extra_args
backends:
  cosyvoice_http:
    base_url: "http://10.50.121.102:8005"
    extra_args:
      max_workers: 4
      timeout: 300

  s2pro_http:
    base_url: "http://10.50.121.102:8010"   # 8010 端口（含音色克隆）
    extra_args:
      max_workers: 4
      enable_reference_audio: true
      timeout: 300

  indextts_http:
    base_url: "http://10.50.121.102:8009"
    extra_args:
      max_workers: 4
      timeout: 300

# Fallback 模型（LLM 没覆盖的 segment 用这个）
# 必须是某个 model_configs/*.json 的 name 字段
# 且该 model_config 的 backend 必须在 enabled_backends 里
default_model: CosyVoice3
```

**启用方式**（二选一）：

1. **CLI flag**（推荐，临时启用）：
   ```bash
   python -m src_next.core.audiobook_pipeline \
       --input input/sample_story_01.txt \
       --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
       --use-tts-director
   ```

2. **Profile yaml 内置**（持久启用，WebUI 友好）：
   ```yaml
   # 在任意 yellow_*.yaml 加一行
   pipeline:
     use_tts_director: true
   ```

**生效逻辑**：
- `use_tts_director=true` 时，pipeline 加载 `backends.yaml`，**忽略** profile.tts 的 `backend` / `base_url` / `extra_args`，**保留** profile.tts.`output_subdir`（控制 wav 落盘子目录）
- `use_tts_director=false` 时（默认），pipeline 完全用 profile.tts，不读 `backends.yaml`

### 7.2 Adapter 双接口并存（方案 A）

```python
def synthesize(self, instructions, voicebank_result, output_dir, ...):
    if not instructions:
        return []
    if isinstance(instructions[0], ModelSpecificTTSInstruction):
        return self._synthesize_model_specific(instructions, voicebank_result, output_dir, ...)
    return self._synthesize_legacy(instructions, voicebank_result, output_dir, ...)
```

老 mapping 逻辑（`_EMOTION_TO_S2PRO_TAG` / `_build_instruction` / `_emotion_to_tag`）全部保留，老路径调用时仍生效。新路径纯透传 `instruction.parameters`。

### 7.3 Per-segment 自由 model selection

LLM 为每个 segment 独立选 model，**不约束**同一 speaker 必须用同一 model。音色一致性
由 voice cloning 保证：

- voicebank stage 已经为每个 speaker 生成一个参考 wav（`voice_ref`）。
- 所有 backend（CosyVoice3 / S2Pro / IndexTTS2）的 `voice_input` 都依赖参考音频。
- 同一 speaker 的所有 segment 共享同一个 `voice_ref`，即便 model 不同，克隆出来的
  音色都是同一个人的。
- 实际鼓励：同一角色在情绪差异大的台词中自然切换 model（激动台词用 S2Pro，平复
  叙述用 CosyVoice3），让表演更丰富。

如果未来加 voice_input="optional_reference" 的 model（如 Qwen3TTS），不依赖参考音频
克隆，那条 segment 会用模型默认音色——这种 segment 不参与"音色一致性"假设，prompt
里会明确说明。

### 7.4 Pipeline stage 8 重写

```python
# 按 instruction.model 分组
grouped = defaultdict(list)
for inst in tts_instructions:
    grouped[inst.model].append(inst)

# 每组 lazy 创建 adapter 并 synthesize
backends_yaml = load_backends_yaml()  # 加载 src_next/tts/backends.yaml
audio_segments_by_id = {}
for model_name, group in grouped.items():
    backend = model_config_loader.get_backend(model_name)  # model.name → backend key
    cfg = backends_yaml["backends"][backend]                # 从 backends.yaml 取服务地址
    adapter = create_adapter_for_backend(backend, **cfg)    # registry 加 lazy cache
    seg_results = adapter.synthesize(group, voicebank_result, str(output_dir))
    for r in seg_results:
        audio_segments_by_id[r.segment_id] = r

# 按 segment_id 排序保持原顺序
audio_segments = [audio_segments_by_id[inst.segment_id] for inst in tts_instructions]
```

### 7.5 Fallback 策略

LLM 没覆盖的 segment → `_fallback_instruction(segment, default_model_name, default_params)`：

- `default_model_name` 推导顺序：
  1. `backends.yaml:default_model`（全局显式指定，如 `"CosyVoice3"`）
  2. 否则取 `backends.yaml:enabled_backends[0]` 对应的 `model_config.name`（如 `enabled_backends[0]="cosyvoice_http"` → 查 cosyvoice3.json → `"CosyVoice3"`）
- `parameters` = 该 model_config 里所有字段的 `default` 值组成的 dict
- `voice_ref` = `voicebank_result.speaker_to_voice.get(segment.speaker, "")`
- `attempt` = 1（方向1 不涉及 Critic 修复）

### 7.6 Reuse 兼容

`--reuse-existing` 模式按 stage **name** 匹配 JSON 文件名（不按编号），所以新链路下：
- `tts_instructions.json` 存在 → 跳过 stage 7 tts_director
- 老 `director_plan.json` 在新链路下不被读
- 反之亦然

## 8. Error Handling

| 异常 | 处理 |
|---|---|
| LLM 输出非 JSON / JSON parse 失败 | retry 1 次（重发 prompt）→ 仍失败用 fallback 覆盖所有 segment |
| LLM 输出缺 segment_id | fallback 补齐（model 用 default，parameters 用 default 值）|
| LLM 输出 invalid model name（不在 loaded model_configs 的 name 集合）| fallback 覆盖该 segment |
| LLM 输出 invalid parameters 字段（不在 model_config schema）| 用 model_config default 覆盖该字段，写 warning |
| adapter HTTP 失败 | 单段失败不阻断（沿用老链路行为），failed segment 标 `success=False` |
| voice_ref 缺失 | CosyVoice/IndexTTS 走模型默认音色 + warning；S2Pro 默认 `enable_reference_audio=false` |
| `backends.yaml` 不存在 / 解析失败 / 字段缺失 | 启动时立即报错（fail-fast），不进入 pipeline |
| `backends.yaml:default_model` 不在 enabled_backends 对应的 model_configs 里 | 启动时立即报错（fail-fast）|
| `backends.yaml:enabled_backends` 引用了 `backends` 字典里不存在的 key | 启动时立即报错（fail-fast）|
| model_config 文件解析失败 | model_config_loader 启动时立即报错（fail-fast），不进入 pipeline |
| 跨开关 reuse 格式不匹配（如老链路跑过的 tts_instructions.json 含 TTSInstruction，但本次 use_tts_director=true）| reuse 检测时校验 JSON 首元素是否含 `model` 字段；不匹配则 warning + 忽略 reuse，重新跑 stage 7 |

## 9. Testing Strategy

### 9.1 Unit Tests（mock LLM，CI fast 跑）

`tests/test_tts_director_unit.py`：
- 1:1 输出契约（输入 N segments → 输出 N instructions，segment_id 对应）
- 同 speaker 跨段允许使用不同 model（mock LLM 返回不同 → 不做统一，直接透传）
- fallback 路径（mock LLM 缺 segment → fallback 补齐）
- invalid model name 处理
- invalid parameters 字段处理
- model_config_loader 加载 + schema 校验

`tests/test_adapters_model_specific.py`（mock HTTP）：
- 各 adapter `_synthesize_model_specific` 透传正确性（验证 HTTP 请求参数 = instruction.parameters）
- voice_ref 缺失时各 adapter fallback 行为
- 单段失败隔离

### 9.2 Integration Tests（真服务，PR 合并前必跑，`@pytest.mark.integration`）

`tests/test_tts_director_integration.py`：
- 真 Gemma4 HTTP 调用（用 yellow_qwen3http_cosyvoicehttp profile 的 LLM 配置）
- 验证 LLM 实际能产出合法 `ModelSpecificTTSInstruction[]`
- 验证 model 选择合理（narrator 倾向 CosyVoice3，excited dialogue 倾向 S2Pro 等）
- 验证 LLM 输出的 parameters schema 与 model_config 一致

### 9.3 Smoke Tests（mock 链路端到端）

`tests/test_pipeline_use_tts_director_switch.py`：
- 开关 false → 走老链路 10 stage，落盘 `director_plan.json` + `tts_instructions.json` 两份
- 开关 true → 走新链路 9 stage，只落盘 `tts_instructions.json`
- stage 编号显示正确（[X/10] vs [X/9]）
- 老链路产物在新链路下不被读

`tests/test_multi_backend_synthesis.py`：
- 多 model 分组调度正确（3 个 segment 选 3 个不同 model → 创建 3 个 adapter）
- 排序保持原 segment_id 顺序

## 10. Risks & Open Questions

1. **LLM 选 model 的合理性**：LLM 看到详细 description 后能否做出合理选择？需要 integration 测试验证。如果 LLM 倾向于"乱选"（如全选 S2Pro），可能需要在 prompt 加更强决策引导（如要求逐段解释选择理由）。
2. **同 speaker 跨段 model 切换的连续性**：模型切换本身不影响音色（voice cloning 保证），但听感上"同一角色的两句话用了不同 TTS 后端"可能在韵律 / 节奏上有微小差异。如果用户反馈违和，可在 prompt 加"连续同情绪台词优先用同一 model"软约束。
3. **多 adapter 创建的性能开销**：每个 model 第一次调用都要 lazy-create adapter（含 HTTP 连接池初始化）。3 个 model 串行调用会增加 ~1-2 秒。可接受。
4. **prompt 长度膨胀**：3 个 model_config 都很详细（每个 ~50 行 JSON），全部注入 system prompt 后 token 数显著增加。如果未来加更多 model，需要拆成"short_description 优先 + 详细 schema 按需查"两段式。
5. **C2 adapter 改造的代码量**：s2pro_adapter 已 807 行，加 `_synthesize_model_specific` 后会到 ~1000 行。可接受（adapter 本来就独立大文件），但需要小心保持双路径不互相污染。

## 11. References

- `refactor_audio_oscar/refactor_plan.md` §4（方向1 详细设计）+ §8（协作策略）+ §12（风险）
- `src_next/core/data_models.py:ModelSpecificTTSInstruction`（数据契约已落地）
- `usage_guide_cosyvoice.md` / `usage_guide_indextts.md` / `usage_guide_s2pro.md`（model_configs 字段来源）
- Audio-Oscar `agents/speech_generator.py`（LLM 直接输出模型参数的模式参考）
- Audio-Oscar `tts/tts_config.json`（model_configs JSON 格式参考）
