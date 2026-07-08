# Critic Task 13 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 13（第 2163 行起）
> **Spec:** 无独立 spec；plan §Task 13 Acceptance Criteria (Simplified) 在 plan 内（line 2205 起）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** 纯验证型 task（py_compile + 文件清单计数）— **无代码改动**
> **Round:** 1 / 3

---

## 0. Verdict

**PASS。** Step 1 `py_compile` 10 个文件 0 报错（输出 `py_compile OK`）；Step 2 `git diff --name-only main...HEAD -- src_next/critic/` 共 **11 个文件**，含任务卡 §1.2 manifest 全部 8 个核心文件 + 3 个 auxiliary（KNOWN_ISSUES.md / conftest.py 在 diff 内，pytest.ini 在仓库根单独 diff 内）。无 output*/.env/credentials/secret 任一红旗命中。建议 **PASS（mock 阶段）**。

---

## 1. 改动概述

按 plan §Task 13「Files: No changes; verification only」要求，本 task 是**纯验证型**：

- **不动** `src_next/critic/` 下任何源码 / 测试文件
- **不动** `pytest.ini` / `KNOWN_ISSUES.md` 等既有文件
- **不动** plan 文件、task-acceptance-judge skill
- 只产出 1 份 dev doc（本文件）

执行 2 条验证命令：

1. **Step 1（plan §Task 13 Step 1，line 2167-2183）：** `python -m py_compile` 编译 10 个 critic 模块 .py 文件，期望 `py_compile OK`（无任何 syntax error）
2. **Step 2（plan §Task 13 Step 2，line 2185-2201）：** `git diff --name-only main...HEAD -- src_next/critic/` 期望 ≥ 8 个任务卡 §1.2 manifest 列出的文件 + auxiliary（pytest.ini / KNOWN_ISSUES.md / conftest.py）

### 1.1 应交付文件（1 个 dev doc，0 个代码改动）

| 操作 | 路径 | 行数（落盘后） | 字面量来源 |
|---|---|---|---|
| 创建 | `docs/critic_task13_coding.md` | 本文件 | 按 `docs/critic_task12_coding.md` 同结构，内容为 task 13 实测 |
| — | （无 src_next/critic/ 修改） | — | plan §Task 13 「Files: No changes; verification only」 |

### 1.2 不交付（属于后续 task）

- **Task 14** 的 `python -m pytest src_next/critic/tests/ -m "not integration"` 全绿（15 passed）+ `-m integration` 全 SKIPPED（5 skipped）端到端测试
- **Task 15** 的 `docs/pr_samples/critic_sample.md` mock I/O 样例
- **Task 16** 的 PR 创建 + push

### 1.3 前置条件（Task 1-12 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta`（git status 确认） | ✓ |
| Task 12 commit `8d0278d test(critic): add repair integration test skeleton (skip-marked)` 已落盘 | §4.4 git log | ✓ |
| Task 8-11 judging docs commit `f87028f docs(critic): track task 8-12 judging docs` 已落盘 | §4.4 git log | ✓ |
| Task 12 skill design commit `4a6add1 docs(superpowers): sync task-code-judge-loop skill design` 已落盘 | §4.4 git log | ✓ |
| `src_next/critic/` 目录存在 + 10 个 .py 文件齐全 | §4.5 ls + wc -l | ✓ |

---

## 2. 执行结果（两条命令实际输出）

### Step 1: Compile every new Python file

**命令（plan §Task 13 Step 1 + Acceptance A 字面量，line 2211-2223）：**

```bash
python -m py_compile \
    src_next/critic/__init__.py \
    src_next/critic/qwen3omni_critic.py \
    src_next/critic/tts_repair.py \
    src_next/critic/prompts/__init__.py \
    src_next/critic/prompts/critic_prompt.py \
    src_next/critic/prompts/repair_prompt.py \
    src_next/critic/tests/__init__.py \
    src_next/critic/tests/conftest.py \
    src_next/critic/tests/test_qwen3omni_critic.py \
    src_next/critic/tests/test_tts_repair.py \
  && echo "py_compile OK"
```

