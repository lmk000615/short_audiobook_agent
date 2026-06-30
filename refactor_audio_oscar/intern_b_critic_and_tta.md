# 实习生B 任务卡：方向3 + 方向4（Critic 评估-修复 + 段间音效）

> 配合 `refactor_plan.md` 第 6、7 节使用。本卡分两部分，对应两个独立 PR，可以分阶段提交。

---

## Part I：方向3 - Critic 评估-修复机制

### 1.1 任务一句话概述

用 Qwen3-Omni 多模态模型听 TTS 合成的每段音频，从 5 个维度打分；低分段落用 LLM 修复指令后重新合成，最多重试 N 次，保留历史最佳结果。

涉及两件事：
1. **Critic 评估器**：调 Qwen3-Omni 听音频 → 输出 `CriticResult`
2. **Repair Agent**：根据 `CriticResult.suggestions` 调整 `ModelSpecificTTSInstruction.parameters` → 让上游重合成

### 1.2 改动范围

#### ✅ 你可以创建的文件

| 操作 | 文件 | 说明 |
|---|---|---|
| 新增 | `src_next/critic/__init__.py` | critic 包初始化 |
| 新增 | `src_next/critic/qwen3omni_critic.py` | Qwen3-Omni 评估器 |
| 新增 | `src_next/critic/tts_repair.py` | 指令修复 Agent |
| 新增 | `src_next/critic/prompts/__init__.py` | prompts 包 |
| 新增 | `src_next/critic/prompts/critic_prompt.py` | 评分 prompt 模板 |
| 新增 | `src_next/critic/prompts/repair_prompt.py` | 修复 prompt 模板 |
| 新增 | `src_next/critic/tests/test_qwen3omni_critic.py` | 单元测试 |
| 新增 | `src_next/critic/tests/test_tts_repair.py` | 单元测试 |

#### ❌ 你不能动的文件

| 文件 | 原因 |
|---|---|
| `src_next/core/audiobook_pipeline.py` | 阶段一任何人都不改 |
| `src_next/core/data_models.py` | 数据契约已由主开发定义（`CriticResult` / `ModelSpecificTTSInstruction` 已在末尾） |
| `src_next/tts/*_adapter.py` | TTS adapter 改造属于主开发 |
| `src_next/analysis/*` | analysis 层属于主开发 / 实习生A |
| `src_next/voicebank/*` | voicebank 层不动 |

### 1.3 接口契约（必须严格匹配）

#### 1.3.1 Critic 评估器

```python
# src_next/critic/qwen3omni_critic.py

from src_next.core.data_models import Segment, CriticResult, ModelSpecificTTSInstruction


class Qwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频质量。"""

    def __init__(self, base_url: str = "http://10.50.121.102:8011",
                 timeout: int = 120, bypass_proxy: bool = True):
        """
        Args:
            base_url: Qwen3-Omni 服务地址（默认黄区 8011）。
            timeout: 单次评估超时（秒）。Qwen3-Omni 单请求较慢，建议 120s+。
            bypass_proxy: 是否绕过系统代理（黄区内网 true）。
        """

    def evaluate(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
    ) -> CriticResult:
        """
        评估单段音频。

        Args:
            audio_path: 待评估音频文件路径（服务器可读）。
            segment: 对应的 Segment（含原文 text、speaker、segment_type）。
            tts_instruction: 生成该音频用的 TTS 指令（含 model / parameters，
                Critic 用 parameters 中的期望情感/语速作为对照）。

        Returns:
            CriticResult: 5 维评分 + suggestions。
            失败时不抛异常，返回 overall=0.5 / 各维 0.5 的中性结果，
            并在 suggestions 写明失败原因（"评估失败：xxx，建议人工复核"）。
        """
```

#### 1.3.2 Repair Agent

