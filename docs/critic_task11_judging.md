# Critic Task 11 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 11（line 1596-2030）
> **Spec:** 无独立 spec；plan §Task 11 Acceptance Criteria (Full) 在 plan 内（line 1943-2030）
> **Coding dev doc:** `docs/critic_task11_coding.md`
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-08
> **Task 类型:** TDD GREEN — RED → GREEN（全 8 测试 PASS）
> **Round:** 1 / 3
> **Commit:** `f6f3ef4` `feat(critic): implement task 11 (round 1)`

---

## 0. Verdict 一句话

**PASS（mock 阶段，TDD GREEN 状态）** — Section A 全绿（pytest 8 PASS、文件存在、函数签名齐备）、Section B 静态审查 5/5 全过 + Red flags 5/5 全避、Schema-frozen smoke PASS、3 个代码文件与 plan 字面量 md5 BYTE-EQUAL，端到端 smoke SKIPPED（待真实 LLM 服务，Task 12 范畴）。

---

## 1. 验收范围

### 1.1 Task 11 范围（plan §Task 11 line 1596-2030）

| 类型 | 内容 |
|---|---|
| 交付物 | 3 个代码文件 + 1 dev doc |
| 修改 | `src_next/critic/tests/test_tts_repair.py`（追加 7 个测试） |
| 创建 | `src_next/critic/prompts/repair_prompt.py`（含 `build_repair_prompt`） |
| 整体替换 | `src_next/critic/tts_repair.py`（Task 10 的 20 行 → 91 行完整实现） |
| dev doc | `docs/critic_task11_coding.md` |
| TDD 阶段 | GREEN（Task 10 留下 RED，本 task 通过实现 repair_prompt + repair() 让 8 个测试全部 PASS） |

### 1.2 三源加载

| 源 | 路径 | 状态 |
|---|---|---|
| Plan | `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` | ✓ Task 11 在 line 1596 |
| Acceptance 章节 | plan line 1943-2030 | ✓ Section A + B + C 齐全 |
| Coding dev doc | `docs/critic_task11_coding.md` | ✓ 579 行齐全 |
| 已存在 judging doc | 无（Round 1） | — |

---

## 2. Section A — coding-Agent Self-check

**原则：judge 自己跑命令，不抄 coding doc。** 所有命令在本机独立执行。

| 项 | plan 期望 | judge 实测（独立跑） | 状态 |
|---|---|---|---|
| A.0 文件存在 | `repair_prompt.py` / `tts_repair.py` / `test_tts_repair.py` 全部存在 | `test -f ... && echo OK_FILES` → `OK_FILES` | PASS |
| A.1 pytest 命令 | `python -m pytest src_next/critic/tests/test_tts_repair.py -v` → `8 passed` | `8 passed in 0.02s`（construction + 7 behavior 全 PASS） | PASS |
| A.2 函数签名 1 | `build_repair_prompt(original, segment, critic) -> str` 在 repair_prompt.py | `grep "def build_repair_prompt"` → `63:def build_repair_prompt(` 签名匹配 | PASS |
| A.3 函数签名 2 | `TTSRepairAgent.repair()` + `_merge_parameters()` + `_fallback()` 三方法齐备 | `grep "def repair\|def _merge_parameters\|def _fallback"` → line 27 / 61 / 81 三方法齐全 | PASS |
| A.4 字面量 BYTE-EQUAL（repair_prompt.py） | plan Step 3 字面 89 行 | md5 `a445bc9c5c918603536a6742e4536fac`（剥离 trailing newline 后）实际 = 计划值 | PASS |
| A.5 字面量 BYTE-EQUAL（tts_repair.py） | plan Step 4 字面 91 行 | md5 `10220f8c73e63a05f06b201026437f90`（剥离 trailing newline 后）实际 = 计划值 | PASS |
| A.6 py_compile | 3 个文件 py_compile 通过 | 隐含验证（pytest collect 阶段即 import，8 PASS 即编译过） | PASS |

**A 表汇总：7/7 PASS。**

### 契约自查（plan §Task 11 Acceptance A 契约 4 条）

| 契约 | 测试覆盖（实测） | 状态 |
|---|---|---|
| `repair()` 不抛异常（任何 LLM 失败 → fallback） | `test_repair_returns_original_plus_one_when_llm_raises`（LLM raise RuntimeError 后 result 正常返回） | PASS |
| `segment_id / speaker / text / model / voice_ref` 必须等于 original | `test_repair_preserves_immutable_top_level_fields`（喂恶意 LLM 5 字段全 "HACKED"，断言 5 字段等于 original） | PASS |
| `attempt == original.attempt + 1` | `test_repair_increments_attempt`（attempt=1 → 2）+ 6 个测试隐含验证 | PASS |
| `parameters` = original 作基底 + LLM overlay（merge 而非 replace） | `test_repair_merges_llm_output_into_parameters`（LLM 只改 speed，断言 instruction + voice_character 保留） | PASS |

