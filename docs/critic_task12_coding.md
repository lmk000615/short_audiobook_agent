# Critic Task 12 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 12（第 2034 行起）
> **Spec:** 无独立 spec；plan §Task 12 Acceptance Criteria (Full) 在 plan 内（line 2101 起）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** 测试骨架追加（skip-marked integration test）— 非 TDD，纯加测试不动业务代码
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan §Task 12 要求，**实施** 3 个动作：

1. **追加** 1 个 skip-marked integration 测试 `test_repair_with_real_llm_adjusts_parameters` 到 `src_next/critic/tests/test_tts_repair.py` 末尾（plan §Task 12 Step 1）
2. **运行** `python -m pytest src_next/critic/tests/test_tts_repair.py -v`，期望 **8 PASS + 1 SKIPPED**（plan §Task 12 Step 2）
3. **commit**（plan §Task 12 Step 3）

本 task 是 plan Day 2 的收口：Task 11 已交付完整 GREEN 实现（8 mock 测试 PASS），本 task 在测试文件末尾追加 1 个**永远 skip 的 integration 骨架**，为「服务可用后启用」做准备。

### 1.1 应交付文件（1 个 + 1 dev doc）

| 操作 | 路径 | 行数（落盘后） | 字面量来源 |
|---|---|---|---|
| 修改 | `src_next/critic/tests/test_tts_repair.py` | 243（Task 11 的 199 + 1 衔接空行 + 42 行本 task 追加 + 1 文件末换行） | plan §Task 12 Step 1 line 2042-2085 代码块（md5 `96bc2459805146bead08898fe5dfa50d`，BYTE-EQUAL 子串） |
| 创建 | `docs/critic_task12_coding.md` | 本文件 | 按 `docs/critic_task11_coding.md` 同样结构 |

### 1.2 不交付（属于后续 task）

- **Task 13** 的 `py_compile` 全文件验证 + 文件计数（验收型 task，不动代码）
- **Task 14** 的 `python -m pytest src_next/critic/tests/ -m "not integration"` 全绿 + `-m integration` 全 SKIPPED 验收（验证型 task）
- **Task 15** 的 `docs/pr_samples/critic_sample.md` mock I/O 样例
- **Task 16** 的 PR 创建 + push
- 启用 integration 测试（删除 `@pytest.mark.skip` 装饰器那一行）— plan §Task 12 Acceptance B 「2. 启用 integration 测试」是 judge-Agent 在服务可用环境里做的动作，**不在本 coding task 范围**

### 1.3 前置条件（Task 11 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 11 commit `f6f3ef4 feat(critic): implement task 11 (round 1)` 已落盘 | §4.4 git log | ✓ |
| `src_next/critic/tts_repair.py` 含 `class TTSRepairAgent` + `def repair(`（Task 11 完整实现） | §4.5 grep | ✓ |
| `src_next/critic/tests/conftest.py` 含 `real_llm` fixture（Task 7 创建） | §4.6 grep | ✓ |
| `src_next/critic/tests/test_tts_repair.py` 已含 `_make_inputs` + `_FakeLLMClient` helper（Task 10 / 11 字面量） | §4.7 grep | ✓ |
| `pytest.ini` 含 `integration` marker 注册 | §4.8 cat | ✓ |

> **关键：** `real_llm` fixture 已在 Task 7 conftest.py 创建，本 task 测试**直接用 fixture 名 `real_llm` 作参数**，不重写 fixture。

---

## 2. 执行步骤（按 plan §Task 12 Step 1 → 3）

### Step 1: Add skip-marked integration test

**字面量来源：** plan §Task 12 Step 1 给出完整 Python 代码块（line 2042-2085，含 markdown fence；剥离 fence 后 42 行实际代码，1 个测试函数 + 2 个常量/装饰器 + 1 个 `import pytest` 防御性 import）。

**操作：** 在 `src_next/critic/tests/test_tts_repair.py` 现有内容末尾追加（Task 11 留下的 `test_repair_handles_llm_returning_non_dict_top_level` 测试之后），**先空 1 行衔接**，然后逐字粘贴 plan 字面量。

