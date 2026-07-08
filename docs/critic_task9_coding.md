# Critic Task 9 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 9（第 1288 行起）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 9 沿用 plan §Task 9 Acceptance Criteria Full）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** 测试代码型（追加 skip-marked integration 测试骨架，不动业务代码）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan §Task 9 要求，**修改** `src_next/critic/tests/test_qwen3omni_critic.py`：在文件末尾追加 4 个 skip-marked integration 测试（`test_critic_high_quality_audio_scores_high` / `test_critic_low_quality_audio_scores_low` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment`）+ 1 个共享常量 `_INTEGRATION_SKIP_REASON` + 顶部 3 行分隔注释。本 task 不动业务代码，只扩测试骨架，与 Task 7 已落盘的 `conftest.py` fixture（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav`）配套，等 Qwen3-Omni 服务可访问后只需删除 `@pytest.mark.skip` 行即可激活。

> Plan 原文 Task 9 标题：**Write integration test skeletons (skip-marked, ready for future activation)**。Step 2 期望 `pytest -v` "7 PASS + 4 SKIPPED"，但实测 **9 passed + 4 skipped** —— 见 §6.1 偏离登记：plan 作者预设 Task 6 只交付 3 个测试，但 Task 6 实际交付 5 个测试（Task 8 已记录同一偏离），所以基线是 5 + 4 (Task 8 robustness) = 9，加本 task 4 个 skip = 9 passed + 4 skipped。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 修改 | `src_next/critic/tests/test_qwen3omni_critic.py` | 追加 plan line 1299-1364 完整 Python 代码块（66 行，逐字粘贴，md5 比对 BYTE-EQUAL，0 字符偏离） |
| 创建 | `docs/critic_task9_coding.md` | 本文件，按 `docs/critic_task8_coding.md` 同样结构写 |

### 1.2 不交付（属于后续 task）

- `fixtures/` 目录的 3 段测试音频（KNOWN_ISSUES.md §3 标注"服务可访问后准备"——4 个 integration 测试 skip 阶段不需要真实音频，只引用 fixture 路径字符串）
- TTSRepairAgent（Task 10/11）
- `test_tts_repair.py`（Task 10 起）
- KNOWN_ISSUES.md §1 启用条件本身（plan 文档体系在 Task 1-3 阶段已落盘）

### 1.3 前置条件（Task 1-8 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 8 commit `1d655b4`（4 个 robustness 测试已落盘）已落盘 | §4.4 git log | ✓ |
| Task 7 commit `0e74e9b`（conftest.py + 3 fixture audio 路径 + `real_critic` / `*_wav` fixture 名固化）已落盘 | §4.5 grep conftest.py fixture 名 | ✓ |
| `pytest.ini` 注册了 `integration` mark（避免 unknown marker warning） | §4.6 grep `pytest.ini` | ✓ |
| `_make_segment_and_instruction` helper 已存在于测试文件（Task 5 加） | §4.5 grep 命中 line 23 | ✓ |

> **关键：** 本 task 4 个 integration 测试全部依赖 conftest 的 4 个 fixture（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav`），fixture 名必须在 conftest.py 中已定义——本 task 实测 conftest.py line 18-47 已定义全部 4 个，无 fixture 缺失。若 conftest 未定义则 collection 阶段会 ERROR（不是 SKIP），本 task 不会触发。

---

## 2. 执行步骤（按 plan §Task 9 Step 1 → 3）

### Step 1: Append skip-marked integration tests for all 3 cases + sorting

**字面量来源：** plan §Task 9 Step 1 给出完整 Python 代码块（line 1299-1364，共 66 行，含 markdown fence 上下行），**逐字粘贴**到 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾（在 Task 8 robustness 测试末尾之后，加 2 个空行分隔）。

**字面量校验方法：** Python 脚本抽取 plan line 1299-1364（0-indexed `lines[1298:1364]`）+ 测试文件中从顶部 `# ────────...` 分隔注释起到文件末尾的内容，对两端做 md5 比对，实测：

```
plan md5:    96f34b90943113957a1f12e1bd72d4e9
append md5:  96f34b90943113957a1f12e1bd72d4e9
→ BYTE-EQUAL（rstrip 后 66 行对 66 行）
```

