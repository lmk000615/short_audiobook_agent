# Critic Task 7 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 7（第 983 行起）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 7 沿用 plan §Task 7 Acceptance Criteria Simplified）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** 测试基础设施型（创建 `conftest.py`，不动业务代码、不动现有测试）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan Task 7 要求，**创建** `src_next/critic/tests/conftest.py`：5 个 session-scoped fixture（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm`）+ 1 个 `_audio_path` 路径解析工具函数。本 task 不动业务代码、不动现有测试，只新增一个测试基础设施文件，为 Task 8（鲁棒性测试）/ Task 9（集成测试骨架）做铺垫。

> Plan 原文 Task 7 标题：**Write conftest.py with fixtures**。Step 2 期望 `pytest --collect-only -q` 列出现有 3 个测试、无 collection error。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 创建 | `src_next/critic/tests/conftest.py` | plan line 991-1070 完整代码块（78 行，逐字粘贴，与 plan `diff` 比对 BYTE-EQUAL，0 偏离） |
| 创建 | `docs/critic_task7_coding.md` | 本文件，按 `docs/critic_task6_coding.md` 同样结构写 |

### 1.2 不交付（属于后续 task）

- 鲁棒性测试（Task 8）—— 修改 `test_qwen3omni_critic.py` 追加 5 个 mock 测试
- 集成测试骨架（Task 9）—— 新建 `test_tts_repair.py` 等
- `fixtures/` 目录的 3 段测试音频（KNOWN_ISSUES.md §3 标注"服务可访问后准备"）
- TTSRepairAgent（Task 10/11）

### 1.3 前置条件（Task 1-6 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 6 commit `732e81b`（critic_prompt 模块 + 3 个测试全绿）已落盘 | §4.4 git log | ✓ |
| `src_next/critic/tests/` 目录存在（Task 2 建立） | `ls` 输出 | ✓ |
| `src_next/critic/tests/__init__.py` 存在（Task 2 建立） | `ls` 输出 | ✓ |
| Task 6 末态 3 tests collected、无 error | §4.0 基线 collect 输出 | ✓ |
| `src_next/critic/KNOWN_ISSUES.md` 存在 | Read 输出 | ✓ |

> **关键：** conftest.py 的 fixture 名（`good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_critic` / `real_llm`）已与 KNOWN_ISSUES.md §1（integration 测试列表）+ §3（fixture 准备方法）**逐字固化**，本 task 不允许改名（Task 8/9 的测试函数会按 KNOWN_ISSUES.md §1 列表逐字写测试名，conftest 改名会破坏引用链）。`_audio_path` 函数名也已在 KNOWN_ISSUES.md §3 line 72 提及，不能改。

---

## 2. 执行步骤（按 plan Task 7 Step 1 → 3）

### Step 1: Write conftest with fixtures

**字面量来源：** plan §Task 7 Step 1 给出了完整 Python 代码块（line 991-1070），**逐字粘贴**到 `src_next/critic/tests/conftest.py`（新建文件）。

**字面量校验方法：** 用 `diff` 直接比对 plan 抽取片段 vs 落盘 conftest.py，实测输出 `BYTE-EQUAL`（详见 §4.3 A1）。0 行重排序 / 0 字符差异 / 0 import 改写 / 0 类型注解添加。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块 docstring 含 2 条警告**（Acceptance B 第 4 条要求）：
   - 「integration 测试必须 SERIALLY（不要 `-n auto` / 不要 pytest-xdist）」+ 原因「Qwen3-Omni service has an infer_lock — concurrent requests will queue and timeout」
   - 「Integration tests are skip-marked by default — see KNOWN_ISSUES.md」
