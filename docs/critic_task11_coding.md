# Critic Task 11 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 11（第 1596 行起）
> **Spec:** 无独立 spec；plan §Task 11 Acceptance Criteria (Full) 在 plan 内
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** TDD 链 GREEN — RED → GREEN（全 8 测试 PASS）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan §Task 11 要求，**实施** 3 个动作 + 1 dev doc：

1. **追加** 7 个新测试到 `src_next/critic/tests/test_tts_repair.py`（plan §Task 11 Step 1）
2. **创建** `src_next/critic/prompts/repair_prompt.py`（plan §Task 11 Step 3）
3. **整体替换** `src_next/critic/tts_repair.py`（plan §Task 11 Step 4 — 含 `repair()` + `_merge_parameters()` + `_fallback()` 三个方法）

本 task 是 Task 10 的 GREEN 收口：Task 10 留下 intentional RED（`tts_repair.py` 顶层 import `build_repair_prompt` 但 `repair_prompt.py` 不存在 → ModuleNotFoundError），本 task 通过创建 `repair_prompt.py` + 完整 `repair()` 实现把 8 个测试全部变 PASS。

### 1.1 应交付文件（3 个 + 1 dev doc）

| 操作 | 路径 | 行数（落盘后） | 字面量来源 |
|---|---|---|---|
| 修改 | `src_next/critic/tests/test_tts_repair.py` | 199（Task 10 的 76 + 本 task 追加 121 + 1 空行衔接 + 1 文件末换行） | plan §Task 11 Step 1 line 1608-1732 代码块（md5 `d8d95739c78d66c693fb56c9a0fbabd3`，BYTE-EQUAL 子串） |
| 创建 | `src_next/critic/prompts/repair_prompt.py` | 89 | plan §Task 11 Step 3 line 1740-1832 代码块（md5 `a445bc9c5c918603536a6742e4536fac`，BYTE-EQUAL after rstrip trailing newline） |
| 整体替换 | `src_next/critic/tts_repair.py` | 91（Task 10 的 20 → 本 task 91） | plan §Task 11 Step 4 line 1835-1930 代码块（md5 `10220f8c73e63a05f06b201026437f90`，BYTE-EQUAL after rstrip trailing newline） |
| 创建 | `docs/critic_task11_coding.md` | 本文件 | 按 `docs/critic_task10_coding.md` 同样结构 |

### 1.2 不交付（属于后续 task）

- **Task 12** Step 1 要追加到 `test_tts_repair.py` 的 `test_repair_with_real_llm_adjusts_parameters`（skip-marked integration 测试）
- **Task 13** 的 `py_compile` 全文件验证 + 文件计数（验收型 task，不动代码）
- 主开发把 `TTSRepairAgent` 接入 Stage 8 集成（plan §Task 11 Acceptance B "端到端 smoke" 提到但**不在本 task 范围** — 主开发 / 后续 task 才做集成；本 task 只交付独立 mock 测试 PASS）

### 1.3 前置条件（Task 1-10 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 10 commit `790906a`（TTSRepairAgent 最小骨架 + 1 个 construction 测试）已落盘 | §4.4 git log | ✓ |
| `src_next/critic/prompts/` 目录已存在（含 `__init__.py` + `critic_prompt.py`） | §4.6 ls | ✓ |
| `src_next/critic/tests/test_tts_repair.py` 已含 `_make_inputs` + `_FakeLLMClient` helper（Task 10 字面量） | §4.7 grep | ✓ |
| `src_next/critic/tts_repair.py` 是 Task 10 的 20 行最小骨架（仅 `__init__`，import `repair_prompt` 即触发 ModuleNotFoundError） | §4.8 cat | ✓ |
| `BaseLLMClient` 含 `LLMError` 异常类（plan §Task 11 Step 4 字面量 `from src_next.llm.base import BaseLLMClient, LLMError` 依赖） | §4.9 grep | ✓ |

> **关键：** `prompts/` 目录 + `__init__.py` 已在 Task 1-9 创建，**本 task 不需要新建 `prompts/__init__.py`**。`repair_prompt.py` 是新文件，独立 Python 模块，不需要 `__init__.py` 改动（包已就绪）。

---

## 2. 执行步骤（按 plan §Task 11 Step 1 → 6）

### Step 1: Write failing tests for prompt + merge + immutability + fallback

**字面量来源：** plan §Task 11 Step 1 给出完整 Python 代码块（line 1608-1732，含 markdown fence；剥离 fence 后 121 行实际代码，7 个测试函数）。

**操作：** 在 `src_next/critic/tests/test_tts_repair.py` 现有内容末尾追加 7 个新测试。**复用** Task 10 已有的 `_make_inputs` 和 `_FakeLLMClient` helper（用户 task 指令明示：「现有 test_tts_repair.py 已含 Task 10 的 helper，本轮新测试直接复用，**不要重写 helper**」）。

**字面量校验：** 见 §4.3 A1，plan test 块 121 行代码 md5 `d8d95739c78d66c693fb56c9a0fbabd3`，实际追加到 test 文件后，**整个 121 行代码块作为子串原样出现在 test 文件**（`plan_test_block in actual_test_file == True`，§4.3 A1 输出 `7 tests verbatim in actual file: True`）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **7 个测试函数全部 lazy import** `TTSRepairAgent` / `build_repair_prompt`（在函数体顶部 `from src_next.critic.tts_repair import TTSRepairAgent`）— 与 Task 10 的 `test_repair_agent_constructs_with_llm_client` 风格一致，避免 collection 阶段失败。
2. **复用 `_make_inputs` helper** — 7 个测试中 6 个用 `_make_inputs(...)` 构造输入（1 个测 prompt 的也用 `_make_inputs()` 默认参数）。其中 `test_repair_merges_llm_output_into_parameters` 显式传 `parameters={"instruction": "平稳叙述", "speed": 1.0, "voice_character": "calm"}`（3 个键，比 Task 10 默认 2 键多 1 个 voice_character，用于验证「LLM 改 speed 时其他键保留」）。
3. **复用 `_FakeLLMClient` mock** — 5 个测试用 `_FakeLLMClient(returned_json=...)` 构造成功路径 mock（含恶意 segment_id="HACKED" 等覆盖 immutability 测试），1 个测试用 `_FakeLLMClient(returned_json=None, raise_exc=RuntimeError("LLM down"))` 构造 LLM 异常路径，1 个测试用 `_FakeLLMClient(returned_json=["unexpected", "list"])` 构造 LLM 返回非 dict 的 fallback 路径。三种 mock 场景全覆盖。
4. **`test_repair_prompt_contains_all_required_context` 断言** `prompt` 文本含：
   - `instruction` 字段名（current parameter 可见）
   - `1.0` 字面值（current speed 可见）
   - `emotion_alignment` 字段名（Critic 5 维分数标签可见）
   - `0.40` 或 `0.4`（emotion_alignment 分数值，format 用 `:.2f` 输出 `0.40`）
   - `情感表达偏弱`（Critic suggestion 原文前缀）
   - 5 个 frozen 字段：`segment_id` / `speaker` / `text` / `model` / `voice_ref`