```python
# src_next/critic/tts_repair.py

from src_next.core.data_models import Segment, CriticResult, ModelSpecificTTSInstruction
from src_next.llm.base import BaseLLMClient


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def repair(
        self,
        original: ModelSpecificTTSInstruction,
        segment: Segment,
        critic: CriticResult,
    ) -> ModelSpecificTTSInstruction:
        """
        根据低分维度和 suggestions，调整 parameters。

        契约：
        - 返回新的 ModelSpecificTTSInstruction，**不改 segment_id / speaker /
          text / model**（避免声音不一致）。
        - attempt 字段 +1。
        - parameters 由 LLM 重写（保留原 parameters 中 LLM 没动的字段）。
        - LLM 失败 → 返回 original（attempt +1），不抛异常。
        """
```

### 1.4 服务调用细节（重要）

#### Qwen3-Omni 服务关键约束

| 维度 | 详情 |
|---|---|
| 服务地址 | `http://10.50.121.102:8011` |
| **并发限制** | 服务用 `infer_lock`，**同一时间只处理一个请求** |
| 推荐端点 | `/v1/omni/audio_analysis`（`task: "sound_analysis"`） |
| 音频输入方式 | **传服务器文件路径**（字符串），不需要 base64 |
| 响应格式 | JSON `{"request_id": "...", "text": "...", ...}`（`return_audio=false` 时） |
| 代理 | 必须 `proxies={"http": None, "https": None}` 绕过代理 |

参考 `ussage_guide_qwen3_omni.md` 第 8 节「音频分析」+ 第 11 节「注意事项」。

#### 为什么用 `audio_analysis` 而不是 `chat`

- `audio_analysis` 专为"听音频 → 文字描述 / 分析"设计，输出 schema 稳定。
- `chat` 接口更通用但输出格式自由，需要更复杂的 prompt 约束。
- 一期建议用 `audio_analysis` + 自定义 prompt（在 `text` 字段里写评分要求）。

#### 评分 prompt 设计建议

`text` 字段示例（作为 audio_analysis 的 prompt）：

```
请仔细听这段音频，并对照以下信息评分：

## 原文
{segment.text}

## 期望表现
- 模型: {tts_instruction.model}
- 期望情感/风格: {tts_instruction.parameters.get('instruct_text') or tts_instruction.parameters.get('instruction')}
- 期望语速: {tts_instruction.parameters.get('speed', 'N/A')}

## 评分维度（每项 0.0-1.0）
1. quality: 音质清晰度
2. emotion_alignment: 情感是否与期望一致
3. character_consistency: 声音特征是否符合 {segment.speaker} 的设定
4. rhythm_naturalness: 节奏是否自然
5. intelligibility: 文本是否清晰可辨

## 输出（严格 JSON，不要加任何额外文字）
{"quality": 0.xx, "emotion_alignment": 0.xx, "character_consistency": 0.xx,
 "rhythm_naturalness": 0.xx, "intelligibility": 0.xx,
 "suggestions": "中文修复建议"}
```

#### 输出解析的鲁棒性

LLM 输出可能：
- 包在 ```json ... ``` 代码块里 → 用正则提取
- 字段名拼写错（`rhythm_natural` 而不是 `rhythm_naturalness`）→ 用 fuzzy match 或在 prompt 里强调字段名
- 漏字段 → `CriticResult.from_json` 已经处理（缺失补 0.5）
- 完全不是 JSON → 整体 fallback 为中性评分

### 1.5 Repair 策略约束

| 修复能力 | 是否允许 | 原因 |
|---|---|---|
| 改 parameters（如调 emotion / speed / instruct_text） | ✅ 允许 | 主要修复手段 |
| 改 text（修原文） | ❌ 禁止 | 原文是用户的资产，不能改 |
| 换 model（如 CosyVoice → S2Pro） | ❌ 禁止 | 跨模型音色不一致 |
| 改 voice_ref（换参考音频） | ❌ 禁止 | 同一角色必须用同一 voice_ref |
| 改 segment_id / speaker | ❌ 禁止 | 与上游对齐契约 |

prompt 必须明确告诉 LLM"只能调 parameters 内字段，不能动其他字段"。

### 1.6 单元测试要求

测试分两类，**都要写**：

#### A. 功能测试：**真实调 Qwen3-Omni**

Critic 的核心价值是"听音频 → 准确评分"，mock 验证不了评分质量。必须用真 Qwen3-Omni 跑通才知道 prompt + 解析逻辑是否工作。