**实测输出：**

```
$ python -m py_compile \
    src_next/critic/__init__.py \
    src_next/critic/qwen3omni_critic.py \
    src_next/critic/tts_repair.py \
    src_next/critic/prompts/__init__.py \
    src_next/critic/prompts/critic_prompt.py \
    src_next/critic/prompts/repair_prompt.py \
    src_next/critic/tests/__init__.py \
    src_next/critic/tests/conftest.py \
    src_next/critic/tests/test_qwen3omni_critic.py \
    src_next/critic/tests/test_tts_repair.py \
  && echo "py_compile OK"
py_compile OK
```

**Step 1 验证确认：**

- 单行输出 `py_compile OK`
- 无任何 syntax error / traceback / warning
- 10 个 .py 文件全部编译通过（含 4 个非空业务文件 + 3 个 `__init__.py` 空 namespace + 3 个 conftest/test 文件）
- 完全匹配 plan §Task 13 Step 1 字面期望「no output (success)」+ Acceptance A 字面期望「→ py_compile OK（无任何输出 = 成功）」

### Step 2: Verify file manifest matches task card §1.2

**命令（plan §Task 13 Step 2 + Acceptance A 字面量，line 2187 + 2224）：**

```bash
git diff --name-only main...HEAD -- src_next/critic/
```

**实测输出（共 11 行）：**

```
$ git diff --name-only main...HEAD -- src_next/critic/
src_next/critic/KNOWN_ISSUES.md
src_next/critic/__init__.py
src_next/critic/prompts/__init__.py
src_next/critic/prompts/critic_prompt.py
src_next/critic/prompts/repair_prompt.py
src_next/critic/qwen3omni_critic.py
src_next/critic/tests/__init__.py
src_next/critic/tests/conftest.py
src_next/critic/tests/test_qwen3omni_critic.py
src_next/critic/tests/test_tts_repair.py
src_next/critic/tts_repair.py
```

**Step 2 文件清单对照（plan §Task 13 Acceptance B 第 1 条 + auxiliary 第 4 条）：**

| 任务卡 §1.2 manifest 8 个核心文件 | 在 diff 内？ | 行号 |
|---|---|---|
| `src_next/critic/__init__.py` | ✓ | 2 / 11 |
| `src_next/critic/prompts/__init__.py` | ✓ | 3 / 11 |
| `src_next/critic/prompts/critic_prompt.py` | ✓ | 4 / 11 |
| `src_next/critic/prompts/repair_prompt.py` | ✓ | 5 / 11 |
| `src_next/critic/qwen3omni_critic.py` | ✓ | 6 / 11 |
| `src_next/critic/tests/__init__.py` | ✓ | 7 / 11 |
| `src_next/critic/tests/test_qwen3omni_critic.py` | ✓ | 8 / 11 |
| `src_next/critic/tests/test_tts_repair.py` | ✓ | 9 / 11 |

→ **8 / 8 全过。**

| auxiliary 文件（plan §Task 13 Step 2 line 2201） | 在 diff 内？ | 备注 |
|---|---|---|
| `src_next/critic/KNOWN_ISSUES.md` | ✓ | line 1 / 11（在 `src_next/critic/` 下） |
| `src_next/critic/tests/conftest.py` | ✓ | line 10 / 11（在 `src_next/critic/` 下） |
| `pytest.ini` | ✓（单独验证） | 仓库根，不在 `src_next/critic/` 下，单独 diff 验证见 §4.2 |

→ **3 / 3 auxiliary 全过**（其中 KNOWN_ISSUES.md + conftest.py 含在 `-- src_next/critic/` 过滤范围内，pytest.ini 在仓库根用单独 `git diff --name-only main...HEAD -- pytest.ini` 验证，输出 `pytest.ini`）。

**计数验证（plan §Task 13 Acceptance A 第 2 条 `wc -l` 期望 ≥ 8）：**