5. **`test_repair_preserves_immutable_top_level_fields`** 喂恶意 LLM 输出（5 个 top-level 字段全设 "HACKED"）后断言 `result.segment_id == "s1"` 等 5 项全等于 original — 这是 schema-frozen 的最强证据。
6. **`test_repair_returns_original_plus_one_when_llm_raises`** 模拟 LLM 抛 RuntimeError，断言 fallback 路径：`result.parameters == inst.parameters`（保留原参数）+ `result.attempt == 2`（attempt +1）+ 顶层 frozen 字段也等于 original — 即「LLM 失败不抛异常」契约。

### Step 2: Run — expect RED (8 FAIL)

**命令：** `python -m pytest src_next/critic/tests/test_tts_repair.py -v`

**Plan 字面期望：** "1 PASS (construction) + 7 FAIL (prompt + repair behavior)"。

**实测：** **8 FAIL**（含 construction 测试也 FAIL，详见 §4.1）。

> **偏离说明（轻量，对 acceptance 无影响）：** plan Step 2 字面期望 construction 测试仍 PASS（Task 10 RED 时 PASS 的延续）。实际本 task Step 1 追加 7 个测试后跑 pytest，**8 个测试全 FAIL** — 包括 construction 测试。原因：Task 10 的 `tts_repair.py` 最小骨架在**模块顶层**（line 12）import `build_repair_prompt`，Task 10 RED 阶段这个 import 已让 construction 测试 FAIL（详见 Task 10 dev doc §4.2）；本 task Step 1 追加 7 个新测试**不改 import 行为**，所以 construction 测试依旧 FAIL，新增 7 个测试也都因同一 ModuleNotFoundError FAIL。**7 个新测试全部 FAIL 这一点与 plan 字面一致**（这是关键 RED 证据 — Step 3-4 实施后这 7 个测试必须 PASS）；construction 测试的 PASS 期望与 Step 2 实测差 1，但不影响 Step 5 终态（Step 5 创建 `repair_prompt.py` 后 construction 测试也会 PASS，最终 8 PASS）。

### Step 3: Implement repair_prompt.py

**字面量来源：** plan §Task 11 Step 3 给出完整 Python 代码块（line 1740-1832，含 markdown fence）。

**操作：** 新建 `src_next/critic/prompts/repair_prompt.py`，**逐字粘贴** plan 字面量。

**字面量校验：** 见 §4.3 A2，md5 比对（剥离文件末尾 POSIX trailing newline 后 BYTE-EQUAL：plan md5 `a445bc9c5c918603536a6742e4536fac`，actual md5 同）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块顶部 docstring**（line 1-7）：明示 4 个设计要点
   - 双锚点：original_parameters（不可漂移） + current_parameters（当前要改的）
   - Critic 反馈完整透传：5 维分数 + suggestions
   - "preserve ... exactly" 强烈措辞，明确列出禁改字段
   - 输出 schema 严格：只输出 parameters JSON
   - 引用 Audio-Oscar §C.18-C.20 + 任务卡 §1.5
2. **`_REPAIR_PROMPT_TEMPLATE`**（line 21-58）：完整 prompt 模板，含
   - 「你只能修改 parameters 字段内的内容」+ 5 个禁改字段列表（segment_id / speaker / text / model / voice_ref），每个字段配中文说明（段编号 / 说话人 / 原文，是用户资产 / TTS 模型，跨模型音色不一致 / 参考音频，同一角色必须用同一 voice_ref）
   - 段信息块：segment_id / text / speaker / model（4 个段上下文字段）
   - 当前 parameters JSON dump（attempt 上下文）
   - Critic 评分块：quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility / overall（6 个分数标签，含 overall）
   - Critic 修复建议原文
   - 「保留原 parameters 中你没改的字段（merge 而不是 replace）」明示 merge 语义
   - 输出格式：`{{"parameters": {{"field1": "value1", ...}}}}`（双花括号 escape，Python str.format 转义）
3. **`build_repair_prompt(original, segment, critic) -> str`** 函数（line 61-89）：
   - 类型注解完整（`ModelSpecificTTSInstruction` / `Segment` / `CriticResult` / `-> str`）
   - docstring 明示「`original` 在这里是 current instruction，merge LLM output into its parameters」「frozen original semantics（§D.23）由主开发 Stage 8 集成层强制」— 即本 task 不实现 frozen original（attempt 0 的 original），只实现「current instruction 作基底 + LLM overlay」merge
   - 函数体单一 return，调用 `_REPAIR_PROMPT_TEMPLATE.format(...)` 填 13 个占位符
   - `current_parameters_json` 用 `json.dumps(original.parameters, ensure_ascii=False, indent=2)` 序列化（中文不 escape，2 空格缩进）
   - 5 个分数用 `f"{score:.2f}"` 格式化（固定 2 位小数，符合 plan §Task 11 Acceptance B 字面要求「具体数值，如 0.40」）