实现要点：

1. **Qwen3-Omni 客户端 fixture**：
   ```python
   # tests/conftest.py
   import pytest
   from src_next.critic.qwen3omni_critic import Qwen3OmniCritic

   @pytest.fixture(scope="session")
   def real_critic():
       return Qwen3OmniCritic(base_url="http://10.50.121.102:8011")
   ```

2. **测试音频准备**：在 `tests/fixtures/` 放 2-3 段短 wav（5-10 秒，覆盖不同情绪 / 质量），方便重复跑。
   - 可以用现有 voicebank 输出裁剪一段
   - 或者用 `soundfile` 合成一段纯 TTS 输出

3. **标记为 integration 测试**：`@pytest.mark.integration`，CI fast 模式可跳过。

4. **必须串行运行**：Qwen3-Omni 有 `infer_lock`，并发请求会排队甚至超时。
   ```bash
   # 不要加 -n auto 或 -p no:cacheprovider
   pytest src_next/critic/tests/test_qwen3omni_critic.py -m integration
   ```

5. **断言要容忍评分波动**：LLM 评分有随机性，不要 `assert result.quality == 0.85`。改用：
   - **范围断言**：`assert 0.7 <= result.quality <= 1.0`（高分音频应该高分）
   - **排序断言**：准备一好一坏两段音频，断言 `good.quality > bad.quality`（相对值更稳定）

6. **Critic 功能测试至少 3 个 case**：
   - case 1：高质量音频 + 期望情感匹配 → 5 维分都 ≥ 0.7
   - case 2：低质量音频（含截断 / 杂音） → quality 分 < 0.6
   - case 3：情感不匹配（期望 sad，实际 neutral 音频）→ emotion_alignment < 0.6

#### B. Robustness 测试：**mock HTTP**

验证"服务出问题时不让 pipeline 崩"，**必须 mock**（真服务没法稳定复现故障）：
- mock `requests.post` 返回 500 / 超时 / 非 JSON 文本
- 验证 Critic 返回中性评分（overall=0.5）+ suggestions 写明失败原因，不抛异常

#### Repair 测试

Repair Agent 调的是普通 LLM（不是 Qwen3-Omni），所以：

- **功能测试用真 LLM**（Gemma4 HTTP via profile）：验证修复后的 parameters 确实改善了（如低 speed 被调高）。
- **Robustness 测试用 mock**：模拟 LLM 返回非法 JSON / 缺字段，验证 fallback。
- **必须验证**：repair 后 segment_id / speaker / text / model / voice_ref 不变（用真 LLM 时这点尤其重要——prompt 写不好 LLM 可能乱改字段）。

#### 参考实现

```python
# src_next/critic/tests/test_qwen3omni_critic.py

import pytest
from pathlib import Path
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.mark.integration
def test_critic_high_quality_audio(real_critic):
    """高质量音频应该得到较高评分。"""
    audio = str(FIXTURES / "good_narration.wav")
    seg = Segment(segment_id="s1", text="测试文本", speaker="narrator",
                  segment_type="narration", raw_index=0)
    inst = ModelSpecificTTSInstruction(
        segment_id="s1", speaker="narrator", text="测试文本", model="S2Pro",
        parameters={"instruction": "平稳叙述"},
    )
    result = real_critic.evaluate(audio, seg, inst)
    assert 0.6 <= result.quality <= 1.0
    assert 0.0 <= result.overall <= 1.0
    assert isinstance(result.suggestions, str)


def test_critic_handles_500_error(monkeypatch):
    """服务返回 500 时不崩，返回中性评分。"""
    import src_next.critic.qwen3omni_critic as mod
    class _BadResp:
        status_code = 500
        text = "internal error"
    def fake_post(*a, **kw):
        return _BadResp()
    monkeypatch.setattr(mod.requests, "post", fake_post)

    critic = Qwen3OmniCritic(base_url="http://fake")
    seg = Segment(segment_id="s1", text="x", speaker="narrator",
                  segment_type="narration", raw_index=0)
    inst = ModelSpecificTTSInstruction(
        segment_id="s1", speaker="narrator", text="x", model="S2Pro", parameters={},
    )
    result = critic.evaluate("/nonexistent.wav", seg, inst)
    assert result.overall == 0.5  # 中性 fallback
    assert "失败" in result.suggestions or "error" in result.suggestions.lower()
```

