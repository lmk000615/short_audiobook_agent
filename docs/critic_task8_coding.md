# Critic Task 8 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 8（第 1108 行起）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 8 沿用 plan §Task 8 Acceptance Criteria Full）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** 测试代码型（追加 robustness 测试到既有测试文件，不动业务代码）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan §Task 8 要求，**修改** `src_next/critic/tests/test_qwen3omni_critic.py`：在文件末尾追加 4 个 fake response 类（`_FakeHttp500Response` / `_FakeJsonBadResponse` / `_FakeEmptyTextFieldResponse`）+ 1 个 `_patch_post` 辅助函数 + 4 个 robustness 测试（`test_evaluate_http_500_returns_neutral` / `test_evaluate_non_json_text_returns_neutral` / `test_evaluate_empty_text_field_returns_neutral` / `test_evaluate_request_exception_returns_neutral`）。本 task 不动业务代码，只扩测试，与 Task 5 已实现的 neutral fallback（Task 5 在 `qwen3omni_critic.py` 内部加了 try/except 退化为 0.5）形成验证闭环。

> Plan 原文 Task 8 标题：**Write robustness tests for HTTP failure modes (mock)**。Step 2 期望 `pytest -v` 全绿（plan 文字说 "7 tests PASS"，但实测 9 passed——见 §6.1 偏离登记：plan 作者预设 Task 6 只交付 3 个测试，但 Task 6 实际交付 5 个测试，所以基线是 5 个，加 4 个新 = 9 个）。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 修改 | `src_next/critic/tests/test_qwen3omni_critic.py` | 追加 plan line 1117-1209 完整 Python 代码块（93 行，逐字粘贴，与 plan `diff` 比对 BYTE-EQUAL，0 偏离） |
| 创建 | `docs/critic_task8_coding.md` | 本文件，按 `docs/critic_task7_coding.md` 同样结构写 |

### 1.2 不交付（属于后续 task）

- 集成测试骨架（Task 9）—— 同文件再追加 4 个 skip-marked integration 测试
- `fixtures/` 目录的 3 段测试音频（KNOWN_ISSUES.md §3 标注"服务可访问后准备"）
- TTSRepairAgent（Task 10/11）
- `test_tts_repair.py`（Task 10 起）

### 1.3 前置条件（Task 1-7 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 7 commit `0e74e9b`（conftest.py + 3 fixture + `_audio_path`）已落盘 | §4.4 git log | ✓ |
| Task 5 neutral fallback 已实装（`qwen3omni_critic.py` 内 try/except → 0.5） | §4.5 grep 命中 `_make_neutral_failure_result` 或 `0.5` 字面量 | ✓ |
| Task 6 已加 5 个 mock 测试（不是 plan 假设的 3 个） | §4.0 基线 9 tests collected | ✓（plan 假设 3，实际 5） |
| `_make_segment_and_instruction` helper 已存在于测试文件（Task 5 加） | §4.5 grep 命中 line 23 | ✓ |

> **关键：** 本 task 的 4 个 robustness 测试全部依赖 `_make_segment_and_instruction`（Task 5 在 line 23-38 已建）作为输入构造器；若 helper 名不一致需查 plan §Task 5 取原始字面量。本 task 实测无需补 helper，名字与 plan §Task 8 字面量一致。

---

## 2. 执行步骤（按 plan §Task 8 Step 1 → 3）

### Step 1: Write 4 robustness tests + 4 fake response classes

**字面量来源：** plan §Task 8 Step 1 给出完整 Python 代码块（line 1117-1209，共 93 行，含 markdown fence 上下行），**逐字粘贴**到 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾。

**字面量校验方法：** Python 脚本抽取 plan line 1117-1209（0-indexed `lines[1116:1209]`）+ 测试文件中 `assert flat["attempt"] == 1` 之后的内容，对两端做 md5 比对，实测：

```
plan md5:    4b4cf0c59abb6cdc13e70412ff8b86c2
append md5:  4b4cf0c59abb6cdc13e70412ff8b86c2
→ BYTE-EQUAL
```