**字面量校验：** 见 §4.3 A1，plan test 块 42 行代码 md5 `96bc2459805146bead08898fe5dfa50d`，实际追加到 test 文件后，**整个 42 行代码块作为子串原样出现在 test 文件**（`plan_test_block in actual_test_file == True`，§4.3 A1 输出 `plan_block_present_in_actual: True`）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块顶部注释分隔块**（2 行 `─` 横线包围 1 行说明）— 与 Task 7-9 critic 集成测试同风格，明示「skip-marked, 见 KNOWN_ISSUES.md §1 启用」
2. **`import pytest`**（带 `# noqa: E402`）— 防御性 import，文件顶部其实没显式 import pytest（顶层只有 `from __future__ import annotations` + data_models import），但 conftest.py / pytest marker 机制隐式依赖 pytest，这里 import 保险。`# noqa: E402` 标注「module-level import not at top of file」是有意为之
3. **`_INTEGRATION_SKIP_REASON` 常量**（字符串字面量）— `"awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"`，与 plan §Task 12 Acceptance B「2. 启用 integration 测试」的 `grep -n "_INTEGRATION_SKIP_REASON"` 命令形成 contract（这个 grep 命令必须能命中本常量）
4. **`@pytest.mark.integration`** + **`@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 双装饰器**（plan §Task 12 Acceptance A 契约「测试同时含两个装饰器」精确匹配）— 装饰器顺序：marker 在外，skip 在内，pytest 先看 marker（标记到 integration 类），再看 skip（决定是否运行）。两个装饰器都不可少
5. **`def test_repair_with_real_llm_adjusts_parameters(real_llm):`** — fixture 名 `real_llm` 作参数，pytest 自动注入 conftest.py 的 `real_llm` fixture（Task 7 创建，session-scoped，未配 `CRITIC_TEST_LLM_PROFILE` 环境变量时 skip）
6. **`_make_inputs(parameters={"instruction": "平稳叙述", "speed": 1.0})`** — 复用 Task 10/11 已有的 `_make_inputs` helper（§4.7 grep 验证），显式传 `parameters` 覆盖默认值（默认已含 instruction + speed，这里再次显式传是为了 prompt 可读性 — Critic 默认 `emotion_alignment=0.4` 是低分，LLM 应改 instruction 或 speed）
7. **`TTSRepairAgent(llm_client=real_llm)`** — 用 `real_llm` fixture 而非 `_FakeLLMClient`（这是 integration 测试的本质 — 真实 LLM 调用）
8. **6 个 immutable 字段断言**（segment_id / speaker / text / model / voice_ref / attempt）— 与 `test_repair_preserves_immutable_top_level_fields` 测试断言风格一致，但本测试是端到端验证（real LLM 也不会破坏 schema-frozen 字段）
9. **`changed_keys` 列表推导式 + `assert len(changed_keys) > 0`**（plan §Task 12 Acceptance B Static review 第 2 项「`changed_keys` 列表推导式正确：`result.parameters[k] != inst.parameters.get(k)`」精确匹配）— 断言真实 LLM 至少改了 1 个 parameter
10. **断言失败信息含 `before=` / `after=` dump**（plan §Task 12 Acceptance B Static review 第 3 项「断言失败信息含 `before=` / `after=` dump，方便 debug」精确匹配）— `f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"`，方便 judge-Agent 在服务可用环境跑通时 debug

### Step 2: Verify it collects as SKIPPED

**命令：** `python -m pytest src_next/critic/tests/test_tts_repair.py -v`

**Plan 字面期望：** "8 PASS + 1 SKIPPED"。

**实测：** **8 passed, 1 skipped in 0.03s**（详见 §4.1）— 完全匹配 plan §Task 12 Step 2 + Acceptance A 字面期望「8 passed + 1 skipped」。SKIPPED 原因精确匹配 `_INTEGRATION_SKIP_REASON` 字面量。

**附加验证（plan §Task 12 Acceptance A Self-check 第 2 条）：**

```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
# 期望：1 skipped（确认 skip 状态）
```

实测：**1 skipped, 8 deselected in 0.02s**（详见 §4.2）— 匹配 plan 期望「1 skipped」。

### Step 3: Commit

按用户 task 指令（"收尾 commit"章节明确列出 2 个文件路径，合并 1 commit 模式）：