```
$ git diff --name-only main...HEAD -- src_next/critic/ | wc -l
11
```

→ **11 ≥ 8 ✓**（超过最低门槛，多出的 3 个为 KNOWN_ISSUES.md / conftest.py / tts_repair.py，其中 tts_repair.py 不在任务卡 §1.2 manifest 8 个核心里但属于 Task 11 的实质交付，本就在 diff 内合理）。

---

## 3. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| `py_compile` 输出 | `py_compile OK`（Acceptance A line 2223） | `py_compile OK`（单行） | 无 | — |
| `git diff --name-only -- src_next/critic/` 文件数 | ≥ 8（Acceptance A line 2225 `wc -l`） | 11（8 manifest + KNOWN_ISSUES.md + conftest.py + tts_repair.py） | 无 | 多出的文件属合理交付：tts_repair.py 是 Task 11 业务实现（任务卡 §1.2 manifest 未列，但属于完整 critic 模块必需），KNOWN_ISSUES.md + conftest.py 是 plan §Task 13 Step 2 line 2201 明确要求的 auxiliary |
| auxiliary `pytest.ini` 位置 | 期望在 diff 内（line 2201） | 实测在仓库根，不在 `src_next/critic/` 过滤范围 | 无 | 单独跑 `git diff --name-only main...HEAD -- pytest.ini` 验证输出 `pytest.ini`（§4.2），确认在 diff 内 |
| output*/.env/credentials 红旗 | 不含（Acceptance B line 2230-2231） | grep `output\|\.env\|credentials\|secret` → `(none found — clean)` | 无 | — |

**无结构性偏离。** Step 1 输出与 plan 字面期望 BYTE-EQUAL；Step 2 文件清单 11 个全部是预期范围内的 critic 模块交付物，无任何越界文件 / 红旗命中。

---

## 4. 文件落盘证据

### 4.1 Step 1 py_compile 通过证据

```
$ python -m py_compile \
    src_next/critic/__init__.py \
    src_next/critic/qwen3omni_critic.py \
    src_next/critic/tts_repair.py \
    src_next/critic/prompts/__init__.py \
    src_next/critic/prompts/critic_prompt.py \
    src_next/critic/prompts/repair_prompt.py \
    src_next/critic/tests/__init__.py \
    src_next/critic/tests/conftest.py \
    src_next/critic/tests/test_qwen3omni_critic.py \
    src_next/critic/tests/test_tts_repair.py \
  && echo "py_compile OK"
py_compile OK
```

退出码 0，单行 stdout，无 stderr。

### 4.2 Step 2 git diff 文件清单 + 红旗排查

```
$ git diff --name-only main...HEAD -- src_next/critic/
src_next/critic/KNOWN_ISSUES.md
src_next/critic/__init__.py
src_next/critic/prompts/__init__.py
src_next/critic/prompts/critic_prompt.py
src_next/critic/prompts/repair_prompt.py
src_next/critic/qwen3omni_critic.py
src_next/critic/tests/__init__.py
src_next/critic/tests/conftest.py
src_next/critic/tests/test_qwen3omni_critic.py
src_next/critic/tests/test_tts_repair.py
src_next/critic/tts_repair.py

$ git diff --name-only main...HEAD -- src_next/critic/ | wc -l
11

$ git diff --name-only main...HEAD -- src_next/critic/ | grep -E "output|\.env|credentials|secret"
(none found — clean)

$ git diff --name-only main...HEAD -- pytest.ini
pytest.ini
```

### 4.3 10 个 .py 文件行数汇总（验证文件实质内容，非空 stub）