0 行重排序 / 0 字符差异 / 0 import 改写 / 0 类型注解添加 / 0 断言改写。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **4 个测试覆盖 3 类音频 + 1 个排序：**
   - `test_critic_high_quality_audio_scores_high`：good_narration.wav 应得 quality ≥ 0.7 且 intelligibility ≥ 0.7（绝对阈值，给 LLM 留主观空间，不用 `> 0.9`）
   - `test_critic_low_quality_audio_scores_low`：bad_clipping.wav 应得 quality < 0.6（用 `< 0.6` 而不是 `< 0.5`，避免与 neutral fallback 0.5 混淆——若 critic 退化到 neutral 会正好 0.5 通过 `< 0.5` 但通过不了 `< 0.6`，所以这里更严苛）
   - `test_critic_sorting_good_higher_than_bad`：相对排序断言（`good.quality > bad.quality` 且 `good.overall > bad.overall`），避免 LLM 评分漂移导致绝对阈值测试 flaky
   - `test_critic_emotion_mismatch_scores_low_alignment`：用强对比 prompt `极度悲伤，哭泣感` 而不是弱对比 `略带忧伤`，让 emotion_alignment < 0.6 断言更稳定
2. **共享常量 `_INTEGRATION_SKIP_REASON`**（plan line 1303-1305）：
   - 抽出单一字符串常量：`"awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1"`
   - 4 个测试全部 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 引用此常量，不重复硬编码（plan §Task 9 Acceptance Red flags 第 2 条："skip reason 写死字符串而不是用 `_INTEGRATION_SKIP_REASON` 常量"会 FAIL）
   - 字符串内容引用 `KNOWN_ISSUES.md §1`，方便启用时 grep 交叉查找
3. **每个测试两个装饰器叠加**（plan §Task 9 Acceptance 契约第 1 条）：
   - `@pytest.mark.integration`：标记为 integration 类别（`pytest.ini` 已注册，可用 `-m integration` / `-m "not integration"` 筛选）
   - `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`：直接跳过（不依赖环境变量 / fixture 检测），启用时只需全局搜索删除 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 一行
   - 顺序：`@pytest.mark.integration` 在外，`@pytest.mark.skip` 在内（与 plan 字面量一致；顺序对 skip 行为无影响，但保持字面量一致性便于 judge 静态审查）
4. **顶部 3 行分隔注释**（plan line 1299-1301）：`# ────────...` + `# Integration tests — skip-marked. See KNOWN_ISSUES.md §1 to activate.` + `# ────────...`，让代码视觉上隔离 unit 测试和 integration 测试
5. **复用 `_make_segment_and_instruction`**（Task 5 line 23-38 加的 helper）作为输入构造器——4 个测试都 `seg, inst = _make_segment_and_instruction()`，不重新写 helper（与 plan 字面量一致）
6. **测试 1 和测试 4 修改 `inst.parameters`**：测试 1 改为 `{"instruction": "平稳叙述"}`（弱情绪 prompt，good_narration 应匹配）；测试 4 改为 `{"instruction": "极度悲伤，哭泣感"}`（强情绪 prompt，neutral-tone 音频应严重不匹配）。测试 2 和测试 3 不改 parameters（沿用 helper 默认值 `平稳叙述，略带忧伤`），因为测试 2 只测低质量音频的 quality 不测 emotion，测试 3 是相对排序两边用同一 prompt 公平
7. **断言使用范围比较 / 不等式比较，不用 `==`**（plan §Task 9 Acceptance Red flags 第 3 条："断言用 `==` 而不是范围比较"会 FAIL——LLM 不会稳定输出固定值）。具体：
   - 测试 1：`0.0 <= result.quality <= 1.0` + `result.quality >= 0.7` + `result.intelligibility >= 0.7`（范围 + 下界）
   - 测试 2：`result.quality < 0.6`（上界）
   - 测试 3：`good_result.quality > bad_result.quality` + `good_result.overall > bad_result.overall`（相对排序，两个维度都断言）
   - 测试 4：`result.emotion_alignment < 0.6`（上界）

### Step 2: Verify the tests collect and are skip-marked (not failed)

**命令 1：** `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v`

**Plan 期望（字面）：** 7 PASS + 4 SKIPPED（4 skipped 显示 `_INTEGRATION_SKIP_REASON`）

**实测：** **9 passed + 4 skipped in 0.12s** —— 见 §4.1 实测输出。原因详见 §6.1 偏离登记（与 Task 8 同一偏离根源：plan 作者假设 Task 6 只交付 3 个测试，但 Task 6 实际交付 5 个，Task 8 又加了 4 个 robustness，所以基线已是 9）。本 task 4 个新 integration 测试**全部 SKIPPED**（不是 FAILED / 不是 ERROR），达到 plan §Task 9 Acceptance A "Self-check 命令本机可跑"的实质要求（"7 PASS + 4 SKIPPED"是 plan 数错基线，不是测试本身的问题）。4 个 skipped 的 reason 全部是 `awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1`。