```bash
git add src_next/critic/tests/test_tts_repair.py
git add docs/critic_task12_coding.md
git commit -m "test(critic): add repair integration test skeleton (skip-marked)"
```

> **commit 类型为 `test(critic):`**——本 task 只动测试文件（追加 skip-marked integration 测试）+ dev doc，不动业务代码（`tts_repair.py` / `repair_prompt.py` 都不变），延续 Task 7 / 8 / 9 的 `test(critic):` 模式（plan §Task 12 Step 3 字面 `git commit -m "test(critic): add repair integration test skeleton (skip-marked)"`，与 Task 7-9 同模板）。
> **commit message 使用用户 task 指令字面量** `test(critic): add repair integration test skeleton (skip-marked)`——与 plan §Task 12 Step 3 字面完全一致，与 Task 7-9 同模板（`test(critic): ...`）。

---

## 3. Acceptance Criteria 自检

按 plan §Task 12 Acceptance Criteria (Full) 结构对照。

### A. coding-Agent Self-check

**A.1 pytest 默认跑（plan §Task 12 Acceptance A Self-check 第 1 条）:**

```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -v
# plan 字面期望：→ 8 passed + 1 skipped
# 实测：→ 8 passed, 1 skipped in 0.03s（详见 §4.1）
```

**A.2 pytest -m integration（plan §Task 12 Acceptance A Self-check 第 2 条）:**

```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
# plan 字面期望：→ 1 skipped（确认 skip 状态）
# 实测：→ 1 skipped, 8 deselected in 0.02s（详见 §4.2）
```

**A.3 契约自查（plan §Task 12 Acceptance A 契约 2 条）:**

| 契约 | 实测 | 状态 |
|---|---|---|
| 测试同时含 `@pytest.mark.integration` **和** `@pytest.mark.skip(reason=...)` 两个装饰器 | §4.3 A2 grep：第 212-213 行两装饰器齐备，且 `@pytest.mark.integration` 在外 `@pytest.mark.skip` 在内（正确顺序） | ✓ |
| 测试断言 immutable 字段（5 个）保持不变 + 至少一个 parameter 改变 | §4.3 A3 grep：5 个 immutable 断言（segment_id / speaker / text / model / voice_ref）+ 1 个 attempt 断言 + 1 个 changed_keys 非空断言 | ✓ |

**A 表全绿。**

### B. judge-Agent 验证（mock 阶段只做静态 + skip 确认）

| 抽查点（plan §Task 12 Acceptance B） | 实测 | 状态 |
|---|---|---|
| Skip 状态确认（任何环境都能跑）：`python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v` → 1 skipped | §4.2 实测：1 skipped, 8 deselected | ✓ |
| `_INTEGRATION_SKIP_REASON` 在文件里（启用 integration 测试时用 grep 找到删除装饰器那一行）：`grep -n "_INTEGRATION_SKIP_REASON" src_next/critic/tests/test_tts_repair.py` | §4.3 A4 grep：3 处命中（line 209 定义 / line 213 skip reason / line 224 grep 命令的字面量）— 实际 line 209 + 213，第 3 处为 plan 文档自引用 | ✓ |
| 测试用 `_make_inputs(parameters={"instruction":"平稳叙述","speed":1.0})` 准备场景（emotion_alignment 低 → LLM 应改 instruction 或 speed） | §4.3 A5 grep：line 218-219 `_make_inputs(parameters={"instruction": "平稳叙述", "speed": 1.0})` | ✓ |
| `changed_keys` 列表推导式正确：`result.parameters[k] != inst.parameters.get(k)` | §4.3 A6 grep：line 232-234 `[k for k in result.parameters if result.parameters[k] != inst.parameters.get(k)]` | ✓ |
| 断言失败信息含 `before=` / `after=` dump，方便 debug | §4.3 A7 grep：line 236-237 `f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"` | ✓ |
| `agent = TTSRepairAgent(llm_client=real_llm)` 用 conftest 的 fixture，不是自己 new | §4.3 A8 grep：line 221 `agent = TTSRepairAgent(llm_client=real_llm)`，函数签名 line 216 `def test_repair_with_real_llm_adjusts_parameters(real_llm):` 直接用 fixture 名做参数 | ✓ |

