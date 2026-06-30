# 实习生A 任务卡：方向2 - segment_resolver（Agent 化文本处理）

> 配合 `refactor_plan.md` 第 5 节使用。本卡只讲你**要做什么、不能动什么、怎么验收**，业务背景看总方案。

---

## 1. 你的任务一句话概述

把当前 `src_next/analysis/quote_classifier.py` + `src_next/analysis/story_resolver.py` 两个模块**合并为一个 LLM Agent 调用**，让 LLM 同时判断"是不是对白"和"是谁说的"，消除中间数据落地。

最终产出一个新模块：`src_next/analysis/segment_resolver.py`。

---

## 2. 改动范围

### ✅ 你可以创建 / 修改的文件

| 操作 | 文件 | 说明 |
|---|---|---|
| 新增 | `src_next/analysis/segment_resolver.py` | 你的主要产出 |
| 新增 | `src_next/analysis/prompts/segment_resolver_prompt.py` | Prompt 模板（与现有 `story_resolver.py` 同目录风格） |
| 新增 | `src_next/analysis/tests/test_segment_resolver.py` | 单元测试（黄金集，见第 5 节） |

### ❌ 你不能动的文件（碰了 PR 直接打回）

| 文件 | 原因 |
|---|---|
| `src_next/core/audiobook_pipeline.py` | 阶段一任何人都不改，统一留给主开发阶段二集成 |
| `src_next/core/data_models.py` | 数据契约已由主开发定义，你只读导入 |
| `src_next/core/segment_builder.py` | 规则分段骨架保留，比 LLM 更可靠 |
| `src_next/analysis/quote_classifier.py` | 老链路保留作 fallback |
| `src_next/analysis/story_resolver.py` | 老链路保留作 fallback |
| `src_next/tts/*` | TTS 层属于主开发 / 实习生B 的领域 |
| `src_next/critic/*` / `src_next/tta/*` | 实习生B 的领域 |

---

## 3. 接口契约（必须严格匹配）

### 3.1 函数签名

```python
# src_next/analysis/segment_resolver.py

from src_next.core.data_models import Segment, CharacterProfile
from src_next.llm.base import BaseLLMClient


def resolve_segments(
    segments: list[Segment],
    character_profiles: list[CharacterProfile],
    llm_client: BaseLLMClient,
) -> list[Segment]:
    """
    合并原 quote_classifier + story_resolver 的职责：
    1. 判断每个引号候选是不是真对白 / 心理活动 / 强调词或书名
    2. 对真对白 / 心理活动段，识别 speaker

    契约：
    - 输入：segment_builder 切出来的 segment 列表，所有引号候选
      的 speaker 都是 "unknown"，segment_type 是 "dialogue"（候选）。
      narration 段（引号外内容）speaker="narrator"，segment_type="narration"。
    - 输出：处理后的 segment 列表，segment_type 和 speaker 已填好。
    - **允许 N → M（M ≤ N）**：被判定为非对白（quoted_term / title_or_name）
      的引号候选会并回相邻的 narration 段（与原 quote_classifier 行为一致）。
    - segment_id 可以重新分配（并回后总数变少），但 raw_index 必须保留
      原值，方便下游 character_analyzer 按段落重组上下文。
    """
```

### 3.2 segment_type 枚举（与现有 `Segment` 定义一致）

| 取值 | 含义 | speaker 应该填什么 |
|---|---|---|
| `narration` | 旁白叙述 / 非对白引号并回 | `"narrator"` |
| `dialogue` | 真实角色说出的对白 | 角色名（从 CharacterProfile.name 或 aliases 匹配） |
| `inner_thought` | 心理活动（心想 / 暗想） | 该角色名 |

### 3.3 5 类 → 3 类的归并规则

原 quote_classifier 输出 5 类，新 Agent 内部判断时也按 5 类思考，但输出 segment_type 时归并：

| 原 5 类 | 新 segment_type | 处理 |
|---|---|---|
| `dialogue` | `dialogue` | 保留为独立 segment，填 speaker |
| `inner_thought` | `inner_thought` | 保留为独立 segment，填 speaker |
| `quoted_term` | （并回 narration） | 与相邻 narration 合并，speaker=narrator |
| `title_or_name` | （并回 narration） | 同上 |
| `unknown` | （并回 narration） | 同上（保守 fallback） |

