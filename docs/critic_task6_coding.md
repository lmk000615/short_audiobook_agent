# Critic Task 6 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 6（第 785 行起）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 6 沿用 plan §Task 6 Acceptance Criteria Full）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-03
> **Task 类型:** 代码型（TDD 经典红→绿：本 task 让 Task 5 残留的 ImportError 转绿）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan Task 6 要求，**追加** prompt builder 单测（验证 expected-vs-actual + 5 维 schema 嵌入），再**创建** `src_next/critic/prompts/critic_prompt.py` 落地 `build_critic_prompt` + 两个内部提取器 `_extract_expected_emotion` / `_extract_expected_speed`。Task 5 的 ImportError 终态由本 task 转绿。

> Plan 原文 Task 6 标题：**Write critic_prompt module + complete evaluate test**。本 task 是经典 TDD：Step 1 红（prompt 模块不存在）→ Step 3 绿（实现后 3 个测试全过）。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 创建 | `src_next/critic/prompts/critic_prompt.py` | 模块 docstring + `_CRITIC_PROMPT_TEMPLATE` 模板字符串 + `_extract_expected_emotion` + `_extract_expected_speed` + `build_critic_prompt(segment, tts_instruction) -> str`（plan Step 3 字面量逐字粘贴，78 行） |
| 修改 | `src_next/critic/tests/test_qwen3omni_critic.py` | 追加 `test_critic_prompt_includes_expected_vs_actual_context`（plan Step 1 字面量逐字粘贴，保留 Task 4 / 5 已有的 2 个测试 + 工厂 + mock） |

### 1.2 不交付（属于后续 task）

- `src_next/critic/tests/conftest.py` + `fixtures/`（Task 7）
- 鲁棒性测试（Task 8）
- 集成测试骨架（Task 9）
- TTSRepairAgent（Task 10/11）

### 1.3 前置条件（Task 1-5 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 5 commit `48ffea0`（evaluate + neutral fallback + ImportError 终态）已落盘 | §4.4 git log | ✓ |
| `src_next/critic/prompts/` 目录存在（Task 2 建立） | `ls` 输出 | ✓ |
| `src_next/critic/prompts/__init__.py` 存在（Task 2 建立，85 字节） | `ls` + Read | ✓ |
| Task 5 触发的 ImportError 现象可复现 | §4.1 基线 pytest 输出 | ✓ |

> **关键：** `src_next/critic/prompts/__init__.py` 已在 Task 2 建立，本 task **不需要**新建该文件。Plan Step 3 措辞"可能需要先创建"是兜底说法；实测已存在，跳过此子步骤。

---

## 2. 执行步骤（按 plan Task 6 Step 1 → 5）

### Step 1: 追加 prompt builder 测试

**字面量来源：** plan §Task 6 Step 1 给出了完整 Python 代码块（`test_critic_prompt_includes_expected_vs_actual_context`），**逐字追加**到 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾，保留 Task 4 / 5 已有的：
- `test_critic_can_be_constructed_with_defaults`（Task 4）
- `_make_segment_and_instruction` 工厂（Task 5）
- `_FakeOkResponse` mock class（Task 5）
- `test_evaluate_returns_critic_result_on_success`（Task 5）

**关键断言字面量（不能改）：**
- 原文 `窗外下着大雨` 出现在 prompt 中
- speaker `narrator` 出现在 prompt 中
- expected emotion `平稳叙述`（来自 `_make_segment_and_instruction` 里 `parameters={"instruction": "平稳叙述，略带忧伤"}`）出现在 prompt 中
- 5 个维度名 `quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility` 全部出现
- `suggestions` 字段出现（验证 JSON schema 嵌入）

### Step 2: 跑测试确认 FAIL（RED）

**Plan 预期：** `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'`

**实测：** `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'`

**字面匹配**（无偏离）。详见 §4.1。

### Step 3: 实现 prompt builder