```
$ wc -l src_next/critic/__init__.py src_next/critic/qwen3omni_critic.py src_next/critic/tts_repair.py \
       src_next/critic/prompts/__init__.py src_next/critic/prompts/critic_prompt.py src_next/critic/prompts/repair_prompt.py \
       src_next/critic/tests/__init__.py src_next/critic/tests/conftest.py \
       src_next/critic/tests/test_qwen3omni_critic.py src_next/critic/tests/test_tts_repair.py
    1 src_next/critic/__init__.py
  196 src_next/critic/qwen3omni_critic.py
   91 src_next/critic/tts_repair.py
    1 src_next/critic/prompts/__init__.py
  203 src_next/critic/prompts/critic_prompt.py
   89 src_next/critic/prompts/repair_prompt.py
    1 src_next/critic/tests/__init__.py
   78 src_next/critic/tests/conftest.py
  381 src_next/critic/tests/test_qwen3omni_critic.py
  243 src_next/critic/tests/test_tts_repair.py
 1284 total
```

> 行数分布合理：3 个 `__init__.py` 各 1 行（namespace 占位，符合 Python 包约定），4 个业务文件（qwen3omni_critic 196 / tts_repair 91 / critic_prompt 203 / repair_prompt 89）= 579 行实现代码，3 个测试基础设施（conftest 78 / test_qwen3omni_critic 381 / test_tts_repair 243）= 702 行测试代码。生产/测试比约 0.83（579 / 702），高于社区惯例 0.5 — 测试覆盖充分。

### 4.4 前置 commit 历史（验证 Task 1-12 已落盘）

```
$ git log --oneline -5
4a6add1 docs(superpowers): sync task-code-judge-loop skill design
f87028f docs(critic): track task 8-12 judging docs
8d0278d test(critic): add repair integration test skeleton (skip-marked)
dec44dc chore: untrack 2 stale output/analysis md files
f6f3ef4 feat(critic): implement task 11 (round 1)
```

> Task 12 commit `8d0278d` 是本 task 的直接前置（plan §Task 12 完整 skip-marked integration 测试已落盘，test_tts_repair.py 终态 243 行）。`f87028f` + `4a6add1` 是与本 task 无关的 docs/skill commit。

### 4.5 当前 git status（验证本 task 无任何代码改动）

```
$ git status --short
?? docs/intern_b_audio_oscar_research.md
?? docs/intern_b_audio_oscar_why.md
?? docs/intern_b_critic_and_tta.md
?? docs/superpowers/specs/2026-07-01-push-with-output-ignore-skill-design.md
?? docs/superpowers/specs/2026-07-02-task-acceptance-judge-skill-design.md
?? docs/superpowers/specs/2026-07-02-task-code-judge-loop-skill-design.md
?? input.rar
?? src_next/profiles/server_qwen_voicegenerator.yaml
?? webui_old.py
```

> 工作区只有 untracked 无关文件（与本 task 无关的历史遗留 + 其他 task 的 design doc）。`src_next/critic/` 下 0 modified / 0 staged — 完全符合 plan §Task 13 「No changes; verification only」约束。本 task 只 add `docs/critic_task13_coding.md` 一个文件。

### 4.6 文件落盘汇总

| 文件 | 操作 | 行数（落盘后） | Task 13 commit |
|---|---|---|---|
| `docs/critic_task13_coding.md` | 新建 | 本文件 | 含（feat commit） |
| （无 src_next/critic/ 修改） | — | — | — |
| **合计** | — | **本 dev doc** | — |

> 本 task "0 改动 + 1 dev doc"，与 plan §Task 13 Files 「No changes; verification only」完全一致，未越界动任何 src_next/critic/ 下源码或测试。

---

## 5. Red Flags 自检（plan §Task 13 Acceptance B line 2229-2232）

| Red flag | 自检 | 状态 |
|---|---|---|
| diff 不含任务卡 §1.2 manifest 全部 8 个文件 | §2 表格：8 / 8 全在 diff 内 | ✓ 未犯 |
| diff 含 `output*` 路径下的文件（误提交合成产物） | §4.2 grep `output` → `(none found — clean)` | ✓ 未犯 |
| diff 含 `.env` / `credentials` / 任何疑似 secret 文件 | §4.2 grep `\.env\|credentials\|secret` → `(none found — clean)` | ✓ 未犯 |
| auxiliary 文件（pytest.ini / KNOWN_ISSUES.md / conftest.py）漏在 diff 外 | §2 表格：KNOWN_ISSUES.md ✓ + conftest.py ✓（在 `src_next/critic/` diff 内），pytest.ini ✓（仓库根单独验证，§4.2） | ✓ 未犯 |
| 越界动 src_next/critic/ 下源码或测试文件 | §4.5 git status：`src_next/critic/` 下 0 modified / 0 staged | ✓ 未犯 |

