# Critic Task 9 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 9（line 1288-1378）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 9 沿用 plan §Task 9 Acceptance Criteria Full）
> **Coding dev doc:** `docs/critic_task9_coding.md`（已落盘于 commit `72e3d4b`）
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-08
> **Task 类型:** 测试代码型（追加 skip-marked integration 测试骨架，不动业务代码）
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS** — Task 9 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加的 4 个 skip-marked integration 测试 + 1 个共享常量 `_INTEGRATION_SKIP_REASON` + 3 行分隔注释（共 +68 行）与 plan line 1299-1364 代码块 md5 比对 **BYTE-EQUAL**（md5 `52b084274ef238539e0f434f177bf6e6`，66 行对 66 行，0 字符偏离）；judge 自跑两条 Self-check 命令实测 `9 passed, 4 skipped in 0.10s` + `-m integration` `4 skipped, 9 deselected in 0.02s`（4 新 integration 测试全部 SKIPPED，不是 FAILED / 不是 ERROR，既有 9 个测试无回归；plan 字面期望 "7 PASS + 4 SKIPPED"，多出的 2 是 Task 6 既存基线，详见 §5 偏离登记）；commit `72e3d4b` 已落盘，scope 严格（仅 2 文件 / +560 行）；Acceptance A 表 2/2 + 2 contract 全部 PASS，B 表 5/5 全部 PASS + 4 Red flag 全部未触发；0 scope creep。

---

## 1. 验收范围

| 项 | 值 |
|---|---|
| Plan Task 9 标题 | Write integration test skeletons (skip-marked, ready for future activation) |
| Plan Acceptance 章节 | `### Acceptance Criteria (Task 9 — Full)` (line 1381-1443) |
| Coding dev doc | `docs/critic_task9_coding.md`（492 行，随测试文件同 commit 落盘） |
| Commit | `72e3d4b test(critic): add 4 integration test skeletons (task 9, round 1)` |
| Commit 范围 | `src_next/critic/tests/test_qwen3omni_critic.py`（M, +68）+ `docs/critic_task9_coding.md`（A, +492）= +560 lines / 2 files |
| 验收方式 | mock + 静态（plan B "启用 integration 测试" 属服务可用时 judge 操作，本机 mock 阶段不跑） |
| 验收环境 | Windows 11 / Python 3.12.10 / pytest 9.0.3 / branch `feature/critic-and-tta` @ `72e3d4b` |

**Plan 字面量来源（用于 §4 字面量核对）：** plan §Task 9 Step 1 给出的完整 Python 代码块（line 1299-1364，共 66 行非空内容，含 3 行分隔注释 + 常量 + 4 个测试函数）。

---

## 2. Section A — coding-Agent Self-check

plan line 1391-1397 列出的 2 条 bash Self-check 命令 + 配套 2 条 contract（line 1400-1401）。judge 自己重跑，**未抄 coding doc 实测列**。

| 项 | 期望（plan 字面） | judge 实测 | 状态 |
|---|---|---|---|
| A1 | `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → 7 passed + 4 skipped（SKIPPED 不是 FAILED） | judge 重跑输出 `collected 13 items` → 9 PASSED（既有 unit/robustness 全绿）+ 4 SKIPPED（本 task 4 个 integration 测试全部 SKIPPED）+ `9 passed, 4 skipped in 0.10s`（exit 0）。**数量偏离 +2**：plan 期望 7 passed，实测 9 passed，多出的 2 是 Task 6 既存（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`），与本 task 无关，详见 §5 偏离登记 | **PASS**（实质结论：4 个新 integration 测试全 SKIPPED + 既有 9 个测试无回归；数量偏离非实现 bug） |
| A2 | `python -m pytest src_next/critic/tests/ -m integration -v` → 4 skipped（确认全部 skip，没有意外 FAIL） | judge 重跑输出 `collected 13 items / 9 deselected / 4 selected` → 4 SKIPPED（本 task 4 个 integration 测试全部 SKIPPED，deselected 9 个非 integration 测试）+ `4 skipped, 9 deselected in 0.02s`（exit 0）。0 failed / 0 error，`integration` mark 在 `pytest.ini` 已注册无 unknown marker warning | **PASS** |

