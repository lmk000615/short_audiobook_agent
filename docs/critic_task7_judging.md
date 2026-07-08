# Critic Task 7 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 7（line 983-1106）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 7 沿用 plan §Task 7 Acceptance Criteria Simplified）
> **Coding dev doc:** `docs/critic_task7_coding.md`（已落盘于 commit `0e74e9b`）
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-08
> **Task 类型:** 测试基础设施型（新增 `src_next/critic/tests/conftest.py`，不动业务代码）
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS** — Task 7 创建的 `src_next/critic/tests/conftest.py` 与 plan line 991-1070 代码块 `diff` 输出 BYTE-EQUAL（0 字符偏离）；既有 3 个测试仍然全绿（`3 passed in 0.09s`）；`pytest --collect-only -q` 实测 `3 tests collected in 0.01s`（无 collection error）；commit `0e74e9b` 已落盘且 scope 严格（仅 conftest.py + dev doc 2 文件，+458 行）；Acceptance A 表 2/2 + B 表 5/5 全部 PASS，0 red flag。

---

## 1. 验收范围

| 项 | 值 |
|---|---|
| Plan Task 7 标题 | Write conftest.py with fixtures |
| Plan Acceptance 章节 | `### Acceptance Criteria (Task 7 — Simplified)` (line 1086-1106) |
| Coding dev doc | `docs/critic_task7_coding.md`（380 行，随 conftest.py 同 commit 落盘） |
| Commit | `0e74e9b test(critic): add conftest with real_critic + audio path + real_llm fixtures` |
| Commit 范围 | `src_next/critic/tests/conftest.py`（+78）+ `docs/critic_task7_coding.md`（+380）= +458 lines / 2 files |
| 验收方式 | mock + 静态（plan 标注「Simplified」— 无 integration 条件） |
| 验收环境 | Windows 11 / Python 3.12.10 / pytest 9.0.3 / branch `feature/critic-and-tta` @ `0e74e9b` |

**Plan 字面量来源（用于 §4 字面量核对）：** plan §Task 7 Step 1 给出的完整 Python 代码块（line 992-1069，共 78 行非空内容）。

---

## 2. Section A — coding-Agent Self-check

plan line 1090-1095 列出的 2 条 bash 命令。judge 自己重跑，**未抄 coding doc 实测列**。

| 项 | 期望（plan 字面） | judge 实测 | 状态 |
|---|---|---|---|
| A1 | `test -f src_next/critic/tests/conftest.py && echo OK` → 输出 `OK` | Bash 输出 `OK`（同时 `wc -l = 78`、`py_compile` 输出 `PY_COMPILE_OK` 作为附加证据） | **PASS** |
| A2 | `python -m pytest src_next/critic/tests/ --collect-only -q` → 列出现有 3 个测试、无 collection error | 输出 3 行测试名 + `3 tests collected in 0.01s`，exit 0，无 error/warning | **PASS** |

**附加（judge 主动跑）：**