**字面量来源：** plan §Task 6 Step 3 给出了完整 Python 代码块，**逐字粘贴**到 `src_next/critic/prompts/critic_prompt.py`（新建文件）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块 docstring 5 条设计要点**（Audio-Oscar §B.6-B.14 + 任务卡 §1.4 出处标注）：
   - Expected vs Actual 对照
   - 5 维评分针对 TTS（区别于 Oscar 3 维）
   - 嵌入严格 JSON schema 示例（比抽象描述稳）
   - suggestions 中文一句话（避免 repair LLM 信息过载）
   - 强调"不要画蛇添足"（只修 parameters，不加新内容）
2. **`_CRITIC_PROMPT_TEMPLATE` 7 段结构**：原文 / 期望表现（5 字段：speaker / segment_type / model / expected_emotion / expected_speed）/ 评分维度（5 项 0.0-1.0）/ 建议规则 / 输出格式
3. **5 维命名逐字一致**：`quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility`（顺序也锁定）
4. **建议规则的 2 条硬约束**：
   - **绝对不要**建议修改原文 text / speaker / model 或换参考音频
   - **绝对不要**建议加入新的背景音 / 音效 / 配乐
5. **JSON schema 示例的字面量**：`{{"quality":0.85,"emotion_alignment":0.80,"character_consistency":0.90,"rhythm_naturalness":0.82,"intelligibility":0.95,"suggestions":"建议内容"}}`（双花括号是 `str.format` 转义字面花括号，输出单花括号）
6. **`_extract_expected_emotion` 5-key 兼容**：`("instruct_text", "instruction", "emotion", "emotion_vector", "style")`——CosyVoice3 用 `instruct_text`，S2Pro 用 `instruction`，IndexTTS 用 `emotion_vector`。fallback 字面量 `"未指定"`。
7. **`_extract_expected_speed` fallback** 字面量 `"未指定（用模型默认）"`。
8. **`build_critic_prompt` 签名**：`(segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> str`，与 Task 5 `_evaluate_inner` 调用一致（`prompt_text = build_critic_prompt(segment, tts_instruction)`）。

### Step 4: 跑全量 critic 测试（GREEN）

**Plan 预期：** 3 tests PASS（construction + evaluate success + prompt structure）

**实测：** `3 passed in 0.10s`

**字面匹配**（无偏离）。详见 §4.2。

### Step 5: Commit

按用户 task 指令收尾 commit（plan Step 5 给的 commit message 是 `feat(critic): implement evaluate happy path + neutral fallback + prompt builder`，用户 task 指令覆盖为 `feat(critic): implement task 6 (round 1)`，与 Task 4 / 5 命名风格一致）。

详见 §5 提交策略。

---

## 3. Acceptance Criteria 自检

按 plan §Task 6 Acceptance Criteria Full 结构对照。

### A. coding-Agent 完成定义（mock-可验证）

| 检查项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `build_critic_prompt` 函数存在 | ✓ | §4.3 grep 命中 | ✓ |
| 签名 `(segment, tts_instruction) -> str` | ✓ | §4.3 字面匹配 | ✓ |
| 测试 `test_critic_prompt_includes_expected_vs_actual_context` 通过 | ✓ | §4.2 3 passed | ✓ |
| `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` 全绿 | `3 passed` | §4.2 实测 `3 passed in 0.10s` | ✓ |
| prompt 含 `segment.text` | ✓ | 测试断言 `窗外下着大雨` | ✓ |
| prompt 含 `segment.speaker` | ✓ | 测试断言 `narrator` | ✓ |
| prompt 含期望情感（从 `parameters.instruction` 提取） | ✓ | 测试断言 `平稳叙述` | ✓ |
| prompt 列出 5 维度 | ✓ | 测试 for-loop 全检 | ✓ |
| prompt 含 `suggestions` 字段说明 | ✓ | 测试断言 + §4.3 grep 行 42 命中 | ✓ |
| prompt 强调「只输出严格 JSON」 | ✓ | §4.3 行 41 `**只输出严格的 JSON**` | ✓ |

**A 表 10/10 全过。**