**Contract 检查（plan line 1400-1401）：**

| Contract | 期望 | judge 实测 | 状态 |
|---|---|---|---|
| C1 | 每个 integration 测试同时有 `@pytest.mark.integration` **和** `@pytest.mark.skip(reason=...)` 两个装饰器 | Grep `^@pytest.mark` 命中 8 处（line 325/326/342/343/351/352/370/371），4 个测试函数（line 327/344/353/372）每个上方都有 2 个装饰器：`@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)`。装饰器顺序：integration 在外、skip 在内，与 plan 字面量一致 | **PASS** |
| C2 | skip reason 文字与 KNOWN_ISSUES.md §1 启用条件互相引用 | Read test 文件 line 320-322 `_INTEGRATION_SKIP_REASON = "awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1"`；Read `KNOWN_ISSUES.md` line 6 `## 1. Integration 测试全部 skip（待服务可访问）` + line 14-18 启用方法。Skip reason 字符串内含 `KNOWN_ISSUES.md §1`，KNOWN_ISSUES.md §1 启用方法第 1 条 `全局搜索 @pytest.mark.skip(reason="awaiting"` 引用回 integration 测试，**双向交叉引用成立** | **PASS** |

**附加（judge 主动跑，非 plan 必需）：**

- `python -m py_compile src_next/critic/tests/test_qwen3omni_critic.py` → `OK`（CLAUDE.md §10 第 1 条语法检查通过）
- `git diff --stat HEAD` → 工作区 clean，commit `72e3d4b` 已封盘，无 pending 改动
- Read test 文件 line 316-318 确认 3 行分隔注释 `# ──...` + `# Integration tests — skip-marked. See KNOWN_ISSUES.md §1 to activate.` + `# ──...` 存在（与 plan line 1299-1301 字面量一致）

**Section A 汇总：2/2 + 2 contract 全部 PASS。** Plan 字面 "7 passed + 4 skipped" 与实测 "9 passed + 4 skipped" 的偏差按实质结论判 PASS（4 个新 integration 测试全 SKIP + 既有 9 个测试无回归的实质结论不受影响），偏离原因见 §5。

---

## 3. Section B — judge-Agent 抽查

plan line 1425-1430 列出的 5 条静态审查点 + 4 条 Red flags（line 1432-1436）。judge 用 Read / Grep 工具逐条核对，**未用"我扫了一眼"代替工具调用**。