- `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → `3 passed in 0.09s`（既有测试未被 conftest 破坏）
- `python -m py_compile src_next/critic/tests/conftest.py` → `PY_COMPILE_OK`（CLAUDE.md §10 第 1 条）

**Section A 汇总：2/2 PASS。**

---

## 3. Section B — judge-Agent 抽查

plan line 1097-1102 列出的 5 条静态审查点。judge 用 Read / Grep / Bash 工具逐条核对，**未用"我扫了一眼"代替工具调用**。

| 抽查点 | 期望 | judge 实测证据 | 状态 |
|---|---|---|---|
| B1 | `conftest.py` 含 5 个 fixture：`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm` | Grep `^@pytest\.fixture|^def ` → 5 个 `@pytest.fixture(scope="session")`（行 18/35/40/45/50）+ 5 个对应 fixture 函数（行 19 `real_critic` / 36 `good_narration_wav` / 41 `bad_clipping_wav` / 46 `emotion_mismatch_wav` / 51 `real_llm`）+ 1 个工具函数 `_audio_path`（行 25，无 `@pytest.fixture` 装饰器） | **PASS** |
| B2 | `_audio_path()` 读 `CRITIC_FIXTURES_ROOT` 环境变量，未设置时 fallback 到本地 `FIXTURES_DIR` | Grep → 行 15 `FIXTURES_DIR = Path(__file__).parent / "fixtures"` / 行 27 `root = os.environ.get("CRITIC_FIXTURES_ROOT")` / 行 28-30 `if root: return str(Path(root) / filename)` / 行 32 `return str(FIXTURES_DIR / filename)`（fallback 分支） | **PASS** |
| B3 | `real_llm` fixture 含 `pytest.skip(...)` 分支（profile 找不到时优雅 skip 而非抛错） | Grep → 行 59-60 `except ImportError: pytest.skip("LLM backend not importable — skipping integration test")` + 行 62-64 `profile_path = os.environ.get("CRITIC_TEST_LLM_PROFILE") / if not profile_path: pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set — skipping real-LLM integration test")`（2 个 skip 分支，覆盖 ImportError 与 env 缺失两种场景） | **PASS** |
| B4 | 模块 docstring 含「integration 测试必须 serially（不要 -n auto）」警告 | Grep `SERIALLY\|infer_lock\|skip-marked\|Integration tests` → 行 3 `⚠️ Integration tests must run SERIALLY (no -n auto / no pytest-xdist) because` / 行 4 `Qwen3-Omni service has an infer_lock — concurrent requests will queue and timeout.` / 行 6 `⚠️ Integration tests are skip-marked by default — see KNOWN_ISSUES.md.` | **PASS** |
| B5 | `git log --oneline -3` 含 `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | Bash `git log --oneline -3` 顶上 `0e74e9b test(critic): add conftest with real_critic + audio path + real_llm fixtures`（commit 已落盘，非 PENDING） | **PASS** |

**Section B 汇总：5/5 PASS（含 commit 已落盘，非 PENDING）。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 字面量 BYTE-EQUAL 核对

judge 用 Python 逐行 diff plan line 992-1069（去 markdown fence 后 78 行）vs `src_next/critic/tests/conftest.py`（78 行）：

```
plan_lines_count: 78
actual_lines_count: 78
BYTE-EQUAL
```

**0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。** plan 字面量逐字落盘。

### 4.2 关键字面量点

| 关键字面量 | plan line | conftest.py 行 | 一致 |
|---|---|---|---|
| `Qwen3OmniCritic(base_url="http://10.50.121.102:8011")` | plan line 1013 | conftest.py 行 22 | ✓ |
| `FIXTURES_DIR = Path(__file__).parent / "fixtures"` | plan line 1006 | conftest.py 行 15 | ✓ |
| `CRITIC_FIXTURES_ROOT` 环境变量 | plan line 1018 | conftest.py 行 27 | ✓ |
| `CRITIC_TEST_LLM_PROFILE` 环境变量 | plan line 1053 | conftest.py 行 62 | ✓ |
| `pytest.skip("LLM backend not importable...")` | plan line 1051 | conftest.py 行 60 | ✓ |
| `pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set...")` | plan line 1055 | conftest.py 行 64 | ✓ |
| `backend = llm_cfg.get("type", "qwen_http").lower()` | plan line 1066 | conftest.py 行 75 | ✓（注：plan 字面量是 `llm.type`，与现有 profile yaml 用 `llm.backend` 字段不一致 — 但 plan 字面量优先，本 task 不修正） |
| commit message `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | plan line 1081 | git commit `0e74e9b` | ✓ |

### 4.3 文件 scope 核对

| 路径 | 操作 | plan 期望 | 实测 |
|---|---|---|---|
| `src_next/critic/tests/conftest.py` | Create | 1 个文件，78 行 | ✓ 78 行，新建 |
| `docs/critic_task7_coding.md` | Create（dev doc） | 1 个 dev doc | ✓ 380 行，新建 |
| 其他文件 | 不动 | — | `git diff HEAD~1 HEAD --stat` 仅 2 个文件，无 scope 越界 |

**Commit stat 完整：**
```
docs/critic_task7_coding.md       | 380 ++++++++++++++++++++++++++++++++++++++
src_next/critic/tests/conftest.py |  78 ++++++++
2 files changed, 458 insertions(+)
```

### 4.4 `src_next/critic/tests/` 目录终态

```
__init__.py           (Task 2 建立)
__pycache__/          (pytest 缓存)
conftest.py           (Task 7 新建，78 行)
test_qwen3omni_critic.py  (Task 4-6 已建，117 行)
```

无 Task 9 / 11 的 `test_tts_repair.py` 等越界文件，scope 严格。

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| conftest.py 字面量 | 与 plan line 991-1070 逐字一致 | `diff` 输出 BYTE-EQUAL | 无 | — |
| `real_llm` 字段名 `llm.type` | plan 字面量是 `llm_cfg.get("type", "qwen_http")` | 落盘字面量相同 | 现有 profile yaml（如 `yellow_qwen3http_cosyvoicehttp.yaml`）用 `llm.backend` 而非 `llm.type`，integration 测试真触发时可能 fallback 到默认 `qwen_http` 分支 | **本 task 不修正** — plan 字面量优先。Task 9 集成测试真触发时再评估（可能用专用 integration profile 配 `llm.type` 字段绕过） |
| `src_next/critic/tests/fixtures/` 目录 | plan 未提及创建 | 未创建 | `FIXTURES_DIR` 常量指向不存在的目录；audio fixture 仅返回路径字符串，不验证文件存在 | KNOWN_ISSUES.md §3 line 65 已记录"服务可访问后准备"，本 task 跳过 |
| commit 类型 | plan Step 3 字面量 `test(critic): ...` | 实测 `test(critic): ...` | 无（与 Task 4/5/6 的 `feat(critic):` 不同，但与 plan Step 3 字面量一致） | — |

**无结构性偏离。** 0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。

---

## 6. Red Flags 排查

按固定清单逐项排查。

| Red Flag 项 | 是否触发 | 证据 |
|---|---|---|
| 字面量不一致 | 否 | §4.1 BYTE-EQUAL，0 字符差异 |
| scope 越界（改了不该改的文件） | 否 | §4.3 commit 仅 2 文件（conftest.py + dev doc），与 plan §Task 7 Files 表一致 |
| 章节顺序错乱（dev doc / judging doc） | 否 | dev doc §1-§7 完整，judging doc §0-§9 完整 |
| `--no-verify` 跳过 hook | 否 | git log 显示 commit 正常生成，无 hook 跳过痕迹 |
| 改 `src/` 旧链路 | 否 | commit 范围仅 `src_next/` + `docs/` |
| 改 `requirements.txt` | 否 | commit 范围无 requirements.txt |
| 改 `core/data_models.py` 加 backend 专用字段 | 否 | 本 task 不动 data_models.py |
| 在 `core/` 或 `analysis/` import 具体 backend | 否 | 本 task 改的是 `src_next/critic/tests/conftest.py`（测试基础设施），不在 core/analysis 范畴；conftest 顶部 import 仅 `os` / `pathlib.Path` / `pytest`，backend 类全部 lazy import 在 fixture 函数体内 |
| 硬编码服务器地址进模块（非 profile） | 部分 | conftest.py 行 22 `Qwen3OmniCritic(base_url="http://10.50.121.102:8011")` 直接硬编码黄区 IP — **但这是 plan 字面量逐字复制**（plan line 1013），integration test fixture 专用，非业务代码；CLAUDE.md §9 第 7 条约束的是"模块"，conftest 测试 fixture 不算业务模块。**不算 red flag** |
| 既有测试被破坏 | 否 | `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → `3 passed in 0.09s`，既有 3 个测试全绿 |
| `pytest --collect-only` 报 collection error | 否 | `3 tests collected in 0.01s`，exit 0 |
| commit 未做（PENDING） | 否 | commit `0e74e9b` 已落盘，工作区 clean（无 staged 改动；仅 untracked 文档与 output 目录，与本 task 无关） |