**命令 2（额外验证，plan §Task 9 Acceptance A Self-check 第 2 条）：** `python -m pytest src_next/critic/tests/ -m integration -v`

**实测：** 4 skipped, 9 deselected —— 全部 integration 标记测试 skip，无意外 FAIL（plan 字面期望一致）。详见 §4.2。

### Step 3: Commit

按用户 task 指令收尾 commit。Plan §Task 9 Step 3 字面 commit message `test(critic): add 4 integration test skeletons (skip-marked, pending service access)`，用户 task 指令指定 commit message `test(critic): add 4 integration test skeletons (task 9, round 1)`——以用户 task 指令为准（用户指令优先级 > plan 字面量），但**注意是 `test(critic):` 而不是 `feat(critic):`**——与 Task 7 / Task 8 同属测试代码，延续 `test(critic):` 前缀。详见 §5 提交策略。

---

## 3. Acceptance Criteria 自检

按 plan §Task 9 Acceptance Criteria (Full) 结构对照。

### A. coding-Agent 完成定义（mock-可验证）

**产出物:**

| 检查项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| 4 个新 integration 测试存在 | `test_critic_high_quality_audio_scores_high` / `test_critic_low_quality_audio_scores_low` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment` | §4.3 B1 grep 命中 4 个 `def test_critic_*` | ✓ |
| 共享常量 `_INTEGRATION_SKIP_REASON` 提取出来 | 单一定义，4 处引用 | §4.3 B4 grep `_INTEGRATION_SKIP_REASON` 命中 1 处定义 + 4 处 `@pytest.mark.skip(reason=...)` 引用 | ✓ |
| `pytest -v` 全绿 + 4 skip | plan 字面 "7 PASS + 4 SKIPPED"（plan 假设基线 3，但实际基线 9） | §4.1 实测 `9 passed, 4 skipped in 0.12s` | ✓（数量偏离见 §6.1） |
| `-m integration` 单独跑全 skip | plan §Task 9 A Self-check 第 2 条 "4 skipped" | §4.2 实测 `4 skipped, 9 deselected in 0.02s` | ✓ |

**契约:**

| 契约 | 实测 | 状态 |
|---|---|---|
| 每个 integration 测试同时有 `@pytest.mark.integration` **和** `@pytest.mark.skip(reason=...)` 两个装饰器 | 4 个测试都含 2 行装饰器（line 324-325 / 341-342 / 350-351 / 369-370） | ✓ |
| skip reason 文字与 KNOWN_ISSUES.md §1 启用条件互相引用 | `_INTEGRATION_SKIP_REASON` 字符串内含 `KNOWN_ISSUES.md §1`，顶部注释也含 `KNOWN_ISSUES.md §1` | ✓ |

**A 表全过。**

### B. judge-Agent 验证（在可访问服务的环境里跑）

> 本 round 1 是 mock 阶段，judge-Agent 不需跑真实服务 smoke（plan §Task 9 B 启用 integration 测试需要服务可用 + 3 个 fixture 音频，本机无服务 / 无音频）。本 task coding-Agent 只交付 skip-marked 骨架。

**静态审查点（LLM 读代码判断）:**

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| 4 个测试断言相对排序（`good > bad`）而不仅是绝对阈值 | 测试 3 `test_critic_sorting_good_higher_than_bad` 同时断言 `good_result.quality > bad_result.quality` + `good_result.overall > bad_result.overall`（line 358-361） | ✓ |
| 高质量音频的断言阈值合理（`>= 0.7` 不是 `> 0.9`） | 测试 1 line 332-333 用 `result.quality >= 0.7` + `result.intelligibility >= 0.7`，留出 LLM 主观空间 | ✓ |
| 低质量音频的断言用 `< 0.6` 而不是 `< 0.5` | 测试 2 line 344 `assert result.quality < 0.6`（不是 `< 0.5`） | ✓ |
| emotion_mismatch 测试用「极度悲伤，哭泣感」这种强对比 prompt | 测试 4 line 373 `inst.parameters = {"instruction": "极度悲伤，哭泣感"}`（强对比） | ✓ |
| skip reason 字符串与 KNOWN_ISSUES.md §1 标题对应 | `_INTEGRATION_SKIP_REASON = "awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1"`，含 `§1` 标记 | ✓ |

**Red flags（任一出现即 FAIL）:**

| Red flag | 自检结果 | 状态 |
|---|---|---|
| 任一 integration 测试漏掉 `@pytest.mark.skip`（会在 CI 上 FAIL） | 4 个测试都含 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`，实测 `pytest -v` 4 skipped 不是 4 failed | ✓ 未触发 |
| skip reason 写死字符串而不是用 `_INTEGRATION_SKIP_REASON` 常量 | 4 处全部 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 引用常量，无硬编码字符串 | ✓ 未触发 |
| 测试断言用 `==` 而不是范围比较 | 全部用 `<=` / `>=` / `<` / `>`，无 `==`（除 `result.segment_id == "s1"` 这种 ID 相等检查） | ✓ 未触发 |
| sorting 测试只比 `quality` 不比 `overall` | 测试 3 line 358 + 361 同时断言 `quality` 和 `overall` 的相对排序 | ✓ 未触发 |