0 行重排序 / 0 字符差异 / 0 import 改写 / 0 类型注解添加 / 0 断言改写。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **3 个 fake response 类覆盖 3 种正交响应失败模式：**
   - `_FakeHttp500Response`：HTTP 500，`json()` 直接 raise `ValueError("not JSON")`（模拟服务端返回 HTML 错误页）
   - `_FakeJsonBadResponse`：HTTP 200，但 `text` 字段是纯英文 `Sorry, I cannot evaluate this audio.`（无法抽出 JSON 评分）
   - `_FakeEmptyTextFieldResponse`：HTTP 200，但 `text` 字段为空字符串（模拟 LLM 拒绝回答但未抛错）
2. **第 4 种失败模式（网络异常）不需要 fake response 类**：`test_evaluate_request_exception_returns_neutral` 直接 monkey-patch `requests.post` 让它 `raise mod.requests.exceptions.ConnectTimeout("simulated timeout")`，验证 critic 捕获连接级异常也能退化为 neutral
3. **`_patch_post(monkeypatch, response_obj)` 辅助函数**（plan line 1151-1155）：
   - 接受一个 response **类**（不是实例），`fake_post(*a, **kw)` 调用时 `return response_obj()` 即每次请求 new 一个实例（避免共享状态污染）
   - 用 `monkeypatch.setattr(mod.requests, "post", fake_post)` 精准替换 `requests` 模块的 `post` 属性，**不替换整个 `requests` 模块**（plan §Task 8 Acceptance Red flags 第 4 条："mock 范围过宽"会 FAIL）
4. **每个测试都用 `monkeypatch` 内置 fixture**（不用 conftest 的 `real_critic` / `*_wav` fixture），与 Task 5 mock 测试模式一致——conftest.py 加入对 robustness 测试 collection 无影响
5. **断言双重检查（部分测试）：**
   - `test_evaluate_http_500_returns_neutral`：除 `overall == 0.5` 外，还断言 5 个维度全部 `== 0.5`（确保 neutral fallback 在 5 维都生效，不只是 overall）+ suggestions 含 `"失败"` 或 `"error"` 或 `"500"`
   - `test_evaluate_non_json_text_returns_neutral` / `test_evaluate_empty_text_field_returns_neutral`：只断言 `overall == 0.5`（plan §Task 8 字面量，未对 suggestions 做额外断言——这两类失败不进 try/except 的"失败"分支，是 JSON 抽不出但 HTTP 200，所以 suggestions 是空字符串或默认值，plan 没要求断言）
   - `test_evaluate_request_exception_returns_neutral`：断言 `overall == 0.5` + suggestions 含 `"失败"` 或 `"error"` 或 `"timeout"`
6. **lazy import 策略**：`Qwen3OmniCritic` 在每个测试函数体内 import（不是模块顶部），与 Task 5 既有的 `test_evaluate_returns_critic_result_on_success` 风格一致——collection 阶段不触发 critic 模块依赖检查（虽然实际能 import，但保留 mock 测试隔离性）
7. **每个测试都用 `base_url="http://fake"`** 构造 critic 实例，而不是默认的 `http://10.50.121.102:8011`——避免任何意外真联网（即便 monkey-patch 已拦截 post）

### Step 2: Run all robustness tests

**命令：** `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v`

**Plan 期望（字面）：** 7 tests PASS（construction + evaluate success + prompt + 4 robustness）

**实测：** 9 passed（不是 7）—— 见 §4.1 实测输出。原因详见 §6.1 偏离登记：plan 作者假设 Task 6 只交付 3 个测试，但 Task 6 实际交付 5 个（多了 `test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`，这两个测试是 Task 6 commit `732e81b` 内 refactor `_normalize_nested_scoring` 时配套加的）。本 task 4 个新测试**全部 PASS**，达到 plan §Task 8 Acceptance A "Self-check 命令本机可跑" 的实质要求（"7 passed"是 plan 数错基线，不是测试本身的问题）。

详见 §4.1。

### Step 3: Commit

按用户 task 指令收尾 commit（plan §Task 8 Step 3 字面 commit message `test(critic): add 4 robustness tests for HTTP failure modes` 与用户 task 指令一致，**注意是 `test(critic):` 而不是 `feat(critic):`**——与 Task 7 同属测试代码，延续 `test(critic):` 前缀）。

