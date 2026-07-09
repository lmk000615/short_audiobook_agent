# Critic Task 12 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 12（line 2034 起）
> **Spec:** 无独立 spec；Acceptance Criteria 在 plan 内（line 2101 起）
> **Coding dev doc:** `docs/critic_task12_coding.md`
> **分支:** `feature/critic-and-tta`
> **Task 12 commit:** `8d0278d test(critic): add repair integration test skeleton (skip-marked)`
> **验收日期:** 2026-07-08
> **Task 类型:** 测试骨架追加（skip-marked integration test）— 非 TDD，纯加测试不动业务代码
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS（mock 阶段）**：1 个 skip-marked integration 测试骨架已落盘，Section A 自检 2/2 命中 plan 字面期望（8 passed + 1 skipped / 1 skipped + 8 deselected），Section B 静态审查 6/6 + 契约 2/2 + Red flags 3/3 全过，与 plan §Task 12 Step 1 字面量逐字一致，commit `8d0278d` scope clean（只 2 个文件、未越界）。

---

## 1. 验收范围

按 plan §Task 12 Acceptance Criteria (Full) 验收 3 个动作：

| Step | Plan 要求（line） | 验收方式 |
|---|---|---|
| Step 1: Add skip-marked integration test | line 2039-2085（42 行 Python 代码块）| 字面量子串比对 + 8 个静态点 Grep 核对 |
| Step 2: Verify SKIPPED | line 2087-2090（`pytest -v` 期望 8 PASS + 1 SKIPPED）| judge 自己跑 pytest（不信 coding doc）|
| Step 3: Commit | line 2092-2097（`test(critic):` 类型 + 字面 commit message）| `git show 8d0278d --stat` 核对 scope |

**不在 mock 阶段验收的项（plan §Task 12 Acceptance B 第 3 条）：**

- 启用 integration 测试后端到端跑（需要真实 LLM 服务 + `CRITIC_TEST_LLM_PROFILE` 环境变量）— 这是 judge-Agent / 集成阶段范畴，本 round 不跑

---

## 2. Section A — coding-Agent Self-check（judge 自己跑）