### 3.4 speaker 解析规则

- 角色名必须从 `character_profiles` 中找：先匹配 `name`，再匹配 `aliases`。
- 找不到匹配 → speaker fallback 为 `"narrator"`（与原 story_resolver 行为一致）。
- `narration` 段的 speaker 永远是 `"narrator"`，不要让 LLM 改。

---

## 4. Prompt 设计要求

### 4.1 必须包含的要素

1. **任务说明**：判断每个引号候选的语义类型 + 说话人。
2. **5 类定义**：清晰列出 dialogue / inner_thought / quoted_term / title_or_name / unknown 的判定依据（可参考原 quote_classifier 的 prompt）。
3. **角色列表**：把 `character_profiles` 的 `name` + `aliases` 列出来，让 LLM 知道有哪些候选 speaker。
4. **上下文**：把同一 raw_index 的 segment 按顺序拼回近似段落原文作为上下文（与原 story_resolver 的策略一致）。
5. **输出 JSON 格式**：严格 schema，segment_id / quote_type / speaker / reason / confidence。

### 4.2 推荐输出 schema

```json
{
  "resolutions": [
    {
      "segment_id": "seg_003",
      "quote_type": "dialogue",
      "speaker": "小明",
      "reason": "小明对妈妈说话",
      "confidence": 0.92
    },
    {
      "segment_id": "seg_005",
      "quote_type": "title_or_name",
      "speaker": "narrator",
      "reason": "《西游记》是书名",
      "confidence": 0.95
    }
  ]
}
```

### 4.3 Prompt 应对边界 case

参考第 5 节黄金集，prompt 必须能处理：
- 段内多个角色对话（同一 raw_index 多个 dialogue segment）
- 心理活动 vs 旁白（"他想" / "暗想" 等触发词）
- 称呼代词（"他" / "她"）需要根据上下文消解到具体角色

---

## 5. 单元测试黄金集（PR 必须含）

新建 `src_next/analysis/tests/test_segment_resolver.py`，至少覆盖以下 case：

| # | case 描述 | 输入片段示例 | 期望输出 |
|---|---|---|---|
| 1 | 简单对白 | `小明说："你好啊。"` | segment_type=dialogue, speaker=小明 |
| 2 | 心理活动 | `小红心想："今天真奇怪。"` | segment_type=inner_thought, speaker=小红 |
| 3 | 书名（非对白） | `他正在读《西游记》。` | 引号并回 narration，speaker=narrator |
| 4 | 强调词（非对白） | `这就是所谓的"奇迹"。` | 引号并回 narration |
| 5 | 段内多角色对话 | `小明说："你好。"小红说："你也好。"` | 两个 dialogue segment，speaker 分别填好 |
| 6 | 称呼代词消解 | `小明走过来。他说："我饿了。"` | speaker=小明（不是"他"） |
| 7 | 角色别名匹配 | `alias="老李"，name="李大爷"`；文本 `老李说："走。"` | speaker=李大爷（canonical name） |
| 8 | 无引号段（纯旁白） | `天空很蓝。` | segment_type=narration, speaker=narrator（不变） |
| 9 | 嵌套引号或破折号引语 | `"我——"他说，"算了。"` | 拆为 2 个 dialogue segment，speaker 都是同一角色 |
| 10 | LLM 找不到匹配角色 | `"..."` 内容含未在 character_profiles 中的称呼 | speaker fallback 为 narrator |
| 11 | LLM 返回非法 JSON | mock LLM 返回 `"not json"` | 不抛异常，整体 fallback：所有 candidate 按规则并回 narration |
| 12 | LLM 漏掉某些 segment_id | mock LLM 只返回部分 segment 的判定 | 漏掉的 candidate fallback 为 narration |

### 测试实现要求

测试分两类，**都要写**：

#### A. 功能测试（case 1-10）：**真实调 LLM**

这是验收的核心。mock 验证不了 prompt 设计得好不好——你的主要产出就是 prompt，必须用真 LLM 跑通才知道 prompt 工作不工作。

实现要点：