---

## Part II：方向4 - 段落间环境音效（一期）

### 2.1 任务一句话概述

为段落间隙生成环境音效（如雨声、风声、脚步声），替代当前的静默间隔，提升沉浸感。

涉及三件事：
1. **音效规划 Agent**：根据故事内容决定哪些段间需要什么音效 → `list[SFXEvent]`
2. **TTA adapter**：调 MOSSSoundEffect 生成音效 wav → 填充 `SFXEvent.audio_path`
3. **audio_merger 改造**：在合并阶段把音效插入段间（一期不与语音叠加）

### 2.2 改动范围

#### ✅ 你可以创建的文件

| 操作 | 文件 | 说明 |
|---|---|---|
| 新增 | `src_next/tta/__init__.py` | tta 包初始化 |
| 新增 | `src_next/tta/base.py` | `BaseTTAAdapter` 抽象类 |
| 新增 | `src_next/tta/moss_soundeffect_adapter.py` | MOSSSoundEffect 实现 |
| 新增 | `src_next/tta/registry.py` | TTA adapter 工厂（参考 `tts/registry.py`） |
| 新增 | `src_next/tta/tests/test_moss_soundeffect_adapter.py` | 单元测试 |
| 新增 | `src_next/analysis/sfx_planner.py` | 音效规划 Agent |
| 新增 | `src_next/analysis/prompts/sfx_planner_prompt.py` | Prompt 模板 |
| 新增 | `src_next/analysis/tests/test_sfx_planner.py` | 单元测试 |

#### ⚠️ 受限文件（需要主开发在阶段二帮你接入）

| 文件 | 限制 |
|---|---|
| `src_next/core/audio_merger.py` | **可以改**，但只在阶段二接入；阶段一你写一个独立的 `audio_merger_v2.py`（同目录）做测试，主开发阶段二会替换原文件 |

### 2.3 接口契约（必须严格匹配）

#### 2.3.1 TTA Adapter 抽象

```python
# src_next/tta/base.py

from abc import ABC, abstractmethod


class BaseTTAAdapter(ABC):
    """Text-to-Audio 适配器抽象。"""

    @abstractmethod
    def generate(
        self,
        description: str,
        parameters: dict,
        duration: float,
        output_path: str,
    ) -> str:
        """
        生成一段音效。

        Args:
            description: 音效自然语言描述（建议英文，如 "gentle rain with distant thunder"）。
            parameters: 模型特定参数（直接透传，schema 由 model_configs 定义）。
            duration: 期望时长（秒）。adapter 据此裁剪 / 循环生成的音频。
            output_path: 输出 wav 路径。

        Returns:
            实际写入的 wav 路径（成功时与 output_path 一致）。
            失败时不抛异常，返回空字符串，由上游决定 fallback（用静音替代）。
        """
```

#### 2.3.2 MOSSSoundEffect Adapter

```python
# src_next/tta/moss_soundeffect_adapter.py

from src_next.tta.base import BaseTTAAdapter


class MOSSSoundEffectAdapter(BaseTTAAdapter):
    """MOSSSoundEffect TTA 服务适配器。"""

    def __init__(self, base_url: str, timeout: int = 300, bypass_proxy: bool = True):
        """
        Args:
            base_url: MOSSSoundEffect 服务地址。
                ⚠️ 当前文档（usage_guide_moss_voicegen.md）描述的是 MOSS-VoiceGenerator
                （TTS），不是 TTA。**开工前必须与运维确认 MOSSSoundEffect 的端点**。
            timeout: 单次生成超时（秒）。
        """

    def generate(self, description, parameters, duration, output_path) -> str:
        # 调用 MOSSSoundEffect HTTP API
        # 失败时返回 ""，不抛异常
        ...
```

#### 2.3.3 SFX Planner