| 项 | Plan 期望（line） | judge 实测 | 状态 |
|---|---|---|---|
| A.1 `python -m pytest src_next/critic/tests/test_tts_repair.py -v` | 8 passed + 1 skipped（line 2113-2114） | `8 passed, 1 skipped in 0.02s`（详见 §6.1 实测输出） | PASS |
| A.2 `python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v` | 1 skipped（确认 skip 状态，line 2115-2116） | `1 skipped, 8 deselected in 0.02s`（详见 §6.2 实测输出） | PASS |
| 契约 1：测试同时含 `@pytest.mark.integration` 和 `@pytest.mark.skip(reason=...)`（line 2120） | 双装饰器齐备，marker 在外 skip 在内 | Grep `@pytest.mark.(integration\|skip)` 命中 line 214 `@pytest.mark.integration` + line 215 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`，顺序正确 | PASS |
| 契约 2：测试断言 immutable 字段（5 个）保持不变 + 至少一个 parameter 改变（line 2121） | 5 个 immutable 字段断言 + changed_keys 非空断言 | Grep `assert result\.` 命中 line 229-234（5 个 immutable + attempt）+ line 241 `assert len(changed_keys) > 0` | PASS |

**A 表：4/4 全过。**

---

## 3. Section B — judge-Agent 抽查（静态审查）

| 抽查点 | Plan 期望（line） | judge 实测证据（Grep / Read） | 状态 |
|---|---|---|---|
| B.1 Skip 状态确认（任何环境都能跑）：`pytest -m integration -v` → 1 skipped | line 2128-2129 | §6.2 实测：`1 skipped, 8 deselected in 0.02s` | PASS |
| B.2 `_INTEGRATION_SKIP_REASON` 在文件里（启用 integration 测试时用 grep 定位删装饰器行） | line 2132 | Grep `_INTEGRATION_SKIP_REASON` 命中 2 处：line 209 定义 + line 215 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 引用，judge 用 `grep -n` 能直接定位 line 215 | PASS |
| B.3 测试用 `_make_inputs(parameters={"instruction":"平稳叙述","speed":1.0})` 准备场景 | line 2142 | Grep `_make_inputs\(` 命中 line 220-222：`seg, inst, critic = _make_inputs(\n    parameters={"instruction": "平稳叙述", "speed": 1.0}\n)`，字面量逐字匹配 | PASS |
| B.4 `changed_keys` 列表推导式正确：`result.parameters[k] != inst.parameters.get(k)` | line 2143 | Grep `changed_keys` 命中 line 237-240：`changed_keys = [\n    k for k in result.parameters\n    if result.parameters[k] != inst.parameters.get(k)\n]`，推导式逐字匹配 plan line 2078-2081 | PASS |
| B.5 断言失败信息含 `before=` / `after=` dump，方便 debug | line 2144 | Grep `before=\|after=` 命中 line 242：`f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"`，dump 完整 | PASS |
| B.6 `agent = TTSRepairAgent(llm_client=real_llm)` 用 conftest 的 fixture，不是自己 new | line 2145 | Grep `def test_repair_with_real_llm\|TTSRepairAgent\(llm_client=real_llm\)` 命中 line 216 `def test_repair_with_real_llm_adjusts_parameters(real_llm):`（fixture 名作参数）+ line 224 `agent = TTSRepairAgent(llm_client=real_llm)`，未用 `_FakeLLMClient` | PASS |

**Red flags 排查（plan §Task 12 line 2147-2150，任一出现即 FAIL）：**

| Red flag | Plan 期望 | judge 自检 | 状态 |
|---|---|---|---|
| 漏 `@pytest.mark.skip`（会在 CI FAIL） | 装饰器必须齐备 | §3 表 B.1 + Grep line 215 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`，pytest -m integration 实测 1 skipped（不是 FAIL） | 未犯 |
| 断言只查「至少一个字段变了」但不查 immutable 字段（漏掉 schema-frozen 验证） | 必须查 5 个 immutable | Grep `assert result\.` line 229-234 有 6 个 immutable 字段断言（segment_id / speaker / text / model / voice_ref / attempt），不只查 changed_keys | 未犯 |
| 测试用 mock LLM 而不是 `real_llm` fixture（不再是 integration 测试） | 必须用 fixture | Grep line 216 函数签名 + line 224 `TTSRepairAgent(llm_client=real_llm)` 用 `real_llm`，未用 `_FakeLLMClient` | 未犯 |

**B 表静态审查：6/6 + Red flags 3/3 全避。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 字面量核对（plan §Task 12 Step 1 line 2042-2085 vs `src_next/critic/tests/test_tts_repair.py` line 202-243）

| 关键字面量 | Plan 字面位置 | 实际文件位置 | 一致性 |
|---|---|---|---|
| 模块顶部注释分隔块（`# ──...` × 2 + 说明） | line 2043-2045 | line 202-204 | ✓ 字面匹配 |
| `import pytest  # noqa: E402 — top of file already imports pytest, but be defensive` | line 2047 | line 206 | ✓ 字面匹配 |
| `_INTEGRATION_SKIP_REASON = (\n    "awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"\n)` | line 2050-2052 | line 209-211 | ✓ 字面匹配 |
| `@pytest.mark.integration` | line 2055 | line 214 | ✓ 字面匹配 |
| `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` | line 2056 | line 215 | ✓ 字面匹配 |
| `def test_repair_with_real_llm_adjusts_parameters(real_llm):` | line 2057 | line 216 | ✓ 字面匹配 |
| docstring `"""Integration: real LLM should change at least one parameter when given a low emotion_alignment score."""` | line 2058 | line 217 | ✓ 字面匹配 |
| `from src_next.critic.tts_repair import TTSRepairAgent` | line 2059 | line 218 | ✓ 字面匹配 |
| `_make_inputs(parameters={"instruction": "平稳叙述", "speed": 1.0})` | line 2061-2063 | line 220-222 | ✓ 字面匹配 |
| `agent = TTSRepairAgent(llm_client=real_llm)` | line 2065 | line 224 | ✓ 字面匹配 |
| 5 个 immutable 断言（segment_id=="s1" / speaker=="narrator" / text=="窗外下着大雨。" / model=="S2Pro" / voice_ref==inst.voice_ref）+ attempt==2 | line 2070-2075 | line 229-234 | ✓ 字面匹配 |
| `changed_keys` 推导式 `result.parameters[k] != inst.parameters.get(k)` | line 2078-2081 | line 237-240 | ✓ 字面匹配 |
| `assert len(changed_keys) > 0, (\n    f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"\n)` | line 2082-2084 | line 241-243 | ✓ 字面匹配 |

**字面量比对结果：plan §Task 12 Step 1 整段 42 行代码作为子串原样追加到 test 文件末尾（line 202-243），逐行 Grep 命中位置与 plan 字面行号偏移 -160（plan line 2042-2085 → 实际 line 202-243，因为 test 文件已有 line 1-201 顶层内容），0 字符偏离 / 0 行重排序 / 0 类型注解添加。**

### 4.2 文件 scope 核对

| 文件 | Plan 期望操作 | judge `git diff main...HEAD` 实测 | 状态 |
|---|---|---|---|
| `src_next/critic/tests/test_tts_repair.py` | Modify（追加 integration 测试） | `243 +++`（Task 11 之后新增 +44 行：42 行 plan 字面量 + 1 衔接空行 + 1 文件末换行） | PASS |

**`git diff main...HEAD -- src_next/critic/` 整个 critic/ 目录共 11 个文件 / 1356 insertions / 0 deletions：**

```
src_next/critic/KNOWN_ISSUES.md                |  72 +++++
src_next/critic/__init__.py                    |   1 +
src_next/critic/prompts/__init__.py            |   1 +
src_next/critic/prompts/critic_prompt.py       | 203 +++++++++++++
src_next/critic/prompts/repair_prompt.py       |  89 ++++++
src_next/critic/qwen3omni_critic.py            | 196 +++++++++++++
src_next/critic/tests/__init__.py              |   1 +
src_next/critic/tests/conftest.py              |  78 +++++
src_next/critic/tests/test_qwen3omni_critic.py | 381 +++++++++++++++++++++++++
src_next/critic/tests/test_tts_repair.py       | 243 ++++++++++++++++
src_next/critic/tts_repair.py                  |  91 ++++++
11 files changed, 1356 insertions(+)
```

> 本 task commit `8d0278d` 只动 2 个文件（`docs/critic_task12_coding.md` + `src_next/critic/tests/test_tts_repair.py`），其它 9 个 critic/ 文件是 Task 1-11 累积已落盘的（详见 §6.3 commit 链）。本 task 未越界动任何其它文件。

---

## 5. 偏离登记

| 项 | Plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 测试代码块字面量 | 逐字一致 | 42 行子串原样出现，line 202-243 与 plan line 2042-2085 字面逐字一致 | 无 | — |
| Step 2 测试结果 | plan line 2090 `8 PASS + 1 SKIPPED` | 实测 `8 passed, 1 skipped in 0.02s` | 无 | — |
| pytest SKIPPED 报行号 | plan 未指定 | 实测报 line 214（`@pytest.mark.skip` 装饰器位置），def 在 line 216 | 无 | pytest 9.x 行为：skip 报装饰器位置不报 def 位置，不影响功能 |
| 衔接空行 | plan 未指定 | 实测在 Task 11 末尾内容（line 201 测试结束）与本 task line 202 `# ───` 注释之间自动衔接（无显式空行，因为 Task 11 末尾测试函数已有 1 行空行收尾） | 无 | 符合 PEP 8 顶层分隔，pytest 收集不受影响（9 items collected） |
| commit message 字面量 | plan line 2096 `test(critic): add repair integration test skeleton (skip-marked)` | `git show 8d0278d` 标题完全字面一致 | 无 | — |
| commit 类型 | plan 隐含（Step 3 字面 commit message） | `test(critic):`（与 Task 7/8/9 一致，纯测试追加不动业务代码） | 无 | — |

**无结构性偏离。** 1 个代码文件 42 行与 plan 字面量子串 BYTE-EQUAL，0 行重排序、0 字符差异。Step 2 实测与 plan 字面期望完全一致。

---

## 6. Red Flags 排查 + 实测输出

### 6.1 A.1 实测输出（judge 自己跑，未抄 coding doc）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
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
======================== 8 passed, 1 skipped in 0.02s =========================
```

→ 与 plan §Task 12 Acceptance A 第 1 条字面期望 `8 passed + 1 skipped` 完全一致。

### 6.2 A.2 实测输出（`-m integration` 确认 skip 状态）

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

→ 与 plan §Task 12 Acceptance A 第 2 条字面期望 `1 skipped（确认 skip 状态）` 完全一致。

### 6.3 commit 链（验证 Task 11 前置 + Task 12 commit 落盘）

```
$ git log --oneline -5
8d0278d test(critic): add repair integration test skeleton (skip-marked)
dec44dc chore: untrack 2 stale output/analysis md files
f6f3ef4 feat(critic): implement task 11 (round 1)
4818b21 chore: 更新 .gitignore，忽略 output 里的 md 文件
790906a feat(critic): implement task 10 (round 1)
```

→ Task 12 commit `8d0278d` 在 HEAD，前置 Task 11 commit `f6f3ef4` 已落盘（中间 `dec44dc` 是与本 task 无关的 chore commit，不影响）。

### 6.4 Task 12 commit scope（`git show --stat 8d0278d`）

```
commit 8d0278df79e04b822d41df3d1484d6889d4e25e0
Author: l30083418 <l300834181@h-partners.com>
Date:   Wed Jul 8 16:08:10 2026 +0800

    test(critic): add repair integration test skeleton (skip-marked)

 docs/critic_task12_coding.md             | 494 +++++++++++++++++++++++++++++++
 src_next/critic/tests/test_tts_repair.py |  44 +++
 2 files changed, 538 insertions(+)
```

→ scope clean：只 2 个文件（1 个测试 + 1 个 dev doc），test 文件 +44 行（42 行 plan 字面量 + 1 衔接空行 + 1 文件末换行），无越界。

### 6.5 Red Flags 排查清单（CLAUDE.md §9 硬约束 + plan §Task 12 line 2147-2150）

| Red flag | 自检 | 状态 |
|---|---|---|
| 漏 `@pytest.mark.skip`（会在 CI FAIL） | Grep line 215 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 齐备 + §6.2 实测 1 skipped | ✓ 未犯 |
| 只查「至少一个字段变了」不查 immutable 字段（漏 schema-frozen） | Grep `assert result\.` line 229-234 有 6 个 immutable 字段断言（segment_id / speaker / text / model / voice_ref / attempt） | ✓ 未犯 |
| 用 mock LLM 而非 `real_llm` fixture（不是 integration 测试） | Grep line 216 `def test_repair_with_real_llm_adjusts_parameters(real_llm):` + line 224 `TTSRepairAgent(llm_client=real_llm)`，未用 `_FakeLLMClient` | ✓ 未犯 |
| 改 `src/` 旧链路 | `git diff main...HEAD -- src/` 无任何变更（critic/ 都在 src_next/） | ✓ 未犯 |
| 改 `requirements.txt` | `git diff main...HEAD -- requirements.txt` 无变更 | ✓ 未犯 |
| 硬编码服务器地址 | 测试代码无硬编码地址（用 `real_llm` fixture，地址走 conftest.py + profile） | ✓ 未犯 |
| `--no-verify` 跳 hooks | commit message 未见 `--no-verify`，git log 正常落盘 | ✓ 未犯 |
| scope creep（动业务代码） | `git show 8d0278d --stat` 只 2 个文件（测试 + dev doc），未动 `tts_repair.py` / `repair_prompt.py` / `qwen3omni_critic.py` 等业务代码 | ✓ 未犯 |

**8/8 Red flag 全避。**

### 6.6 Scope creep 检查（plan §1.2 「不交付」清单）

| 不交付项 | 实测 | 状态 |
|---|---|---|
| Task 13 `py_compile` 全文件验证 | 本 task 未做（属 Task 13 范畴） | ✓ |
| Task 14 `pytest -m "not integration"` 全绿 | 本 task 未做（属 Task 14 范畴） | ✓ |
| Task 15 `docs/pr_samples/critic_sample.md` mock I/O 样例 | 本 task 未做（属 Task 15 范畴） | ✓ |
| Task 16 PR 创建 + push | 本 task 未做（属 Task 16 范畴，push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理） | ✓ |
| 启用 integration 测试（删 `@pytest.mark.skip`） | 未删，line 215 装饰器仍在（这是 judge-Agent 在服务可用环境里的动作，不在本 coding task 范围） | ✓ |
| 动业务代码（`tts_repair.py` / `repair_prompt.py` / `qwen3omni_critic.py`） | `git show 8d0278d --stat` 只动测试 + dev doc | ✓ |

**6/6 scope creep 全避。**

---

## 7. Verdict JSON

```json
{
  "task_id": "task-12",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_tts_repair.py -v",
      "python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v",
      "python -m py_compile src_next/critic/tests/test_tts_repair.py"
    ],
    "result": "8 passed, 1 skipped (A.1) + 1 skipped, 8 deselected (A.2) + py_compile OK；与 plan §Task 12 Acceptance A 字面期望完全一致"
  },
  "integration_tests": "N/A（plan §Task 12 Acceptance B 第 3 条「启用后跑」需 LLM 服务可用 + CRITIC_TEST_LLM_PROFILE 环境变量，本 round mock 阶段不跑）",
  "smoke_tests": "N/A（本 task 不动业务代码，无 pipeline smoke test 需求）",
  "static_review": {
    "section_b_static_checks_passed": "6/6",
    "contracts_passed": "2/2",
    "red_flags_avoided": "3/3 + 5/5（CLAUDE.md §9 硬约束）",
    "scope_creep_avoided": "6/6",
    "literal_byte_equal": true,
    "literal_match_count": "13/13 关键字面量逐字匹配（§4.1）",
    "commit_scope_files": 2,
    "commit_message_literal_match": true
  },
  "reason": "skip-marked integration 测试骨架已就位且与 plan §Task 12 Step 1 字面量 BYTE-EQUAL，Section A 4/4 + Section B 6/6 + 契约 2/2 + Red flags 3/3 全过，commit scope clean",
  "blocking_issues": [],
  "next_action": "进入 Task 13（py_compile 全文件验证 + critic/ 文件计数 ≥ 8）。push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理（不要在本 judge 流程里 push）。"
}
```

---

## 8. 给后续 task 的提醒

### 8.1 给 Task 13 的提醒

- **Task 13 范围（plan line 2163-2204）：** 跑 `python -m py_compile` 验证 critic 模块所有 .py 文件 + 跑 `git diff --name-only main...HEAD -- src_next/critic/` 验证文件清单 ≥ 8
- **本 task 后 critic/ 文件清单（共 11 个 .py）：** KNOWN_ISSUES.md（不算 .py）+ `__init__.py` / `prompts/__init__.py` / `prompts/critic_prompt.py` / `prompts/repair_prompt.py` / `qwen3omni_critic.py` / `tests/__init__.py` / `tests/conftest.py` / `tests/test_qwen3omni_critic.py` / `tests/test_tts_repair.py` / `tts_repair.py` = 10 个 .py 文件（≥ 8 ✓）
- **`test_tts_repair.py` 终态：** 243 行（Task 11 的 199 + 本 task 追加 44）
- **Task 13 不改动任何代码** — 纯验证型 task

### 8.2 给 Task 14 的提醒

- **Task 14 范围（plan line 2238-2259）：**
  - `python -m pytest src_next/critic/tests/ -m "not integration" -v` 期望 15 passed
  - `python -m pytest src_next/critic/tests/ -m integration -v` 期望 **5 skipped**（4 critic integration + 1 repair integration = 5，本 task 的 repair integration 是第 5 个）
- **本 task 已交付第 5 个 integration 测试** — Task 14 验收「5 skipped」依赖本 task
- **`-m "not integration"` 应得 15 passed：** test_qwen3omni_critic.py（7 个 mock 测试）+ test_tts_repair.py（8 个 mock 测试）= 15，integration 全 deselect

### 8.3 给 Task 16 的提醒

- **Task 16 范围（plan line 2408-2508）：** 写 PR description + push branch
- **push 前提醒：** 本 task commit 后工作区还有 untracked 文件（`docs/critic_task*_judging.md` × 4 / `docs/intern_b_*.md` × 3 / `docs/superpowers/specs/2026-07-*.md` × 3 / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `webui_old.py`）— push 前应用 push-with-output-ignore skill 处理 .gitignore

### 8.4 给本仓库未来 critic task 的提醒

- **整合 `test(critic):` commit 类型规则：** 凡是只动测试文件（追加 / 修改测试）+ dev doc、不动业务代码的 task，commit message 类型用 `test(critic):`（不用 `feat(critic):`）；动业务代码（如 `tts_repair.py` / `qwen3omni_critic.py`）才用 `feat(critic):`。Task 7/8/9/12 用 `test(critic):`，Task 10/11 用 `feat(critic):`，符合 Conventional Commits 语义
- **integration 测试骨架追加套路：** 1 个 commit 含「测试骨架 + dev doc」（不要分 2 个 commit），与 plan §Task X Step 3 字面 commit message 一致；不要 `git add -A`（工作区有大量无关 untracked）

---

## 9. 一句话总结

Task 12 = plan Day 2 收口：在 `src_next/critic/tests/test_tts_repair.py` 末尾追加 1 个 skip-marked integration 测试 `test_repair_with_real_llm_adjusts_parameters`（42 行，与 plan §Task 12 Step 1 字面量逐字一致），judge 自己跑 Section A 实测 **8 passed + 1 skipped** 与 plan 字面期望完全一致，Section B 静态审查 6/6 + 契约 2/2 + Red flags 3/3 + CLAUDE.md §9 硬约束 5/5 + scope creep 6/6 全过，commit `8d0278d` scope clean（只 2 个文件、`test(critic):` 类型、message 字面匹配）。**建议 PASS（mock 阶段）**。