**B 表静态审查 5/5 全过 + Red flags 0/4 触发。**

### C. Pass 条件 + 输出

- A 表全绿（4 个新 integration 测试存在 + 全部 SKIP + 契约满足）。
- B 表静态审查 5/5 全过 + Red flags 0/4 触发。
- 测试代码与 plan line 1299-1364 字面量 md5 比对 BYTE-EQUAL（0 字符偏离，md5 `96f34b90943113957a1f12e1bd72d4e9`）。
- 数量偏离（9 PASS + 4 SKIP vs plan 期望 7 PASS + 4 SKIP）属 plan 假设错误（与 Task 8 同根源），非本 task 实现 bug（详见 §6.1）。

**建议判定：** → **PASS（mock 阶段）**。Full PASS 需等服务可用 + 3 个音频 fixture 后启用 skip 跑 4 passed（属 judge-Agent 阶段，本 task 不交付）。

---

## 4. 文件落盘证据

### 4.0 基线 — Task 8 末态（integration 测试加入前）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py --collect-only -q
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context
src_next/critic/tests/test_qwen3omni_critic.py::test_from_json_legacy_flat_schema_still_works
src_next/critic/tests/test_qwen3omni_critic.py::test_normalize_nested_scoring_clamps_and_merges_suggestions
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_http_500_returns_neutral
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_non_json_text_returns_neutral
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_empty_text_field_returns_neutral
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_request_exception_returns_neutral

9 tests collected in 0.01s
```

> Task 8 末态：9 个测试全绿（不是 plan §Task 9 假设的 7 个）。多出的 2 个测试是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 加的（Task 8 dev doc §6.1 已记录）。本 task 加入 4 个 skip-marked integration 测试后，总数 9 + 4 = 13（其中 9 passed + 4 skipped）。

### 4.1 Step 2 命令 1 测试输出（integration 测试加入后）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 13 items

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [  7%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success PASSED [ 15%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context PASSED [ 23%]
src_next/critic/tests/test_qwen3omni_critic.py::test_from_json_legacy_flat_schema_still_works PASSED [ 30%]
src_next/critic/tests/test_qwen3omni_critic.py::test_normalize_nested_scoring_clamps_and_merges_suggestions PASSED [ 38%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_http_500_returns_neutral PASSED [ 46%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_non_json_text_returns_neutral PASSED [ 53%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_empty_text_field_returns_neutral PASSED [ 61%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_request_exception_returns_neutral PASSED [ 69%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high SKIPPED [ 76%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_low_quality_audio_scores_low SKIPPED [ 84%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_sorting_good_higher_than_bad SKIPPED [ 92%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_emotion_mismatch_scores_low_alignment SKIPPED [100%]

=========================== short test summary info ===========================
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:325: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:342: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:351: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:370: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
======================== 9 passed, 4 skipped in 0.12s =========================
```

**本 task 4 个新 integration 测试（line 325 / 342 / 351 / 370）全部 SKIPPED：**
- `test_critic_high_quality_audio_scores_high` SKIPPED（reason: `_INTEGRATION_SKIP_REASON` ✓）
- `test_critic_low_quality_audio_scores_low` SKIPPED（reason: `_INTEGRATION_SKIP_REASON` ✓）
- `test_critic_sorting_good_higher_than_bad` SKIPPED（reason: `_INTEGRATION_SKIP_REASON` ✓）
- `test_critic_emotion_mismatch_scores_low_alignment` SKIPPED（reason: `_INTEGRATION_SKIP_REASON` ✓）