| 抽查点 | 期望 | judge 实测证据 | 状态 |
|---|---|---|---|
| B1 | 4 个测试断言相对排序（`good > bad`）而不仅是绝对阈值——避免 LLM 评分漂移导致测试 flaky | Read test 文件 line 353-367（`test_critic_sorting_good_higher_than_bad`）：line 364 `assert good_result.quality > bad_result.quality, ...` + line 367 `assert good_result.overall > bad_result.overall`。**同时断言 quality 和 overall 两个维度的相对排序**，不只是绝对阈值 | **PASS** |
| B2 | 高质量音频的断言阈值合理（`>= 0.7` 不是 `> 0.9`，留出 LLM 主观空间） | Read test 文件 line 337 `assert result.quality >= 0.7, f"quality too low for good audio: ..."` + line 338 `assert result.intelligibility >= 0.7, ...`。**用 `>= 0.7` 下界，不是 `> 0.9`**，留 LLM 主观空间 | **PASS** |
| B3 | 低质量音频的断言用 `< 0.6` 而不是 `< 0.5`（避免与 neutral fallback 0.5 混淆） | Read test 文件 line 348 `assert result.quality < 0.6, f"quality too high for bad audio: ..."`。**用 `< 0.6`**，不是 `< 0.5`（neutral fallback 是 0.5，用 `< 0.6` 是更严苛阈值，能捕捉 critic 退化到 neutral 的情况） | **PASS** |
| B4 | emotion_mismatch 测试用「极度悲伤，哭泣感」这种强对比 prompt，不是「略带忧伤」这种弱对比 | Read test 文件 line 375 `inst.parameters = {"instruction": "极度悲伤，哭泣感"}` + line 379 `assert result.emotion_alignment < 0.6, ...`。**用强对比 prompt**「极度悲伤，哭泣感」（不是「略带忧伤」），让 neutral-tone 音频的 emotion_alignment < 0.6 断言更稳定 | **PASS** |
| B5 | skip reason 字符串与 KNOWN_ISSUES.md §1 标题对应（方便交叉查找） | Read test 文件 line 320-322 `_INTEGRATION_SKIP_REASON` 含字面量 `KNOWN_ISSUES.md §1`；Read `KNOWN_ISSUES.md` line 6 `## 1. Integration 测试全部 skip（待服务可访问）`。字符串内 `§1` 标记直接对应 KNOWN_ISSUES.md 一级标题 §1，方便启用时 grep 交叉查找 | **PASS** |

**Red flags 排查（plan line 1432-1436，任一触发即 FAIL）：**

| Red flag | judge 实测证据 | 状态 |
|---|---|---|
| 任一 integration 测试漏掉 `@pytest.mark.skip`（会在 CI 上 FAIL） | Grep `@pytest.mark.skip\(reason=` 命中 4 处（line 326/343/352/371），4 个 integration 测试函数（line 327/344/353/372）每个上方都有 skip 装饰器。judge 自跑 `pytest -v` 实测 4 skipped 不是 4 failed（如果漏 skip 装饰器会变成 4 failed，因 fixture 不可达会触发 ConnectError 但 neutral fallback 会让 result 非空，断言失败而非 skip） | **未触发** |
| skip reason 写死字符串而不是用 `_INTEGRATION_SKIP_REASON` 常量 | Grep `_INTEGRATION_SKIP_REASON` 命中 5 处：line 320 定义（`_INTEGRATION_SKIP_REASON = (...)`）+ line 326/343/352/371 共 4 处 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 引用。**0 处硬编码 skip reason 字符串** | **未触发** |
| 测试断言用 `==` 而不是范围比较（如 `assert result.quality == 0.85`，LLM 不会稳定输出固定值） | Read 本 task 4 个测试（line 325-381）全部断言：line 334 `== "s1"`（segment_id 字符串相等检查，合理）/ line 335-336 `0.0 <= result.quality <= 1.0`（范围）/ line 337 `>= 0.7` / line 338 `>= 0.7` / line 348 `< 0.6` / line 364 `>` / line 367 `>` / line 379 `< 0.6`。**0 处用 `==` 比较浮点数**（仅 `segment_id == "s1"` 这种 ID 字符串相等，不在 red flag 范畴） | **未触发** |
| sorting 测试只比 `quality` 不比 `overall`（漏掉综合维度） | Read test 文件 line 364 `assert good_result.quality > bad_result.quality` + line 367 `assert good_result.overall > bad_result.overall`。**两个维度都断言相对排序** | **未触发** |

**Section B 汇总：5/5 PASS + 4/4 Red flag 未触发。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 字面量 md5 比对

judge 用 Python 脚本抽取 plan line 1299-1364（`lines[1298:1364]`，66 行，含 3 行分隔注释 + 常量定义 + 4 个测试函数）vs 测试文件中从顶部 `# ────...` 分隔注释起到文件末尾的内容，rstrip 后做 md5 比对：

```
plan md5:    52b084274ef238539e0f434f177bf6e6
append md5:  52b084274ef238539e0f434f177bf6e6
plan lines:    66
append lines:  66
EQUAL: True
```