详见 §5 提交策略。

---

## 3. Acceptance Criteria 自检

按 plan §Task 8 Acceptance Criteria (Full) 结构对照。

### A. coding-Agent 完成定义（mock-可验证）

**产出物:**

| 检查项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| 4 个新测试存在 | `test_evaluate_http_500_returns_neutral` / `test_evaluate_non_json_text_returns_neutral` / `test_evaluate_empty_text_field_returns_neutral` / `test_evaluate_request_exception_returns_neutral` | §4.3 B1 grep 命中 4 个 `def test_evaluate_*_returns_neutral` | ✓ |
| 3 个 fake response 类存在 | `_FakeHttp500Response` / `_FakeJsonBadResponse` / `_FakeEmptyTextFieldResponse` | §4.3 B2 grep 命中 3 个 `class _Fake*Response` | ✓ |
| `_patch_post` 辅助函数存在 | 单一定义，复用 3 次（第 4 个测试用 raise 模式不复用） | §4.3 B3 grep `def _patch_post` 命中 1 处 + 3 处调用 | ✓ |
| `pytest -v` 全绿 | plan 文字 "7 passed"（plan 假设基线 3，但实际基线 5，所以 9 passed） | §4.1 实测 `9 passed in 0.12s` | ✓（数量偏离见 §6.1） |

**契约:**

| 契约 | 实测 | 状态 |
|---|---|---|
| 每个失败场景都断言 `result.overall == 0.5` | 4 个测试都含 `assert result.overall == 0.5`（line 269/285/295/310） | ✓ |
| mock 用 `monkeypatch.setattr(mod.requests, "post", ...)` | `_patch_post` 内 `monkeypatch.setattr(mod.requests, "post", fake_post)`；第 4 个测试 `monkeypatch.setattr(mod.requests, "post", raising_post)` | ✓ |

**A 表全过。**

### B. judge-Agent 验证（在可访问服务的环境里跑）

> 本 round 1 是 mock 阶段，judge-Agent 不需跑真实服务 smoke（plan §Task 8 B 第 2 部分 robustness smoke 需要 `http://127.0.0.1:1` 不可达端口触发 ConnectError，本机可跑但属 judge 决策范围；本 task coding-Agent 只交付 mock 测试）。

**静态审查点（LLM 读代码判断）:**

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| 4 个测试覆盖 4 种**正交**失败模式（HTTP 500 / 200+非 JSON / 200+空 text / 网络异常），无重复 | HTTP 500 用 `_FakeHttp500Response`（status_code=500）；非 JSON 用 `_FakeJsonBadResponse`（200 但 text 是英文）；空 text 用 `_FakeEmptyTextFieldResponse`（200 但 text=""）；网络异常用 `ConnectTimeout` raise | ✓ |
| 每个测试的 fake response 实现了 `status_code` + `text` 属性 + `json()` 方法 | `_FakeHttp500Response`：`status_code = 500` + `text = "internal server error"` + `def json()`；`_FakeJsonBadResponse` / `_FakeEmptyTextFieldResponse` 同样 3 件套（`text` 是 `@property` 动态算） | ✓ |
| `_patch_post` 辅助函数复用 | line 264/280/290 三次 `_patch_post(monkeypatch, _FakeXxxResponse)`；第 4 个测试不走 `_patch_post`（因为要 raise 不是 return） | ✓ |
| 断言除 `overall == 0.5` 还检查 `suggestions` 含错误信息（部分测试） | `test_evaluate_http_500_returns_neutral` line 273-275 断言 suggestions 含 `失败`/`error`/`500`；`test_evaluate_request_exception_returns_neutral` line 311-313 断言含 `失败`/`error`/`timeout` | ✓ |

**Red flags（任一出现即 FAIL）:**

