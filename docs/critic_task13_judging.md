# Critic Task 13 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 13（line 2163 起）
> **Spec:** 无独立 spec；Acceptance Criteria (Simplified) 在 plan 内（line 2205 起）
> **Coding dev doc:** `docs/critic_task13_coding.md`
> **分支:** `feature/critic-and-tta`
> **Task 13 commit:** `44ab5f7 feat(critic): implement task 13 (round 1)`
> **验收日期:** 2026-07-08
> **Task 类型:** 纯验证型 task（py_compile + 文件计数 + git diff 红旗排查）— **无代码改动**
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS（mock 阶段）**：纯验证型 task，Section A 自检 2/2 命中 plan 字面期望（`py_compile OK` + `git diff | wc -l = 11` ≥ 8），Section B 静态审查 4/4 全过（任务卡 §1.2 manifest 8 文件齐备 / 0 个 `output*` 红旗 / 0 个 `.env|credentials|secret` 红旗 / 3 个 auxiliary 文件全在 diff），commit `44ab5f7` scope clean（只 1 个 dev doc，0 个 `src_next/critic/` 改动，符合 plan §Task 13 「No changes; verification only」约束）。

---

## 1. 验收范围

按 plan §Task 13 Acceptance Criteria (Simplified) 验收 2 个动作 + 4 条静态点：

| Step | Plan 要求（line） | 验收方式 |
|---|---|---|
| Step 1: py_compile 10 个 .py 文件 | line 2167-2183（10 个文件路径 + `python -m py_compile`） | judge 自己跑 py_compile + `echo "py_compile OK"`（不信 coding doc）|
| Step 2: git diff 文件清单 ≥ 8 + auxiliary 齐备 | line 2185-2201（8 个 manifest + 3 个 auxiliary） | judge 自己跑 `git diff --name-only` + wc/grep 核对 |
| Section B.1-B.4 静态点 | line 2229-2232 | Grep / Read 工具核对（每个 PASS 必须有具体工具输出证据） |

**不在本 task 范畴的项：**

- Task 14 `pytest -m "not integration" -v` 期望 15 passed（mock 端到端）— 属 Task 14
- Task 14 `pytest -m integration -v` 期望 5 skipped — 属 Task 14
- Task 15 PR sample 编写 — 属 Task 15
- Task 16 PR 创建 + push — 属 Task 16；push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理

---

## 2. Section A — coding-Agent Self-check（judge 自己跑）

| 项 | Plan 期望（line） | judge 实测 | 状态 |
|---|---|---|---|
| A.1 `python -m py_compile ... 10 个文件 && echo "py_compile OK"` | line 2211-2223：`py_compile OK`（无任何输出 = 成功） | 单行 stdout `py_compile OK`，退出码 0，无 stderr（详见 §6.1） | PASS |
| A.2 `git diff --name-only main...HEAD -- src_next/critic/ \| wc -l` | line 2224-2225：`>= 8`（任务卡 §1.2 manifest） | `11`（详见 §6.2，11 = 8 manifest + KNOWN_ISSUES.md + conftest.py + tts_repair.py） | PASS |

**A 表：2/2 全过。**

---

## 3. Section B — judge-Agent 抽查（静态审查）

| 抽查点 | Plan 期望（line） | judge 实测证据（Grep / Read） | 状态 |
|---|---|---|---|
| B.1 `git diff --name-only main...HEAD -- src_next/critic/` 输出含任务卡 §1.2 全部 8 个文件 | line 2229 | §6.2 实测 diff 11 行，逐行核对 manifest 8 个文件全部命中：`__init__.py` / `prompts/__init__.py` / `prompts/critic_prompt.py` / `prompts/repair_prompt.py` / `qwen3omni_critic.py` / `tests/__init__.py` / `tests/test_qwen3omni_critic.py` / `tests/test_tts_repair.py`，8/8 全过 | PASS |
| B.2 输出**不含** `output*` 路径下的文件 | line 2230 | §6.3 实测 `grep -E "output\|\.env\|credentials\|secret"` 退出码 1（无匹配），clean | PASS |
| B.3 输出**不含** `.env` / `credentials` / 任何疑似 secret 文件 | line 2231 | §6.3 同上 grep 退出码 1，clean | PASS |
| B.4 auxiliary 文件（pytest.ini / KNOWN_ISSUES.md / conftest.py）也在 diff 里 | line 2232 | §6.4 单独验证：`git diff --name-only main...HEAD -- pytest.ini src_next/critic/KNOWN_ISSUES.md src_next/critic/tests/conftest.py` 输出 3 行全部命中（pytest.ini 在仓库根，KNOWN_ISSUES.md + conftest.py 在 `src_next/critic/` 过滤范围内） | PASS |