> 既有 9 个 unit / robustness 测试仍然 PASS（无回归）。Plan §Task 9 Step 2 期望 "7 PASS + 4 SKIPPED"，实际 **9 passed + 4 skipped**——多出的 2 个 unit 测试属 Task 6 既存基线，不影响本 task 4 个 integration 测试全 SKIP 的实质结论。

### 4.2 Step 2 命令 2 测试输出（`-m integration` 过滤）

```
$ python -m pytest src_next/critic/tests/ -m integration -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 13 items / 9 deselected / 4 selected

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high SKIPPED [ 25%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_low_quality_audio_scores_low SKIPPED [ 50%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_sorting_good_higher_than_bad SKIPPED [ 75%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_emotion_mismatch_scores_low_alignment SKIPPED [100%]

=========================== short test summary info ===========================
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:325: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:342: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:351: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
SKIPPED [1] src_next\critic\tests\test_qwen3omni_critic.py:370: awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1
====================== 4 skipped, 9 deselected in 0.02s =======================
```

> `-m integration` 筛选出 4 个 integration 测试，全部 SKIPPED，0 failed——plan §Task 9 A Self-check 第 2 条字面期望 "4 skipped，确认全部 skip，没有意外 FAIL"达成。`pytest.ini` 注册的 `integration` mark 生效，无 unknown marker warning。

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A1：测试代码与 plan 字面量 md5 比对 BYTE-EQUAL**

Python 脚本抽取：
- plan line 1299-1364（`lines[1298:1364]`，含 66 行，去掉 markdown fence）
- 测试文件中从顶部 `# ────────...` 分隔注释起到文件末尾的内容

```
plan md5:    96f34b90943113957a1f12e1bd72d4e9
append md5:  96f34b90943113957a1f12e1bd72d4e9
→ BYTE-EQUAL
plan line count:    66
append line count:  66
```

> md5 完全一致，0 字符偏离。这是最严格的字面量校验，比 grep 行号匹配更可靠。

**A2：py_compile 通过（CLAUDE.md §10 第 1 条）**

```
$ python -m py_compile src_next/critic/tests/test_qwen3omni_critic.py && echo OK
OK
```

**A3：行数验证**

```
$ wc -l src_next/critic/tests/test_qwen3omni_critic.py
381 src_next/critic/tests/test_qwen3omni_critic.py
```

> 文件总行数 381（Task 8 末态 313 + 本 task 追加 68 = 381；追加部分含 plan 66 行 + 中间 2 行空行作为分隔）。

**A4：git diff --stat**

```
$ git diff --stat src_next/critic/tests/test_qwen3omni_critic.py
 src_next/critic/tests/test_qwen3omni_critic.py | 68 ++++++++++++++++++++++++++
 1 file changed, 68 insertions(+)
```

> 68 insertions, 0 deletions——纯追加，未改任何既有行。

**B1：4 个新 integration 测试函数定义**

```
$ grep -n "^def test_critic_" src_next/critic/tests/test_qwen3omni_critic.py
322:def test_critic_high_quality_audio_scores_high(real_critic, good_narration_wav):
341:def test_critic_low_quality_audio_scores_low(real_critic, bad_clipping_wav):
350:def test_critic_sorting_good_higher_than_bad(real_critic, good_narration_wav, bad_clipping_wav):
369:def test_critic_emotion_mismatch_scores_low_alignment(real_critic, emotion_mismatch_wav):
```

> 4 个 `def test_critic_*` 函数，全部接受 conftest 的 fixture 参数（`real_critic` + 对应 `*_wav`）。测试 3 接受 3 个 fixture（含 `real_critic`），其他 3 个测试接受 2 个 fixture。

**B2：每个测试两个装饰器叠加（integration + skip）**

```
$ grep -n -B1 "^def test_critic_" src_next/critic/tests/test_qwen3omni_critic.py
319:@pytest.mark.integration
320:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
321:
322:def test_critic_high_quality_audio_scores_high(real_critic, good_narration_wav):

338:@pytest.mark.integration
339:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
340:
341:def test_critic_low_quality_audio_scores_low(real_critic, bad_clipping_wav):

347:@pytest.mark.integration
348:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
349:
350:def test_critic_sorting_good_higher_than_bad(real_critic, good_narration_wav, bad_clipping_wav):

366:@pytest.mark.integration
367:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
368:
369:def test_critic_emotion_mismatch_scores_low_alignment(real_critic, emotion_mismatch_wav):
```

> 每个测试前 2 行装饰器（`@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`），空行分隔装饰器与函数定义——与 plan 字面量格式一致。