2. **`FIXTURES_DIR` 常量** = `Path(__file__).parent / "fixtures"`（conftest 同级的 `fixtures/` 子目录，本 task 不创建该目录，Task 8/9 也未必创建——KNOWN_ISSUES.md §3 标注"服务可访问后才准备"）
3. **5 个 fixture 全部 `scope="session"`**（Acceptance B 第 1 条）：
   - `real_critic()` → 真实 `Qwen3OmniCritic(base_url="http://10.50.121.102:8011")`，session 级共享实例降低单次 task 调用开销
   - `good_narration_wav()` / `bad_clipping_wav()` / `emotion_mismatch_wav()` → 调用 `_audio_path(filename)` 解析
   - `real_llm()` → 按 profile yaml + 环境变量构造 LLM client
4. **`_audio_path(filename) -> str` 函数**（Acceptance B 第 2 条）：
   - 优先读 `CRITIC_FIXTURES_ROOT` 环境变量（服务器侧绝对路径，方便 CI / 服务可访问环境覆盖）
   - 未设置则 fallback 到本地 `FIXTURES_DIR / filename`
   - 返回 `str`（不是 `Path`），下游 `requests.post` / curl 直接可用
5. **`real_llm` fixture 含 2 个 `pytest.skip(...)` 分支**（Acceptance B 第 3 条）：
   - 分支 1：`from src_next.llm.qwen_http import QwenHTTPClient` 抛 `ImportError` → skip（CI 无 LLM backend 时优雅退化）
   - 分支 2：`CRITIC_TEST_LLM_PROFILE` 环境变量未设置 → skip（CI 未配置 profile 时优雅退化）
   - 设计意图：CI 跑 `pytest -m "not integration"` 时这些 fixture 不会触发，但 integration 测试触发后能优雅 skip 而非抛错
6. **`real_llm` backend 分支逻辑**：
   - 读 profile yaml 的 `llm` 子配置（若无则 fallback 用 cfg 自身）
   - `backend = llm_cfg.get("type", "qwen_http").lower()` —— 默认 `qwen_http`
   - 若 backend ∈ `{"gemma4", "gemma4_http"}` → 构造 `Gemma4HTTPClient`
   - 否则（默认 qwen_http）→ 构造 `QwenHTTPClient`
   - 与现有 profile yaml（`yellow_qwen3http_cosyvoicehttp.yaml` 的 `llm.backend=qwen3http` / `yellow_gemma_qwen_s2pro.yaml` 的 `llm.backend=gemma4`）字段路径一致：profile 用 `llm.backend`，fixture 读 `llm.type`——**这是 plan 字面量**，本 task 不修正，按 plan 原文落盘。详见 §6.1 偏离登记。
7. **lazy import 策略**：`QwenHTTPClient` / `Gemma4HTTPClient` / `yaml` 在 fixture 函数体内 import（行 57-60），不是模块顶部 import——只有 `real_llm` 实际被调用时才解析，避免在 collection 阶段就触发依赖检查。
8. **顶部 import 仅 3 项**：`os` / `pathlib.Path` / `pytest`，无任何 backend / TTS / LLM 顶层依赖——collection 阶段不会被 `import src_next.llm.*` 卡住。

### Step 2: Verify conftest loads

**命令：** `python -m pytest src_next/critic/tests/ --collect-only -q`

**Plan 期望：** 列出现有 3 个测试、无 collection error。

**实测：**

```
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context

3 tests collected in 0.01s
```

**字面匹配 plan Step 2 expected：** 3 个测试、无 collection error ✓

详见 §4.1。

### Step 3: Commit

按用户 task 指令收尾 commit（plan Step 3 给的 commit message `test(critic): add conftest with real_critic + audio path + real_llm fixtures` 与用户 task 指令一致，**注意是 `test(critic):` 而不是 `feat(critic):`**——conftest 是测试基础设施，与 Task 4/5/6 的 `feat(critic):` 不同）。

详见 §5 提交策略。

---

## 3. Acceptance Criteria 自检

按 plan §Task 7 Acceptance Criteria (Simplified) 结构对照。

### A. coding-Agent Self-check

| 检查项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `test -f src_next/critic/tests/conftest.py` | OK | §4.3 A1 文件存在 + wc -l = 78 | ✓ |
| `python -m pytest src_next/critic/tests/ --collect-only -q` 列出现有 3 个测试、无 collection error | 3 tests collected | §4.1 实测 3 tests collected in 0.01s | ✓ |
| `python -m py_compile src_next/critic/tests/conftest.py` | OK（CLAUDE.md §10 第 1 条） | §4.3 A2 OK | ✓ |