**B 表静态审查：4/4 全过。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 字面量核对（plan §Task 13 Step 1 line 2171-2181 vs py_compile 实际编译目标）

| 关键字面量 | Plan 字面位置 | 实际编译目标 | 一致性 |
|---|---|---|---|
| `src_next/critic/__init__.py` | line 2172 | Bash 工具调用参数第 1 个 | ✓ 字面匹配 |
| `src_next/critic/qwen3omni_critic.py` | line 2173 | Bash 工具调用参数第 2 个 | ✓ 字面匹配 |
| `src_next/critic/tts_repair.py` | line 2174 | Bash 工具调用参数第 3 个 | ✓ 字面匹配 |
| `src_next/critic/prompts/__init__.py` | line 2175 | Bash 工具调用参数第 4 个 | ✓ 字面匹配 |
| `src_next/critic/prompts/critic_prompt.py` | line 2176 | Bash 工具调用参数第 5 个 | ✓ 字面匹配 |
| `src_next/critic/prompts/repair_prompt.py` | line 2177 | Bash 工具调用参数第 6 个 | ✓ 字面匹配 |
| `src_next/critic/tests/__init__.py` | line 2178 | Bash 工具调用参数第 7 个 | ✓ 字面匹配 |
| `src_next/critic/tests/conftest.py` | line 2179 | Bash 工具调用参数第 8 个 | ✓ 字面匹配 |
| `src_next/critic/tests/test_qwen3omni_critic.py` | line 2180 | Bash 工具调用参数第 9 个 | ✓ 字面匹配 |
| `src_next/critic/tests/test_tts_repair.py` | line 2181 | Bash 工具调用参数第 10 个 | ✓ 字面匹配 |
| `&& echo "py_compile OK"` | line 2222（Acceptance A） | Bash 工具调用尾段 | ✓ 字面匹配 |

**字面量比对结果：** 10 个 .py 文件路径 + echo 字面量与 plan §Task 13 Step 1 + Acceptance A 逐字一致，judge 跑出 stdout `py_compile OK` 与 plan 字面期望 BYTE-EQUAL。

### 4.2 文件 scope 核对（commit `44ab5f7`）

| 文件 | Plan 期望操作 | judge `git show --stat 44ab5f7` 实测 | 状态 |
|---|---|---|---|
| `docs/critic_task13_coding.md` | 创建（dev doc 落盘） | `+331 +++`（1 file changed, 331 insertions） | PASS |
| `src_next/critic/**` | **不动**（plan §Task 13 「No changes; verification only」） | commit `44ab5f7` 0 个 `src_next/critic/` 改动 | PASS |
| `pytest.ini` | 不动 | commit `44ab5f7` 0 改动 | PASS |
| `KNOWN_ISSUES.md` | 不动 | commit `44ab5f7` 0 改动 | PASS |
| plan 文件 | 不动 | commit `44ab5f7` 0 改动 | PASS |
| task-acceptance-judge skill | 不动 | commit `44ab5f7` 0 改动 | PASS |

**`git show --stat 44ab5f7` 完整输出（§6.5）：** 1 file changed, 331 insertions（+），0 deletions。

### 4.3 累积 critic/ 目录 scope（Task 1-13 累积）

`git diff main...HEAD -- src_next/critic/` 整个目录共 11 个文件 / 1356 insertions / 0 deletions（与 Task 12 judging §4.2 完全一致，本 task 未动 critic/ 下任何文件）：

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

### 4.4 10 个 .py 文件行数验证（确认文件实质内容，非空 stub）

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