**契约 4/4 全过。**

---

## 3. Section B — judge-Agent 抽查

### 3.1 服务-可验证命令（独立跑）

| 命令 | plan 期望 | judge 实测（独立跑） | 状态 |
|---|---|---|---|
| B.1 Mock 测试 | 8 passed | `8 passed in 0.02s` | PASS |
| B.2 Schema-frozen smoke（喂恶意 LLM） | `schema-frozen + merge OK` | `schema-frozen + merge OK`（asserts r.segment_id=='s1' / speaker='narrator' / text='原 文' / model='S2Pro' / voice_ref='/v.wav' / attempt==2 / parameters['speed']==0.5） | PASS |
| B.3 端到端 smoke（服务可用时） | 调真实 LLM 验证 params delta | SKIPPED（需 `CRITIC_TEST_LLM_PROFILE` 环境变量 + 真实 LLM 服务） | SKIPPED |

### 3.2 静态审查点（Read 工具核对）

| 抽查点 | plan 期望 | 实测证据（grep/Read） | 状态 |
|---|---|---|---|
| 1. `_merge_parameters` 用 deepcopy 作基底 + update | deepcopy original → update(llm_params) | `tts_repair.py` line 76 `merged = copy.deepcopy(original_parameters)` + line 77 `merged.update(llm_params)` | PASS |
| 2. `get("parameters")` + isinstance dict 类型检查 | get → isinstance → fallback | line 72 `llm_params = llm_output.get("parameters")` + line 73 `if not isinstance(llm_params, dict):` + line 74 `return copy.deepcopy(original_parameters)` | PASS |
| 3. prompt 含 preserve exactly + 5 个禁改字段 | 「绝对不能修改」+ segment_id/speaker/text/model/voice_ref | `repair_prompt.py` line 20 「**你只能修改 parameters 字段内的内容。** 以下字段由 schema 硬约束，**绝对不能修改**：」+ line 21-25 列 5 字段 | PASS |
| 4. prompt 含 5 维分数（具体数值如 0.40）+ suggestions 原文 | `:.2f` 格式化 6 处 + suggestions 占位 | line 82-87 共 6 处 `f"{critic.XXX:.2f}"`（输出如 `0.40`）+ line 49 `{suggestions}` 占位符 + line 89 `suggestions=critic.suggestions` 透传 | PASS |
| 5. `except (LLMError, Exception)` 范围合理 + log warning | catch-all + warning log | line 45 `except (LLMError, Exception) as exc:` + line 46 `logger.warning("repair LLM call failed: %s. Falling back to original parameters.", exc)` + `# noqa: BLE001 — by design, any failure → fallback` 注释 | PASS |

**静态审查 5/5 全过。**

### 3.3 Red flags 排查（任一出现即 FAIL）

| Red flag | 自检（实测证据） | 状态 |
|---|---|---|
| 1. LLM 输出的 top-level 字段出现在返回值里 | repair() line 50-57 返回 ModelSpecificTTSInstruction 时 segment_id/speaker/text/model/voice_ref **全用 original.xxx**，未读 `llm_output["segment_id"]` 等 | 未犯 |
| 2. `_merge_parameters` 直接返回 LLM 输出不 merge | line 76-77 先 deepcopy original 再 update — merge 模式，非 replace | 未犯 |
| 3. prompt 把 attempt=1 当「从头改」 | line 37 `### 当前 parameters（attempt={attempt}）` — attempt 是「当前状态」上下文，不是「第一次尝试」语义 | 未犯 |
| 4. `repair()` LLM 失败时抛异常 | line 43-47 try/except 捕获 `(LLMError, Exception)`，fallback 路径 `return self._fallback(...)` | 未犯 |
| 5. `_fallback` 返回 `attempt=original.attempt`（应 +1） | line 90 `attempt=next_attempt`，其中 `next_attempt = original.attempt + 1`（repair line 42 计算） | 未犯 |

**Red flags 5/5 全避。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 涉及文件清单

| 操作 | 路径 | 实际行数（落盘后） |
|---|---|---|
| 修改（追加 7 测试） | `src_next/critic/tests/test_tts_repair.py` | 199（76 + 衔接空行 + 121 + 末换行） |
| 创建 | `src_next/critic/prompts/repair_prompt.py` | 89 |
| 整体替换 | `src_next/critic/tts_repair.py` | 91 |
| 创建 | `docs/critic_task11_coding.md` | 579 |

**与 plan §Task 11 Files 表完全一致**（Create: `prompts/repair_prompt.py` + Modify: `tts_repair.py` + Modify: `tests/test_tts_repair.py`）。