**0 行重排序、0 字符差异、0 import 改写、0 类型注解添加、0 断言改写。** plan 字面量逐字落盘。

> 注：coding doc §4.3 A1 自报 md5 `96f34b90943113957a1f12e1bd72d4e9`，与本 judge 实测 md5 `52b084274ef238539e0f434f177bf6e6` 不同——这是抽 chunk 边界不同导致（coding doc 可能用了不同 trim 方式），但 judge 用统一 rstrip + 行对齐方式实测两端完全相等（`EQUAL: True`），结论一致：字面量 BYTE-EQUAL。

### 4.2 关键字面量点

| 关键字面量 | plan line | test 文件行 | 一致 |
|---|---|---|---|
| 3 行分隔注释 `# ──...` + `# Integration tests — skip-marked. See KNOWN_ISSUES.md §1 to activate.` + `# ──...` | plan line 1299-1301 | test line 316-318 | ✓ |
| `_INTEGRATION_SKIP_REASON = ("awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1")` 常量定义 | plan line 1303-1305 | test line 320-322 | ✓ |
| `@pytest.mark.integration` + `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 装饰器对（4 处） | plan line 1308-1309/1325-1326/1334-1335/1353-1354 | test line 325-326/342-343/351-352/370-371 | ✓ |
| 4 个测试函数名 `test_critic_high_quality_audio_scores_high` / `_low_quality_audio_scores_low` / `_sorting_good_higher_than_bad` / `_emotion_mismatch_scores_low_alignment` | plan line 1310/1327/1336/1355 | test line 327/344/353/372 | ✓ |
| `test_critic_high_quality_audio_scores_high` 用 `inst.parameters = {"instruction": "平稳叙述"}` | plan line 1313 | test line 330 | ✓ |
| `test_critic_emotion_mismatch_scores_low_alignment` 用 `inst.parameters = {"instruction": "极度悲伤，哭泣感"}`（强对比 prompt） | plan line 1358 | test line 375 | ✓ |
| `test_critic_high_quality_audio_scores_high` 断言 `result.quality >= 0.7` + `result.intelligibility >= 0.7`（不是 `> 0.9`） | plan line 1320-1321 | test line 337-338 | ✓ |
| `test_critic_low_quality_audio_scores_low` 断言 `result.quality < 0.6`（不是 `< 0.5`） | plan line 1331 | test line 348 | ✓ |
| `test_critic_sorting_good_higher_than_bad` 断言 `good_result.quality > bad_result.quality` + `good_result.overall > bad_result.overall`（两个维度） | plan line 1347/1350 | test line 364/367 | ✓ |
| `test_critic_emotion_mismatch_scores_low_alignment` 断言 `result.emotion_alignment < 0.6` | plan line 1362 | test line 379 | ✓ |
| commit message `test(critic): add 4 integration test skeletons (skip-marked, pending service access)` | plan line 1376 | git commit `72e3d4b` `test(critic): add 4 integration test skeletons (task 9, round 1)` | ⚠️ **字面量偏离**——但用户 task 指令明确指定 `task 9, round 1` 后缀，用户指令优先级 > plan 字面量。详见 §5 偏离登记 |

### 4.3 文件 scope 核对

| 路径 | 操作 | plan 期望 | 实测 |
|---|---|---|---|
| `src_next/critic/tests/test_qwen3omni_critic.py` | Modify（追加） | 仅此 1 个业务代码文件 | ✓ 文件总行数 381（Task 8 末态 313 + 本 task 追加 68） |
| `docs/critic_task9_coding.md` | Create（dev doc） | 1 个 dev doc | ✓ 492 行，新建 |
| 其他文件 | 不动 | — | `git show --stat 72e3d4b` 仅 2 个文件，无 scope 越界 |

**Commit stat 完整：**
```
 docs/critic_task9_coding.md                    | 492 +++++++++++++++++++++++++
 src_next/critic/tests/test_qwen3omni_critic.py |  68 ++++
 2 files changed, 560 insertions(+)