1. **LLM 客户端获取**：通过 profile yaml 加载，不要硬编码地址：
   ```python
   # tests/conftest.py
   import os
   import pytest
   from src_next.utils.yaml_utils import load_profile
   from src_next.llm.registry import create_llm_client

   @pytest.fixture(scope="session")
   def real_llm():
       profile_path = os.environ.get("TEST_LLM_PROFILE",
           "src_next/profiles/yellow_gemma_qwen_s2pro.yaml")
       profile = load_profile(profile_path)
       return create_llm_client(profile["llm"]["backend"], **profile["llm"])
   ```
   黄区用 `yellow_gemma_qwen_s2pro.yaml`（Gemma4 HTTP），蓝区可以指定其他 profile。

2. **标记为 integration 测试**：`@pytest.mark.integration`，CI 默认跑 fast 模式时可跳过：
   ```bash
   # 快速回归（CI 用）
   pytest src_next/analysis/tests/test_segment_resolver.py -m "not integration"

   # 验收前完整跑（PR 合并前必跑）
   pytest src_next/analysis/tests/test_segment_resolver.py -m "integration"
   ```

3. **断言要容忍 LLM 非确定性**：LLM 输出有随机性，不能写死 `assert result.speaker == "小明"`。两种写法：
   - **枚举集合断言**（推荐）：`assert result.speaker in {"小明", "小红"}`（明确是这两人之一即可）
   - **多次运行取众数**：同一 case 跑 3 次，至少 2 次一致才算通过（应对偶尔跑偏）

4. **必跑 case**：1-10 必须全部用真 LLM 跑过且通过，这是 PR 合并的硬条件。

#### B. Robustness 测试（case 11-12）：**mock LLM**

这两个 case 是验证"LLM 出问题时不让 pipeline 崩"，**必须用 mock**：
- 真实 LLM 不会稳定复现"返回非法 JSON"或"漏字段"的场景，没法测。
- mock `BaseLLMClient.generate_json()` 让它返回非法 JSON / 缺字段的 dict，验证 `resolve_segments` 的 fallback 路径。

#### 参考实现

```python
# src_next/analysis/tests/test_segment_resolver.py

import pytest
from src_next.analysis.segment_resolver import resolve_segments
from src_next.core.data_models import Segment, CharacterProfile

# ── A. 功能测试（真 LLM）──────────────────────────────────────

@pytest.mark.integration
def test_case_01_simple_dialogue(real_llm):
    """case 1: 简单对白，明确 attribution。"""
    segments = [Segment(segment_id="seg_001", text="小明说：“你好啊。”",
                        speaker="unknown", segment_type="dialogue", raw_index=0)]
    characters = [CharacterProfile(name="小明", role_type="character")]
    result = resolve_segments(segments, characters, real_llm)
    assert any(s.segment_type == "dialogue" and s.speaker == "小明" for s in result)


@pytest.mark.integration
def test_case_03_book_title_not_dialogue(real_llm):
    """case 3: 书名应被识别为非对白并并回 narration。"""
    segments = [
        Segment(segment_id="seg_001", text="他正在读", speaker="narrator",
                segment_type="narration", raw_index=0),
        Segment(segment_id="seg_002", text="西游记", speaker="unknown",
                segment_type="dialogue", raw_index=0),
        Segment(segment_id="seg_003", text="。", speaker="narrator",
                segment_type="narration", raw_index=0),
    ]
    result = resolve_segments(segments, [], real_llm)
    # 西游记 应被并回 narration，不再以独立 dialogue 出现
    assert all(not (s.text == "西游记" and s.segment_type == "dialogue") for s in result)


# ── B. Robustness 测试（mock LLM）─────────────────────────────

class _MockBadLLM:
    """模拟 LLM 返回非 JSON 字符串。"""
    def generate_json(self, system, user):
        return "this is not json"

def test_case_11_llm_returns_invalid_json():
    """case 11: LLM 返回非 JSON，resolve_segments 不抛异常并 fallback。"""
    segments = [Segment(segment_id="seg_001", text="你好", speaker="unknown",
                        segment_type="dialogue", raw_index=0)]
    result = resolve_segments(segments, [], _MockBadLLM())
    # 不崩 + 引号并回 narration
    assert len(result) >= 1
    assert all(s.speaker == "narrator" for s in result)
```

#### LLM 选择的注意事项

- **黄区默认用 Gemma4 HTTP**（`yellow_gemma_qwen_s2pro.yaml`），速度快、稳定。
- 蓝区如果用 Qwen3，profile 改成对应的蓝区 yaml。
- **不要在测试里硬编码 `http://10.50.121.123:8000`** 这种地址，必须走 profile，方便后续切换 LLM 时只改 yaml 不改测试代码。