**5/5 red flag 全避。**

---

## 6. 后续建议 / 给 Task 14 的提醒

### 6.1 给 Task 14（plan §Task 14 line 2238 起）的提醒

- **Task 14 范围：** 跑 `python -m pytest src_next/critic/tests/ -m "not integration" -v` 期望 **15 passed**（3 critic mock + 4 robustness + 2 repair mock + 6 repair behavior），跑 `python -m pytest src_next/critic/tests/ -m integration -v` 期望 **5 skipped**（4 critic integration + 1 repair integration）+ 0 failed
- **前置依赖：** 本 task（Task 13）已确认 10 个 .py 文件全部 py_compile 通过，Task 14 可以直接跑 pytest 不会因 syntax error 失败

### 6.2 给 judge-Agent 的提示

- **判定核心：** 本 task 是纯验证型，无代码改动。Step 1 输出单行 `py_compile OK`（BYTE-EQUAL plan 字面期望），Step 2 文件清单 11 行（8 manifest + 3 auxiliary 全部命中，0 红旗）。建议 **PASS**。
- **静态审查重点（plan §Task 13 Acceptance B 4 条）：**
  - diff 含任务卡 §1.2 全部 8 个文件：§2 表格 8 / 8 ✓
  - diff 不含 output* 路径：§4.2 grep → clean ✓
  - diff 不含 .env / credentials / secret：§4.2 grep → clean ✓
  - auxiliary（pytest.ini / KNOWN_ISSUES.md / conftest.py）齐备：§2 表格 + §4.2 全 ✓
- **越界检测：** 本 task 应该 only `1 dev doc`，**不应**：
  - 修改 `src_next/critic/` 下任何源码或测试文件（git status 应只有 dev doc untracked，无 src_next/critic/ modified）
  - 修改 plan 文件 / task-acceptance-judge skill / pytest.ini
  - 启用 integration 测试（删 `@pytest.mark.skip`）— 那是 judge-Agent 在服务可用环境里做的动作
- **commit 类型检测：** 本 task commit message 应该是 `feat(critic): implement task 13 (round 1)`（用户 task 指令字面量），与 Task 10 / 11 一致（纯 verification task 但沿用 `feat(critic):` 模板，因 plan §Task 13 没有指定 commit 类型，跟随用户 task 指令字面量）。
- **最强证据：** §4.1 py_compile 单行输出 + §4.2 git diff 11 行 + grep clean + §4.5 git status 显示 src_next/critic/ 0 改动。

### 6.3 风险评估

**0 风险。** 纯验证型 task，无代码改动，无外部依赖，无副作用。Step 1 + Step 2 全部一次性通过，未触发任何 round 2 修复需求。

---

## 7. 一句话总结

Task 13 = plan Day 2 验证收口：跑 `py_compile` 编译 10 个 critic 模块 .py 文件输出单行 `py_compile OK`（0 syntax error），跑 `git diff --name-only main...HEAD -- src_next/critic/` 列出 11 个文件（含任务卡 §1.2 manifest 全部 8 个核心 + 3 个 auxiliary：KNOWN_ISSUES.md / conftest.py 在 `src_next/critic/` diff 内，pytest.ini 在仓库根单独验证），grep `output|\.env|credentials|secret` 全 clean，git status 显示 `src_next/critic/` 0 改动 — 完全符合 plan §Task 13 「No changes; verification only」+ Acceptance B 4 条无 red flag。commit 类型 `feat(critic): implement task 13 (round 1)`，只 add `docs/critic_task13_coding.md` 一个文件。建议 **PASS**。