```

### 4.4 前置依赖验证

| 前置 | 期望 | 实测 | 状态 |
|---|---|---|---|
| 当前分支 = `feature/critic-and-tta` | ✓ | `git log` 显示 commit `72e3d4b` 在 `feature/critic-and-tta` 分支上 | ✓ |
| Task 8 commit `1d655b4` 已落盘（4 个 robustness 测试） | ✓ | `git log --oneline -5` 第 2 行 `1d655b4 test(critic): add 4 robustness tests for HTTP failure modes`，本 task commit `72e3d4b` 的直接 parent 是 `1d655b4` | ✓ |
| Task 7 commit `0e74e9b` 已落盘（conftest.py 4 个 fixture 已固化） | ✓ | Read `conftest.py` line 18-19 `def real_critic()` + line 35-36 `def good_narration_wav()` + line 40-41 `def bad_clipping_wav()` + line 45-46 `def emotion_mismatch_wav()`，4 个 fixture 全部定义 | ✓ |
| `pytest.ini` 注册 `integration` mark（避免 unknown marker warning） | ✓ | Read `pytest.ini` line 3 `integration: marks tests that hit real external services ...`，mark 已注册，judge 自跑 `-m integration` 无 warning | ✓ |
| `_make_segment_and_instruction` helper 已存在（Task 5 加） | ✓ | Grep `_make_segment_and_instruction` 在 test 文件命中（Task 5 既存 helper），本 task 4 个测试都调用此 helper 构造输入 | ✓ |

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 测试代码与 plan line 1299-1364 字面量是否一致 | 逐字一致 | md5 比对 `BYTE-EQUAL`（md5 `52b084274ef238539e0f434f177bf6e6`，66 行对 66 行） | 无 | — |
| `pytest -v` 期望 passed 数 | plan 字面 "7 passed + 4 skipped"（3 既有 + 4 robustness (Task 8) + 0 = 7；plan 作者假设 Task 6 只交付 3 个测试） | 实测 **9 passed + 4 skipped**（5 既有 + 4 robustness (Task 8) + 0 = 9；多出的 2 是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 加的） | 数量偏离 +2 | **本 task 不修正**——多出的 2 个测试属 Task 6 既存基线（Task 8 dev doc §6.1 已记录同一偏离根源，Task 8 judging doc §5 已确认）。本 task 4 个新 integration 测试全 SKIP 的实质结论不受影响 |
| commit message 与 plan 字面量 | plan §Task 9 Step 3 line 1376 字面 `test(critic): add 4 integration test skeletons (skip-marked, pending service access)` | 用户 task 指令字面 `test(critic): add 4 integration test skeletons (task 9, round 1)` | 字面量差异（用户指令覆盖 plan 字面量） | **本 task 按用户指令字面**——用户指令优先级 > plan 字面量，commit message 含 `task 9, round 1` 便于 judge-Agent 抽查时与本 dev doc 对应。**预期偏离，非 bug** |
| conftest.py fixture 名是否需要补 | plan §Task 9 Step 1 假设 conftest.py 已定义 `real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` 4 个 fixture | conftest.py line 18 / 36 / 41 / 46 已定义全部 4 个 fixture（Task 7 commit `0e74e9b`） | 无 | — |
| `integration` mark 是否已注册 | plan §Task 9 假设 `pytest.ini` 已注册 `integration` mark | `pytest.ini` line 3 已注册 | 无 | — |

**无结构性偏离。** 测试代码与 plan 字面量 md5 比对 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加、0 断言改写。唯一偏离是：
1. "passed count 9 vs plan 期望 7"（与 Task 8 同根源，Task 6 既存基线问题）
2. commit message 字面量（用户指令覆盖 plan 字面量）

均非本 task 实现 bug。

---

## 6. Red Flags 排查

按 CLAUDE.md §9 硬约束 + plan §Task 9 Acceptance Red flags 固定清单（line 1432-1436）逐项排查。

| Red Flag 项 | 是否触发 | 证据 |
|---|---|---|
| 字面量不一致 | 否 | §4.1 md5 比对 BYTE-EQUAL，0 字符差异 |
| scope 越界（改了不该改的文件） | 否 | §4.3 `git show --stat 72e3d4b` 仅 2 文件（test_qwen3omni_critic.py M +68 + dev doc A +492） |
| 章节顺序错乱（dev doc / judging doc） | 否 | dev doc §1-§7 完整，judging doc §0-§9 完整 |
| `--no-verify` 跳过 hook | 否 | git log 显示 commit 正常生成，无 hook 跳过痕迹 |
| 改 `src/` 旧链路 | 否 | commit 范围仅 `src_next/` + `docs/` |
| 改 `requirements.txt` | 否 | commit 范围无 requirements.txt |
| 改 `core/data_models.py` 加 backend 专用字段 | 否 | 本 task 不动 data_models.py（仅追加测试代码到 test_qwen3omni_critic.py） |
| 在 `core/` 或 `analysis/` import 具体 backend | 否 | 本 task 改的是 `src_next/critic/tests/`（测试代码），不在 core/analysis 范畴 |
| 硬编码服务器地址进模块（非 profile） | 否 | 本 task 4 个测试调用 `real_critic` fixture（conftest.py line 18-22 实例化 `Qwen3OmniCritic(base_url="http://10.50.121.102:8011")`），但 conftest 是 Task 7 既存，本 task 未硬编码任何 IP |
| 既有测试被破坏 | 否 | `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → `9 passed, 4 skipped in 0.10s`，既有 9 个测试全绿（无回归） |
| `pytest --collect-only` 报 collection error | 否 | `pytest -v` 输出 `collected 13 items` 后正常跑，0 collection error（如果 conftest 漏 fixture 会 collection error，本 task 实测无） |
| commit 未做（PENDING） | 否 | commit `72e3d4b` 已落盘，工作区 clean（仅 untracked 文档与 output 目录，与本 task 无关） |
| 任一 integration 测试漏掉 `@pytest.mark.skip`（plan red flag #1） | 否 | Grep `@pytest.mark.skip\(reason=` 命中 4 处（line 326/343/352/371），4 个测试函数每个都有 skip 装饰器 |
| skip reason 写死字符串而不是用 `_INTEGRATION_SKIP_REASON` 常量（plan red flag #2） | 否 | Grep `_INTEGRATION_SKIP_REASON` 命中 5 处：1 处定义 + 4 处 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 引用，0 处硬编码字符串 |
| 测试断言用 `==` 而不是范围比较（plan red flag #3） | 否 | Read 本 task 4 个测试（line 325-381）全部断言用 `<=` / `>=` / `<` / `>` 范围比较；仅 `result.segment_id == "s1"` 是 ID 字符串相等检查（合理，不在 red flag 范畴） |
| sorting 测试只比 `quality` 不比 `overall`（plan red flag #4） | 否 | Read line 364 `good_result.quality > bad_result.quality` + line 367 `good_result.overall > bad_result.overall`，两个维度都断言 |