```python
# src_next/analysis/sfx_planner.py

from src_next.core.data_models import Segment, CharacterProfile, SFXEvent
from src_next.llm.base import BaseLLMClient


def plan_sfx_events(
    segments: list[Segment],
    character_profiles: list[CharacterProfile],
    llm_client: BaseLLMClient,
    tta_model_configs: list[dict],
) -> list[SFXEvent]:
    """
    为段间规划环境音效。

    契约：
    - 输入：完整 segments + 角色信息 + 可用 TTA 模型描述（用于 prompt 注入）。
    - 输出：list[SFXEvent]，每个 SFXEvent.position 必须是 "after_seg_xxx" 或
      "before_seg_xxx"（一期不支持 in_seg 精确时间戳）。
    - 一期约束：每个 position 至多一个 SFXEvent；同一故事 SFXEvent 数量建议
      不超过 segments 数量的 30%（避免音效泛滥）。

    规则（必须在 prompt 里强调）：
    1. 只添加文本中明确提及或强烈暗示的环境音（"窗外下着雨" → 雨声）。
    2. 不添加文本未提及的装饰性音效。
    3. 对话密集段不加音效（避免干扰对白）。
    4. description 用英文（TTA 模型对英文支持更好）。
    """
```

### 2.4 MOSSSoundEffect 服务现状（必须先确认）

⚠️ **风险点**：当前 `usage_guide_moss_voicegen.md` 描述的是 **MOSS-VoiceGenerator**（语音合成 TTS），**不是音效 TTA**。两者模型不同：

| 维度 | MOSS-VoiceGenerator（已部署） | MOSSSoundEffect（待确认） |
|---|---|---|
| 用途 | 语音合成 | 音效生成 |
| 端口 | 8003 | **待确认** |
| 输入 | text + instruction | description（自然语言） |
| 输出 | 语音 wav | 音效 wav |

**开工前必须做的第一件事**：与运维确认 MOSSSoundEffect 的：
1. 服务地址 / 端口
2. API schema（请求字段、Content-Type）
3. 输出格式（采样率 / 时长是否可控）
4. 是否需要描述传英文

如果服务还没起来，adapter 先写 mock 实现（直接返回空 wav 或静音 wav），保证阶段一其他模块能跑通。MOSSSoundEffect 真起来后改 HTTP 调用即可。

### 2.5 audio_merger 改造（阶段二）

主开发阶段二集成时，会基于你的 `audio_merger_v2.py` 替换 `src_next/core/audio_merger.py`：

```python
# 阶段二后的 audio_merger（你写 v2 时按这个目标设计）

def merge_audio(
    audio_segments: list[AudioSegmentResult],
    sfx_events: list[SFXEvent] | None = None,
    output_path: str = ...,
) -> AudioResult:
    """
    一期：段间插音效（不与语音叠加）。

    流程：
    1. 按 segment 顺序遍历。
    2. 每段音频追加到合并列表。
    3. 查找该 segment_id 对应的 SFXEvent（position == "after_seg_xxx"）：
       - 找到且 audio_path 非空 → 追加音效 wav
       - 找不到 → 追加默认静默（保持段间间隙）
    4. position == "before_seg_xxx" 的音效在第一段之前插入（用于片头环境音）。
    """
```

### 2.6 单元测试要求

测试分两类，**都要写**：

#### A. 功能测试：**真实调服务 / 真 LLM**

##### TTA Adapter 功能测试（前提：MOSSSoundEffect 服务已就绪）

如果服务还没就绪，先跳过这部分（在 PR 描述里注明"待 MOSSSoundEffect 就绪后补 integration 测试"），但不能不写——预留测试代码骨架，服务一就绪即可启用。

```python
@pytest.mark.integration
def test_tta_generates_rain(real_tta_adapter, tmp_path):
    """真实生成雨声音效。"""
    out = str(tmp_path / "rain.wav")
    result = real_tta_adapter.generate(
        description="Gentle rain falling continuously",
        parameters={},
        duration=3.0,
        output_path=out,
    )
    assert result == out
    assert Path(out).exists()
    # 验证 wav 可读 + 时长接近 3.0 秒
    import soundfile as sf
    data, sr = sf.read(out)
    assert 2.5 <= len(data) / sr <= 4.0  # 允许些误差
```