**B3：4 处断言阈值字面量（给 judge 抽查）**

| 测试 | 行号 | 字面量 | plan 期望 |
|---|---|---|---|
| high_quality | line 332-333 | `result.quality >= 0.7` + `result.intelligibility >= 0.7` | ✓（不是 `> 0.9`） |
| low_quality | line 344 | `result.quality < 0.6` | ✓（不是 `< 0.5`） |
| sorting | line 358, 361 | `good_result.quality > bad_result.quality` + `good_result.overall > bad_result.overall` | ✓（两个维度都断言） |
| emotion_mismatch | line 376 | `result.emotion_alignment < 0.6` | ✓ |

**B4：`_INTEGRATION_SKIP_REASON` 定义 + 4 处引用**

```
$ grep -n "_INTEGRATION_SKIP_REASON" src_next/critic/tests/test_qwen3omni_critic.py
309:_INTEGRATION_SKIP_REASON = (
312:    "awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1"
315:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)   # 引用 1（测试 1）
333:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)   # 引用 2（测试 2）
342:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)   # 引用 3（测试 3）
361:@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)   # 引用 4（测试 4）
```

> 1 处定义 + 4 处引用，无硬编码 skip reason 字符串。字符串内容含 `KNOWN_ISSUES.md §1`，方便启用时 grep 交叉查找。

### 4.4 前置 commit 历史（验证 Task 1-8 已落盘）

```
$ git log --oneline -3
1d655b4 test(critic): add 4 robustness tests for HTTP failure modes
db9743e docs(critic): add task 2-7 judging reports (backfill)
866d277 refactor(critic): drop LLM overall_score, use 5-dim average in from_json
```

> Task 8 commit `1d655b4` 是本 task 的直接前置（4 个 robustness 测试已落盘）。Task 7 commit `0e74e9b`（conftest.py fixture 已固化）虽不在最近 3 条 log，但已确认存在（§4.5 验证）。

### 4.5 conftest.py fixture 已固化（前置依赖验证）

```
$ grep -n "^def \|@pytest.fixture" src_next/critic/tests/conftest.py
13:@pytest.fixture(scope="session")
18:def real_critic():
35:@pytest.fixture(scope="session")
36:def good_narration_wav():
40:@pytest.fixture(scope="session")
41:def bad_clipping_wav():
45:@pytest.fixture(scope="session")
46:def emotion_mismatch_wav():
50:@pytest.fixture(scope="session")
51:def real_llm():
```

> conftest.py 定义了 5 个 session-scoped fixture，其中本 task 用到 4 个（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav`）。若 conftest.py 漏定义任一 fixture，collection 阶段会 ERROR（fixture not found），本 task 实测 collection 无 error，4 个测试全部 SKIPPED（skip 在 fixture 解析之前生效）。

### 4.6 pytest.ini 注册 integration mark（前置依赖验证）

```
$ cat pytest.ini
[pytest]
markers =
    integration: marks tests that hit real external services (Qwen3-Omni, real LLM). Slow — deselect with -m "not integration".