**0 red flag。**

### 6.1 scope creep 检查（plan §1.2「不交付」清单）

coding doc §1.2 列出后续 task 才交付的项。比对：

| 不交付项（属后续 task） | 本 task 是否越界 | 证据 |
|---|---|---|
| `fixtures/` 目录的 3 段测试音频 | 否 | integration 测试 skip 阶段不需要真实音频，只引用 fixture 路径字符串（通过 conftest 的 `*_wav` fixture 间接引用）。`src_next/critic/tests/` 目录下无 `fixtures/` 子目录（KNOWN_ISSUES.md §3 标注"服务可访问后准备"） |
| TTSRepairAgent（Task 10/11） | 否 | `src_next/critic/` 目录下无 `tts_repair_agent.py` / `tts_repair_prompt.py` |
| `test_tts_repair.py`（Task 10 起） | 否 | `src_next/critic/tests/` 目录下无 `test_tts_repair.py` |
| KNOWN_ISSUES.md §1 启用条件本身 | 否 | KNOWN_ISSUES.md 在 Task 1-3 阶段已落盘，本 task 未修改 |
| 改业务代码 `qwen3omni_critic.py` | 否 | commit 范围不含 `src_next/critic/qwen3omni_critic.py`（本 task 只追加测试代码） |
| 改 `conftest.py`（Task 7 既存） | 否 | commit 范围不含 `src_next/critic/tests/conftest.py`（conftest.py line count 不变） |
| 改 `pytest.ini` | 否 | commit 范围不含 `pytest.ini`（`integration` mark 已在 Task 1-3 阶段注册） |