> 行数分布合理：3 个 `__init__.py` 各 1 行（namespace 占位，符合 Python 包约定），4 个业务文件（qwen3omni_critic 196 / tts_repair 91 / critic_prompt 203 / repair_prompt 89）= 579 行实现代码，3 个测试基础设施（conftest 78 / test_qwen3omni_critic 381 / test_tts_repair 243）= 702 行测试代码。生产/测试比约 0.83（579 / 702），高于社区惯例 0.5 — 测试覆盖充分。**Task 13 commit 未改动任何 .py 文件，行数与 Task 12 终态完全一致。**

---

## 5. 偏离登记

| 项 | Plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| A.1 py_compile 输出 | `py_compile OK`（line 2223） | 单行 stdout `py_compile OK`，exit 0，无 stderr | 无 | — |
| A.2 diff 行数 | `>= 8`（line 2225） | `11`（8 manifest + KNOWN_ISSUES.md + conftest.py + tts_repair.py） | 无 | 多出的 3 个文件属合理交付：KNOWN_ISSUES.md + conftest.py 是 plan §Task 13 Step 2 line 2201 明确要求的 auxiliary，tts_repair.py 是 Task 11 的实质交付（任务卡 §1.2 manifest 未列但属于完整 critic 模块必需） |
| Section B.1 manifest 8 文件 | 全部在 diff（line 2229） | 8/8 全过 | 无 | — |
| Section B.2-B.3 红旗排查 | 不含 output* / .env / credentials / secret（line 2230-2231） | grep 退出码 1，clean | 无 | — |
| Section B.4 auxiliary 3 文件 | 全部在 diff（line 2232） | 3/3 全过（KNOWN_ISSUES.md + conftest.py 在 src_next/critic/ 过滤范围；pytest.ini 在仓库根单独验证） | 无 | — |
| commit message 字面量 | plan 未指定（§Task 13 「No changes; verification only」无 commit 字面量约束） | `feat(critic): implement task 13 (round 1)`（沿用 Task 10/11 模板） | 无 | plan §Task 13 未规定 commit 类型字面量；coding-Agent 沿用既有 `feat(critic): implement task N (round 1)` 模板（Task 10/11 已建立）。**注：** 严格按 Conventional Commits 语义，纯验证型 task 应该用 `test(critic):` 或 `docs(critic):`，但 plan 无字面量要求，不构成 blocker |
| commit scope | plan 隐含（「No changes; verification only」= 只 dev doc） | commit `44ab5f7` 只 1 个文件（dev doc +331 行），0 个 src_next/critic/ 改动 | 无 | 完全符合 plan §Task 13 字面约束 |

**无结构性偏离。** Step 1 输出与 plan 字面期望 BYTE-EQUAL；Step 2 文件清单 11 个全部是预期范围内的 critic 模块累积交付物（Task 1-12 已落盘），无任何越界文件 / 红旗命中。

---

## 6. Red Flags 排查 + 实测输出

### 6.1 A.1 实测输出（judge 自己跑，未抄 coding doc）

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

退出码 0，单行 stdout `py_compile OK`，无 stderr，无 syntax error / traceback / warning。

→ 与 plan §Task 13 Acceptance A 第 1 条字面期望 `py_compile OK` 完全一致。