**0 red flag。**

### 6.1 scope creep 检查（plan §1.2「不交付」清单）

plan 未显式给 Task 7 的「不交付」清单，但 coding doc §1.2 列出后续 task 才交付的项。比对：

| 不交付项（属后续 task） | 本 task 是否越界 | 证据 |
|---|---|---|
| 鲁棒性测试（Task 8）— 修改 `test_qwen3omni_critic.py` | 否 | `git diff HEAD~1 HEAD --stat` 不含 test_qwen3omni_critic.py |
| 集成测试骨架（Task 9）— 新建 `test_tts_repair.py` 等 | 否 | `src_next/critic/tests/` 目录下无 `test_tts_repair.py`（仅 conftest + test_qwen3omni_critic + __init__） |
| `fixtures/` 目录的 3 段测试音频 | 否 | `src_next/critic/tests/` 目录下无 `fixtures/` 子目录 |
| TTSRepairAgent（Task 10/11） | 否 | `src_next/critic/` 目录下无 `tts_repair_agent.py` / `tts_repair_prompt.py` |

**0 越界。** Scope 严格按 plan §Task 7 Files 表「Create: `src_next/critic/tests/conftest.py`」（仅此 1 项业务代码 + 配套 dev doc）。

---

## 7. Verdict JSON