##### SFX Planner 功能测试（真 LLM）

SFX Planner 的核心是 prompt 设计，必须用真 LLM 验证规划质量：

```python
@pytest.mark.integration
def test_sfx_planner_identifies_rain(real_llm):
    """故事里写明下雨，planner 应规划雨声音效。"""
    segments = [
        Segment(segment_id="seg_001", text="窗外下着大雨。", speaker="narrator",
                segment_type="narration", raw_index=0),
        Segment(segment_id="seg_002", text="雨停了。", speaker="narrator",
                segment_type="narration", raw_index=0),
    ]
    events = plan_sfx_events(segments, [], real_llm, tta_model_configs=[...])
    # 至少有一个雨声相关 event
    assert any("rain" in e.description.lower() for e in events)
    # position 格式合法
    assert all(e.position.startswith(("after_seg_", "before_seg_")) for e in events)
```

#### B. Robustness 测试：**mock**

##### TTA Adapter robustness

- mock `requests.post` 返回 500 / 超时 → adapter 返回空字符串，不抛异常
- mock 返回非 wav 内容（如 HTML 错误页） → adapter 检测 RIFF header 失败，返回空字符串

##### SFX Planner robustness

- mock LLM 返回非法 JSON / 缺字段 → 返回空 list（pipeline 走静默 fallback）
- mock LLM 返回的 position 格式非法（如 `"in_seg_xxx"`） → 该 event 跳过 + 日志警告
- mock LLM 返回不存在的 segment_id → 该 event 跳过

---

## 3. PR 验收标准

### Part I（Critic）PR

- [ ] 8 个文件新增到 `feature/critic-and-tta` 分支（或在分支里分两次 commit）。
- [ ] `Qwen3OmniCritic.evaluate` 签名与 1.3.1 一致。
- [ ] `TTSRepairAgent.repair` 签名与 1.3.2 一致。
- [ ] Critic 不抛异常（任何失败都 fallback 为中性评分）。
- [ ] Repair 不改 segment_id / speaker / text / model / voice_ref。
- [ ] **Critic 功能测试通过（真实 Qwen3-Omni）**：`pytest -m integration` 跑通 3 个 case（含排序断言：好音频分高于坏音频）。
- [ ] **Critic robustness 测试通过（mock）**：500 / 非 JSON 都不崩。
- [ ] **Repair 功能测试通过（真实 LLM via profile）**：修复后 parameters 有可观察变化。
- [ ] **Repair robustness 测试通过（mock）**：LLM 失败 fallback。
- [ ] py_compile + pytest 全绿。
- [ ] **不引入新依赖**：用 `requests` / `BaseLLMClient`，不引入 openai SDK 等。
- [ ] **PR 描述附 1 条真实评分样例**：贴一段音频路径 + 期望 + Qwen3-Omni 实际返回的 JSON + 解析后的 CriticResult。

### Part II（TTA + SFX）PR

- [ ] 8 个文件新增到同一分支。
- [ ] `BaseTTAAdapter` / `MOSSSoundEffectAdapter` / `plan_sfx_events` 签名与 2.3 一致。
- [ ] TTA adapter 失败时返回空字符串，不抛异常。
- [ ] `audio_merger_v2.py` 实现段间插入逻辑。
- [ ] **SFX Planner 功能测试通过（真实 LLM）**：`pytest -m integration` 跑通，能正确识别"下雨"等明确环境音。
- [ ] **TTA 功能测试**：MOSSSoundEffect 已就绪则跑真实 integration；未就绪则在 PR 描述明确标注"待服务就绪后补"，且测试代码骨架已写好（用 `pytest.skip` 而非删除）。
- [ ] **Robustness 测试通过（mock）**：TTA 失败不崩；SFX Planner 非法 position / segment_id 跳过。
- [ ] py_compile + pytest 全绿。
- [ ] **MOSSSoundEffect 服务信息已与运维确认**，或在 PR 描述里明确标注"待运维确认"。

---

## 4. 你完成后会发生什么（集成阶段）

阶段二主开发会做：