### 6.2 A.2 实测输出（diff 行数）

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
```

→ `11 >= 8` ✓，与 plan §Task 13 Acceptance A 第 2 条字面期望 `>= 8` 完全一致。

**任务卡 §1.2 manifest 8 文件逐行核对：**

| Manifest 文件（plan line 2191-2198） | diff 行号 | 命中 |
|---|---|---|
| `src_next/critic/__init__.py` | 2/11 | ✓ |
| `src_next/critic/prompts/__init__.py` | 3/11 | ✓ |
| `src_next/critic/prompts/critic_prompt.py` | 4/11 | ✓ |
| `src_next/critic/prompts/repair_prompt.py` | 5/11 | ✓ |
| `src_next/critic/qwen3omni_critic.py` | 6/11 | ✓ |
| `src_next/critic/tests/__init__.py` | 7/11 | ✓ |
| `src_next/critic/tests/test_qwen3omni_critic.py` | 8/11 | ✓ |
| `src_next/critic/tests/test_tts_repair.py` | 9/11 | ✓ |

→ **8/8 全过。**

**Auxiliary 3 文件（plan line 2201）：**

| Auxiliary 文件 | diff 行号 | 命中验证方式 |
|---|---|---|
| `src_next/critic/KNOWN_ISSUES.md` | 1/11（在 src_next/critic/ 过滤范围内） | §6.2 行 1 |
| `src_next/critic/tests/conftest.py` | 10/11（在 src_next/critic/ 过滤范围内） | §6.2 行 10 |
| `pytest.ini`（仓库根） | 不在 src_next/critic/ 过滤范围 | §6.4 单独验证 |

### 6.3 红旗排查（output / .env / credentials / secret）

```
$ git diff --name-only main...HEAD -- src_next/critic/ | grep -E "output|\.env|credentials|secret"
exit=1
```

→ grep 退出码 1（无匹配），clean。

### 6.4 Auxiliary 单独验证（pytest.ini 在仓库根）

```
$ git diff --name-only main...HEAD -- pytest.ini src_next/critic/KNOWN_ISSUES.md src_next/critic/tests/conftest.py
pytest.ini
src_next/critic/KNOWN_ISSUES.md
src_next/critic/tests/conftest.py
```

→ 3 个 auxiliary 全部命中。

### 6.5 commit 链（验证 Task 12 前置 + Task 13 commit 落盘）

```
$ git log --oneline -5
44ab5f7 feat(critic): implement task 13 (round 1)
4a6add1 docs(superpowers): sync task-code-judge-loop skill design
f87028f docs(critic): track task 8-12 judging docs
8d0278d test(critic): add repair integration test skeleton (skip-marked)
dec44dc chore: untrack 2 stale output/analysis md files
```

→ Task 13 commit `44ab5f7` 在 HEAD，前置 Task 12 commit `8d0278d` 已落盘（中间 `4a6add1` / `f87028f` 是与本 task 无关的 docs/skill commit，不影响）。

### 6.6 Task 13 commit scope（`git show --stat 44ab5f7`）

```
commit 44ab5f71ece2d9cb30752a654463627817d3a622
Author: l30083418 <l300834181@h-partners.com>
Date:   Wed Jul 8 16:40:38 2026 +0800

    feat(critic): implement task 13 (round 1)

 docs/critic_task13_coding.md | 331 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 331 insertions(+)
