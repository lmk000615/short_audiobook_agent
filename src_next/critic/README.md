# src_next/critic — Qwen3-Omni 评估 + LLM 修复子链路（实习生 B 方向3）

> Part I 实现包：Critic 给 TTS 音频打分 → 不达标则 Repair 调 LLM 改 TTS 指令 → 重新合成。
>
> 当前状态：**15 mock 测试全绿；5 integration 测试 skip**（服务不可达，代码就绪待激活）。

---

## 1. 这是什么

把"听一遍 TTS 录的音频、判断好坏、不好就让 LLM 调整指令再录一次"这个闭环落地：

```
   TTSInstruction + audio.wav
              │
              ▼
   ┌──────────────────────┐
   │  Qwen3OmniCritic     │  调 Qwen3-Omni 服务对音频打 5 维评分
   │  .evaluate(...)      │  （pronunciation / pace / emotion / fluency / naturalness）
   └──────────────────────┘
              │
              ▼
        CriticResult
        (overall + 5 维分数 + reason)
              │
              │  result.needs_repair(threshold, overall_floor)?
              │
        ┌─────┴─────┐
        │           │
       否           是
        │           │
        ▼           ▼
     原指令    ┌──────────────────────┐
               │  TTSRepairAgent      │  调 LLM 改写 TTS 指令（emotion/pace/...）
               │  .repair(...)        │  永不动 schema-frozen 字段
               └──────────────────────┘
                          │
                          ▼
                  新的 TTSInstruction
                  （回到 Stage 8 重合成）
```

### 设计原则（任务卡 §1.3）

1. **Critic 失败兜底返回中性 0.5**（不是 0.0）。任务卡明确："不要因为评分失败就把整个 segment 否决掉"。区别于 Audio-Oscar 的 0.0 兜底。
2. **Repair 永不修改 schema-frozen 字段**：`segment_id / speaker / text / model / voice_ref`。这些是 segment 身份字段，改了会破坏下游契约。允许改的：`emotion / pace / tone / volume / pitch / pause_hint / stress_words / delivery_instruction` 等。
3. **不引入新依赖**：仅用 `requests`（HTTP）+ `BaseLLMClient`（已有抽象）。
4. **Critic 必须串行调用**（不能用 ThreadPoolExecutor）— Qwen3-Omni 推理有锁，并发会 silent fail。

---

## 2. 文件清单

| 文件 | 作用 |
|---|---|
| `__init__.py` | 包导出 |
| `qwen3omni_critic.py` | `Qwen3OmniCritic` 主类，HTTP 调 Qwen3-Omni 评分 + neutral fallback |
| `tts_repair.py` | `TTSRepairAgent` 主类，LLM 改写 TTS 指令 + frozen 字段保护 |
| `persistence.py` | `save_critic_session()` / `save_attribute_critic_session()` / `save_long_audio_critic_session()` helper |
| `prompts/__init__.py` | prompt 子包 |
| `prompts/critic_prompt.py` | Critic 的 prompt 模板（5 维评分要求 + JSON 输出格式）|
| `prompts/repair_prompt.py` | Repair 的 prompt 模板（评分反馈 → 改写指令）|
| `prompts/attribute_critic_prompt.py` | 属性感知 Critic 的 prompt 模板（两步法 + DirectorInstruction 锚点）|
| `attribute_result.py` | `AttributeAwareCriticResult` dataclass（5 维 + extracted/expected/consistency）|
| `attribute_critic.py` | `AttributeAwareQwen3OmniCritic` 主类（与 `Qwen3OmniCritic` 并存的属性感知版本）|
| `tests/test_qwen3omni_critic.py` | Critic 测试（构造 / 解析 / 兜底 / merge / 契约 / integration skip）|
| `tests/test_tts_repair.py` | Repair 测试（行为 / frozen 字段 / LLM raise fallback / integration skip）|
| `tests/test_persistence.py` | 持久化测试（scoring-only / scoring+repair / 音频复制 / 命名 / 覆盖）|
| `tests/test_attribute_critic.py` | 属性感知 Critic 测试（14 mock + 2 integration skip）|
| `tests/INTEGRATION_HANDOFF.md` | 属性感知 Critic 的 integration 测试交接文档（给有模型权限的机器）|
| `tests/conftest.py` | pytest fixtures（mock LLM / mock 音频路径 / schema 校验）|
| `KNOWN_ISSUES.md` | 已知 gap + 服务激活指引 + API 端点风险 |
| `README.md` | 本文件 |

---

## 3. 测试状态