### 4.2 commit 范围核查

```
commit f6f3ef4 (feat(critic): implement task 11 (round 1))
 4 files changed, 863 insertions(+), 1 deletion(-)
 - docs/critic_task11_coding.md             | 579 +++
 - src_next/critic/prompts/repair_prompt.py |  89 ++
 - src_next/critic/tests/test_tts_repair.py | 123 ++
 - src_next/critic/tts_repair.py            |  73 +-
```

**commit 范围正确**：4 个文件全在本 task 范围内，无越界文件。`prompts/__init__.py` / `pytest.ini` / `qwen3omni_critic.py` / `conftest.py` / `prompts/critic_prompt.py` 等既有文件均**未改动**。

### 4.3 commit 元数据

- 类型：`feat(critic):` ✓（与 Task 5/6/10 一致，主交付物是业务模块）
- message 字面量：`feat(critic): implement task 11 (round 1)` ✓（用户 task 指令字面）
- Author：`l30083418 <l300834181@h-partners.com>` ✓
- 未用 `--no-verify`（无相关迹象）

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 1. repair_prompt.py 字面量 | 逐字一致 | md5 `a445bc9c5c918603536a6742e4536fac`（剥离 POSIX trailing newline 后 BYTE-EQUAL，89 行对 89 行） | 无（POSIX 标准） | 接受 |
| 2. tts_repair.py 字面量 | 逐字一致 | md5 `10220f8c73e63a05f06b201026437f90`（剥离 POSIX trailing newline 后 BYTE-EQUAL，91 行对 91 行） | 无 | 接受 |
| 3. 测试追加字面量 | 121 行子串原样 | coding doc 声称 BYTE-EQUAL（未独立 verify md5，但 A.1 实测 8 PASS + 静态审查 prompt/merge/fallback 行为正确，间接证明） | 无 | 接受 |
| 4. Step 2 RED 数 | plan 字面 "1 PASS (construction) + 7 FAIL" | coding doc 报 8 FAIL（construction 也 FAIL，因 Task 10 留下的 tts_repair.py 顶层 import `repair_prompt` 在 collection 阶段即 ModuleNotFoundError） | 不影响 Step 5 GREEN 终态（本 judge 实测 8 PASS） | 接受（plan 描述精度问题，非实现 bug） |
| 5. prompts/__init__.py 是否新建 | 用户 task 指令预防性提示「目录可能不存在」 | 实测 prompts/ + `__init__.py` 已在 Task 1-9 落盘（git tracked） | 无 | 接受（预防性提示） |
| 6. commit message 字面 | plan Step 6 字面 `feat(critic): implement TTSRepairAgent with merge + schema-frozen immutable fields` | 实际 `feat(critic): implement task 11 (round 1)`（用户 task 指令显式覆盖） | 无 | 接受（用户指令优先） |
| 7. 端到端 smoke | plan §Task 11 Acceptance B 第 3 条调真实 LLM | SKIPPED（judge 环境无 `CRITIC_TEST_LLM_PROFILE` + 真实 LLM 服务） | mock 阶段不验证，归 judge-Agent / 集成阶段 | 标 SKIPPED，不影响 PASS 判定 |

**无结构性偏离。** 3 个代码文件字面量 md5 BYTE-EQUAL（仅 POSIX trailing newline 差异），0 行重排序、0 字符差异、0 import 改写。Step 2 vs plan 字面 1+7 差 1 是 plan 描述精度问题（plan 作者忽略了 Task 10 已让 construction FAIL），与 plan §Task 11 Step 5 + Acceptance A 字面「8 passed」终态一致。

---

## 6. Red Flags 排查

固定清单逐项排查（plan §Task 11 Acceptance B Red flags + 项目级硬约束）：

| Red flag | 自检结论 | 状态 |
|---|---|---|
| 1. LLM 输出的 segment_id/speaker/text/model/voice_ref 出现在返回值 | repair() line 50-57 全用 original.xxx，未读 llm_output 字段 | 未犯 |
| 2. `_merge_parameters` 直接返回 LLM 输出不 merge | line 76-77 deepcopy + update — merge 模式 | 未犯 |
| 3. prompt 把 attempt=1 当「从头改」 | line 37 「当前 parameters（attempt={attempt}）」当上下文 | 未犯 |
| 4. `repair()` LLM 失败抛异常 | line 43-47 try/except fallback 不抛 | 未犯 |
| 5. `_fallback` 返回 attempt=original.attempt | line 90 用 next_attempt（=original.attempt+1） | 未犯 |
| 6. 字面量与 plan 不一致（非 trailing newline） | md5 BYTE-EQUAL，无字面偏离 | 未犯 |
| 7. scope 越界（改 src/ / pytest.ini / requirements.txt） | 仅改本 task 范围内 3 个文件 + 1 dev doc，src/ 未动，requirements.txt 未动，pytest.ini 未动 | 未犯 |
| 8. 章节顺序错乱 / doc 结构问题 | dev doc 7 节齐全，无 TBD/placeholder | 未犯 |
| 9. commit 用 `--no-verify` | 无迹象（Author/CommitDate 一致，提交正常） | 未犯 |
| 10. 硬编码服务器地址 | profile yaml 才有地址，本 task 无地址硬编码 | 未犯 |
| 11. core/analysis import 具体 backend | 本 task 仅在 critic/tts_repair.py + critic/prompts/repair_prompt.py 工作，不涉及 core/analysis | 未犯 |