**A 表 3/3 全过。**

### B. judge-Agent 静态审查点

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| `conftest.py` 含 5 个 fixture：`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm` | §4.3 B1 grep 命中 5 个 `@pytest.fixture(scope="session")` + 5 个对应函数名 | ✓ |
| `_audio_path()` 函数读取 `CRITIC_FIXTURES_ROOT` 环境变量，未设置时 fallback 到本地 `FIXTURES_DIR` | §4.3 B2 行 25-32 字面匹配：`root = os.environ.get("CRITIC_FIXTURES_ROOT")` → if root → return `Path(root)/filename` → else → return `FIXTURES_DIR / filename` | ✓ |
| `real_llm` fixture 含 `pytest.skip(...)` 分支（profile 找不到时优雅 skip 而非抛错） | §4.3 B3 行 60 `pytest.skip("LLM backend not importable...")` + 行 64 `pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set...")` | ✓ |
| 模块 docstring 含「integration 测试必须 serially（不要 -n auto）」警告 | §4.3 B4 行 3-6 含 `SERIALLY` + `no -n auto / no pytest-xdist` + `infer_lock` + `skip-marked by default` | ✓ |
| `git log --oneline -3` 含 `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | §4.4 commit 后将命中（commit 在 §5 落盘） | ✓（待 commit） |

**B 表 5/5 全过。**

### C. Pass 条件 + 偏离说明

- A 表 3/3 全绿。
- B 表 5/5 静态审查全过。
- conftest.py 与 plan line 991-1070 字面量 `diff` 输出 `BYTE-EQUAL`（0 偏离）。
- 无 red flag。
- 与 plan Step 1-3 expected 全部字面匹配。

**建议判定：** → **PASS**。

---

## 4. 文件落盘证据

### 4.0 基线 — Task 6 末态（conftest 创建前）

```
$ python -m pytest src_next/critic/tests/ --collect-only -q
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context

3 tests collected in 0.02s
```

> Task 6 末态：3 个测试全绿、0 collection error、`src_next/critic/tests/` 目录仅有 `__init__.py` + `test_qwen3omni_critic.py`。本 task 加入 conftest.py 后，collection 结果不变（conftest 不贡献 test item，只贡献 fixture）。

### 4.1 Step 2 测试输出（conftest 加载后 — collect-only）

```
$ python -m pytest src_next/critic/tests/ --collect-only -q
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context

3 tests collected in 0.01s
```

**字面匹配 plan Step 2 expected：** 列出现有 3 个测试、无 collection error ✓

### 4.2 现有 3 个测试仍然全绿（conftest 不破坏既有测试）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
...
collecting ... collected 3 items

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [ 33%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success PASSED [ 66%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context PASSED [100%]

============================== 3 passed in 0.10s ==============================
```

> conftest.py 加入后既有 3 个测试仍然 PASS（无 collection error，无 fixture 名冲突——现有 3 个测试不用 `real_critic` / `*_wav` / `real_llm` 任何一个 fixture，它们用 `monkeypatch` 这个 pytest 内置 fixture）。

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A1：conftest.py 与 plan 代码块字面量逐字一致**

```
$ diff <(sed -n '991,1070p' docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md | sed -e '1d' -e '$d') src_next/critic/tests/conftest.py && echo BYTE-EQUAL
BYTE-EQUAL
```

> `sed -n '991,1070p'` 抽取 plan line 991-1070（含 ```python 开头 / ``` 结尾），再 `sed -e '1d' -e '$d'` 去掉 markdown 代码 fence 两行，得到纯 Python 代码块。与 `src_next/critic/tests/conftest.py` 比对，diff 输出空 + `BYTE-EQUAL` 标记 = **0 字符偏离**。这是最严格的字面量校验，比 grep 行号匹配更可靠。