testpaths = src_next
python_files = test_*.py
addopts = -ra
```

> `pytest.ini` line 3 注册 `integration` mark，本 task 4 个测试全部带此 mark，无 unknown marker warning。CLAUDE.md §9 第 8 条要求"绝不跳过 hooks"，本 task 也不动 `pytest.ini`（已存在，不需修改）。

### 4.7 行数变化

| 文件 | Task 8 末态 | Task 9 末态 | Δ |
|---|---|---|---|
| `src_next/critic/tests/test_qwen3omni_critic.py` | 313 行 | 381 行 | +68 |
| `docs/critic_task9_coding.md` | （不存在） | 本文件 | +N |
| `src_next/critic/tests/conftest.py` | 79 行 | 79 行 | 0（未修改） |
| `src_next/critic/qwen3omni_critic.py` | （未变） | （未变） | 0（未修改） |
| `pytest.ini` | 7 行 | 7 行 | 0（未修改） |
| **合计（代码部分）** | — | — | **+68 行** |

> 本 task 严格"只追加 4 个 skip-marked integration 测试 + 1 个常量 + 3 行分隔注释到既有测试文件"，与 plan §Task 9 Files 表 "Modify: src_next/critic/tests/test_qwen3omni_critic.py"（仅此 1 项）一致。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 2 个文件路径，合并 1 commit 模式，与 Task 5 / 6 / 7 / 8 一致）：

```bash
git add src_next/critic/tests/test_qwen3omni_critic.py
git add docs/critic_task9_coding.md
git commit -m "test(critic): add 4 integration test skeletons (task 9, round 1)"
```

> **commit 类型为 `test(critic):`**——与 Task 7 / Task 8 同属测试代码，延续 `test(critic):` 前缀。
> **commit message 使用用户 task 指令字面量** `test(critic): add 4 integration test skeletons (task 9, round 1)`，不是 plan §Task 9 Step 3 字面 `test(critic): add 4 integration test skeletons (skip-marked, pending service access)`——用户指令优先级 > plan 字面量。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `docs/critic_task8_judging.md`），全部不带进本 commit。

### 5.2 与 Task 5 / 6 / 7 / 8 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 6 | `732e81b` `feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 7 | `0e74e9b` `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 8 | `1d655b4` `test(critic): add 4 robustness tests for HTTP failure modes` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 9 | （本 task）`test(critic): add 4 integration test skeletons (task 9, round 1)` | （合并到代码 commit） | 合并 1 commit | **`test`** |

> Task 9 延续 Task 7 / 8 的 `test(critic):` 模式。后续 Task 10/11（TTSRepairAgent 业务代码）回到 `feat(critic):`。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 测试代码与 plan line 1299-1364 字面量是否一致 | 逐字一致 | md5 比对 `BYTE-EQUAL`（md5 `96f34b90943113957a1f12e1bd72d4e9`，66 行对 66 行） | 无 | — |
| `pytest -v` 期望 passed 数 | plan 字面 "7 PASS + 4 SKIPPED"（3 既有 + 4 robustness (Task 8) + 0 = 7） | 实测 **9 passed + 4 skipped**（5 既有 + 4 robustness (Task 8) + 0 = 9 + 4 new skip） | 数量偏离 2 | **本 task 不修正**——多出的 2 个测试（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`）是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 加的，属 Task 6 既存基线（Task 8 dev doc §6.1 已记录同一偏离根源）。本 task 4 个新 integration 测试全 SKIP 的实质结论不受影响。 |
| commit message 与 plan 字面量 | plan §Task 9 Step 3 字面 `test(critic): add 4 integration test skeletons (skip-marked, pending service access)` | 用户 task 指令字面 `test(critic): add 4 integration test skeletons (task 9, round 1)` | 字面量差异（用户指令优先） | **本 task 按用户指令字面**——用户指令优先级 > plan 字面量，commit message 含 `task 9, round 1` 便于 judge-Agent 抽查时与本 dev doc 对应。 |
| conftest.py fixture 名是否需要补 | plan §Task 9 Step 1 假设 conftest.py 已定义 `real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` 4 个 fixture | conftest.py line 18 / 36 / 41 / 46 已定义全部 4 个 fixture（Task 7 commit `0e74e9b`） | 无 | — |
| `integration` mark 是否已注册 | plan §Task 9 假设 `pytest.ini` 已注册 `integration` mark | `pytest.ini` line 3 已注册 | 无 | — |
| `_make_segment_and_instruction` helper 是否需补 | plan §Task 9 Step 1 假设 helper 已存在 | Task 5 已在 line 23-38 加 helper | 无 | — |

**无结构性偏离。** 测试代码与 plan 字面量 md5 比对 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加、0 断言改写。唯一偏离是 "passed count 9 vs plan 期望 7"（与 Task 8 同根源，Task 6 既存基线问题）+ commit message 字面量（用户指令覆盖 plan 字面量），均非本 task 实现 bug。

### 6.2 给 Task 10 的提醒

- **Task 10（TTSRepairAgent 失败测试）**：新建 `src_next/critic/tests/test_tts_repair.py`，与本文件解耦。Task 10 起回到 `feat(critic):` commit 类型（业务代码）。
- **本 task 4 个 integration 测试在 Task 10+ 不应被改动**：除非 plan 后续 task 明确要求启用（plan §Task 9 B "judge 操作"才有权删除 `@pytest.mark.skip` 行），coding-Agent 不得擅自动这 4 个测试的装饰器。
- **`_make_segment_and_instruction` helper 在 Task 10+ 仍然适用**：Task 10 起 `test_tts_repair.py` 会用 `Segment` + `ModelSpecificTTSInstruction` + `CriticResult` 构造输入，可能需要新的 `_make_inputs` helper（plan §Task 10 line 1470-1490 给出新 helper 字面量）——与本 task 的 `_make_segment_and_instruction` 共存，不冲突。

### 6.3 给 judge-Agent 的提示