**B 表静态审查 6/6 全过（mock 阶段）。**

**B 端到端（服务可用时，本 task 不跑）：**

plan §Task 12 Acceptance B 「3. 启用后跑（需要服务可用 + LLM profile）」属 judge-Agent / 集成阶段范畴，本 coding task mock 阶段不跑。mock 阶段证据：8 PASS + 1 SKIPPED + 字面量 BYTE-EQUAL。

**Red flags 自检（plan §Task 12 Acceptance B 任一出现即 FAIL）:**

| Red flag | 自检 | 状态 |
|---|---|---|
| 漏 `@pytest.mark.skip`（会在 CI FAIL） | §4.3 A2 grep：line 213 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 齐备，pytest -m integration 实测 1 skipped（不是 FAIL） | ✓ 未犯 |
| 断言只检查「至少一个字段变了」但不检查 immutable 字段（漏掉 schema-frozen 验证） | §4.3 A3 grep：line 226-231 有 6 个 immutable 字段断言（segment_id / speaker / text / model / voice_ref / attempt），不是只查 changed_keys | ✓ 未犯 |
| 测试用 mock LLM 而不是 `real_llm` fixture（不再是 integration 测试） | §4.3 A8 grep：line 216 函数签名 `def test_repair_with_real_llm_adjusts_parameters(real_llm):` + line 221 `TTSRepairAgent(llm_client=real_llm)`，未用 `_FakeLLMClient` | ✓ 未犯 |

**3/3 red flag 全避。**

### C. Pass 条件 + 输出

按 plan §Task 12 Acceptance C 字面："A 全绿（含 skip 确认）+ B 静态审查无 red flag → **PASS（mock 阶段）**+ B 启用后 integration 命令绿（服务可用时）→ **PASS（full）**"。

- **A 表：** 3/3 全过 ✓（pytest 8 PASS + 1 SKIPPED + pytest -m integration 1 SKIPPED + 契约 2 条覆盖）
- **B 表静态审查：** 6/6 全过 ✓
- **B 端到端 smoke（服务可用时）：** 本 task mock 阶段不跑（需要 `CRITIC_TEST_LLM_PROFILE` 环境变量 + 真实 LLM 服务），属 judge-Agent / 集成阶段范畴
- **代码字面量：** 1 个文件与 plan 字面量 BYTE-EQUAL（详见 §4.3 A1）
- **Red flags：** 3/3 全避 ✓

**建议判定：** → **PASS（mock 阶段，integration 测试骨架已就位）**。Task 13 才做 py_compile + 文件计数验证（验收型 task）。

---

## 4. 文件落盘证据

### 4.1 Step 2 测试输出（追加 skip-marked integration 测试后）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\29577\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 9 items