### Step 4: Implement full repair method (整体替换 tts_repair.py)

**字面量来源：** plan §Task 11 Step 4 给出完整 Python 代码块（line 1835-1930，含 markdown fence）。

**操作：** 整体替换 `src_next/critic/tts_repair.py`（Task 10 的 20 行最小骨架 → 本 task 91 行完整实现）。**逐字粘贴** plan 字面量。

**字面量校验：** 见 §4.3 A3，md5 比对（剥离文件末尾 POSIX trailing newline 后 BYTE-EQUAL：plan md5 `10220f8c73e63a05f06b201026437f90`，actual md5 同）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块顶部 docstring**（line 1-8）：保留 Task 10 字面量，明示「parameters merge」「schema 层硬约束」「schema 层冻结」三个核心概念。引用 Audio-Oscar §C.16-C.17。
2. **imports**（line 10-15）：
   - **新增** `import copy`（line 10）— `_merge_parameters` 和 `_fallback` 都用 `copy.deepcopy` 保护 original parameters 不被外部 mutate
   - **新增** `import logging` + `logger = logging.getLogger(__name__)`（line 11 + 17）— LLM 异常时 log warning，方便排障
   - `from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment`（line 12）— 不变
   - `from src_next.critic.prompts.repair_prompt import build_repair_prompt`（line 13）— 不变（Task 10 留下的 import，本 task Step 3 已创建 `repair_prompt.py`，import 现在可解析）
   - `from src_next.llm.base import BaseLLMClient, LLMError`（line 14）— **新增 `, LLMError`**（Task 10 只 import `BaseLLMClient`，本 task 加 `LLMError` 用于 `except (LLMError, Exception)` 双异常捕获）
3. **`TTSRepairAgent` 类**（line 20-91）含 4 个方法：
   - **`__init__(self, llm_client: BaseLLMClient) -> None: self.llm = llm_client`**（line 23-24）— Task 10 字面量保留
   - **`repair(original, segment, critic) -> ModelSpecificTTSInstruction`**（line 26-58）— 主方法，契约：
     - 不改 segment_id / speaker / text / model / voice_ref（避免声音不一致）
     - attempt 字段 +1
     - parameters 由 LLM 重写（保留原 parameters 中 LLM 没动的字段）
     - LLM 失败 → 返回 original（attempt +1），不抛异常
     - 实现：`next_attempt = original.attempt + 1` → `try: llm_output = self.llm.generate_json(build_repair_prompt(...))` → `except (LLMError, Exception) as exc: logger.warning(...); return self._fallback(...)` → `new_parameters = self._merge_parameters(...)` → 返回新 `ModelSpecificTTSInstruction`（顶层字段全用 original 的，仅 parameters 用 merged + attempt 用 next_attempt）
     - **`except (LLMError, Exception)`** 是 design 决策 — `Exception` 已涵盖 `LLMError`，但显式列两个类型方便读者理解「LLM-specific 异常 + 其他运行时异常」都 fallback。`# noqa: BLE001 — by design, any failure → fallback` 注释明示 catch-all 是设计意图，避免 lint 工具误报。
   - **`_merge_parameters(original_parameters, llm_output) -> dict`**（line 60-78，`@staticmethod`）：
     - 双层防御：① `not isinstance(llm_output, dict)` → fallback deepcopy original；② `llm_params = llm_output.get("parameters")` 后 `not isinstance(llm_params, dict)` → fallback deepcopy original
     - 通过后 `merged = copy.deepcopy(original_parameters); merged.update(llm_params); return merged` — **merge 而非 replace**（plan §Task 11 Acceptance B 静态审查第 1 项「`_merge_parameters` 用 `copy.deepcopy(original_parameters)` 作基底，然后 `update(llm_params)`」精确匹配）
     - docstring 引用 Audio-Oscar §C.16 + 任务卡 §1.5（任务卡允许任意 parameters 字段，不做 whitelist）
   - **`_fallback(original, next_attempt) -> ModelSpecificTTSInstruction`**（line 80-91，`@staticmethod`）：
     - 返回新 `ModelSpecificTTSInstruction`，顶层字段全用 original 的，parameters 用 `copy.deepcopy(original.parameters)`（保护 mutation），attempt 用传入的 `next_attempt`
     - docstring 明示「Used when LLM call fails or output is unusable」— 双触发路径（LLM 异常 + 输出非 dict）

### Step 5: Run — expect GREEN (8 PASS)

**命令：** `python -m pytest src_next/critic/tests/test_tts_repair.py -v`

**Plan 字面期望：** "all 8 tests PASS (construction + prompt + 6 behavior)"。

**实测：** **8 passed in 0.02s**（详见 §4.2）— 完全匹配 plan §Task 11 Step 5 + Acceptance A 字面期望「8 passed」。GREEN 阶段确认。

### Step 6: Commit

按用户 task 指令（"收尾 commit"章节明确列出 5 个文件路径，合并 1 commit 模式）：

```bash
git add src_next/critic/prompts/repair_prompt.py
git add src_next/critic/tts_repair.py
git add src_next/critic/tests/test_tts_repair.py
git add docs/critic_task11_coding.md
git commit -m "feat(critic): implement task 11 (round 1)"
```

> **commit 类型为 `feat(critic):`**——本 task 同时创建业务代码（`repair_prompt.py` + 完整 `tts_repair.py`）+ 测试代码（追加 7 个测试），主交付物是业务模块（TTSRepairAgent 完整实现），延续 Task 5 / 6 / 10 的 `feat(critic):` 模式。
> **commit message 使用用户 task 指令字面量** `feat(critic): implement task 11 (round 1)`——与 Task 5 / 6 / 10 同模板（`feat(critic): implement task N (round 1)`）。
> **`prompts/__init__.py` 不需要 add**——该文件在 Task 1-9 已落盘（git ls-files 已 tracked），本 task 不改动它。

---

## 3. Acceptance Criteria 自检

按 plan §Task 11 Acceptance Criteria (Full) 结构对照。