```json
{
  "task_id": "task-7-conftest-py",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "test -f src_next/critic/tests/conftest.py && echo OK",
      "python -m py_compile src_next/critic/tests/conftest.py",
      "python -m pytest src_next/critic/tests/ --collect-only -q",
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v"
    ],
    "result": "4/4 PASS — conftest 文件存在 + py_compile OK + collect-only 列出 3 个测试无 error + 既有 3 个测试 3 passed in 0.09s"
  },
  "integration_tests": "N/A — plan 标注 Simplified，无 integration 条件；conftest 中的 real_critic / *_wav / real_llm fixture 实际触发属 Task 9 集成测试范围",
  "smoke_tests": "N/A — Task 7 是测试基础设施型，不动主链路；CLAUDE.md §10 第 2 条 mock 端到端测试不在本 task 验收范围",
  "static_review": {
    "section_a_pass": "2/2",
    "section_b_pass": "5/5",
    "literal_diff": "BYTE-EQUAL (plan line 992-1069 vs src_next/critic/tests/conftest.py, 78 lines, 0 char diff)",
    "commit_scope": "2 files / +458 lines (conftest.py +78 + dev doc +380)",
    "red_flags": "0",
    "scope_creep": "0"
  },
  "reason": "conftest.py 与 plan 字面量 BYTE-EQUAL；既有 3 个测试全绿；commit 已落盘且 scope 严格；0 red flag / 0 scope creep",
  "blocking_issues": [],
  "next_action": "PASS — 可进入 Task 8（鲁棒性测试，修改 test_qwen3omni_critic.py 追加 4-5 个 mock 测试）。提醒：Task 8 mock 测试用 monkeypatch + _FakeResponse 模式，不依赖 conftest 的任何 fixture，conftest 加入对 Task 8 collection 无影响。"
}
```

---

## 8. 给后续 task 的提醒

1. **Task 8（鲁棒性测试）**：4 个新测试函数（`test_evaluate_http_500_returns_neutral` / `test_evaluate_non_json_text_returns_neutral` / `test_evaluate_empty_text_field_returns_neutral` / `test_evaluate_request_exception_returns_neutral`）追加到 `test_qwen3omni_critic.py`，用 `monkeypatch` + `_FakeHttp500Response` / `_FakeJsonBadResponse` / `_FakeEmptyTextFieldResponse` 模式，**不需要 conftest 的任何 fixture**。conftest 加入对 Task 8 collection 无影响。

2. **Task 9（集成测试骨架）**：5 个 integration 测试名要从 `KNOWN_ISSUES.md` line 20-25 逐字复制（含 `test_critic_high_quality_audio_scores_high` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment` / `test_tts_repair.py::test_repair_with_real_llm_adjusts_parameters` 等）。这些测试**直接用本 task 的 5 个 fixture**（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm`）。全部 `@pytest.mark.skip(reason="awaiting Qwen3-Omni service access")` 标记。

3. **`infer_lock` 警告**：未来 integration 测试真触发时**绝对不能加 `-n auto`**（pytest-xdist 并行），否则并发请求会因 Qwen3-Omni 服务端 infer_lock 排队超时。conftest docstring 行 3-4 已固化此约束。

4. **环境变量准备**：服务可访问后必须设置 `CRITIC_FIXTURES_ROOT`（指向服务器侧 audio fixtures 绝对路径）+ `CRITIC_TEST_LLM_PROFILE`（指向 integration profile yaml）才能让 integration 测试真跑（而非被 skip）。KNOWN_ISSUES.md 已记录。

5. **`llm.type` vs `llm.backend` 字段名差异**（§5 偏离登记第 2 行）：plan 字面量是 `llm_cfg.get("type", "qwen_http")`，现有 profile yaml 用 `llm.backend`。**本 task 不修正** — plan 字面量优先。Task 9 集成测试真触发时若发现 fallback 到默认分支，再决定是改 conftest 还是建专用 integration profile。**不要 flag 为本 task 的 red flag。**

6. **commit 类型延续**：Task 8 / 9 同样是测试代码，应延续本 task 的 `test(critic):` commit 类型；Task 10/11（TTSRepairAgent 业务代码）回到 `feat(critic):`。

---

## 9. 一句话总结

Task 7 = 创建 `src_next/critic/tests/conftest.py`（78 行，5 个 session-scoped fixture + `_audio_path` 工具函数），与 plan line 991-1070 代码块 `diff` 输出 BYTE-EQUAL；既有 3 个测试仍然 `3 passed in 0.09s`；commit `0e74e9b` 已落盘且 scope 严格（仅 conftest.py + dev doc 2 文件 / +458 行）；Acceptance A 表 2/2 + B 表 5/5 全过，0 red flag，0 scope creep，**PASS**。