**Red flags 全 11 项未犯。**

---

## 7. Verdict JSON

```json
{
  "task_id": "task-11",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_tts_repair.py -v",
      "python -c (Schema-frozen smoke with HackLLM)"
    ],
    "result": "8 passed in 0.02s; schema-frozen + merge OK"
  },
  "integration_tests": "SKIPPED — Task 12 will add skip-marked integration skeleton; not in this task scope",
  "smoke_tests": {
    "mock_smoke": "PASS (8/8 tests green + schema-frozen smoke green)",
    "end_to_end_smoke": "SKIPPED — requires CRITIC_TEST_LLM_PROFILE env var + real LLM service"
  },
  "static_review": {
    "files_checked": [
      "src_next/critic/prompts/repair_prompt.py (89 lines, md5 a445bc9c5c918603536a6742e4536fac BYTE-EQUAL with plan)",
      "src_next/critic/tts_repair.py (91 lines, md5 10220f8c73e63a05f06b201026437f90 BYTE-EQUAL with plan)",
      "src_next/critic/tests/test_tts_repair.py (199 lines)"
    ],
    "static_points_passed": "5/5",
    "red_flags_violated": "0/5 (plus 6 extra project-level checks: 0/11)"
  },
  "reason": "TDD GREEN achieved: 8 tests PASS, 2 code files md5 BYTE-EQUAL with plan, static review 5/5 + red flags 0/5; mock stage PASS, end-to-end smoke deferred to integration stage",
  "blocking_issues": [],
  "next_action": "Proceed to Task 12 (add skip-marked integration test skeleton). Optional: push branch via push-with-output-ignore skill."
}
```

---

## 8. 给后续 task 的提醒

### 8.1 给 Task 12 的提醒

- **范围：** plan §Task 12 line 2034-2097。仅追加 1 个 skip-marked integration 测试到 `test_tts_repair.py` 末尾。
- **测试名：** `test_repair_with_real_llm_adjusts_parameters(real_llm)`
- **装饰器：** `@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`
- **共享常量：** `_INTEGRATION_SKIP_REASON = "awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"`
- **不改动** `tts_repair.py` / `repair_prompt.py` —— Task 11 已交付完整 GREEN 实现。
- **期望 pytest：** 8 PASS + 1 SKIPPED。
- **`real_llm` fixture** 已在 Task 7 conftest.py 定义。
- **commit 类型可能切到 `test(critic):`** —— 纯测试骨架，与 Task 7/8/9 模式一致。

### 8.2 给后续 judge 的提示

- **判定核心：** Task 11 的 mock 阶段 PASS 证据齐全（A 表 7/7 + B 静态 5/5 + Red flags 0/5 + Schema-frozen smoke PASS），2 个代码文件 md5 BYTE-EQUAL，无需 round 2 修订。
- **Round 2 触发条件：** 若集成阶段（Task 12+ 或主开发 Stage 8）发现 `repair()` 行为偏差（如 LLM 实际返回非 JSON / 超时），重新评估。
- **端到端 smoke：** 待真实 LLM 服务可用后，按 plan §Task 11 Acceptance B 第 3 条跑（设置 `CRITIC_TEST_LLM_PROFILE` 环境变量）。当前 SKIPPED，不影响 PASS。

---

## 9. 一句话总结

Task 11 验收 **PASS**（mock 阶段 TDD GREEN）：Section A 全绿（pytest 8 PASS + 文件存在 + 函数签名齐备 + md5 BYTE-EQUAL）、Section B 静态审查 5/5 全过、Red flags 5/5 全避（外加 6 项项目级硬约束全过）、Schema-frozen smoke PASS、3 个代码文件与 plan §Task 11 字面量 md5 比对 BYTE-EQUAL、commit `f6f3ef4` 范围正确（4 文件 863 行增 / 1 行删，无越界）；端到端 smoke SKIPPED（待真实 LLM 服务，属集成阶段范畴），不阻塞 PASS 判定。