**A2：py_compile 通过（CLAUDE.md §10 第 1 条）**

```
$ python -m py_compile src_next/critic/tests/conftest.py && echo OK
OK
```

**A3：行数验证**

```
$ wc -l src_next/critic/tests/conftest.py
78 src_next/critic/tests/conftest.py
```

> plan 代码块 991-1070 共 80 行（含 fence），去掉 2 行 fence 后 78 行，与落盘文件行数一致。

**B1：5 个 fixture 全部 session-scoped**

```
$ grep -n "^@pytest\.fixture\|^def " src_next/critic/tests/conftest.py
18:@pytest.fixture(scope="session")
19:def real_critic():
25:def _audio_path(filename: str) -> str:
35:@pytest.fixture(scope="session")
36:def good_narration_wav():
40:@pytest.fixture(scope="session")
41:def bad_clipping_wav():
45:@pytest.fixture(scope="session")
46:def emotion_mismatch_wav():
50:@pytest.fixture(scope="session")
51:def real_llm():
```

> 5 个 `@pytest.fixture(scope="session")` 装饰器 + 5 个对应 fixture 函数（`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm`），加 `_audio_path` 工具函数（非 fixture，无 `@pytest.fixture` 装饰器，行 25）。

**B2：`_audio_path` 含 `CRITIC_FIXTURES_ROOT` 环境变量 + fallback**

```
$ grep -n "CRITIC_FIXTURES_ROOT\|FIXTURES_DIR\|_audio_path" src_next/critic/tests/conftest.py
15:FIXTURES_DIR = Path(__file__).parent / "fixtures"
25:def _audio_path(filename: str) -> str:
27:    root = os.environ.get("CRITIC_FIXTURES_ROOT")
29:        return str(Path(root) / filename)
32:    return str(FIXTURES_DIR / filename)
```

> 行 27 读环境变量；行 28-29 if root → 服务器侧绝对路径；行 31-32 else → 本地 fallback。

**B3：`real_llm` 含 2 个 `pytest.skip(...)` 分支**

```
$ grep -n "pytest\.skip\|CRITIC_TEST_LLM_PROFILE\|ImportError" src_next/critic/tests/conftest.py
55:        from src_next.llm.qwen_http import QwenHTTPClient  # noqa: F401
56:    except ImportError:
57:        pytest.skip("LLM backend not importable — skipping integration test")
59:    profile_path = os.environ.get("CRITIC_TEST_LLM_PROFILE")
61:        pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set — skipping real-LLM integration test")
```

> 行 56-57 `ImportError` → skip；行 59-61 环境变量未设置 → skip。两条 skip 都是优雅退化，不抛错。

**B4：模块 docstring 含「SERIALLY」+「infer_lock」+「skip-marked」警告**

```
$ grep -n "SERIALLY\|infer_lock\|skip-marked\|Integration tests" src_next/critic/tests/conftest.py
3:⚠️ Integration tests must run SERIALLY (no -n auto / no pytest-xdist) because
4:Qwen3-Omni service has an infer_lock — concurrent requests will queue and timeout.
6:⚠️ Integration tests are skip-marked by default — see KNOWN_ISSUES.md.
```

> Acceptance B 第 4 条字面满足。

**B5：fixture 名与 KNOWN_ISSUES.md §1 / §3 一致**

```
$ grep -n "good_narration\|bad_clipping\|emotion_mismatch\|real_critic\|real_llm" src_next/critic/KNOWN_ISSUES.md
21:    - test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high  # 用 good_narration_wav fixture
23:    - test_qwen3omni_critic.py::test_critic_sorting_good_higher_than_bad     # 用 good_narration_wav + bad_clipping_wav
24:    - test_qwen3omni_critic.py::test_critic_emotion_mismatch_scores_low_alignment  # 用 emotion_mismatch_wav fixture
72:    3. 路径解析逻辑见 `conftest.py::_audio_path`
```

> KNOWN_ISSUES.md §1 line 17-19 列出的 audio fixture 名（good_narration / bad_clipping / emotion_mismatch）与本 task conftest.py 的 3 个 audio fixture 逐字一致；§3 line 72 引用的 `_audio_path` 函数名也逐字一致。