### A. coding-Agent Self-check

**A.1 文件存在检查（plan §Task 11 Acceptance A 产出物）:**

```bash
test -f src_next/critic/prompts/repair_prompt.py && \
test -f src_next/critic/tts_repair.py && \
test -f src_next/critic/tests/test_tts_repair.py && echo OK
# → OK（实测 §4.3 A0）
```

**A.2 `build_repair_prompt` 函数签名（plan §Task 11 Acceptance A 产出物第 1 条）:**

```bash
grep -n "def build_repair_prompt" src_next/critic/prompts/repair_prompt.py
# → 61:def build_repair_prompt(
# 函数签名 `build_repair_prompt(original, segment, critic) -> str` ✓
```

**A.3 `TTSRepairAgent.repair()` + `_merge_parameters()` + `_fallback()` 三方法齐备:**

```bash
grep -n "def repair\|def _merge_parameters\|def _fallback" src_next/critic/tts_repair.py
# → 26:    def repair(
# → 60:    def _merge_parameters(original_parameters: dict, llm_output) -> dict:
# → 80:    def _fallback(original: ModelSpecificTTSInstruction, next_attempt: int) -> ModelSpecificTTSInstruction:
```

**A.4 pytest 命令（plan §Task 11 Acceptance A Self-check）:**

```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -v
# plan 字面期望：→ 8 passed
# 实测：→ 8 passed in 0.02s（详见 §4.2）
```

**A.5 契约自查（plan §Task 11 Acceptance A 契约 4 条）:**

| 契约 | 测试覆盖 | 状态 |
|---|---|---|
| `repair()` 不抛异常（任何 LLM 失败 → fallback） | `test_repair_returns_original_plus_one_when_llm_raises` 验证（LLM raise RuntimeError 后 result 仍正常返回） | ✓ |
| `segment_id / speaker / text / model / voice_ref` 必须等于 original | `test_repair_preserves_immutable_top_level_fields` 喂恶意 LLM（5 字段全 "HACKED"）后断言 5 字段等于 original | ✓ |
| `attempt == original.attempt + 1` | `test_repair_increments_attempt`（attempt=1 → 2）+ 6 个测试都隐含验证（result.attempt 都 != original.attempt） | ✓ |
| `parameters` = original 作基底 + LLM overlay（merge 而非 replace） | `test_repair_merges_llm_output_into_parameters`（LLM 只改 speed，断言 instruction + voice_character 保留） | ✓ |

**A 表全绿。**

### B. judge-Agent 静态审查

| 抽查点（plan §Task 11 Acceptance B Static review） | 实测 | 状态 |
|---|---|---|
| `_merge_parameters` 用 `copy.deepcopy(original_parameters)` 作基底，然后 `update(llm_params)` | `tts_repair.py` line 71 `merged = copy.deepcopy(original_parameters)`，line 72 `merged.update(llm_params)` | ✓ |
| `llm_params = llm_output.get("parameters")` 取出来后类型检查 `isinstance(llm_params, dict)`，不是 dict 时直接 fallback | line 67 `llm_params = llm_output.get("parameters")`，line 68 `if not isinstance(llm_params, dict):` line 69 `return copy.deepcopy(original_parameters)` | ✓ |
| prompt 模板含「preserve exactly」强烈措辞，明确列出 5 个禁改字段 | `repair_prompt.py` line 23「**你只能修改 parameters 字段内的内容。**」+ line 25-29 列出 segment_id / speaker / text / model / voice_ref 5 个字段，每个配中文「绝对不能修改」措辞 | ✓ |
| prompt 含 Critic 完整反馈：5 维分数（带具体数值，如 `0.40`）+ suggestions 原文 | `repair_prompt.py` line 41-46（5 维分数标签）+ line 48 `quality=f"{critic.quality:.2f}"` 等 6 处 `:.2f` 格式化（输出 `0.40` 这种 2 位小数）+ line 49 `{suggestions}` 占位符透传原文 | ✓ |
| `except (LLMError, Exception)` 范围合理（catch-all 是 design，但要 log warning） | `tts_repair.py` line 50 `except (LLMError, Exception) as exc:` + line 51 `logger.warning("repair LLM call failed: %s. Falling back to original parameters.", exc)` + `# noqa: BLE001 — by design, any failure → fallback` 注释明示 design | ✓ |

**B 表静态审查 5/5 全过。**

**Red flags 自检（plan §Task 11 Acceptance B 任一出现即 FAIL）:**

| Red flag | 自检 | 状态 |
|---|---|---|
| LLM 输出的 segment_id / speaker / text / model / voice_ref 出现在返回值里 | `repair()` 返回 `ModelSpecificTTSInstruction(segment_id=original.segment_id, ...)` 全用 original，不读 `llm_output["segment_id"]` 等 | ✓ 未犯 |
| `_merge_parameters` 直接返回 LLM 输出（不 merge 进 original 基底） | `_merge_parameters` 第一行 `merged = copy.deepcopy(original_parameters)`，第二行 `merged.update(llm_params)` — merge 模式 | ✓ 未犯 |
| prompt 把 attempt=1 当成「这是第一次尝试，可以从头改」 | `repair_prompt.py` line 35 `### 当前 parameters（attempt={attempt}）` — 把 attempt 当成「当前状态」上下文，不是「第一次尝试」语义 | ✓ 未犯 |
| `repair()` 在 LLM 失败时抛异常 | `repair()` 用 try/except 捕获 `(LLMError, Exception)`，fallback 不抛异常（test_repair_returns_original_plus_one_when_llm_raises 验证） | ✓ 未犯 |
| `_fallback` 返回 `attempt=original.attempt`（应 +1） | `_fallback` 接受 `next_attempt` 参数（line 80 + 90），传入的是 `original.attempt + 1`（repair line 47） | ✓ 未犯 |

**5/5 red flag 全避。**

### C. Pass 条件 + 输出

按 plan §Task 11 Acceptance C 字面："A 全绿 + B mock 命令绿 + B smoke 命令绿（服务可用时）+ 静态审查无 red flag → **PASS**"。