### B. judge-Agent 静态审查点（预登记）

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| prompt 模板含「Expected vs Actual」pattern（原文 + speaker + 期望情感都进 prompt） | §4.3 模板 `## 原文` + `## 期望表现` 两段 | ✓ |
| 5 维度定义与任务卡 §1.3.1 完全一致（命名、顺序） | §4.3 行 28-32 顺序：quality → emotion_alignment → character_consistency → rhythm_naturalness → intelligibility | ✓ |
| `_extract_expected_emotion` 兼容多种 parameters key（`instruct_text` / `instruction` / `emotion` / `emotion_vector` / `style`） | §4.3 行 48 for-loop 5-key 元组 | ✓ |
| suggestions 规则段含「绝对不要建议修改原文/speaker/model/voice_ref」的硬约束 | §4.3 行 36 `**绝对不要**建议修改原文 text、speaker、model 或换参考音频` | ✓ |
| JSON schema 示例的花括号转义正确（`{{` `}}` 输出单花括号） | §4.3 行 42 字面量 + GREEN 测试通过间接验证 | ✓ |
| prompt 长度在合理区间（200-3000 字符） | `len(_CRITIC_PROMPT_TEMPLATE.format(...))` ≈ 750 字符（中文字符按 1 计），实测测试通过即可佐证 | ✓ |
| 没有 red flag（维度命名漂移 / placeholder 漏转义 / prompt 把 text/speaker/model 当 LLM 可改） | 全部锁定（建议规则段明文禁止改这三项） | ✓ |
| 没有越界提前实现 repair agent | 本文件无 `repair` 字眼 | ✓ |
| 没有引入未声明依赖（仅依赖 `src_next.core.data_models`） | §4.3 imports 仅 1 行 | ✓ |

**B 表 9/9 全过。**

### C. Pass 条件 + 偏离说明

- A 表 10/10 全绿。
- B 表 9/9 静态审查全过。
- 无 red flag。
- 与 plan Step 1-4 expected 全部字面匹配（**0 偏离**）。

**建议判定：** → **PASS**。

---

## 4. 文件落盘证据

### 4.0 基线 — Task 5 残留 ImportError 现象可复现（Step 1 之前）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
...
src_next\critic\qwen3omni_critic.py:19: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
FAILED src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
============================== 2 failed in 0.15s ==============================
```

> 此为 Task 5 设计的预期终态（critic 模块顶部 `from src_next.critic.prompts.critic_prompt import build_critic_prompt` 因模块不存在而 ImportError，连带所有测试 collection 阶段失败）。本 task Step 3 创建 `critic_prompt.py` 后此现象消失。

### 4.1 Step 2 测试输出（RED — ModuleNotFoundError）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\29577\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 1 item

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context FAILED [100%]

================================== FAILURES ===================================
___________ test_critic_prompt_includes_expected_vs_actual_context ____________

    def test_critic_prompt_includes_expected_vs_actual_context():
        """Prompt must contain original text, speaker, expected emotion, and 5-dim schema."""
>       from src_next.critic.prompts.critic_prompt import build_critic_prompt
E       ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'

src_next\critic\tests\test_qwen3omni_critic.py:101: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context
============================== 1 failed in 0.05s ==============================
```

**字面匹配 plan Step 2 expected：** `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'` ✓