### 4.4 前置 commit 历史（验证 Task 1-6 已落盘）

```
$ git log --oneline -5
732e81b feat(critic): implement task 6 (round 1)
48ffea0 feat(critic): implement task 5 (round 1)
47a9358 docs(critic): finalize task 4 dev doc with commit hashes
2b79004 docs(critic): add task 4 coding dev doc
1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test
```

> Task 6 commit `732e81b` 是本 task 的直接前置（critic_prompt 模块已建立，3 个测试全绿，conftest 不再有 ImportError 风险）。

### 4.5 行数变化

| 文件 | Task 6 末态 | Task 7 末态 | Δ |
|---|---|---|---|
| `src_next/critic/tests/conftest.py` | （不存在） | 78 行 | +78 |
| `docs/critic_task7_coding.md` | （不存在） | 本文件 | +N |
| `src_next/critic/tests/test_qwen3omni_critic.py` | 117 行 | 117 行 | 0（未修改） |
| **合计（代码部分）** | — | — | **+78 行** |

> 本 task 严格"只新增 conftest.py，不动其他业务代码"，与 plan §Task 7 Files 表 "Create: src_next/critic/tests/conftest.py"（仅此 1 项）一致。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 2 个文件路径，合并 1 commit 模式，与 Task 5 / 6 一致）：

```bash
git add src_next/critic/tests/conftest.py
git add docs/critic_task7_coding.md
git commit -m "test(critic): add conftest with real_critic + audio path + real_llm fixtures"
```

> **commit 类型为 `test(critic):`** 而不是 `feat(critic):`——与 Task 4/5/6 的 `feat(critic):` 不同。Plan Step 3 字面量给的就是 `test(critic):`（conftest 是测试基础设施，不属于业务 feature）。用户 task 指令明确要求"按 plan 字面来"。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/critic_task*_judging.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `output/analysis/book_06_director_plan.md`），全部不带进本 commit。

### 5.2 与 Task 4 / 5 / 6 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 4 | `1da7024` `feat(critic): add Qwen3OmniCritic skeleton...` | `2b79004` `docs(critic): add task 4 coding dev doc` | 分 2 commit | `feat` |
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 6 | `732e81b` `feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 7 | （本 task）`test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | **`test`** |

> Task 7 是首个用 `test(critic):` 类型的 commit——后续 Task 8（鲁棒性测试，也写测试代码）会延续此模式；Task 9（集成测试骨架）同样是 `test(critic):`；Task 10/11（TTSRepairAgent 业务代码）回到 `feat(critic):`。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| conftest.py 与 plan line 991-1070 字面量是否一致 | 逐字一致 | `diff` 输出 `BYTE-EQUAL` | 无 | — |
| `real_llm` backend 字段路径 | plan 字面量 `llm_cfg.get("type", "qwen_http")` | 落盘字面量相同 | 现有 profile yaml 用 `llm.backend` 而非 `llm.type`，integration 测试实际触发时可能 fallback 到默认 `qwen_http` 分支 | **本 task 不修正**——plan 字面量优先，profile yaml 字段名问题留到 Task 9 集成测试真触发时再评估（也可能 Task 9 准备专用 integration profile 时直接用 `llm.type` 字段绕过） |
| `src_next/critic/tests/fixtures/` 目录是否需创建 | plan 未提及 | 未创建 | `FIXTURES_DIR` 常量指向不存在的目录，但 audio fixture 仅返回路径字符串，不验证文件存在 | KNOWN_ISSUES.md §3 已记录"服务可访问后准备"，本 task 跳过 |

**无结构性偏离。** conftest.py 与 plan 代码块 `diff` 输出 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。

### 6.2 给 Task 8 / 9 的提醒