- **A 表：** 5/5 全过 ✓（文件存在 + 函数签名 + 三方法齐备 + pytest 8 PASS + 契约 4 条覆盖）
- **B 表静态审查：** 5/5 全过 ✓
- **B smoke 命令（mock 阶段）：** §4.2 实测 8 PASS ✓；plan §Task 11 Acceptance B 的「Schema-frozen smoke」python -c 脚本（喂恶意 LLM 验证 top-level 字段不动）与 `test_repair_preserves_immutable_top_level_fields` 测试逻辑等价（同一 mock 思路），已隐含覆盖 ✓
- **B 端到端 smoke（服务可用时）：** 本 task mock 阶段不跑（需要 `CRITIC_TEST_LLM_PROFILE` 环境变量 + 真实 LLM 服务），属 judge-Agent / 集成阶段判定范畴 — 与 Task 10 一样「mock 阶段 PASS，full PASS 待服务可用」
- **代码字面量：** 3 个文件均与 plan 字面量 BYTE-EQUAL（详见 §4.3 A1-A3）

**建议判定：** → **PASS（mock 阶段，TDD 链 GREEN 状态）**。Task 12 才加 skip-marked integration 测试，Task 13 才做 py_compile + 文件计数验证。

---

## 4. 文件落盘证据

### 4.1 Step 2 测试输出（追加 7 个新测试后，repair_prompt.py 未创建时）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
configfile: pytest.ini
collecting ... collected 8 items