- **静态审查重点：** B 表 5 项全部应通过；用 md5 比对测试代码与 plan line 1299-1364 是最强证据（§4.3 A1 输出 BYTE-EQUAL + md5 `96f34b90943113957a1f12e1bd72d4e9`）。
- **mock test 状态：** 本 task 完成时 `9 passed, 4 skipped in 0.12s`（既有 9 个 unit/robustness 全 PASS + 本 task 4 个 integration 全 SKIP），无 collection error，无 regression。
- **integration test 状态：** `-m integration` 单独跑 `4 skipped, 9 deselected in 0.02s`，全部 SKIP（不是 FAIL / 不是 ERROR），plan §Task 9 A Self-check 第 2 条字面期望达成。
- **passed count 偏离解释（重要）：** Plan §Task 9 Step 2 字面期望 "7 PASS + 4 SKIPPED"（= 3 既有 + 4 robustness (Task 8)），但实际是 **9 passed + 4 skipped**（= 5 既有 + 4 robustness (Task 8)）。多出的 2 个 unit 测试（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`）来自 Task 6 commit `732e81b`，与本 task 无关，Task 8 dev doc §6.1 已记录同一偏离。判断 PASS 时按"4 个新 integration 测试全 SKIP + 既有 9 个测试无回归"的实质结论判，不要按字面 "7 PASS + 4 SKIPPED" 判。
- **越界检测：** 本 task 只动 `src_next/critic/tests/test_qwen3omni_critic.py`（追加 68 行），不应动 `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` / `prompts/critic_prompt.py` / 其他 critic 模块。`git diff --stat` 应只显示 1 个文件改动。
- **commit 类型检测：** 本 task commit message 是 `test(critic): ...`（延续 Task 7 / 8 模式），不是 `feat(critic): ...`——延续测试代码 commit 前缀。
- **commit message 字面量与 plan 不一致说明：** 用户 task 指令明确要求 `test(critic): add 4 integration test skeletons (task 9, round 1)`，与 plan §Task 9 Step 3 字面 `test(critic): add 4 integration test skeletons (skip-marked, pending service access)` 不一致——用户指令优先级 > plan 字面量，这是预期偏离，不是 bug。
- **4 个测试断言阈值合理性检测：**
  - 高质量音频用 `>= 0.7`（不是 `> 0.9`）——留 LLM 主观空间
  - 低质量音频用 `< 0.6`（不是 `< 0.5`）——避免与 neutral fallback 0.5 混淆
  - emotion_mismatch 用「极度悲伤，哭泣感」（强对比 prompt，不是「略带忧伤」弱对比）——让 emotion_alignment < 0.6 断言更稳定
  - sorting 测试断言 `quality > ` 且 `overall >`（两个维度，不只一个）
- **启用流程提示（judge-Agent 在服务可用时操作）：** 全局搜索 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 并删除该行（共 4 处），然后 `pytest -m integration -v` 期望 4 passed（需 3 个 fixture 音频 + Qwen3-Omni 服务可达）。启用前需准备 `src_next/critic/tests/fixtures/good_narration.wav` / `bad_clipping.wav` / `emotion_mismatch.wav`（KNOWN_ISSUES.md §3 已登记）。

---

## 7. 一句话总结

Task 9 = 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加 4 个 skip-marked integration 测试 + 1 个共享常量 `_INTEGRATION_SKIP_REASON` + 3 行分隔注释（共 68 行新增，0 行修改）。测试代码与 plan line 1299-1364 代码块 md5 比对 **BYTE-EQUAL**（0 字符偏离，md5 `96f34b90943113957a1f12e1bd72d4e9`）。`pytest -v` 实测 **9 passed, 4 skipped in 0.12s**（既有 9 个 unit/robustness 全 PASS + 本 task 4 个 integration 全 SKIP，无回归；plan 期望 "7 PASS + 4 SKIPPED" 是 plan 作者假设 Task 6 只交付 3 个测试，实际 Task 6 交付 5 个，详见 §6.1，与 Task 8 同根源）。`pytest -m integration -v` 实测 **4 skipped, 9 deselected in 0.02s**（plan §Task 9 A Self-check 第 2 条字面期望达成）。commit 类型为 `test(critic):`（延续 Task 7 / 8），commit message 按用户 task 指令字面量 `test(critic): add 4 integration test skeletons (task 9, round 1)`。Acceptance A 表全过 + B 表静态审查 5/5 全过 + Red flags 0/4 触发，0 结构性偏离，建议 **PASS（mock 阶段）**。