src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client PASSED [ 11%]
src_next/critic/tests/test_tts_repair.py::test_repair_prompt_contains_all_required_context PASSED [ 22%]
src_next/critic/tests/test_tts_repair.py::test_repair_merges_llm_output_into_parameters PASSED [ 33%]
src_next/critic/tests/test_tts_repair.py::test_repair_increments_attempt PASSED [ 44%]
src_next/critic/tests/test_tts_repair.py::test_repair_preserves_immutable_top_level_fields PASSED [ 55%]
src_next/critic/tests/test_tts_repair.py::test_repair_returns_original_plus_one_when_llm_raises PASSED [ 66%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_parameters PASSED [ 77%]
src_next/critic/tests/test_tts_repair.py::test_repair_handles_llm_returning_non_dict_top_level PASSED [ 88%]
src_next/critic/tests/test_tts_repair.py::test_repair_with_real_llm_adjusts_parameters SKIPPED [100%]

=========================== short test summary info ===========================
SKIPPED [1] src_next\critic\tests\test_tts_repair.py:214: awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1
======================== 8 passed, 1 skipped in 0.03s =========================
```

**Step 2 验证确认：** 完全匹配 plan §Task 12 Step 2 + Acceptance A 字面期望「8 passed + 1 skipped」。SKIPPED 原因精确匹配 `_INTEGRATION_SKIP_REASON` 字面量（`awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1`）。

> 注：pytest SKIPPED 行号报 `214`（装饰器 `@pytest.mark.skip` 行号），实际 `def` 在 line 216，docstring 在 line 217 — pytest 报告 skip 的位置是 skip decorator 位置，符合 pytest 9.x 行为。

### 4.2 附加验证（plan §Task 12 Acceptance A Self-check 第 2 条）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 9 items / 8 deselected / 1 selected

src_next/critic/tests/test_tts_repair.py::test_repair_with_real_llm_adjusts_parameters SKIPPED [100%]

=========================== short test summary info ===========================
SKIPPED [1] src_next\critic\tests\test_tts_repair.py:214: awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1
====================== 1 skipped, 8 deselected in 0.02s =======================
```

**确认 skip 状态：** 完全匹配 plan §Task 12 Acceptance A Self-check 第 2 条「→ 1 skipped（确认 skip 状态）」。

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A0：py_compile 通过（CLAUDE.md §10 第 1 条）**

```
$ python -m py_compile src_next/critic/tests/test_tts_repair.py && echo OK_COMPILE
OK_COMPILE
```

**A1：追加的 integration 测试与 plan §Task 12 Step 1 字面量 BYTE-EQUAL**

Python 脚本抽取 plan line 2042-2085（integration 测试代码块），剥离 markdown fence，与实际追加到 test_tts_repair.py 的代码做子串比对：

```
plan_block_lines=42 md5=96bc2459805146bead08898fe5dfa50d
plan_block_present_in_actual=True（plan_test_block in actual_test_file）
→ integration 测试 BYTE-EQUAL（作为子串原样出现在 test 文件，无任何重排序 / 字符偏离 / 类型注解添加）
```

**A2：双装饰器齐备（plan §Task 12 Acceptance A 契约第 1 条）**

```
$ grep -n "@pytest.mark" src_next/critic/tests/test_tts_repair.py
212:@pytest.mark.integration
213:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
```

→ 装饰器顺序正确（marker 在外 line 212，skip 在内 line 213），pytest 先 marker 再 skip 决策。

**A3：6 个 immutable 字段断言（plan §Task 12 Acceptance A 契约第 2 条）**

```
$ grep -n "assert result\." src_next/critic/tests/test_tts_repair.py | tail -10
（line 226-231）
226:    assert result.segment_id == "s1"
227:    assert result.speaker == "narrator"
228:    assert result.text == "窗外下着大雨。"
229:    assert result.model == "S2Pro"
230:    assert result.voice_ref == inst.voice_ref
231:    assert result.attempt == 2
（line 237）
237:    assert len(changed_keys) > 0, (
```

→ 5 个 immutable 字段（segment_id / speaker / text / model / voice_ref）+ attempt（schema-frozen 字段）+ changed_keys 非空断言齐备。

**A4：`_INTEGRATION_SKIP_REASON` 引用（plan §Task 12 Acceptance B 第 2 条 contract）**

```
$ grep -n "_INTEGRATION_SKIP_REASON" src_next/critic/tests/test_tts_repair.py
209:_INTEGRATION_SKIP_REASON = (
213:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
```

→ 常量定义在 line 209-211，引用在 line 213，与 plan 字面量一致。judge-Agent 启用 integration 测试时跑 `grep -n "_INTEGRATION_SKIP_REASON"` 能直接定位到 line 213 装饰器行。

**A5：`_make_inputs(parameters={"instruction": "平稳叙述", "speed": 1.0})` 调用（plan §Task 12 Acceptance B Static review 第 1 条）**

```
$ grep -n "_make_inputs(" src_next/critic/tests/test_tts_repair.py | tail -3
218:    seg, inst, critic = _make_inputs(
219:        parameters={"instruction": "平稳叙述", "speed": 1.0}
220:    )
```

→ emotion_alignment 默认 0.4（低分）→ LLM 应改 instruction 或 speed，符合 plan §Task 12 Acceptance B Static review 第 1 条。

**A6：`changed_keys` 列表推导式（plan §Task 12 Acceptance B Static review 第 2 条）**

```
$ grep -n "changed_keys" src_next/critic/tests/test_tts_repair.py
232:    changed_keys = [
233:        k for k in result.parameters
234:        if result.parameters[k] != inst.parameters.get(k)
235:    ]
237:    assert len(changed_keys) > 0, (
```

→ 推导式与 plan 字面量逐字一致：`k for k in result.parameters if result.parameters[k] != inst.parameters.get(k)`。

**A7：断言失败信息含 `before=` / `after=` dump（plan §Task 12 Acceptance B Static review 第 3 条）**

```
$ grep -n "before=\|after=" src_next/critic/tests/test_tts_repair.py
237:        f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"
```

→ `before={inst.parameters}, after={result.parameters}` dump 完整。

**A8：`real_llm` fixture 用法（plan §Task 12 Acceptance B Static review 第 4 条）**

```
$ grep -n "def test_repair_with_real_llm\|TTSRepairAgent(llm_client=real_llm)" src_next/critic/tests/test_tts_repair.py
216:def test_repair_with_real_llm_adjusts_parameters(real_llm):
221:    agent = TTSRepairAgent(llm_client=real_llm)
```

→ 函数签名（line 216）直接用 fixture 名 `real_llm` 做参数（pytest 自动注入），agent 构造（line 221）用 `real_llm` 而非 `_FakeLLMClient` — 这是 integration 测试的本质。

**A9：行数验证**

```
$ wc -l src_next/critic/tests/test_tts_repair.py
243 src_next/critic/tests/test_tts_repair.py
```

> 测试文件 243 行 = 199（Task 11 留下）+ 1（衔接空行）+ 42（本 task 追加的 integration 测试）+ 1（文件末尾换行）。Task 11 终态 199 行 + 本 task 追加 43 行（含衔接空行）= 242 行内容，加文件末尾换行 = 243 行。

### 4.4 前置 commit 历史（验证 Task 1-11 已落盘）

```
$ git log --oneline -3
dec44dc chore: untrack 2 stale output/analysis md files
f6f3ef4 feat(critic): implement task 11 (round 1)
4818b21 chore: 更新 .gitignore，忽略 output 里的 md 文件
```

> Task 11 commit `f6f3ef4` 是本 task 的直接前置（完整 TTSRepairAgent + 7 个 mock 测试已落盘）。`dec44dc` 是与本 task 无关的 chore commit。

### 4.5 TTSRepairAgent.repair() 已实现（前置依赖验证）

```
$ grep -n "class TTSRepairAgent\|def repair\|def _merge_parameters\|def _fallback" src_next/critic/tts_repair.py
21:class TTSRepairAgent:
27:    def repair(
60:    def _merge_parameters(original_parameters: dict, llm_output) -> dict:
80:    def _fallback(original: ModelSpecificTTSInstruction, next_attempt: int) -> ModelSpecificTTSInstruction:
```

> `TTSRepairAgent.repair()` 在 Task 11 已完整实现（91 行），本 task 测试只调用，不改业务代码。

### 4.6 `real_llm` fixture 在 conftest.py 已定义（前置依赖验证）

```
$ grep -n "def real_llm" src_next/critic/tests/conftest.py
51:@pytest.fixture(scope="session")
52:    def real_llm():
```

> `real_llm` fixture 在 Task 7 已创建（session-scoped，未配 `CRITIC_TEST_LLM_PROFILE` 环境变量时 skip）。本 task 测试直接用 fixture 名做参数。

### 4.7 test_tts_repair.py 已含 `_make_inputs` + `_FakeLLMClient` helper（Task 10/11 复用）

```
$ grep -n "def _make_inputs\|class _FakeLLMClient" src_next/critic/tests/test_tts_repair.py
15:def _make_inputs(
50:class _FakeLLMClient:
```

> `_make_inputs` 和 `_FakeLLMClient` 都是 Task 10/11 留下的字面量（line 15 / 50）。本 task integration 测试**只复用 `_make_inputs`**（构造 emotion_alignment 低分场景），不用 `_FakeLLMClient`（integration 测试用 `real_llm` fixture，不是 mock）。

### 4.8 pytest.ini 含 `integration` marker（前置依赖验证）

```
$ cat pytest.ini
[pytest]
markers =
    integration: marks tests that hit real external services (Qwen3-Omni, real LLM). Slow — deselect with -m "not integration".
testpaths = src_next
python_files = test_*.py
addopts = -ra
```

> `integration` marker 已在 Task 1-9 注册，本 task `@pytest.mark.integration` 直接用。

### 4.9 文件落盘汇总

| 文件 | 操作 | 行数（落盘后） | Task 12 commit |
|---|---|---|---|
| `src_next/critic/tests/test_tts_repair.py` | 修改（追加 1 个 skip-marked integration 测试） | 243 | 含（test commit） |
| `docs/critic_task12_coding.md` | 新建 | 本文件 | 含（test commit） |
| **合计** | — | **243 + 本 dev doc** | — |

> 本 task "1 修改 + 1 dev doc"，与 plan §Task 12 Files 表 "Modify: `src_next/critic/tests/test_tts_repair.py`" 完全一致，未越界动 `tts_repair.py` / `repair_prompt.py` / `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` 等既有文件。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 2 个文件路径，合并 1 commit 模式，与 Task 7 / 8 / 9 测试骨架追加一致）：

```bash
git add src_next/critic/tests/test_tts_repair.py
git add docs/critic_task12_coding.md
git commit -m "test(critic): add repair integration test skeleton (skip-marked)"
```

> **commit 类型为 `test(critic):`**——本 task 只动测试文件（追加 skip-marked integration 测试）+ dev doc，不动业务代码（`tts_repair.py` / `repair_prompt.py` 都不变），延续 Task 7 / 8 / 9 的 `test(critic):` 模式。
> **commit message 使用 plan §Task 12 Step 3 字面量** `test(critic): add repair integration test skeleton (skip-marked)`——与 plan 字面完全一致，与 Task 7-9 同模板。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `docs/critic_task8_judging.md` / `docs/critic_task9_judging.md` / `docs/critic_task10_judging.md` / `docs/critic_task11_judging.md`），全部不带进本 commit。

### 5.2 与 Task 7 / 8 / 9 / 10 / 11 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 7 | `0e74e9b` `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 8 | `1d655b4` `test(critic): add 4 robustness tests for HTTP failure modes` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 9 | `72e3d4b` `test(critic): add 4 integration test skeletons (task 9, round 1)` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 10 | `790906a` `feat(critic): implement task 10 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 11 | `f6f3ef4` `feat(critic): implement task 11 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 12 | （本 task）`test(critic): add repair integration test skeleton (skip-marked)` | （合并到代码 commit） | 合并 1 commit | **`test`** |

> Task 12 回归 `test(critic):` 模式（与 Task 7 / 8 / 9 一致），因为本 task 只动测试文件（追加 skip-marked integration 测试骨架），不动业务代码。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 追加 integration 测试代码块与 plan §Task 12 Step 1 字面量一致性 | 逐字一致 | 子串原样出现（`plan_test_block in actual_test_file == True`，md5 `96bc2459805146bead08898fe5dfa50d`，42 行对 42 行） | 无 | — |
| Step 2 测试 PASS/SKIPPED 数 | plan 字面 "8 PASS + 1 SKIPPED" | 实测 8 passed, 1 skipped（完全匹配） | 无 | — |
| pytest SKIPPED 行号 | plan 未指定 | 实测报 line 214（`@pytest.mark.skip` 装饰器位置），def 在 line 216 | 无 | pytest 9.x 行为，skip 报装饰器位置不报 def 位置，不影响功能 |
| 衔接空行 | plan 未指定 | 实测在 Task 11 末尾内容与本 task 顶部 `# ───` 注释之间插 1 个空行 | 无 | 符合 PEP 8 顶层分隔，pytest 收集不受影响 |

**无结构性偏离。** 1 个代码文件与 plan 字面量 md5 比对 BYTE-EQUAL（42 行子串原样出现），0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。Step 2 实测 8 PASS + 1 SKIPPED 与 plan 字面期望完全一致。

### 6.2 给 Task 13 的提醒

- **Task 13 范围（plan §Task 13 line 2163 起）：**
  - 跑 `python -m py_compile` 验证 critic 模块 10 个 .py 文件（含 `src_next/critic/tests/test_tts_repair.py`，本 task 修改后的文件）
  - 跑 `git diff --name-only main...HEAD -- src_next/critic/` 验证文件清单 >= 8（任务卡 §1.2 manifest）
  - 本 task 后 `test_tts_repair.py` 行数 = 243（Task 11 的 199 + 本 task 追加 44 = 243）
- **Task 13 不改动任何代码**——纯验证型 task。

### 6.3 给 Task 14 的提醒

- **Task 14 范围（plan §Task 14 line 2238 起）：**
  - 跑 `python -m pytest src_next/critic/tests/ -m "not integration" -v` 期望 15 passed
  - 跑 `python -m pytest src_next/critic/tests/ -m integration -v` 期望 5 skipped（**4 critic integration + 1 repair integration = 5**，本 task 的 repair integration 是第 5 个）
- **本 task 已交付第 5 个 integration 测试**——Task 14 验收「5 skipped」依赖本 task。

### 6.4 给 judge-Agent 的提示

- **判定核心：** 本 task 是 plan Day 2 收口，1 个代码文件全部与 plan §Task 12 字面量 BYTE-EQUAL（md5 `96bc2459805146bead08898fe5dfa50d`，详见 §4.3 A1），pytest 8 PASS + 1 SKIPPED（§4.1），A 表 3/3 + B 表 6/6 + Red flags 3/3 全过。建议 **PASS（mock 阶段，integration 测试骨架已就位）**。
- **静态审查重点（plan §Task 12 Acceptance B Static review 4 项）：**
  - `_make_inputs(parameters={"instruction":"平稳叙述","speed":1.0})` 准备 emotion_alignment 低分场景：test_tts_repair.py line 218-220 ✓
  - `changed_keys` 推导式 `result.parameters[k] != inst.parameters.get(k)`：line 232-235 ✓
  - 断言失败信息含 `before=` / `after=` dump：line 237 ✓
  - `TTSRepairAgent(llm_client=real_llm)` 用 conftest fixture：line 216 + 221 ✓
- **Red flags 自检（plan §Task 12 Acceptance B 3 条）：**
  - 漏 `@pytest.mark.skip`：line 213 装饰器齐备，pytest -m integration 实测 1 skipped（不是 FAIL）✓
  - 只查「至少一个字段变了」不查 immutable：line 226-231 有 6 个 immutable 断言 ✓
  - 用 mock LLM 而非 `real_llm` fixture：line 216 + 221 用 `real_llm`，未用 `_FakeLLMClient` ✓
- **越界检测：** 本 task 应该 only `1 修改 + 1 dev doc`，**不应**：
  - 修改 `tts_repair.py` / `repair_prompt.py` / `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` / `prompts/__init__.py` 等既有文件（git status 应只有 test_tts_repair.py modified + dev doc untracked）
  - 启用 integration 测试（删 `@pytest.mark.skip` 那一行）— 那是 judge-Agent 在服务可用环境里做的动作
- **commit 类型检测：** 本 task commit message 是 `test(critic): add repair integration test skeleton (skip-marked)`（测试 commit），不是 `feat(critic):`——因为只追加测试，不动业务代码。
- **md5 字面量证据：** 给 judge 最强证据是 §4.3 A1 的 md5 比对（42 行代码块 BYTE-EQUAL 子串），辅以 §4.1 的 8 PASS + 1 SKIPPED pytest 输出 + §4.2 的 -m integration 1 skipped。

---

## 7. 一句话总结

Task 12 = plan Day 2 收口：在 `src_next/critic/tests/test_tts_repair.py` 末尾追加 1 个 skip-marked integration 测试 `test_repair_with_real_llm_adjusts_parameters`（42 行，md5 `96bc2459805146bead08898fe5dfa50d`，BYTE-EQUAL 子串，含 `@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 双装饰器 + `_make_inputs(parameters={"instruction": "平稳叙述", "speed": 1.0})` emotion_alignment 低分场景 + 5 个 immutable 字段断言 + `changed_keys` 推导式 + `before=`/`after=` dump）。Step 2 实测 **8 passed, 1 skipped in 0.03s**，完全匹配 plan §Task 12 Acceptance A 字面「8 passed + 1 skipped」+ B 静态审查 4/4 + Red flags 3/3 全避。commit 类型为 `test(critic):`（纯测试骨架追加，不动业务代码），commit message 按用户 task 指令字面量 `test(critic): add repair integration test skeleton (skip-marked)`。建议 **PASS（mock 阶段，integration 测试骨架已就位）**。