| 测试 | 数量 | 状态 |
|---|---|---|
| `test_qwen3omni_critic.py` mock | 11 | ✅ 全绿 |
| `test_qwen3omni_critic.py` integration | 4 | ⏸️ skip（待服务可访问）|
| `test_tts_repair.py` mock | 8 | ✅ 全绿 |
| `test_tts_repair.py` integration | 1 | ⏸️ skip |
| `test_persistence.py` mock | 11 | ✅ 全绿 |
| `test_long_audio_critic.py` mock | 9 | ✅ 全绿 |
| `test_long_audio_critic.py` integration | 1 | ⏸️ skip |
| `test_attribute_critic.py` mock | 14 | ✅ 全绿 |
| `test_attribute_critic.py` integration | 2 | ⏸️ skip（`RUN_INTEGRATION=1` 激活）|

**为什么 integration skip**：实习生本机无法访问 Qwen3-Omni 服务（`10.50.121.102:8011`）和本地 LLM 服务。运维确认服务存在且正常，只是本机访问不到。代码就绪，等环境就绪后激活是机械步骤。

**激活方法**：
- 原 Qwen3OmniCritic integration：见 [`KNOWN_ISSUES.md §1`](./KNOWN_ISSUES.md)
- AttributeAwareQwen3OmniCritic integration：见 [`tests/INTEGRATION_HANDOFF.md`](./tests/INTEGRATION_HANDOFF.md)

---

## 4. 用法

### 4.1 Critic 单独使用

```python
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import TTSInstruction

critic = Qwen3OmniCritic(
    base_url="http://10.50.121.102:8011",
    api_key="...",
    timeout=30,
)

result = critic.evaluate(
    audio_path="/path/to/seg.wav",
    text="你好世界",
    instruction=TTSInstruction(...),
    speaker="narrator",
)

print(result.overall)         # 0.0-1.0
print(result.dimensions)      # {"pronunciation": 0.8, "pace": 0.7, ...}
print(result.needs_repair(threshold=0.7, overall_floor=0.6))
```

### 4.2 Repair 单独使用

```python
from src_next.critic.tts_repair import TTSRepairAgent
from src_next.llm.registry import create_llm_client

llm = create_llm_client(profile_yaml="src_next/profiles/xxx.yaml")
repair = TTSRepairAgent(llm_client=llm)

new_instruction = repair.repair(
    original=current_instruction,   # 当前 TTSInstruction
    critic_result=result,           # Critic 输出
    attempt=2,                      # 第几次尝试（影响 prompt 的紧迫度）
)
# new_instruction.segment_id == current_instruction.segment_id   ← 永远相等
# new_instruction.emotion 可能被改
```

### 4.3 在 Stage 8 pipeline 中接入（待主开发做）

Critic + Repair 当前**未接入** `core/audiobook_pipeline.py`。集成时的注意点：

- Critic 调用必须**串行**（去掉 Stage 9 的 `ThreadPoolExecutor`，或为 Critic 单独串行通道）
- `original` 参数当前指"当前指令"；若要 frozen-original 语义（Audio-Oscar §D.23），调用方需自己保存 attempt=1 的指令并传入
- `needs_repair()` 已挂在 `CriticResult`（在 `core/data_models.py`），用 `min(dims) < threshold OR overall < overall_floor` 判定

### 4.4 落盘评分与修复产物

调用 `evaluate()` / `repair()` 后，可用 `save_critic_session()` 把结果归档到本地，便于事后回看与调试：

```python
from src_next.critic import save_critic_session
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.critic.tts_repair import TTSRepairAgent

critic = Qwen3OmniCritic(...)
repair = TTSRepairAgent(llm_client=...)

result = critic.evaluate("/path/to/seg.wav", segment, instruction)
new_inst = (
    repair.repair(original=instruction, segment=segment, critic=result)
    if result.needs_repair(threshold=0.7, overall_floor=0.6)
    else None
)

folder = save_critic_session(
    audio_path="/path/to/seg.wav",
    critic_result=result,
    repair_result=new_inst,        # None 时不写 repair.json
    # output_root=None → 默认项目根 output/
)
# folder = output/critic/seg/
#   ├── scoring.json   (CriticResult 序列化：5 维分 + overall + suggestions + attempt)
#   ├── repair.json    (修复后的 ModelSpecificTTSInstruction；未触发修复则无此文件)
#   └── seg.wav        (输入音频的副本，便于文件夹自包含)
```

行为约定：
- 文件夹名 = `Path(audio_path).stem`（去扩展名），如 `seg_001.wav` → `output/critic/seg_001/`
- 同名音频重评**覆盖**既有文件（不版本化）；attempt 字段记录在 JSON 内
- 默认输出根 = 项目根 `output/`，可通过 `output_root=` 覆盖（如未来接入 pipeline 时改用 profile 的 `output.root`）
- `audio_path` 不存在会抛 `FileNotFoundError`