**0 越界。** Scope 严格按 plan §Task 9 Files 表「Modify: `src_next/critic/tests/test_qwen3omni_critic.py`」（仅此 1 项业务代码 + 配套 dev doc）。

---

## 7. Verdict JSON

```json
{
  "task_id": "task-9-integration-test-skeletons",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v",
      "python -m pytest src_next/critic/tests/ -m integration -v",
      "python -m py_compile src_next/critic/tests/test_qwen3omni_critic.py"
    ],
    "result": "3/3 PASS — pytest -v 实测 9 passed + 4 skipped in 0.10s（既有 9 个 unit/robustness 全绿 + 本 task 4 个 integration 全 SKIP，无回归）；pytest -m integration 实测 4 skipped + 9 deselected in 0.02s（plan A Self-check 第 2 条字面期望达成）；py_compile OK。Plan 字面期望 7 passed + 4 skipped 与实测 9 passed + 4 skipped 的偏差属 Task 6 既存基线（Task 8 同根源），非本 task 引入。"
  },
  "integration_tests": "SKIPPED — 本 task 是 skip-marked 测试骨架，4 个 integration 测试全部 @pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)。Plan B 「启用 integration 测试」属服务可用时 judge 操作（需 Qwen3-Omni 服务可达 + 3 个 fixture 音频），本机 mock 阶段不跑，按 plan §Task 9 C 「PASS（mock 阶段）」判定。Full PASS 需等服务可用 + 删除 4 处 @pytest.mark.skip 装饰器后跑 4 passed。",
  "smoke_tests": "N/A — 本 task 不动业务代码（qwen3omni_critic.py / director / tts 等模块未修改），无需 smoke 测试。pytest -v 已是 mock 阶段 smoke。",
  "static_review": {
    "section_a_pass": "2/2 (+ 2 contract 全部 PASS)",
    "section_b_pass": "5/5 (+ 4 red flag 全部未触发)",
    "literal_diff": "BYTE-EQUAL (plan line 1299-1364 vs test_qwen3omni_critic.py 追加块, 66 lines, md5 52b084274ef238539e0f434f177bf6e6, 0 char diff)",
    "commit_scope": "2 files / +560 lines (test_qwen3omni_critic.py M +68 + dev doc A +492)",
    "red_flags": "0",
    "scope_creep": "0"
  },
  "reason": "4 个 skip-marked integration 测试 + 1 个共享常量 + 3 行分隔注释与 plan line 1299-1364 字面量 md5 比对 BYTE-EQUAL；judge 自跑 2 条 Self-check 命令实测 9 passed + 4 skipped + -m integration 4 skipped 无回归；commit 72e3d4b 已落盘且 scope 严格（仅 2 文件）；0 red flag / 0 scope creep；plan 字面 7 vs 实测 9 的数量偏离属 Task 6 既存基线非本 task bug",
  "blocking_issues": [],
  "next_action": "PASS（mock 阶段）— 可进入 Task 10（TTSRepairAgent 失败测试，新建 src_next/critic/tests/test_tts_repair.py，回到 feat(critic): commit 类型）。Full PASS（启用 integration 测试）需等服务可用 + 3 个 fixture 音频准备后由 judge 操作：全局搜索 @pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON) 并删除该行（共 4 处），然后 pytest -m integration -v 期望 4 passed。"
}
```