1. **Stage 7 拆并行**：tts_synthesis 和 sfx_generation 同时启动（ThreadPoolExecutor）。
2. **Stage 8 插 Critic 循环**：
   ```python
   for attempt in range(1, max_retries + 1):
       critic_results = {seg_id: critic.evaluate(...) for seg_id, path in audio_segments.items()}
       # 更新历史最佳
       needs_repair = {k: v for k, v in critic_results.items() if v.needs_repair()}
       if not needs_repair: break
       for seg_id, result in needs_repair.items():
           repaired = repair_agent.repair(tts_instructions[seg_id], segments[seg_id], result)
           tts_instructions[seg_id] = repaired
           audio_segments[seg_id] = tts_adapter.synthesize(repaired).audio_path
   ```
3. **Stage 9 替换 audio_merger**：用你的 `audio_merger_v2` 替换原文件。
4. 开关 `enable_critic` / `enable_sfx` 默认关闭，开启后才走你的代码。

---

## 5. 关键参考文件

| 文件 | 看什么 |
|---|---|
| `ussage_guide_qwen3_omni.md` 第 8 节 | `/v1/omni/audio_analysis` 端点用法 |
| `ussage_guide_qwen3_omni.md` 第 11 节 | 注意事项（infer_lock / 代理 / 路径传文件） |
| `src_next/tts/s2pro_adapter.py` | HTTP adapter 实现模式（multipart / 错误处理 / bypass_proxy） |
| `src_next/tts/registry.py` | registry + adapter 工厂模式（TTA 照抄） |
| `src_next/voicebank/qwen3_http.py` | voicebank adapter 模式（生成 wav 落盘 + 失败兜底） |
| `src_next/core/data_models.py` 末尾 | `CriticResult` / `SFXEvent` / `ModelSpecificTTSInstruction` 字段定义 |
| `src_next/core/audio_merger.py` | 现有 merger 实现（你的 v2 要兼容它的输入输出） |

---

## 6. 常见陷阱

1. **Qwen3-Omni 单请求锁**：不要用 ThreadPoolExecutor 并发调 Critic，必须串行（`for seg_id in ...: critic.evaluate(...)`）。否则后到的请求会等锁，超时堆积。**测试也一样**：integration 测试不要加 `-n auto`（pytest-xdist 并行），串行跑。
2. **音频路径必须是服务器可读的绝对路径**：Qwen3-Omni 服务在 `10.50.121.102` 上跑，它会去读这个路径的文件，相对路径或本地路径无效。**测试时把音频放在服务器能访问的共享路径**，或者本地起服务跑测试。
3. **CriticResult 不要自己定义**：从 `core.data_models` 导入，主开发已经定义好了 `from_json` / `needs_repair`。
4. **Repair 的 LLM 输出必须 merge 而不是 replace**：LLM 可能只返回它想改的字段，原来 parameters 里的其他字段要保留。**功能测试要专门验证这点**——prompt 写不好 LLM 真的会乱删字段。
5. **MOSSSoundEffect 失败时不能让 pipeline 崩**：TTA adapter 返回空字符串，audio_merger 用静默 fallback。一期音效是 nice-to-have 不是必须。
6. **SFXEvent.description 用英文**：TTA 模型对英文描述效果更好。SFX Planner 的 prompt 必须强制 LLM 输出英文 description（即使中文故事）。**功能测试要验证这点**。
7. **integration 测试用 `@pytest.mark.integration` 标记**：CI fast 模式（`-m "not integration"`）跳过，PR 合并前手动跑完整 integration。不要把 integration 测试和 mock 测试混在同一个未标记的 case 里。

---

## 7. 完成定义（Definition of Done）

- Part I 和 Part II 各自一个 PR（或一个 PR 两次 commit），提交到 `feature/critic-and-tta` 分支。
- PR 描述包含：
  - Critic 评分的 1 条真实样例（用任意 wav 跑一次真实 Qwen3-Omni，截图评分输出）
  - MOSSSoundEffect 服务确认情况（端点 / schema）
  - 测试覆盖说明
- 主开发 review 通过 + CI 单测全绿。
- 阶段二集成后端到端跑通（主开发执行）。