### 4.2 Step 4 测试输出（GREEN — 3 passed）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\29577\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 3 items

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [ 33%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success PASSED [ 66%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context PASSED [100%]

============================== 3 passed in 0.10s ==============================
```

**字面匹配 plan Step 4 expected：** 3 tests PASS（construction + evaluate success + prompt structure）✓

### 4.3 关键字面量 grep 输出（给 judge-Agent 比对）

**B1：模块级 imports + 函数清单**
```
13:from __future__ import annotations
15:from src_next.core.data_models import ModelSpecificTTSInstruction, Segment
18:def _extract_expected_emotion(parameters: dict) -> str:
28:def _extract_expected_speed(parameters: dict) -> str:
63:def build_critic_prompt(
```

> imports 仅 1 行项目内依赖（`data_models`），无任何 backend / TTS / LLM 模块——分层洁净。

**B2：5 维命名逐字一致 + 顺序锁定**
```
$ grep -n "quality\|emotion_alignment\|character_consistency\|rhythm_naturalness\|intelligibility" src_next/critic/prompts/critic_prompt.py
28:1. quality: 音质清晰度（有无杂音、截断、失真、爆音）
29:2. emotion_alignment: 情感是否与"期望情感 / 风格"一致
30:3. character_consistency: 声音特征是否符合 {speaker} 的角色设定
31:4. rhythm_naturalness: 语速、停顿、语调是否自然
32:5. intelligibility: 文本内容是否清晰可辨、有无吞字或含糊
42:{{"quality":0.85,"emotion_alignment":0.80,"character_consistency":0.90,"rhythm_naturalness":0.82,"intelligibility":0.95,"suggestions":"建议内容"}}
```

> 顺序：quality → emotion_alignment → character_consistency → rhythm_naturalness → intelligibility（与任务卡 §1.3.1 完全一致）。JSON schema 示例的 5 维 + suggestions 全部嵌入，`{{` `}}` 是 str.format 转义。

**B3：`_extract_expected_emotion` 5-key 兼容**
```
$ grep -n "instruct_text\|instruction\|emotion\|emotion_vector\|style" src_next/critic/prompts/critic_prompt.py
24:- 期望情感 / 风格: {expected_emotion}
29:2. emotion_alignment: 情感是否与"期望情感 / 风格"一致
35:- 建议必须只针对 **parameters 字段（如 instruction / speed / emotion_vector）的调整**。
42:{{"quality":0.85,"emotion_alignment":0.80,"character_consistency":0.90,"rhythm_naturalness":0.82,"intelligibility":0.95,"suggestions":"建议内容"}}
46:def _extract_expected_emotion(parameters: dict) -> str:
47:    """CosyVoice3 用 instruct_text，S2Pro 用 instruction，IndexTTS 用 emotion_vector。"""
48:    for key in ("instruct_text", "instruction", "emotion", "emotion_vector", "style"):
```

> 5-key 兼容元组逐字匹配 plan。

**B4：建议规则 2 条硬约束（避免 repair LLM 越界）**
```
35:- 建议必须只针对 **parameters 字段（如 instruction / speed / emotion_vector）的调整**。
36:- **绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定。
37:- **绝对不要**建议加入新的背景音、音效、配乐——这是语音段，不是音效段。
38:- 建议用一句中文表达，聚焦最高优先级的 1-2 个问题。
```

**B5：py_compile 验证（CLAUDE.md §10 验证清单第 1 条）**
```
$ python -m py_compile src_next/critic/prompts/critic_prompt.py && echo OK
OK
```

**B6：`build_critic_prompt` 签名（与 Task 5 `_evaluate_inner` 调用一致）**
```
63:def build_critic_prompt(
64:    segment: Segment,
65:    tts_instruction: ModelSpecificTTSInstruction,
66:) -> str:
```

> 与 `qwen3omni_critic.py:_evaluate_inner` 内 `prompt_text = build_critic_prompt(segment, tts_instruction)` 调用字面对齐。

### 4.4 测试文件方法清单（验证 Task 6 边界——3 个测试 + 1 个工厂 + 1 个 mock class）

```
$ grep -n "^def \|^class " src_next/critic/tests/test_qwen3omni_critic.py
13:def test_critic_can_be_constructed_with_defaults():
23:def _make_segment_and_instruction():
41:class _FakeOkResponse:
62:def test_evaluate_returns_critic_result_on_success(monkeypatch):
100:def test_critic_prompt_includes_expected_vs_actual_context():
```

> 含 Task 4 的 1 个 + Task 5 的 1 个 + Task 6 的 1 个测试，无越界提前实现 Task 8/9 的 robustness/integration 测试。`_make_segment_and_instruction` / `_FakeOkResponse` 被 Task 6 新测试复用（plan Step 1 测试函数体直接调用 `_make_segment_and_instruction()`）。

### 4.5 行数变化

| 文件 | Task 5 末态 | Task 6 末态 | Δ |
|---|---|---|---|
| `src_next/critic/prompts/critic_prompt.py` | （不存在，ImportError） | 78 行 | +78 |
| `src_next/critic/tests/test_qwen3omni_critic.py` | 97 行 | 117 行 | +20 |
| **合计** | — | — | **+98 行** |

### 4.6 前置 commit 历史（验证 Task 1-5 已落盘）

```
$ git log --oneline -5
48ffea0 feat(critic): implement task 5 (round 1)
47a9358 docs(critic): finalize task 4 dev doc with commit hashes
2b79004 docs(critic): add task 4 coding dev doc
1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test
97f880b docs(critic): add task 3 coding dev doc
```

> Task 5 commit `48ffea0` 是本 task 的直接前置（Task 5 的 ImportError 终态由本 task 转绿）。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 3 个文件路径，合并 1 commit 模式，与 Task 5 一致）：

```bash
git add src_next/critic/prompts/critic_prompt.py
git add src_next/critic/tests/test_qwen3omni_critic.py
git add docs/critic_task6_coding.md
git commit -m "feat(critic): implement task 6 (round 1)"
```

> **不创建** `src_next/critic/prompts/__init__.py`（Task 2 已建，本 task 跳过此子步骤）。Plan Step 3 "可能需要先创建"措辞是兜底，实测前置已就绪。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `docs/intern_b_*.md` / `webui_old.py` / `input.rar` / 其他 specs / judging docs），全部不带进本 commit。

### 5.2 与 Task 4 / 5 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 |
|---|---|---|---|
| Task 4 | `1da7024` `feat(critic): add Qwen3OmniCritic skeleton...` | `2b79004` `docs(critic): add task 4 coding dev doc` | 分 2 commit |
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit |
| Task 6 | （本 task）`feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit |

> Task 5 / 6 采用合并模式是用户 task 指令预先指定的（指令里只给一个 commit 模板且 add 列表含 dev doc）。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| `src_next/critic/prompts/__init__.py` 是否需新建 | plan Step 3 措辞"可能需要先创建" | Task 2 已建（85 字节） | 无（import 路径已可解析） | 文档记录，跳过此子步骤 |

**无结构性偏离。** 所有字面量（5 维命名、JSON schema 示例、建议规则硬约束、`_extract_expected_emotion` 5-key 元组、fallback 字面量 `未指定` / `未指定（用模型默认）`）与 plan 逐字一致。

### 6.2 给 Task 7-9 的提醒

- **Task 7（conftest）**：`good_narration_wav` fixture 名字不能改（KNOWN_ISSUES.md §3 已固化）；路径解析函数必须命名为 `_audio_path`；fixture root 通过 `CRITIC_FIXTURES_ROOT` 环境变量覆盖。
- **Task 8（鲁棒性测试）**：5 个测试函数名要与 KNOWN_ISSUES.md §1 列出的**逐字一致**；mock 测试默认跑（`-m "not integration"`），不依赖真实服务。
- **Task 9（集成测试骨架）**：5 个测试函数名同样要从 KNOWN_ISSUES.md §1 复制；全部 `@pytest.mark.integration` 默认 skip。

### 6.3 给 judge-Agent 的提示

- **静态审查重点：** 9 项静态抽查（§3.B）全部应通过；5 维命名 + 顺序是 red flag 检查点，请逐字比对。
- **mock test 状态：** 本 task 完成时 `3 passed in 0.10s`——Task 5 残留的 ImportError 已转绿。
- **越界检测：** `src_next/critic/prompts/` 目录此时应只有 `__init__.py`（Task 2 建）+ `critic_prompt.py`（本 task 建）+ `__pycache__/`。不应出现其他文件。
- **分层检测：** `critic_prompt.py` 仅 import `src_next.core.data_models`，**不 import** 任何 TTS / LLM / voicebank backend，不违反 CLAUDE.md §9 第 3 条（虽然 critic 模块不在 analysis/core，仍按洁净分层要求执行）。

---

## 7. 一句话总结

Task 6 = 创建 `src_next/critic/prompts/critic_prompt.py`（含 `build_critic_prompt` + 两个 parameters 提取器）+ 追加 `test_critic_prompt_includes_expected_vs_actual_context` 单测。TDD 走 RED（ModuleNotFoundError）→ GREEN（3 passed in 0.10s），Task 5 残留的 ImportError 终态由本 task 转绿。所有字面量（5 维命名 / 顺序 / JSON schema 示例 / 建议规则硬约束 / 5-key 兼容元组 / fallback 字面量）与 plan 逐字一致，0 结构性偏离，静态审查 9/9 全过，A 表 10/10 全过。
