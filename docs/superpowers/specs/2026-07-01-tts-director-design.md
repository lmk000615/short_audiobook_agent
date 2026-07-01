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
- LLM 根据文本内容 + 角色档案从可用 TTS 池中**为每个 segment 选最优 model**（同 speaker 全文用同 model 一致性约束）。
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
    LLM 任务：为每个 segment 选 model + 输出该 model 的 parameters
    约束：同一 speaker 全文用同一 model（避免声音不一致）
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
| 新增 | `tests/test_tts_director_unit.py`（mock LLM，1:1 + 一致性 + fallback）|
| 新增 | `tests/test_tts_director_integration.py`（真 LLM，`@pytest.mark.integration`）|

### C2: adapter 双接口改造

| 操作 | 文件 |
|---|---|
| 修改 | `src_next/tts/s2pro_adapter.py`（加 `_synthesize_model_specific`）|
| 修改 | `src_next/tts/cosyvoice_http.py`（同上）|
| 修改 | `src_next/tts/indextts_http.py`（同上）|
| 新增 | `tests/test_adapters_model_specific.py`（mock HTTP，验证透传）|

### C3: profile + registry + pipeline 集成

| 操作 | 文件 |
|---|---|
| 修改 | `src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml`（tts 块加 available_backends + backends_config）|
| 修改 | `src_next/profiles/yellow_qwen3http_indexttshttp.yaml`（同上）|
| 修改 | `src_next/profiles/yellow_gemma_qwen_s2pro.yaml`（同上）|
| 修改 | `src_next/tts/registry.py`（加 `create_adapter_for_model(model_name)` + lazy cache）|
| 修改 | `src_next/core/audiobook_pipeline.py`（stage 7 切换 + stage 8 按 model 分组）|
| 修改 | `src_next/utils/yaml_utils.py`（profile 校验识别新 schema）|
| 新增 | `tests/test_pipeline_use_tts_director_switch.py`（mock 链路 smoke）|
| 新增 | `tests/test_multi_backend_synthesis.py`（多 adapter 分组调度）|

### C4: docs sync

| 操作 | 文件 |
|---|---|
| 修改 | `src_next_主链路运行及核心模块说明.md`（stage 编号 + 新 profile schema + LLM 选 model 说明）|
| 修改 | `src_next_总体架构说明.md`（架构图说明）|
| 修改 | `CLAUDE.md` §4 表格 + §6 开关说明 + §11 维护表加一行 |
| 修改 | `README.md` 同步 |

### 保留不动

- `src_next/analysis/story_director.py`（老链路 fallback）
- `src_next/core/tts_instruction_builder.py`（老链路 fallback）

## 7. Key Design Decisions

### 7.1 Profile 双 schema 兼容

```yaml
# 老链路（use_tts_director: false）— 不变
tts:
  backend: cosyvoice_http
  base_url: "http://10.50.121.102:8005"
  output_subdir: audio_segments

# 新链路（use_tts_director: true）— 新 schema
tts:
  available_backends: [cosyvoice_http, s2pro_http, indextts_http]
  backends_config:
    cosyvoice_http: {base_url: "http://10.50.121.102:8005"}
    s2pro_http: {base_url: "http://10.50.121.102:8010"}
    indextts_http: {base_url: "http://10.50.121.102:8009"}
  output_subdir: audio_segments
```

`yaml_utils.discover_profiles()` 根据 `pipeline.use_tts_director` 校验对应 schema。两种 schema 不能混用，混用报错。

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

### 7.3 Per-segment model selection + 同 speaker 一致性

LLM 为每个 segment 独立选 model。两层保障一致性：

- **prompt 层**：system prompt 明确"同一 speaker 全文必须选同一 model"
- **后处理层**：tts_director 输出后扫描，若同 speaker 出现多个 model，统一用首次出现的 model（写 warning 到 log）

### 7.4 Pipeline stage 8 重写