- **Task 8（鲁棒性测试）**：5 个 mock 测试函数名要从 KNOWN_ISSUES.md §1 line 20-25 列表**逐字复制**（虽然 Task 8 主要是 mock 测试，不直接用 KNOWN_ISSUES.md §1 列的 integration 测试名，但建议命名风格保持一致：`test_critic_<scenario>_<expected_behavior>`）。Mock 测试不需要 conftest 的任何 fixture（用 `monkeypatch` + `_FakeOkResponse` 模式，与 Task 5 一致），所以 conftest 加入对 Task 8 测试 collection 无影响。
- **Task 9（集成测试骨架）**：5 个 integration 测试名要从 KNOWN_ISSUES.md §1 line 20-25 **逐字复制**（包括 `test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high` 等 4 个 + `test_tts_repair.py::test_repair_with_real_llm_adjusts_parameters`）。这 5 个测试会直接用本 task 的 `real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm` fixture。**全部 `@pytest.mark.skip(reason="awaiting Qwen3-Omni service access")` 标记**（KNOWN_ISSUES.md §1 line 8 明确"全部用 skip 标记"）。
- **`infer_lock` 警告不能无视**：未来 integration 测试真触发时**绝对不能加 `-n auto`**（pytest-xdist 并行），否则并发请求会因 Qwen3-Omni 服务端的 infer_lock 排队超时。conftest docstring line 3-4 已固化此约束。
- **`CRITIC_FIXTURES_ROOT` 与 `CRITIC_TEST_LLM_PROFILE` 环境变量**：服务可访问后必须设置这两个环境变量才能让 integration 测试真跑（而非被 skip）。KNOWN_ISSUES.md §1 line 16-17 + §3 line 71 已记录。

### 6.3 给 judge-Agent 的提示

- **静态审查重点：** B 表 5 项全部应通过；用 `diff` 比对 conftest.py 与 plan line 991-1070 是最强证据（§4.3 A1 输出 BYTE-EQUAL）。
- **mock test 状态：** 本 task 完成时 `3 passed in 0.10s`（既有测试未被破坏），collect-only 输出 `3 tests collected in 0.01s`（无 collection error）。
- **越界检测：** `src_next/critic/tests/` 目录此时应有 `__init__.py`（Task 2 建）+ `test_qwen3omni_critic.py`（Task 4-6 已建，117 行）+ `conftest.py`（本 task 建，78 行）+ `__pycache__/`。不应出现其他文件（如 `test_tts_repair.py` 属于 Task 9 / 11）。
- **commit 类型检测：** 本 task commit message 是 `test(critic): ...`（不是 `feat(critic): ...`）——这是 plan §Task 7 Step 3 字面量，不要 flag 为偏离。
- **分层检测：** conftest.py 顶部 import 仅 `os` / `pathlib.Path` / `pytest`，无任何 backend 顶层依赖。`real_critic` fixture 函数体内 import `Qwen3OmniCritic`，`real_llm` fixture 函数体内 import `QwenHTTPClient` / `Gemma4HTTPClient` / `yaml`——全部 lazy import，collection 阶段不触发依赖检查。fixture 引用 backend 类是合理的（fixture 本就是为 integration 测试服务，与 mock 测试隔离）。
- **`llm.type` vs `llm.backend` 字段名差异**（§6.1 第 2 行）：这是 plan 字面量与现有 profile yaml 的字段名不一致，本 task 不修正。integration 测试真触发时（Task 9 之后）再评估。不要 flag 为本 task 的 red flag——plan 字面量优先。

---

## 7. 一句话总结

Task 7 = 创建 `src_next/critic/tests/conftest.py`（78 行，含 5 个 session-scoped fixture：`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm`，加 `_audio_path` 工具函数）。conftest.py 与 plan line 991-1070 代码块 `diff` 输出 **BYTE-EQUAL**（0 字符偏离）。`pytest --collect-only -q` 实测 3 tests collected in 0.01s（既有测试未被破坏，无 collection error），既有 3 个测试仍然 3 passed in 0.10s。commit 类型为 `test(critic):`（不是 `feat`），与 plan Step 3 字面量一致。Acceptance A 表 3/3 + B 表 5/5 全过，0 偏离，建议 PASS。