### 4.5 属性感知 Critic（并存方案）

`AttributeAwareQwen3OmniCritic` 是 `Qwen3OmniCritic` 的**并存方案**（原 critic 不动）。
差异在于评估流程是两步法：

1. **属性提取**：critic 听音频后客观描述实际表现（emotion / intensity / pace /
   volume / pitch + 必填 evidence）
2. **文本一致性对比**：拿上游 `DirectorInstruction` 作为真相源锚点，逐项判断
   音频与文本情感基调是否一致，输出 `overall_verdict` (high/medium/low)
3. **不一致 → 输出修改建议**

并保留原 5 维评分（向后兼容 `TTSRepairAgent`）。

```python
from src_next.critic.attribute_critic import AttributeAwareQwen3OmniCritic
from src_next.critic.attribute_result import AttributeAwareCriticResult
from src_next.core.data_models import DirectorInstruction

critic = AttributeAwareQwen3OmniCritic(
    base_url="http://10.50.121.102:8011",
    timeout=200,
)

result: AttributeAwareCriticResult = critic.evaluate(
    audio_path="/path/to/seg.wav",
    segment=seg,
    tts_instruction=inst,
    director_instruction=di,   # 新增必填参数
)

# 5 维（与 CriticResult 同语义）
print(result.overall, result.emotion_alignment)

# 属性感知新增字段
print(result.extracted_attributes)      # {"emotion": "sad", "intensity": 0.6, "evidence": "..."}
print(result.expected_attributes)       # 从 DirectorInstruction 现场渲染（真相源）
print(result.attribute_consistency)     # {"overall_verdict": "medium", ...}

# 降级为 CriticResult，喂给 TTSRepairAgent
if result.needs_repair(threshold=0.7, overall_floor=0.75):
    new_inst = repair_agent.repair(
        original=inst, segment=seg, critic=result.to_critic_result(),
    )
```

**真相源约定（重要）**：`expected_attributes` 永远从 `DirectorInstruction` 现场
渲染，**不取 LLM 回填值**。LLM 在 prompt 里被要求复述期望属性仅用于自检。这避免
LLM 抄错期望值导致一致性结论失真。

**落盘**：用 `save_attribute_critic_session()`，与 `save_critic_session` 落盘目录
相同（同一段音频只会用一种 critic 评估，不会冲突）。`scoring.json` 内嵌
`extracted_attributes` / `expected_attributes` / `attribute_consistency` 三段。

**Integration 测试交接**：见 [`tests/INTEGRATION_HANDOFF.md`](./tests/INTEGRATION_HANDOFF.md)。
本机无模型权限时 integration 测试默认 skip，需要黄区网络 + `RUN_INTEGRATION=1` 激活。

---

## 5. ⚠️ 已知风险（详见 KNOWN_ISSUES.md）

### 5.1 API 端点（已敲定：`/v1/omni/chat` + base64 音频）

`qwen3omni_critic.py::_evaluate_inner` 当前调 `/v1/omni/chat` 端点，音频以 **base64 编码字符串** 形式传入 `audio` 字段。该路径已于 2026-07-09 经真实服务测试验证可行。

**为什么不走 task card §1.4 推荐的 `/v1/omni/audio_analysis`**：真实服务测试发现该端点不接受本地文件路径形式的 `audio` 字段，task card 设想的 (a) 路径不成立，触发了预判的 (b) 风险场景。详见 [`KNOWN_ISSUES.md §2`](./KNOWN_ISSUES.md) 的历史决策记录。

### 5.2 测试音频 fixture 未实际准备

`conftest.py` 里的 fixture 只解析路径，不验证文件存在。准备方法见 [`KNOWN_ISSUES.md §3`](./KNOWN_ISSUES.md)。

---

## 6. Mock 样例

[`docs/pr_samples/critic_sample.md`](../../docs/pr_samples/critic_sample.md) 展示 prompt 设计的预期 I/O 格式 + 解析鲁棒性覆盖。真实评分样例待服务可访问后补充。

---

## 7. 相关文档

- [任务卡 / 设计 spec](../../docs/intern_b_critic_and_tta.md)
- [Plan（含 16 个 task 拆解）](../../docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md)
- [Audio-Oscar 调研对比](../../docs/intern_b_audio_oscar_research.md)
- [Audio-Oscar 设计借鉴](../../docs/intern_b_audio_oscar_why.md)
- [已知风险与待办](./KNOWN_ISSUES.md)
- [Mock 测试样例](../../docs/pr_samples/critic_sample.md)