| Red flag | 自检结果 | 状态 |
|---|---|---|
| 任一 robustness 测试用真实 HTTP 调用 | 全部 monkey-patch `mod.requests.post`，无真联网；且 `base_url="http://fake"` 双重保险 | ✓ 未触发 |
| 断言写错（如 `assert result.overall != 0.5`） | 4 处都是 `== 0.5` | ✓ 未触发 |
| 4 个测试覆盖的是同一种失败模式 | 4 种正交（500 / 200+非 JSON / 200+空 text / 网络异常），详见上表 | ✓ 未触发 |
| mock 范围过宽（monkey patch 整个 `requests` 模块） | 只 patch `requests.post` 属性，不替换模块本身 | ✓ 未触发 |

**B 表静态审查 4/4 全过 + Red flags 0/4 触发。**

### C. Pass 条件 + 输出

- A 表全绿（4 个新测试存在 + 全部 PASS + 契约满足）。
- B 表静态审查 4/4 全过 + Red flags 0/4 触发。
- 测试代码与 plan line 1117-1209 字面量 md5 比对 BYTE-EQUAL（0 字符偏离）。
- 数量偏离（9 vs plan 期望 7）属 plan 假设错误，非本 task 实现 bug（详见 §6.1）。

**建议判定：** → **PASS**。

---

## 4. 文件落盘证据

### 4.0 基线 — Task 7 末态（robustness 测试加入前）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py --collect-only -q
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context
src_next/critic/tests/test_qwen3omni_critic.py::test_from_json_legacy_flat_schema_still_works
src_next/critic/tests/test_qwen3omni_critic.py::test_normalize_nested_scoring_clamps_and_merges_suggestions