```python
# 按 instruction.model 分组
grouped = defaultdict(list)
for inst in tts_instructions:
    grouped[inst.model].append(inst)

# 每组 lazy 创建 adapter 并 synthesize
audio_segments_by_id = {}
for model_name, group in grouped.items():
    backend = model_config_loader.get_backend(model_name)
    cfg = profile_dict["tts"]["backends_config"][backend]
    adapter = create_tts_adapter(backend, **cfg)  # registry 加 lazy cache
    seg_results = adapter.synthesize(group, voicebank_result, str(output_dir))
    for r in seg_results:
        audio_segments_by_id[r.segment_id] = r

# 按 segment_id 排序保持原顺序
audio_segments = [audio_segments_by_id[inst.segment_id] for inst in tts_instructions]
```

### 7.5 Fallback 策略

LLM 没覆盖的 segment → `_fallback_instruction(segment, default_model_name, default_params)`：

- `default_model_name` 推导顺序：
  1. `profile.pipeline.tts_director_default_model`（可选，用户显式指定，如 `"CosyVoice3"`）
  2. 否则取 `profile.tts.available_backends[0]` 对应的 `model_config.name`（如 `available_backends[0]="cosyvoice_http"` → 查 cosyvoice3.json → `"CosyVoice3"`）
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
| 同 speaker 多 model | 后处理统一（用首次出现的 model）+ warning |
| adapter HTTP 失败 | 单段失败不阻断（沿用老链路行为），failed segment 标 `success=False` |
| voice_ref 缺失 | CosyVoice/IndexTTS 走模型默认音色 + warning；S2Pro 默认 `enable_reference_audio=false` |
| profile schema 混用（同时有 backend 和 available_backends）| yaml_utils 校验时报错，列出冲突字段 |
| model_config 文件解析失败 | model_config_loader 启动时立即报错（fail-fast），不进入 pipeline |
| 跨开关 reuse 格式不匹配（如老链路跑过的 tts_instructions.json 含 TTSInstruction，但本次 use_tts_director=true）| reuse 检测时校验 JSON 首元素是否含 `model` 字段；不匹配则 warning + 忽略 reuse，重新跑 stage 7 |

## 9. Testing Strategy

### 9.1 Unit Tests（mock LLM，CI fast 跑）

`tests/test_tts_director_unit.py`：
- 1:1 输出契约（输入 N segments → 输出 N instructions，segment_id 对应）
- 同 speaker 一致性（mock LLM 故意返回不一致 → 后处理统一）
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

1. **LLM 选 model 的合理性**：LLM 看到详细 description 后能否做出合理选择？需要 integration 测试验证。如果 LLM 倾向于"乱选"（如全选 S2Pro），可能需要在 prompt 加更强约束或后处理。
2. **同 speaker 跨段绝对一致性**：后处理统一能保证 model 一致，但 parameters（如 emotion_vector）跨段可能漂移。需要在 prompt 明确"同 speaker 全文 emotion 一致"，或加后处理 clamp。
3. **多 adapter 创建的性能开销**：每个 model 第一次调用都要 lazy-create adapter（含 HTTP 连接池初始化）。3 个 model 串行调用会增加 ~1-2 秒。可接受。
4. **prompt 长度膨胀**：3 个 model_config 都很详细（每个 ~50 行 JSON），全部注入 system prompt 后 token 数显著增加。如果未来加更多 model，需要拆成"short_description 优先 + 详细 schema 按需查"两段式。
5. **C2 adapter 改造的代码量**：s2pro_adapter 已 807 行，加 `_synthesize_model_specific` 后会到 ~1000 行。可接受（adapter 本来就独立大文件），但需要小心保持双路径不互相污染。

## 11. References

- `refactor_audio_oscar/refactor_plan.md` §4（方向1 详细设计）+ §8（协作策略）+ §12（风险）
- `src_next/core/data_models.py:ModelSpecificTTSInstruction`（数据契约已落地）
- `usage_guide_cosyvoice.md` / `usage_guide_indextts.md` / `usage_guide_s2pro.md`（model_configs 字段来源）
- Audio-Oscar `agents/speech_generator.py`（LLM 直接输出模型参数的模式参考）
- Audio-Oscar `tts/tts_config.json`（model_configs JSON 格式参考）