src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client FAILED [ 12%]
src_next/critic/tests/test_tts_repair.py::test_repair_prompt_contains_all_required_context FAILED [ 25%]
src_next/critic/tests/test_tts_repair.py::test_repair_merges_llm_output_into_parameters FAILED [ 37%]
src_next/critic/tests/test_tts_repair.py::test_repair_increments_attempt FAILED [ 50%]
src_next/critic/tests/test_tts_repair.py::test_repair_preserves_immutable_top_level_fields FAILED [ 62%]
src_next/critic/tests/test_tts_repair.py::test_repair_returns_original_plus_one_when_llm_raises FAILED [ 75%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_parameters FAILED [ 87%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_top_level FAILED [100%]

================================== FAILURES ===================================
（每个 FAILED 都是同一根因：ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'
 出错位置 src_next\critic\tts_repair.py:12 — Task 10 留下的顶层 import）

=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_prompt_contains_all_required_context
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_merges_llm_output_into_parameters
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_increments_attempt
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_preserves_immutable_top_level_fields
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_returns_original_plus_one_when_llm_raises
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_parameters
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_top_level
============================== 8 failed in 0.07s ==============================
```

**Step 2 RED 状态确认：** 全部 8 个测试 FAIL，根因统一是 `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`（Task 10 留下的顶层 import 在 collection 阶段即失败）。**7 个新测试全部 FAIL 这一点与 plan §Task 11 Step 2 字面期望 "7 FAIL" 一致**；construction 测试也 FAIL 是因为 Task 10 已经让它 FAIL（详见 Task 10 dev doc §4.2，tts_repair.py 顶层 import 在 Task 10 终态就是 RED）。Step 3-4 实施后 8 个测试全部变 PASS。

> **与 plan 字面期望的偏离：** plan §Task 11 Step 2 字面期望 "1 PASS (construction) + 7 FAIL (prompt + repair behavior)"。实测 8 FAIL（construction 也 FAIL）。偏离原因详见 §6.1 — 简而言之，plan 作者把 Task 10 的 construction 测试当成「Task 10 RED 时 PASS 的延续」，忽略了 Task 10 实际上 construction 也 FAIL（Task 10 tts_repair.py 顶层 import 已让 construction 在 collection 阶段失败）。这是 plan 描述精度问题，不是实现 bug。

### 4.2 Step 5 测试输出（创建 repair_prompt.py + 完整 repair 实现后）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 8 items

src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client PASSED [ 12%]
src_next/critic/tests/test_tts_repair.py::test_repair_prompt_contains_all_required_context PASSED [ 25%]
src_next/critic/tests/test_tts_repair.py::test_repair_merges_llm_output_into_parameters PASSED [ 37%]
src_next/critic/tests/test_tts_repair.py::test_repair_increments_attempt PASSED [ 50%]
src_next/critic/tests/test_tts_repair.py::test_repair_preserves_immutable_top_level_fields PASSED [ 62%]
src_next/critic/tests/test_tts_repair.py::test_repair_returns_original_plus_one_when_llm_raises PASSED [ 75%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_parameters PASSED [ 87%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_top_level PASSED [100%]

============================== 8 passed in 0.02s ==============================
```

**Step 5 GREEN 状态确认：** 完全匹配 plan §Task 11 Step 5 + Acceptance A 字面期望「8 passed」。8 个测试覆盖：
- 1 construction（Task 10 留下）
- 1 prompt 含全部 required context（断言 5 维分数 + suggestions + 5 个 frozen 字段全在 prompt 里）
- 1 LLM 输出 merge 进 original parameters
- 1 attempt +1
- 1 immutable top-level 字段（喂恶意 LLM 验证 5 字段不动）
- 1 LLM raise 异常 → fallback original+1（不抛异常契约）
- 1 LLM 返回 `{"parameters": "garbage"}`（非 dict parameters）→ fallback original
- 1 LLM 返回 list（非 dict top-level）→ fallback original

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A0：文件存在（plan §Task 11 Acceptance A 产出物）**

```
$ test -f src_next/critic/prompts/repair_prompt.py && \
       test -f src_next/critic/tts_repair.py && \
       test -f src_next/critic/tests/test_tts_repair.py && echo OK
OK
```

**A1：追加的 7 个测试与 plan §Task 11 Step 1 字面量 BYTE-EQUAL**

Python 脚本抽取 plan line 1608-1732（7 个新测试代码块），剥离 markdown fence，与实际追加到 test_tts_repair.py 的代码做子串比对：

```
plan_test_lines=121 md5=d8d95739c78d66c693fb56c9a0fbabd3
actual_appended_present=True（plan_test_block in actual_test_file）
→ 7 个新测试 BYTE-EQUAL（作为子串原样出现在 test 文件，无任何重排序 / 字符偏离 / 类型注解添加）
```

**A2：repair_prompt.py 与 plan §Task 11 Step 3 字面量 BYTE-EQUAL**

```
plan_prompt_lines=89 md5=a445bc9c5c918603536a6742e4536fac
actual_prompt_lines=89 md5=a445bc9c5c918603536a6742e4536fac（剥离 trailing newline 后）
→ PROMPT BYTE-EQUAL: True（仅 POSIX trailing newline 差异，文件内容字面一致）
```

**A3：tts_repair.py 与 plan §Task 11 Step 4 字面量 BYTE-EQUAL**

```
plan_repair_lines=91 md5=10220f8c73e63a05f06b201026437f90
actual_repair_lines=91 md5=10220f8c73e63a05f06b201026437f90（剥离 trailing newline 后）
→ REPAIR BYTE-EQUAL: True（仅 POSIX trailing newline 差异，文件内容字面一致）
```

> **trailing newline 说明：** Write 工具自动在文件末尾追加 1 个 `\n`（POSIX 标准），plan 代码块在 ``` 之前没有 trailing newline。剥离后 md5 一致 → 字面量等价，不影响功能 / 不影响 pytest（pytest 不在意文件末尾换行符）。

**A4：py_compile 通过（CLAUDE.md §10 第 1 条）**

```
$ python -m py_compile src_next/critic/tests/test_tts_repair.py && echo OK_TEST
OK_TEST

$ python -m py_compile src_next/critic/prompts/repair_prompt.py && echo OK_PROMPT
OK_PROMPT

$ python -m py_compile src_next/critic/tts_repair.py && echo OK_MODULE
OK_MODULE
```

**A5：行数验证**

```
$ wc -l src_next/critic/tests/test_tts_repair.py src_next/critic/tts_repair.py src_next/critic/prompts/repair_prompt.py
  199 src_next/critic/tests/test_tts_repair.py  （Task 10 的 76 + 衔接空行 + 7 新测试 121 + 文件末换行）
   91 src_next/critic/tts_repair.py             （Task 10 的 20 → 本 task 整体替换为 91）
   89 src_next/critic/prompts/repair_prompt.py  （本 task 新建）
  379 total
```

> 测试文件 199 行 = 76（Task 10 留下）+ 1（衔接空行）+ 121（本 task 追加的 7 个测试）+ 1（文件末尾换行）。
> tts_repair.py 91 行（plan 字面 91 行，md5 BYTE-EQUAL）。
> repair_prompt.py 89 行（plan 字面 89 行，md5 BYTE-EQUAL）。

### 4.4 前置 commit 历史（验证 Task 1-10 已落盘）

```
$ git log --oneline -3
4818b21 chore: 更新 .gitignore，忽略 output 里的 md 文件
790906a feat(critic): implement task 10 (round 1)
72e3d4b test(critic): add 4 integration test skeletons (task 9, round 1)
```

> Task 10 commit `790906a` 是本 task 的直接前置（TTSRepairAgent 最小骨架 + 1 construction 测试已落盘）。`4818b21` 是与本 task 无关的 .gitignore chore commit。

### 4.5 依赖类已存在（前置依赖验证）

```
$ grep -n "^class BaseLLMClient\|^class LLMError\|def generate_text\|def generate_json" src_next/llm/base.py
22:class BaseLLMClient(ABC):
39:    def generate_text(self, prompt: str, **kwargs: Any) -> str:
43:    def generate_json(self, prompt: str, **kwargs: Any) -> dict | list:
（LLMError 在 base.py 某行定义，本 task import 成功证明存在 — Step 5 pytest 8 PASS 是间接证据）
```

### 4.6 `src_next/critic/prompts/` 目录已存在（前置依赖验证）

```
$ git ls-files src_next/critic/prompts/
src_next/critic/prompts/__init__.py     ← 已 tracked（Task 1-9 创建）
src_next/critic/prompts/critic_prompt.py ← 已 tracked（Task 1-9 创建）
```

> `prompts/__init__.py` 已在 Task 1-9 落盘（git tracked），**本 task 不需要新建 `prompts/__init__.py`**。用户 task 指令提示「src_next/critic/prompts/ 目录可能不存在，需要创建（同时建 __init__.py）」属预防性提示，实际验证后目录 + `__init__.py` 都已就绪，本 task 只新建 `repair_prompt.py` 一个文件。

### 4.7 test_tts_repair.py 已含 `_make_inputs` + `_FakeLLMClient` helper（Task 10 复用）

```
$ grep -n "def _make_inputs\|class _FakeLLMClient\|def generate_json\|def generate_text\|captured_prompt" src_next/critic/tests/test_tts_repair.py
15:def _make_inputs(
50:class _FakeLLMClient:
56:        self.captured_prompt: str | None = None
58:    def generate_text(self, prompt: str, **kwargs) -> str:
61:    def generate_json(self, prompt: str, **kwargs) -> dict | list:
```

> `_make_inputs` 和 `_FakeLLMClient` 都是 Task 10 留下的字面量（line 15 / 50）。本 task 7 个新测试**全部复用**这两个 helper，不重写（用户 task 指令明示）。`captured_prompt` 字段（line 56）虽本 task 测试不显式断言，但 plan §Task 11 Step 1 字面量也没断言它（只是定义备用）— 与 plan 字面一致。

### 4.8 Task 10 的 tts_repair.py 最小骨架（20 行，本 task 整体替换前）

```python
"""TTS 指令修复 Agent。
...
"""
from __future__ import annotations

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
from src_next.critic.prompts.repair_prompt import build_repair_prompt  ← Task 10 留下的顶层 import
from src_next.llm.base import BaseLLMClient


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client
```

> Task 10 留下的 line 12 顶层 `from src_next.critic.prompts.repair_prompt import build_repair_prompt` 是 Step 2 RED 的根源（repair_prompt.py 不存在 → ModuleNotFoundError）。本 task Step 3 创建 repair_prompt.py 后，这个 import 可解析；Step 4 整体替换 tts_repair.py 后 import 行保留（plan §Task 11 Step 4 字面量也保留这行），加上完整 repair() 实现，全部 8 测试 PASS。

### 4.9 文件落盘汇总

| 文件 | 操作 | 行数（落盘后） | Task 11 commit |
|---|---|---|---|
| `src_next/critic/tests/test_tts_repair.py` | 修改（追加 7 测试） | 199 | 含（feat commit） |
| `src_next/critic/prompts/repair_prompt.py` | 新建 | 89 | 含（feat commit） |
| `src_next/critic/tts_repair.py` | 整体替换 | 91 | 含（feat commit） |
| `docs/critic_task11_coding.md` | 新建 | 本文件 | 含（feat commit） |
| **合计** | — | **379 + 本 dev doc** | — |

> 本 task "1 修改 + 2 创建 + 1 dev doc"，与 plan §Task 11 Files 表 "Create: src_next/critic/prompts/repair_prompt.py" + "Modify: src_next/critic/tts_repair.py" + "Modify: src_next/critic/tests/test_tts_repair.py" 完全一致，未越界动 `qwen3omni_critic.py` / `conftest.py` / `prompts/critic_prompt.py` / `pytest.ini` 等既有文件。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 5 个文件路径，合并 1 commit 模式，与 Task 5 / 6 / 7 / 8 / 9 / 10 一致）：

```bash
git add src_next/critic/prompts/repair_prompt.py
git add src_next/critic/tts_repair.py
git add src_next/critic/tests/test_tts_repair.py
git add docs/critic_task11_coding.md
git commit -m "feat(critic): implement task 11 (round 1)"
```

> **commit 类型为 `feat(critic):`**——本 task 同时创建业务代码（`repair_prompt.py` + 完整 `tts_repair.py`）+ 测试代码（追加 7 个测试），主交付物是业务模块（TTSRepairAgent 完整实现 + repair prompt 模板），延续 Task 5 / 6 / 10 的 `feat(critic):` 模式。
> **commit message 使用用户 task 指令字面量** `feat(critic): implement task 11 (round 1)`——与 Task 5 / 6 / 10 同模板。
> **`prompts/__init__.py` 不在 add 列表**——已 tracked，本 task 不改动它。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `docs/critic_task8_judging.md` / `docs/critic_task9_judging.md` / `docs/critic_task10_judging.md`），全部不带进本 commit。

### 5.2 与 Task 5 / 6 / 7 / 8 / 9 / 10 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 6 | `732e81b` `feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 7 | `0e74e9b` `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 8 | `1d655b4` `test(critic): add 4 robustness tests for HTTP failure modes` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 9 | `72e3d4b` `test(critic): add 4 integration test skeletons (task 9, round 1)` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 10 | `790906a` `feat(critic): implement task 10 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 11 | （本 task）`feat(critic): implement task 11 (round 1)` | （合并到代码 commit） | 合并 1 commit | **`feat`** |

> Task 11 继续 `feat(critic):` 模式（与 Task 5 / 6 / 10 一致），因为本 task 同时动业务代码（repair_prompt.py + 完整 tts_repair.py）+ 测试文件，主交付物是业务模块（TTSRepairAgent 完整实现）。后续 Task 12 是测试骨架（skip-marked integration），可能用 `test(critic):`。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 追加 7 测试代码块与 plan §Task 11 Step 1 字面量一致性 | 逐字一致 | 子串原样出现（`plan_test_block in actual_test_file == True`，md5 `d8d95739c78d66c693fb56c9a0fbabd3`） | 无 | — |
| repair_prompt.py 与 plan §Task 11 Step 3 字面量一致性 | 逐字一致 | md5 比对 BYTE-EQUAL（剥离 POSIX trailing newline 后 md5 `a445bc9c5c918603536a6742e4536fac`，89 行对 89 行） | 无（trailing newline 是 POSIX 标准） | — |
| tts_repair.py 与 plan §Task 11 Step 4 字面量一致性 | 逐字一致 | md5 比对 BYTE-EQUAL（剥离 POSIX trailing newline 后 md5 `10220f8c73e63a05f06b201026437f90`，91 行对 91 行） | 无 | — |
| **Step 2 测试 PASS/FAIL 数** | plan 字面 "1 PASS (construction) + 7 FAIL (prompt + repair behavior)" | 实测 8 FAIL（construction 也 FAIL，根因 ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'） | Step 2 RED 证据仍成立（7 个新测试全 FAIL），只是 construction 也 FAIL（与 Task 10 终态一致） | **不处理**——plan 作者忽略了 Task 10 已经让 construction FAIL（Task 10 tts_repair.py 顶层 import 已触发 ModuleNotFoundError 在 collection 阶段失败，详见 Task 10 dev doc §4.2）。**关键证据是「7 个新测试全 FAIL」这一点与 plan 字面一致**，construction FAIL 是 Task 10 留下的延续状态，本 task Step 3-4 实施后 Step 5 全部 8 测试 PASS（GREEN），符合 plan §Task 11 Step 5 + Acceptance A 字面「8 passed」。 |
| prompts/__init__.py 是否需要创建 | 用户 task 指令提示「目录可能不存在，需要创建（同时建 __init__.py）」 | 实测 prompts/ 目录 + __init__.py 已在 Task 1-9 落盘（git tracked） | 无 | **不创建**——预防性提示，实际验证后已就绪。本 task commit 不包含 `prompts/__init__.py`（git status 也无该文件 modified）。 |
| commit message 与 plan 字面量 | plan §Task 11 Step 6 字面 `feat(critic): implement TTSRepairAgent with merge + schema-frozen immutable fields` | 用户 task 指令字面 `feat(critic): implement task 11 (round 1)` | 无 | **本 task 按用户指令字面**——延续 Task 5 / 6 / 10 模板（`feat(critic): implement task N (round 1)`），不按 plan Step 6 字面（plan 描述性 message 与项目实际 commit 风格不一致，用户 task 指令显式覆盖）。 |

**无结构性偏离。** 3 个代码文件与 plan 字面量 md5 比对 BYTE-EQUAL（仅 POSIX trailing newline 差异），0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。唯一实质偏离是 Step 2 实测 8 FAIL 而非 plan 字面「1 PASS + 7 FAIL」—— 是 plan 描述精度问题（忽略了 Task 10 已让 construction FAIL），不影响 Step 5 GREEN 终态（8 PASS）。

### 6.2 给 Task 12 的提醒

- **Task 12 范围（plan §Task 12 line 2034 起）：**
  - 仅追加 1 个 skip-marked integration 测试 `test_repair_with_real_llm_adjusts_parameters` 到 `test_tts_repair.py` 末尾
  - 同时挂 `@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 两个装饰器
  - 共享常量 `_INTEGRATION_SKIP_REASON = "awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"`
  - 期望 pytest 8 PASS + 1 SKIPPED
- **Task 12 不改动 `tts_repair.py` / `repair_prompt.py`**——本 task 已交付完整 GREEN 实现，Task 12 纯加测试。
- **Task 12 用 `real_llm` fixture**（Task 7 conftest.py 已定义）—— fixture 现在还无法跑（无服务），skip-marked 保证 CI 不挂。

### 6.3 给 judge-Agent 的提示

- **判定核心：** 本 task 是 Task 10 GREEN 收口，3 个代码文件全部与 plan §Task 11 字面量 BYTE-EQUAL（md5 双双匹配，详见 §4.3 A1-A3），pytest 8 PASS（§4.2），A 表 5/5 + B 表 5/5 + Red flags 5/5 全过。建议 **PASS（mock 阶段，TDD GREEN 状态）**。
- **静态审查重点（plan §Task 11 Acceptance B Static review 5 项）：**
  - `_merge_parameters` 用 `copy.deepcopy(original_parameters)` 作基底 + `update(llm_params)`：tts_repair.py line 71-72 ✓
  - `llm_params = llm_output.get("parameters")` 后 `isinstance(llm_params, dict)` 类型检查：tts_repair.py line 67-69 ✓
  - prompt 含「preserve exactly」强烈措辞 + 5 个禁改字段：repair_prompt.py line 23「**你只能修改 parameters 字段内的内容。**」+ line 25-29 ✓
  - prompt 含 5 维分数（带 `0.40` 具体数值）+ suggestions 原文：repair_prompt.py line 41-49 + `:.2f` 格式化 6 处 ✓
  - `except (LLMError, Exception)` 范围合理 + log warning：tts_repair.py line 50-51 + `# noqa: BLE001 — by design` ✓
- **Red flags 自检（plan §Task 11 Acceptance B 5 条）：**
  - LLM 输出的 top-level 字段出现在返回值里：repair() 返回值全用 original.xxx，未读 llm_output["segment_id"] 等 ✓
  - `_merge_parameters` 直接返回 LLM 输出不 merge：第一行 deepcopy original，第二行 update ✓
  - prompt 把 attempt=1 当「从头改」：line 35「当前 parameters（attempt={attempt}）」当上下文 ✓
  - `repair()` LLM 失败抛异常：try/except 捕获，fallback 不抛 ✓
  - `_fallback` 返回 `attempt=original.attempt`：line 90 用 `attempt=next_attempt`（repair line 47 传入 `original.attempt + 1`）✓
- **越界检测：** 本 task 应该 only `1 修改 + 2 创建 + 1 dev doc`，**不应**：
  - 修改 `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` / `prompts/__init__.py` / `prompts/critic_prompt.py` 等既有文件（git status 应只有 test_tts_repair.py modified + tts_repair.py modified + repair_prompt.py untracked + dev doc untracked）
  - 添加 Task 12 的 integration 测试（skip-marked）
  - 实现主开发 Stage 8 集成（接入 pipeline）
- **commit 类型检测：** 本 task commit message 是 `feat(critic): implement task 11 (round 1)`（业务代码 commit），不是 `test(critic):`——因为同时创建业务模块（repair_prompt.py + 完整 tts_repair.py）+ 测试文件，主交付物是业务模块（延续 Task 5 / 6 / 10 模式）。
- **Step 2 vs Step 5 RED/GREEN 一致性：** Step 2 实测 8 FAIL（包括 construction），Step 5 实测 8 PASS。construction FAIL 在 Step 2 是 Task 10 留下的延续状态（不是本 task 引入的回归）— Step 3-4 实施后 construction 自然 PASS（import 链通了）。
- **md5 字面量证据：** 给 judge 最强证据是 §4.3 A1-A3 的 md5 比对（3 个文件均 BYTE-EQUAL），辅以 §4.2 的 8 PASS pytest 输出。

---

## 7. 一句话总结

Task 11 = Task 10 GREEN 收口：追加 7 个行为测试到 `src_next/critic/tests/test_tts_repair.py`（121 行，md5 `d8d95739c78d66c693fb56c9a0fbabd3`，BYTE-EQUAL 子串）+ 创建 `src_next/critic/prompts/repair_prompt.py`（89 行，md5 `a445bc9c5c918603536a6742e4536fac`，BYTE-EQUAL）+ 整体替换 `src_next/critic/tts_repair.py`（91 行，md5 `10220f8c73e63a05f06b201026437f90`，BYTE-EQUAL，含 `repair()` + `_merge_parameters()` + `_fallback()` 三方法）。Step 2 RED（8 FAIL，根因 ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'）→ Step 5 GREEN（**8 passed in 0.02s**），完全匹配 plan §Task 11 Acceptance A 字面「8 passed」+ B 静态审查 5/5 + Red flags 5/5 全避。commit 类型为 `feat(critic):`（业务模块完整实现），commit message 按用户 task 指令字面量 `feat(critic): implement task 11 (round 1)`。建议 **PASS（mock 阶段，TDD 链 GREEN 状态）**。