---

## 6. PR 验收标准（每条都需满足）

- [ ] **只新增 3 个文件**：`segment_resolver.py` + `prompts/segment_resolver_prompt.py` + `tests/test_segment_resolver.py`（可加 `conftest.py`），没有改动禁区文件。
- [ ] **`resolve_segments` 函数签名**与第 3.1 节完全一致（参数名、类型、返回类型）。
- [ ] **segment_type 取值**严格在 {`narration`, `dialogue`, `inner_thought`} 三者之内。
- [ ] **narration 段的 speaker** 永远是 `"narrator"`。
- [ ] **N → M 并回**逻辑正确：quoted_term / title_or_name / unknown 类型的引号被并回相邻 narration。
- [ ] **raw_index 保留**：并回后的 segment 保留原 raw_index 值。
- [ ] **功能测试 case 1-10 通过（真实 LLM）**：`pytest -m integration` 全绿。这是 PR 合并的硬条件，**不是可选**。
- [ ] **Robustness case 11、12 通过（mock LLM）**：LLM 失败时不抛异常。
- [ ] **py_compile + 全部测试**：`pytest src_next/analysis/tests/test_segment_resolver.py`（含 integration + mock）通过。
- [ ] **不引入新依赖**：只用项目已有的 `BaseLLMClient` 抽象。
- [ ] **PR 描述附 1 条真实样例**：贴一段输入文本 + LLM 实际返回的 JSON + 最终 segment 列表，让 reviewer 看到端到端效果。

---

## 7. 你完成后会发生什么（集成阶段）

阶段二（约 1 周后，主开发执行）会做这些事，你**不需要做**：

1. 在 `audiobook_pipeline.py` 的 Stage 3 位置加开关：
   ```python
   if self.config.pipeline.get("use_agent_resolver", False):
       segments = resolve_segments(segments, characters, llm_client)  # 你的函数
   else:
       segments = classify_and_merge_quotes(segments, llm_client)     # 老链路
       segments = resolve_speakers(segments, llm_client)
   ```
2. 删除 `quote_classifier.py` / `story_resolver.py`（如果方向2 稳定后决定下线老链路）。
3. 端到端验证你的 Agent 输出和老链路一致或更优。

只要你的接口契约对、测试过，集成阶段几乎不会让你返工。

---

## 8. 参考文件

| 文件 | 看什么 |
|---|---|
| `src_next/analysis/quote_classifier.py` | 5 类分类的判定依据、prompt 写法 |
| `src_next/analysis/story_resolver.py` | 段落上下文重组策略、speaker fallback 逻辑 |
| `src_next/core/segment_builder.py` | 上游输入格式（特别是 raw_index 的语义） |
| `src_next/core/data_models.py` 的 `Segment` / `CharacterProfile` | 数据字段定义 |
| `src_next/llm/base.py` 的 `BaseLLMClient` | LLM 抽象接口（`generate_json` 方法） |

---

## 9. 常见陷阱

1. **不要在 prompt 里把全文都丢给 LLM**：按 raw_index 分组，每次只处理一个段落组（与原 story_resolver 一致），否则上下文太长 LLM 会漏判。
2. **不要让 LLM 自己造角色名**：必须从 character_profiles 列表里选，prompt 要明确"speaker 必须是以下列表之一或 narrator"。
3. **不要返回 segment_id 之外的字段当主键**：用 segment_id 对齐输入输出，不要用 text 或 raw_index 做对齐。
4. **不要在 resolve_segments 里发 HTTP 请求**：只通过 `llm_client` 抽象，不发直接 HTTP（避免黄区代理 / 端口耦合）。
5. **并回时不要丢文本**：quoted_term / title_or_name 并回 narration 时，原引号字符（"《》"或 `""`）要保留在 narration 文本里，与原 quote_classifier 行为一致。

---

## 10. 完成定义（Definition of Done）

- 3 个文件提交到 `feature/segment-resolver` 分支。
- PR 描述包含：测试输出截图、黄金集覆盖说明、与老链路的输出对比（同一段输入分别跑老 / 新，结果差异）。
- 主开发 review 通过 + CI 单测全绿。
- 阶段二集成后端到端跑通一次（这一步由主开发执行，不阻塞你的 PR merge）。