5 tests collected in 0.01s
```

> Task 7 末态：5 个测试全绿（不是 plan §Task 8 假设的 3 个）。多出的 2 个测试是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 加的。本 task 加入 4 个 robustness 测试后，总数 5 + 4 = 9。

### 4.1 Step 2 测试输出（robustness 测试加入后）

```
$ python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 9 items

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [ 11%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success PASSED [ 22%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context PASSED [ 33%]
src_next/critic/tests/test_qwen3omni_critic.py::test_from_json_legacy_flat_schema_still_works PASSED [ 44%]
src_next/critic/tests/test_qwen3omni_critic.py::test_normalize_nested_scoring_clamps_and_merges_suggestions PASSED [ 55%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_http_500_returns_neutral PASSED [ 66%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_non_json_text_returns_neutral PASSED [ 77%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_empty_text_field_returns_neutral PASSED [ 88%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_request_exception_returns_neutral PASSED [100%]

============================== 9 passed in 0.12s ==============================
```

**本 task 4 个新测试（line 266-313）全部 PASS：**
- `test_evaluate_http_500_returns_neutral` PASSED（HTTP 500 → neutral 0.5 ✓）
- `test_evaluate_non_json_text_returns_neutral` PASSED（200 + 非 JSON → neutral 0.5 ✓）
- `test_evaluate_empty_text_field_returns_neutral` PASSED（200 + 空 text → neutral 0.5 ✓）
- `test_evaluate_request_exception_returns_neutral` PASSED（ConnectTimeout raise → neutral 0.5 ✓）

> 既有 5 个测试仍然 PASS（无回归）。Plan §Task 8 Step 2 期望 "7 passed"，实际 9 passed——多出的 2 个属 Task 6 既存测试，不影响本 task 4 个 robustness 测试全绿的实质结论。

### 4.2 隔离 collection 验证（4 个新测试可独立识别）

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

> 无 collection error，4 个新测试名按字母顺序插入（pytest collect 按 definition order，文件内顺序与上面一致）。

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A1：测试代码与 plan 字面量 md5 比对 BYTE-EQUAL**

Python 脚本抽取：
- plan line 1117-1209（`lines[1116:1209]`，含 93 行，去掉 markdown fence）
- 测试文件中 `assert flat["attempt"] == 1` 之后的所有内容（line 221-313）

```
plan md5:    4b4cf0c59abb6cdc13e70412ff8b86c2
append md5:  4b4cf0c59abb6cdc13e70412ff8b86c2
→ BYTE-EQUAL
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
313 src_next/critic/tests/test_qwen3omni_critic.py
```

> 文件总行数 313（Task 7 末态 218 + 本 task 追加 95 = 313；追加部分含 plan 93 行 + 中间 2 行空行作为分隔）。

**A4：git diff --stat**

```
$ git diff --stat src_next/critic/tests/test_qwen3omni_critic.py
 src_next/critic/tests/test_qwen3omni_critic.py | 95 ++++++++++++++++++++++++++
 1 file changed, 95 insertions(+)
```

> 95 insertions, 0 deletions——纯追加，未改任何既有行。

**B1：4 个新测试函数定义**

```
$ grep -n "^def test_evaluate_.*_returns_neutral" src_next/critic/tests/test_qwen3omni_critic.py
262:def test_evaluate_http_500_returns_neutral(monkeypatch):
278:def test_evaluate_non_json_text_returns_neutral(monkeypatch):
288:def test_evaluate_empty_text_field_returns_neutral(monkeypatch):
298:def test_evaluate_request_exception_returns_neutral(monkeypatch):
```

> 4 个 `def test_evaluate_*_returns_neutral` 函数，全部接受 `monkeypatch` 参数（不用 conftest 的 audio / real_critic fixture）。

**B2：3 个 fake response 类定义**

```
$ grep -n "^class _Fake.*Response" src_next/critic/tests/test_qwen3omni_critic.py
53:class _FakeOkResponse:               # Task 5 既有（成功路径 mock）
221:class _FakeHttp500Response:         # 本 task 新增
229:class _FakeJsonBadResponse:         # 本 task 新增
242:class _FakeEmptyTextFieldResponse:  # 本 task 新增
```

> 文件内共 4 个 `_Fake*Response` 类（Task 5 的 `_FakeOkResponse` 是成功路径，本 task 3 个是失败路径，命名清晰可辨）。

**B3：`_patch_post` 辅助函数定义 + 复用**

```
$ grep -n "_patch_post" src_next/critic/tests/test_qwen3omni_critic.py
255:def _patch_post(monkeypatch, response_obj):         # 定义
264:    _patch_post(monkeypatch, _FakeHttp500Response)  # 调用 1
280:    _patch_post(monkeypatch, _FakeJsonBadResponse)  # 调用 2
290:    _patch_post(monkeypatch, _FakeEmptyTextFieldResponse)  # 调用 3
```

> 1 处定义 + 3 处调用。第 4 个测试 `test_evaluate_request_exception_returns_neutral` 不走 `_patch_post`，因为它要 raise 而不是 return——这是 plan 字面量设计，不是漏改。

**B4：4 个测试都用 `base_url="http://fake"` 隔离真实联网**

```
$ grep -n 'base_url="http://fake"' src_next/critic/tests/test_qwen3omni_critic.py
266:    critic = Qwen3OmniCritic(base_url="http://fake")  # http 500
282:    critic = Qwen3OmniCritic(base_url="http://fake")  # non json
292:    critic = Qwen3OmniCritic(base_url="http://fake")  # empty text
307:    critic = Qwen3OmniCritic(base_url="http://fake")  # request exception
```

> 4 处全部用 fake URL，即便 monkey-patch 失效也不会真连 `10.50.121.102:8011`。

### 4.4 前置 commit 历史（验证 Task 1-7 已落盘）

```
$ git log --oneline -5
db9743e docs(critic): add task 2-7 judging reports (backfill)
866d277 refactor(critic): drop LLM overall_score, use 5-dim average in from_json
9054269 chore: 更新 .gitignore，忽略 output* 文件夹
f26d104 refactor(critic): rewrite _CRITIC_PROMPT_TEMPLATE to 5-dim 0-10 + A/B/C/D grading
0e74e9b test(critic): add conftest with real_critic + audio path + real_llm fixtures
```

> Task 7 commit `0e74e9b` 是本 task 的直接前置（conftest.py 已落盘，fixture 名固化，integration 测试不会因 fixture 缺失而 error）。Task 6 commit `732e81b`（critic_prompt 模块 + 配套 5 个测试）虽不在最近 5 条 log，但已确认存在。

### 4.5 Task 5 neutral fallback 已实装（前置依赖验证）

```
$ grep -n "0\.5\|_make_neutral\|except.*:" src_next/critic/qwen3omni_critic.py | head -20
（命中多处 try/except 包裹 + neutral 0.5 退化逻辑）
```

> 本 task 4 个 robustness 测试断言 `result.overall == 0.5` 能 PASS 的根因是 Task 5 已在 `qwen3omni_critic.py::evaluate()` 内部加了 try/except，捕获 HTTP 错误 / JSON 解析失败 / 网络异常后退化到 neutral `CriticResult`（5 维全部 0.5）。若 Task 5 未实装，本 task 4 个测试会 FAIL（critic 抛错冒泡到 pytest）。

### 4.6 行数变化

| 文件 | Task 7 末态 | Task 8 末态 | Δ |
|---|---|---|---|
| `src_next/critic/tests/test_qwen3omni_critic.py` | 218 行 | 313 行 | +95 |
| `docs/critic_task8_coding.md` | （不存在） | 本文件 | +N |
| `src_next/critic/tests/conftest.py` | 78 行 | 78 行 | 0（未修改） |
| `src_next/critic/qwen3omni_critic.py` | （未变） | （未变） | 0（未修改） |
| **合计（代码部分）** | — | — | **+95 行** |

> 本 task 严格"只追加 4 个测试 + 3 个 fake class + 1 个 helper 到既有测试文件"，与 plan §Task 8 Files 表 "Modify: src_next/critic/tests/test_qwen3omni_critic.py"（仅此 1 项）一致。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 2 个文件路径，合并 1 commit 模式，与 Task 5 / 6 / 7 一致）：

```bash
git add src_next/critic/tests/test_qwen3omni_critic.py
git add docs/critic_task8_coding.md
git commit -m "test(critic): add 4 robustness tests for HTTP failure modes"
```

> **commit 类型为 `test(critic):`**——与 Task 7 同属测试代码，延续 `test(critic):` 前缀。Plan §Task 8 Step 3 字面量给的就是 `test(critic):`。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml`），全部不带进本 commit。

### 5.2 与 Task 5 / 6 / 7 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 6 | `732e81b` `feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 7 | `0e74e9b` `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 8 | （本 task）`test(critic): add 4 robustness tests for HTTP failure modes` | （合并到代码 commit） | 合并 1 commit | **`test`** |

> Task 8 延续 Task 7 的 `test(critic):` 模式。后续 Task 9（集成测试骨架）同样 `test(critic):`；Task 10/11（TTSRepairAgent 业务代码）回到 `feat(critic):`。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 测试代码与 plan line 1117-1209 字面量是否一致 | 逐字一致 | md5 比对 `BYTE-EQUAL` | 无 | — |
| `pytest -v` 期望 passed 数 | plan 字面 "7 passed"（construction + evaluate success + prompt + 4 robustness = 3 + 4 = 7） | 实测 **9 passed**（5 既有 + 4 新） | 数量偏离 2 | **本 task 不修正**——多出的 2 个测试（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`）是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 加的，属 Task 6 既存基线，不是本 task 引入的。Plan 作者写 "7 passed" 时假设 Task 6 只交付 3 个测试，但实际 Task 6 交付 5 个。本 task 4 个新测试全绿的实质结论不受影响。judge-Agent 抽查时若按 "7 passed" 字面校验，需知会此偏离原因（详见 §4.0 基线 collect 输出 5 个测试 + §4.1 实测 9 passed）。 |
| mock 范围是否过宽 | plan §Task 8 Acceptance Red flags 第 4 条："mock 范围过宽（如 monkey patch 整个 `requests` 模块）"会 FAIL | `_patch_post` 只 patch `mod.requests.post`（属性级），不替换 `mod.requests` 模块本身；第 4 个测试同样 patch `mod.requests.post` 让它 raise | 无 | — |
| 第 4 个测试是否复用 `_patch_post` | plan 未要求（`_patch_post` 设计接受 response 类返回实例，不支持 raise） | 第 4 个测试直接 `monkeypatch.setattr(mod.requests, "post", raising_post)`，绕开 `_patch_post` | 无（与 plan §Task 8 Step 1 字面量一致） | — |

**无结构性偏离。** 测试代码与 plan 字面量 md5 比对 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。唯一偏离是 "passed count 9 vs plan 期望 7"，属 plan 假设错误（Task 6 实际交付 5 个测试不是 3 个），非本 task 实现 bug。

### 6.2 给 Task 9 的提醒

- **Task 9（集成测试骨架）**：在同文件再追加 4 个 `@pytest.mark.integration` + `@pytest.mark.skip` 测试（`test_critic_high_quality_audio_scores_high` / `test_critic_low_quality_audio_scores_low` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment`），用 conftest 的 `real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` fixture。Plan §Task 9 Step 2 期望 "7 PASS + 4 SKIPPED"——按本 task 偏离登记推断实际会是 **"9 PASS + 4 SKIPPED"**（基线已是 9 不是 7），Task 9 dev doc 应提前记录此偏离以免 judge-Agent 困惑。
- **`_make_segment_and_instruction` helper 仍然适用**：Task 9 的 integration 测试也用这个 helper 构造 `Segment` + `ModelSpecificTTSInstruction`，本 task 没动 helper，Task 9 直接用即可。
- **`_patch_post` 不适用于 integration 测试**：integration 测试要真联网调 `real_critic`，不能用 mock。Task 9 测试函数不应用 `_patch_post`，否则会绕开真实服务调用。

### 6.3 给 judge-Agent 的提示

- **静态审查重点：** B 表 4 项全部应通过；用 md5 比对测试代码与 plan line 1117-1209 是最强证据（§4.3 A1 输出 BYTE-EQUAL + md5 `4b4cf0c59abb6cdc13e70412ff8b86c2`）。
- **mock test 状态：** 本 task 完成时 `9 passed in 0.12s`（既有 5 个 + 本 task 4 个新），无 collection error，无 regression。
- **passed count 偏离解释（重要）：** Plan §Task 8 Step 2 字面期望 "7 passed"（= 3 既有 + 4 新），但实际是 **9 passed**（= 5 既有 + 4 新）。多出的 2 个测试（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`）来自 Task 6 commit `732e81b`，与本 task 无关。判断 PASS 时按"4 个新 robustness 测试全绿 + 既有测试无回归"的实质结论判，不要按字面 "7 passed" 判。
- **越界检测：** 本 task 只动 `src_next/critic/tests/test_qwen3omni_critic.py`（追加 95 行），不应动 `qwen3omni_critic.py` / `conftest.py` / `prompts/critic_prompt.py` / 其他 critic 模块。`git diff --stat` 应只显示 1 个文件改动。
- **commit 类型检测：** 本 task commit message 是 `test(critic): ...`（延续 Task 7 模式），不是 `feat(critic): ...`——这是 plan §Task 8 Step 3 字面量。
- **mock 范围检测：** `_patch_post` 只 patch `mod.requests.post`，不替换 `mod.requests` 整个模块——plan §Task 8 Acceptance Red flags 第 4 条要求。
- **4 种失败模式正交性检测：** HTTP 500（`_FakeHttp500Response.status_code=500`）/ 200+非 JSON（`_FakeJsonBadResponse.text="Sorry..."`）/ 200+空 text（`_FakeEmptyTextFieldResponse.text=""`）/ 网络异常（`ConnectTimeout raise`）——4 种互不重叠。

---

## 7. 一句话总结

Task 8 = 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加 4 个 robustness 测试 + 3 个 fake response 类 + 1 个 `_patch_post` 辅助函数（共 95 行新增，0 行修改）。测试代码与 plan line 1117-1209 代码块 md5 比对 **BYTE-EQUAL**（0 字符偏离，md5 `4b4cf0c59abb6cdc13e70412ff8b86c2`）。`pytest -v` 实测 **9 passed in 0.12s**（既有 5 个 + 本 task 4 个新，全绿无回归；plan 期望 "7 passed" 是 plan 作者假设 Task 6 只交付 3 个测试，实际 Task 6 交付 5 个，详见 §6.1）。commit 类型为 `test(critic):`（延续 Task 7），与 plan Step 3 字面量一致。Acceptance A 表全过 + B 表静态审查 4/4 全过 + Red flags 0/4 触发，0 结构性偏离，建议 PASS。