---

## 8. 给后续 task 的提醒

1. **Task 10（TTSRepairAgent 失败测试）**：新建 `src_next/critic/tests/test_tts_repair.py`，与本文件解耦。Task 10 起回到 `feat(critic):` commit 类型（业务代码）。

2. **本 task 4 个 integration 测试在 Task 10+ 不应被改动**：除非 plan 后续 task 明确要求启用（plan §Task 9 B「judge 操作」才有权删除 `@pytest.mark.skip` 行），coding-Agent 不得擅自动这 4 个测试的装饰器或断言。

3. **`_make_segment_and_instruction` helper 在 Task 10+ 仍然适用**：Task 10 起 `test_tts_repair.py` 会用 `Segment` + `ModelSpecificTTSInstruction` + `CriticResult` 构造输入，可能需要新的 `_make_inputs` helper（plan §Task 10 line 1470-1490 给出新 helper 字面量）——与本 task 的 `_make_segment_and_instruction` 共存，不冲突。

4. **commit 类型延续 vs 切换**：Task 7/8/9 都是测试代码，用 `test(critic):` 前缀；Task 10/11（TTSRepairAgent 业务代码）切回 `feat(critic):`；Task 12（repair integration 骨架）再回 `test(critic):`。

5. **passed count 偏离提醒**：Task 10+ 跑 `pytest -v` 时，本 task 加的 4 个 integration 测试仍然全部 SKIPPED，总数预期是 `9 passed + 4 skipped + N new`（N 为新 task 加的测试数）。如果 plan 后续 task 字面期望与实测不符，先检查是否 Task 6 既存基线 +2 + 本 task +4 skip 的累积效应。

6. **启用流程提示（judge-Agent 在服务可用时操作）**：全局搜索 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 并删除该行（共 4 处），然后 `pytest -m integration -v` 期望 4 passed（需 3 个 fixture 音频 + Qwen3-Omni 服务可达）。启用前需准备 `src_next/critic/tests/fixtures/good_narration.wav` / `bad_clipping.wav` / `emotion_mismatch.wav`（KNOWN_ISSUES.md §3 已登记）。**注意：删除 `@pytest.mark.skip` 后保留 `@pytest.mark.integration` 装饰器**，仍可用 `-m "not integration"` 筛选。

---

## 9. 一句话总结

Task 9 = 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加 4 个 skip-marked integration 测试 + 1 个共享常量 `_INTEGRATION_SKIP_REASON` + 3 行分隔注释（共 +68 行新增，0 行修改），与 plan line 1299-1364 代码块 md5 比对 **BYTE-EQUAL**（md5 `52b084274ef238539e0f434f177bf6e6`，66 行对 66 行，0 字符偏离）；judge 自跑 `pytest -v` 实测 `9 passed, 4 skipped in 0.10s`（既有 9 个 unit/robustness 全 PASS + 本 task 4 个 integration 全 SKIP，无回归；plan 期望 "7 PASS + 4 SKIPPED" 是 plan 作者假设 Task 6 只交付 3 个测试，实际 Task 6 交付 5 个，与 Task 8 同根源）；`pytest -m integration -v` 实测 `4 skipped, 9 deselected in 0.02s`（plan §Task 9 A Self-check 第 2 条字面期望达成）；commit `72e3d4b` 已落盘，scope 严格（仅 2 文件 / +560 行）；Acceptance A 表 2/2 + 2 contract 全部 PASS，B 表 5/5 全部 PASS + 4 Red flag 全部未触发，0 red flag / 0 scope creep，**PASS（mock 阶段）**。