```

→ scope clean：只 1 个 dev doc（+331 行），0 个 src_next/critic/ 改动，0 个其它文件改动。完全符合 plan §Task 13 「No changes; verification only」字面约束。

### 6.7 Red Flags 排查清单（CLAUDE.md §9 硬约束 + plan §Task 13 line 2229-2232）

| Red flag | 自检 | 状态 |
|---|---|---|
| diff 不含任务卡 §1.2 manifest 全部 8 个文件 | §6.2 表格：8/8 全在 diff 内 | ✓ 未犯 |
| diff 含 `output*` 路径下的文件（误提交合成产物） | §6.3 grep 退出码 1，clean | ✓ 未犯 |
| diff 含 `.env` / `credentials` / secret 文件 | §6.3 grep 退出码 1，clean | ✓ 未犯 |
| auxiliary 文件（pytest.ini / KNOWN_ISSUES.md / conftest.py）漏在 diff 外 | §6.2 + §6.4：3/3 全过 | ✓ 未犯 |
| 越界动 `src_next/critic/` 下源码或测试文件 | §6.6 `git show --stat 44ab5f7` 只 1 个 dev doc，0 个 src_next/critic/ 改动 | ✓ 未犯 |
| 改 `src/` 旧链路 | `git diff main...HEAD -- src/` 无任何变更（critic/ 都在 src_next/） | ✓ 未犯 |
| 改 `requirements.txt` | `git diff main...HEAD -- requirements.txt` 无变更 | ✓ 未犯 |
| 硬编码服务器地址 | 本 task 是纯验证型，无代码改动，自然无硬编码 | ✓ 未犯 |
| `--no-verify` 跳 hooks | commit `44ab5f7` 正常落盘，git log 显示完整 | ✓ 未犯 |
| scope creep（动业务代码） | §6.6 commit 只 dev doc，未动 src_next/critic/ 任何文件 | ✓ 未犯 |

**10/10 Red flag 全避。**

### 6.8 Scope creep 检查（plan §Task 13 「No changes; verification only」 + 后续 task 不交付清单）

| 不交付项 | 实测 | 状态 |
|---|---|---|
| Task 14 `pytest -m "not integration"` 全绿 | 本 task 未做（属 Task 14 范畴） | ✓ |
| Task 14 `pytest -m integration -v` 5 skipped | 本 task 未做（属 Task 14 范畴） | ✓ |
| Task 15 `docs/pr_samples/critic_sample.md` mock I/O 样例 | 本 task 未做（属 Task 15 范畴） | ✓ |
| Task 16 PR 创建 + push | 本 task 未做（属 Task 16 范畴；push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理） | ✓ |
| 启用 integration 测试（删 `@pytest.mark.skip`） | 未删（这是 judge-Agent 在服务可用环境里的动作，不在本 coding task 范围） | ✓ |
| 动业务代码（src_next/critic/ 下任何 .py） | §6.6 `git show --stat 44ab5f7` 0 改动 | ✓ |
| 改 pytest.ini / KNOWN_ISSUES.md | §6.6 commit 未动这两个文件 | ✓ |
| 改 plan 文件 / task-acceptance-judge skill | §6.6 commit 未动 | ✓ |

**8/8 scope creep 全避。**

### 6.9 当前 git status（验证本 task 后工作区状态）

```
$ git status --short
?? docs/intern_b_audio_oscar_research.md
?? docs/intern_b_audio_oscar_why.md
?? docs/intern_b_critic_and_tta.md
?? docs/superpowers/specs/2026-07-01-push-with-output-ignore-skill-design.md
?? docs/superpowers/specs/2026-07-02-task-acceptance-judge-skill-design.md
?? input.rar
?? src_next/profiles/server_qwen_voicegenerator.yaml
?? webui_old.py
```

> 工作区只有 untracked 无关文件（与本 task 无关的历史遗留 + 其他 task 的 design doc）。`src_next/critic/` 下 0 modified / 0 staged — 完全符合 plan §Task 13 「No changes; verification only」约束。本 task commit `44ab5f7` 只 add `docs/critic_task13_coding.md` 一个文件。

---

## 7. Verdict JSON

```json
{
  "task_id": "task-13",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m py_compile src_next/critic/{__init__.py,qwen3omni_critic.py,tts_repair.py,prompts/__init__.py,prompts/critic_prompt.py,prompts/repair_prompt.py,tests/__init__.py,tests/conftest.py,tests/test_qwen3omni_critic.py,tests/test_tts_repair.py} && echo py_compile OK",
      "git diff --name-only main...HEAD -- src_next/critic/ | wc -l",
      "git diff --name-only main...HEAD -- src_next/critic/ | grep -E \"output|\\.env|credentials|secret\"",
      "git diff --name-only main...HEAD -- pytest.ini src_next/critic/KNOWN_ISSUES.md src_next/critic/tests/conftest.py",
      "git show --stat 44ab5f7"
    ],
    "result": "py_compile OK + diff 行数 11 (>= 8) + grep 退出码 1 (clean) + auxiliary 3/3 + commit scope 1 file（dev doc only）；与 plan §Task 13 Acceptance A+B 字面期望完全一致"
  },
  "integration_tests": "N/A（plan §Task 13 不要求 integration 测试，integration 测试启用属 Task 14 范畴）",
  "smoke_tests": "N/A（本 task 是纯验证型，无代码改动，无 pipeline smoke test 需求）",
  "static_review": {
    "section_a_self_checks_passed": "2/2",
    "section_b_static_checks_passed": "4/4",
    "red_flags_avoided": "10/10（CLAUDE.md §9 硬约束 6 + plan §Task 13 line 2229-2232 红 4）",
    "scope_creep_avoided": "8/8",
    "literal_byte_equal": true,
    "literal_match_count": "11/11 关键字面量逐字匹配（§4.1：10 个 .py 文件路径 + echo 字面量）",
    "commit_scope_files": 1,
    "commit_scope_violations": 0,
    "commit_message_literal_match": "N/A（plan §Task 13 未规定 commit message 字面量；沿用 Task 10/11 模板 `feat(critic): implement task N (round 1)`，不构成 blocker）"
  },
  "reason": "纯验证型 task 通过：py_compile 10 个 .py 文件单行输出 py_compile OK + git diff 文件清单 11 行（含任务卡 §1.2 manifest 全部 8 + auxiliary 3）+ 0 红旗（output/.env/credentials/secret 全 clean）+ commit scope 1 file（dev doc only，0 个 src_next/critic/ 改动），完全符合 plan §Task 13 「No changes; verification only」字面约束",
  "blocking_issues": [],
  "next_action": "进入 Task 14（pytest -m \"not integration\" -v 期望 15 passed + -m integration -v 期望 5 skipped）。push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理（不要在本 judge 流程里 push）。"
}
```

---

## 8. 给后续 task 的提醒

### 8.1 给 Task 14 的提醒

- **Task 14 范围（plan line 2238-2259）：**
  - `python -m pytest src_next/critic/tests/ -m "not integration" -v` 期望 **15 passed**（test_qwen3omni_critic.py 7 个 mock + test_tts_repair.py 8 个 mock = 15）
  - `python -m pytest src_next/critic/tests/ -m integration -v` 期望 **5 skipped**（4 个 critic integration + 1 个 repair integration = 5）
- **前置依赖已就绪：** 本 task（Task 13）已确认 10 个 .py 文件全部 py_compile 通过，Task 14 可以直接跑 pytest 不会因 syntax error 失败
- **integration 测试当前状态：** 5 个 integration 测试全部带 `@pytest.mark.skip`，在本 mock 环境下不会跑

### 8.2 给 Task 16 的提醒

- **push 前提醒：** 本 task commit `44ab5f7` 后工作区还有 untracked 文件（`docs/intern_b_*.md` × 3 / `docs/superpowers/specs/2026-07-*.md` × 2 / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `webui_old.py`）— push 前应用 push-with-output-ignore skill 处理 .gitignore，避免误推

### 8.3 给本仓库未来 critic task 的提醒

- **纯验证型 task 的 commit 类型选择：** 本 task 沿用 `feat(critic):` 模板（Task 10/11 已建立），但严格按 Conventional Commits 语义，纯验证型 task 应该用 `test(critic):` 或 `docs(critic):`。**未来类似的纯验证型 task 建议用 `test(critic):` 类型**，与 Conventional Commits 语义对齐
- **Section A 命令解析风险：** plan §Task 13 Acceptance A 的 bash 代码块用 `\` 续行 + `&&` 链接，judge 必须完整复制命令（包括 echo 部分），不能省略 `&& echo "py_compile OK"`，否则 stdout 不匹配 plan 字面期望
- **`git diff --name-only` 过滤范围：** 注意 `-- src_next/critic/` 过滤会排除仓库根文件（如 `pytest.ini`），需要单独验证 `git diff --name-only main...HEAD -- pytest.ini`，否则 auxiliary 检查会漏掉

---

## 9. 一句话总结

Task 13 = plan Day 2 验证收口：纯验证型 task，judge 自己跑 Section A 实测 **`py_compile OK` + diff 行数 11（≥ 8）** 与 plan 字面期望 BYTE-EQUAL，Section B 静态审查 4/4 全过（manifest 8 文件齐备 + 0 个 `output*|\.env|credentials|secret` 红旗 + auxiliary 3 文件全在 diff）+ CLAUDE.md §9 硬约束 Red flags 10/10 + scope creep 8/8 全避，commit `44ab5f7` scope clean（只 1 个 dev doc +331 行，0 个 `src_next/critic/` 改动），完全符合 plan §Task 13 「No changes; verification only」字面约束。**建议 PASS（mock 阶段）**。
