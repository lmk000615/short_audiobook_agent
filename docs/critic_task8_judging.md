# Critic Task 8 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 8（line 1108-1224）
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 8 沿用 plan §Task 8 Acceptance Criteria Full）
> **Coding dev doc:** `docs/critic_task8_coding.md`（已落盘于 commit `1d655b4`）
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-08
> **Task 类型:** 测试代码型（追加 robustness 测试到既有测试文件，不动业务代码）
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS** — Task 8 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加的 4 个 robustness 测试 + 3 个 fake response 类 + 1 个 `_patch_post` helper（共 +95 行）与 plan line 1117-1209 代码块 md5 比对 **BYTE-EQUAL**（md5 `4b4cf0c59abb6cdc13e70412ff8b86c2`，0 字符偏离）；judge 自跑 `pytest -v` 实测 `9 passed in 0.09s`（4 新 + 5 既有，无回归；plan 字面期望 7 passed，多出的 2 是 Task 6 既存基线，详见 §5 偏离登记）；B smoke 不可达端口 fallback 实测 `connection-fail fallback OK; overall= 0.5`；commit `1d655b4` 已落盘，scope 严格（仅测试文件 + dev doc 2 文件 / +512 行）；Acceptance A 表 1/1 + B 表 4/4 全部 PASS，0 red flag。

---

## 1. 验收范围

| 项 | 值 |
|---|---|
| Plan Task 8 标题 | Write robustness tests for HTTP failure modes (mock) |
| Plan Acceptance 章节 | `### Acceptance Criteria (Task 8 — Full)` (line 1226-1285) |
| Coding dev doc | `docs/critic_task8_coding.md`（417 行，随测试文件同 commit 落盘） |
| Commit | `1d655b4 test(critic): add 4 robustness tests for HTTP failure modes` |
| Commit 范围 | `src_next/critic/tests/test_qwen3omni_critic.py`（+95）+ `docs/critic_task8_coding.md`（+417）= +512 lines / 2 files |
| 验收方式 | mock + 静态 + 本地 smoke（plan B smoke 第 2a 条「不可达端口 ConnectError」本机可跑） |
| 验收环境 | Windows 11 / Python 3.12.10 / pytest 9.0.3 / branch `feature/critic-and-tta` @ `1d655b4` |

**Plan 字面量来源（用于 §4 字面量核对）：** plan §Task 8 Step 1 给出的完整 Python 代码块（line 1117-1209，共 93 行非空内容）。

---

## 2. Section A — coding-Agent Self-check

plan line 1237-1240 列出的 1 条 bash 命令 + 配套 contract（line 1243-1244）。judge 自己重跑，**未抄 coding doc 实测列**。

| 项 | 期望（plan 字面） | judge 实测 | 状态 |
|---|---|---|---|
| A1 | `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → 7 passed（construction + evaluate success + prompt + 4 robustness） | judge 重跑输出 `collected 9 items` + 4 个 robustness 测试名 PASSED + 既有 5 个测试仍 PASSED + `9 passed in 0.09s`（exit 0）。**数量偏离 +2**：plan 期望 7，实测 9，多出的 2 个是 Task 6 既存（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`），与本 task 无关，详见 §5 偏离登记 | **PASS**（实质结论：4 个新 robustness 测试全绿 + 既有测试无回归；数量偏离非实现 bug） |

**Contract 检查（plan line 1243-1244）：**

| Contract | 期望 | judge 实测 | 状态 |
|---|---|---|---|
| C1 | 每个失败场景都断言 `result.overall == 0.5` | Grep `result\.overall` 命中 line 269/285/295/310 共 4 处 `assert result.overall == 0.5`（4 个新测试各 1 处） | **PASS** |
| C2 | mock 用 `monkeypatch.setattr(mod.requests, "post", ...)`，不真联网 | Grep `_patch_post` line 255 定义 + line 264/280/290 三处调用；line 305 第 4 个测试直接 `monkeypatch.setattr(mod.requests, "post", raising_post)`；4 处全部 patch **`mod.requests.post` 属性**（非整个 `mod.requests` 模块）；且 4 处全部 `base_url="http://fake"`（line 266/282/292/307）双重保险防真联网 | **PASS** |

**附加（judge 主动跑，非 plan 必需）：**

- `python -m py_compile src_next/critic/tests/test_qwen3omni_critic.py` → `OK`（CLAUDE.md §10 第 1 条）
- `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py --collect-only -q` → `9 tests collected`，无 collection error
- Plan B smoke 2a（不可达端口）：judge 本机直接跑了 plan line 1255-1265 那段 `python -c "..."`，输出 `connection-fail fallback OK; overall= 0.5`（满足 plan line 1263 的 `assert r.overall == 0.5` 断言）

**Section A 汇总：1/1 + 2 contract 全部 PASS。** Plan 字面 "7 passed" 与实测 "9 passed" 的偏差按实质结论判 PASS（不是字面意义上的"对不上就 FAIL"），偏离原因见 §5。

---

## 3. Section B — judge-Agent 抽查

plan line 1268-1278 列出的 4 条静态审查点 + 4 条 Red flags。judge 用 Read / Grep / Bash 工具逐条核对，**未用"我扫了一眼"代替工具调用**。

| 抽查点 | 期望 | judge 实测证据 | 状态 |
|---|---|---|---|
| B1 | 4 个测试覆盖 4 种**正交**失败模式（HTTP 500 / 200+非 JSON / 200+空 text / 网络异常），无重复 | Read line 221-252 4 个 fake 类：`_FakeHttp500Response.status_code = 500`（line 222）覆盖 HTTP 500；`_FakeJsonBadResponse.json()` 返回 `{"text": "Sorry, I cannot evaluate this audio."}` + `status_code = 200`（line 231）覆盖 200+非 JSON（text 是 English 无法抽 JSON）；`_FakeEmptyTextFieldResponse.json()` 返回 `{"text": ""}` + `status_code = 200`（line 244）覆盖 200+空 text；`test_evaluate_request_exception_returns_neutral` line 303 `raise mod.requests.exceptions.ConnectTimeout("simulated timeout")` 覆盖网络异常。4 种互不重叠（status_code 不同 / 触发路径不同） | **PASS** |
| B2 | 每个测试的 fake response 实现了 `status_code` + `text` 属性 + `json()` 方法（避免 AttributeError） | Read line 221-252：`_FakeHttp500Response`：`status_code = 500`（class attr）+ `text = "internal server error"`（class attr）+ `def json(self): raise ValueError("not JSON")`；`_FakeJsonBadResponse`：`status_code = 200` + `@property def text`（line 236-239 动态算）+ `def json()`；`_FakeEmptyTextFieldResponse` 同 `_FakeJsonBadResponse` 结构但 `json()` 返回 `{"text": ""}`。3 件套齐全 | **PASS** |
| B3 | `_patch_post` 辅助函数复用，不重复 monkey patch 模板 | Grep `_patch_post` 命中 4 处：line 255 `def _patch_post(monkeypatch, response_obj):`（定义）+ line 264/280/290 三处调用（`_patch_post(monkeypatch, _FakeHttp500Response)` / `_patch_post(monkeypatch, _FakeJsonBadResponse)` / `_patch_post(monkeypatch, _FakeEmptyTextFieldResponse)`）。第 4 个测试 `test_evaluate_request_exception_returns_neutral` 不复用 `_patch_post`，因为它要 `raise` 而不是 `return response_obj()`，plan 字面量设计如此，**不算漏改** | **PASS** |
| B4 | 断言除了 `overall == 0.5` 还检查了 `suggestions` 含错误信息（部分测试） | Read line 273-275（`test_evaluate_http_500_returns_neutral`）`assert ("失败" in result.suggestions or "error" in result.suggestions.lower() or "500" in result.suggestions)`；line 311-313（`test_evaluate_request_exception_returns_neutral`）`assert ("失败" in result.suggestions or "error" in result.suggestions.lower() or "timeout" in result.suggestions.lower())`。2/4 测试做了 suggestions 额外断言（HTTP 500 + 网络异常两类触发了 Task 5 的 except 分支注入"失败/error/...）；另 2/4（200+非 JSON / 200+空 text）只断言 `overall == 0.5`，符合 plan "部分测试" 字面量 | **PASS** |

**Red flags 排查（plan line 1274-1278，任一触发即 FAIL）：**

| Red flag | judge 实测证据 | 状态 |
|---|---|---|
| 任一 robustness 测试用真实 HTTP 调用（应该全部 mock） | 4 个测试全部 `monkeypatch.setattr(mod.requests, "post", ...)` 拦截 post；且 4 处 `base_url="http://fake"`（line 266/282/292/307）双重保险——即便 monkeypatch 失效也不会真连 `10.50.121.102:8011` | **未触发** |
| 断言写错（如 `assert result.overall != 0.5`） | Grep `result\.overall` 命中 4 处全部 `== 0.5`（line 269/285/295/310），无 `!=` / `>` / `<` | **未触发** |
| 4 个测试覆盖的是同一种失败模式（如都是 500） | 4 种正交：500（status_code）/ 200+非 JSON（text 是 English）/ 200+空 text（text=""）/ 网络异常（ConnectTimeout raise）——见 B1 证据 | **未触发** |
| mock 范围过宽（如 monkey patch 整个 `requests` 模块） | Grep `monkeypatch\.setattr` 命中 line 259/305，全部 `mod.requests, "post", ...`（patch 的是 `mod.requests` 模块的 `post` 属性，不是替换整个 `mod.requests` 模块对象） | **未触发** |

**Section B 汇总：4/4 PASS + 4/4 Red flag 未触发。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 字面量 md5 比对

judge 用 Python 脚本抽取 plan line 1117-1209（`lines[1116:1209]`，93 行）vs 测试文件 line 221-313（追加块），md5 比对：

```
plan md5:  4b4cf0c59abb6cdc13e70412ff8b86c2
test md5:  4b4cf0c59abb6cdc13e70412ff8b86c2
match: True
```

**0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。** plan 字面量逐字落盘。这是比 grep 行号匹配更严格的字面量校验。

### 4.2 关键字面量点

| 关键字面量 | plan line | test 文件行 | 一致 |
|---|---|---|---|
| `class _FakeHttp500Response: status_code = 500` | plan line 1117-1119 | test line 221-223 | ✓ |
| `_FakeJsonBadResponse.json()` 返回 `{"text": "Sorry, I cannot evaluate this audio."}` | plan line 1130 | test line 234 | ✓ |
| `_FakeEmptyTextFieldResponse.json()` 返回 `{"text": ""}` | plan line 1143 | test line 247 | ✓ |
| `_patch_post(monkeypatch, response_obj):` 签名 + `monkeypatch.setattr(mod.requests, "post", fake_post)` | plan line 1151-1155 | test line 255-259 | ✓ |
| 4 个测试函数名 `test_evaluate_http_500_returns_neutral` / `_non_json_text_` / `_empty_text_field_` / `_request_exception_` | plan line 1158/1174/1184/1194 | test line 262/278/288/298 | ✓ |
| `base_url="http://fake"`（4 处） | plan line 1162/1178/1188/1203 | test line 266/282/292/307 | ✓ |
| `assert result.overall == 0.5`（4 处） | plan line 1165/1181/1191/1206 | test line 269/285/295/310 | ✓ |
| `test_evaluate_request_exception_returns_neutral` 用 `mod.requests.exceptions.ConnectTimeout("simulated timeout")` | plan line 1199 | test line 303 | ✓ |
| commit message `test(critic): add 4 robustness tests for HTTP failure modes` | plan line 1221 | git commit `1d655b4` | ✓ |

### 4.3 文件 scope 核对

| 路径 | 操作 | plan 期望 | 实测 |
|---|---|---|---|
| `src_next/critic/tests/test_qwen3omni_critic.py` | Modify（追加） | 仅此 1 个业务代码文件 | ✓ 文件总行数 313（Task 7 末态 218 + 本 task 追加 95） |
| `docs/critic_task8_coding.md` | Create（dev doc） | 1 个 dev doc | ✓ 417 行，新建 |
| 其他文件 | 不动 | — | `git show --stat 1d655b4` 仅 2 个文件，无 scope 越界 |

**Commit stat 完整：**
```
 docs/critic_task8_coding.md                    | 417 +++++++++++++++++++++++++
 src_next/critic/tests/test_qwen3omni_critic.py |  95 ++++++
 2 files changed, 512 insertions(+)
```

### 4.4 前置依赖验证

| 前置 | 期望 | 实测 | 状态 |
|---|---|---|---|
| 当前分支 = `feature/critic-and-tta` | ✓ | `git status` 顶上 `On branch feature/critic-and-tta` | ✓ |
| Task 7 commit `0e74e9b` 已落盘（conftest.py） | ✓ | `git log --oneline -10` 第 6 行 `0e74e9b test(critic): add conftest with real_critic + audio path + real_llm fixtures` | ✓ |
| Task 5 neutral fallback 已实装（`qwen3omni_critic.py` 内 try/except → 0.5） | ✓ | judge 本机跑 plan B smoke 2a（不可达端口）输出 `connection-fail fallback OK; overall= 0.5`，证明 Task 5 fallback 链路活；4 个 robustness 测试断言 `overall == 0.5` 全 PASS | ✓ |
| `_make_segment_and_instruction` helper 已存在 | ✓ | Grep `^def _make_segment_and_instruction` 命中 line 23（Task 5 既有） | ✓ |

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 测试代码与 plan line 1117-1209 字面量是否一致 | 逐字一致 | md5 比对 `BYTE-EQUAL`（4b4cf0c59abb6cdc13e70412ff8b86c2） | 无 | — |
| `pytest -v` 期望 passed 数 | plan 字面 "7 passed"（construction + evaluate success + prompt + 4 robustness = 3 + 4 = 7） | 实测 **9 passed**（5 既有 + 4 新） | 数量偏离 +2 | **本 task 不修正**——多出的 2 个测试（`test_from_json_legacy_flat_schema_still_works` + `test_normalize_nested_scoring_clamps_and_merges_suggestions`）是 Task 6 commit `732e81b` 配套 `_normalize_nested_scoring` refactor 时加的，属 Task 6 既存基线（不是本 task 引入）。Plan 作者写 "7 passed" 时假设 Task 6 只交付 3 个测试，但实际 Task 6 交付 5 个。本 task 4 个新 robustness 测试全绿 + 既有测试无回归的实质结论不受影响。**判定时按实质结论 PASS，不按字面 "7 passed" 机械判 FAIL** |
| mock 范围是否过宽 | plan Red flags 第 4 条："mock 范围过宽（如 monkey patch 整个 `requests` 模块）"会 FAIL | `_patch_post` 只 patch `mod.requests.post`（属性级），不替换 `mod.requests` 模块本身；第 4 个测试同样 `monkeypatch.setattr(mod.requests, "post", raising_post)` | 无 | — |
| 第 4 个测试是否复用 `_patch_post` | plan 未要求（`_patch_post` 设计接受 response 类返回实例，不支持 raise） | 第 4 个测试直接 `monkeypatch.setattr(mod.requests, "post", raising_post)`，绕开 `_patch_post` | 无（与 plan §Task 8 Step 1 字面量一致，line 1196-1201 逐字复制） | — |
| Plan B smoke 第 2a 条（不可达端口 ConnectError） | plan 标"服务可用时"，但本机也可跑（端口 1 不可达） | judge 本机直跑输出 `connection-fail fallback OK; overall= 0.5` | 无（额外验证，超出 plan 必需） | — |

**无结构性偏离。** 测试代码与 plan 字面量 md5 比对 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。唯一偏离是 "passed count 9 vs plan 期望 7"，属 plan 假设错误（Task 6 实际交付 5 个测试不是 3 个），非本 task 实现 bug。

---

## 6. Red Flags 排查

按 CLAUDE.md §9 硬约束 + plan §Task 8 Acceptance Red flags 固定清单逐项排查。

| Red Flag 项 | 是否触发 | 证据 |
|---|---|---|
| 字面量不一致 | 否 | §4.1 md5 比对 BYTE-EQUAL，0 字符差异 |
| scope 越界（改了不该改的文件） | 否 | §4.3 `git show --stat 1d655b4` 仅 2 文件（test_qwen3omni_critic.py +95 + dev doc +417） |
| 章节顺序错乱（dev doc / judging doc） | 否 | dev doc §1-§7 完整，judging doc §0-§9 完整 |
| `--no-verify` 跳过 hook | 否 | git log 显示 commit 正常生成，无 hook 跳过痕迹 |
| 改 `src/` 旧链路 | 否 | commit 范围仅 `src_next/` + `docs/` |
| 改 `requirements.txt` | 否 | commit 范围无 requirements.txt |
| 改 `core/data_models.py` 加 backend 专用字段 | 否 | 本 task 不动 data_models.py（仅追加测试代码到 test_qwen3omni_critic.py） |
| 在 `core/` 或 `analysis/` import 具体 backend | 否 | 本 task 改的是 `src_next/critic/tests/`（测试代码），不在 core/analysis 范畴 |
| 硬编码服务器地址进模块（非 profile） | 否 | 4 处 `base_url="http://fake"`（line 266/282/292/307），全部用 fake URL，**未硬编码任何真实 IP** |
| 既有测试被破坏 | 否 | `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` → `9 passed in 0.09s`，既有 5 个测试全绿（无回归） |
| `pytest --collect-only` 报 collection error | 否 | `9 tests collected in 0.01s`，exit 0 |
| commit 未做（PENDING） | 否 | commit `1d655b4` 已落盘，工作区 clean（仅 untracked 文档与 output 目录，与本 task 无关） |
| 任一 robustness 测试用真实 HTTP 调用（plan red flag #1） | 否 | 4 处全部 monkey-patch `mod.requests.post` + `base_url="http://fake"` 双重保险 |
| 断言写错如 `!=`（plan red flag #2） | 否 | 4 处全部 `== 0.5` |
| 4 个测试覆盖同一失败模式（plan red flag #3） | 否 | 4 种正交（500 / 200+非 JSON / 200+空 text / 网络异常） |
| mock 范围过宽，替换整个 `requests` 模块（plan red flag #4） | 否 | 仅 patch `mod.requests.post` 属性，未替换 `mod.requests` 模块对象 |

**0 red flag。**

### 6.1 scope creep 检查（plan §1.2「不交付」清单）

coding doc §1.2 列出后续 task 才交付的项。比对：

| 不交付项（属后续 task） | 本 task 是否越界 | 证据 |
|---|---|---|
| 集成测试骨架（Task 9）— 同文件再追加 4 个 skip-marked integration 测试 | 否 | `git diff HEAD~1 HEAD --stat` 显示 test_qwen3omni_critic.py +95 行；这些行全部是 robustness mock 测试 + fake class + helper，**无 `@pytest.mark.integration` / `@pytest.mark.skip` 标记**，无 `_INTEGRATION_SKIP_REASON` 常量 |
| `fixtures/` 目录的 3 段测试音频 | 否 | `src_next/critic/tests/` 目录下无 `fixtures/` 子目录（Task 7 KNOWN_ISSUES.md §3 标注"服务可访问后准备"） |
| TTSRepairAgent（Task 10/11） | 否 | `src_next/critic/` 目录下无 `tts_repair_agent.py` / `tts_repair_prompt.py` |
| `test_tts_repair.py`（Task 10 起） | 否 | `src_next/critic/tests/` 目录下无 `test_tts_repair.py` |
| 改业务代码 `qwen3omni_critic.py` | 否 | commit 范围不含 `src_next/critic/qwen3omni_critic.py`（Task 5 已实装 neutral fallback，本 task 只补测试） |

**0 越界。** Scope 严格按 plan §Task 8 Files 表「Modify: `src_next/critic/tests/test_qwen3omni_critic.py`」（仅此 1 项业务代码 + 配套 dev doc）。

---

## 7. Verdict JSON

```json
{
  "task_id": "task-8-robustness-tests",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v",
      "python -m py_compile src_next/critic/tests/test_qwen3omni_critic.py",
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py --collect-only -q"
    ],
    "result": "3/3 PASS — pytest -v 实测 9 passed in 0.09s（4 新 robustness + 5 既有，无回归）；py_compile OK；collect-only 9 tests collected 无 error。Plan 字面期望 7 passed 与实测 9 passed 的偏差属 Task 6 既存基线，非本 task 引入。"
  },
  "integration_tests": "N/A — Task 8 是 mock 测试型，不动主链路；plan B 第 2 部分 robustness smoke 第 2a 条（不可达端口）judge 本机已跑通过（输出 connection-fail fallback OK; overall= 0.5），第 2b 条服务可用时 smoke 不在 mock 验收范围",
  "smoke_tests": "PASS — judge 本机直跑 plan line 1255-1265 的 plan B smoke 第 2a 条（base_url=http://127.0.0.1:1 不可达端口），输出 connection-fail fallback OK; overall= 0.5，满足 plan line 1263 的 assert r.overall == 0.5 断言",
  "static_review": {
    "section_a_pass": "1/1 (+ 2 contract 全部 PASS)",
    "section_b_pass": "4/4 (+ 4 red flag 全部未触发)",
    "literal_diff": "BYTE-EQUAL (plan line 1117-1209 vs test_qwen3omni_critic.py line 221-313, 93 lines, md5 4b4cf0c59abb6cdc13e70412ff8b86c2, 0 char diff)",
    "commit_scope": "2 files / +512 lines (test_qwen3omni_critic.py +95 + dev doc +417)",
    "red_flags": "0",
    "scope_creep": "0"
  },
  "reason": "4 个 robustness 测试与 plan 字面量 md5 比对 BYTE-EQUAL；judge 自跑 9 passed 无回归；commit 1d655b4 已落盘且 scope 严格；0 red flag / 0 scope creep；plan 字面 7 vs 实测 9 的数量偏离属 Task 6 既存基线非本 task bug",
  "blocking_issues": [],
  "next_action": "PASS — 可进入 Task 9（集成测试骨架，同文件再追加 4 个 @pytest.mark.integration + @pytest.mark.skip 测试，用 conftest 的 real_critic / *_wav fixture）。提醒：Task 9 plan §Task 9 Step 2 期望 7 PASS + 4 SKIPPED，按本 task 偏离登记推断实际会是 9 PASS + 4 SKIPPED（基线已是 9 不是 7），Task 9 dev doc 应提前记录此偏离以免 judge-Agent 困惑。"
}
```

---

## 8. 给后续 task 的提醒

1. **Task 9（集成测试骨架）**：在同文件再追加 4 个 `@pytest.mark.integration` + `@pytest.mark.skip` 测试（`test_critic_high_quality_audio_scores_high` / `test_critic_low_quality_audio_scores_low` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment`），用 conftest 的 `real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` fixture。Plan §Task 9 Step 2 期望 "7 PASS + 4 SKIPPED"——按本 task 偏离登记推断实际会是 **"9 PASS + 4 SKIPPED"**（基线已是 9 不是 7），Task 9 dev doc 应提前记录此偏离以免 judge-Agent 困惑。

2. **`_make_segment_and_instruction` helper 仍然适用**：Task 9 的 integration 测试也用这个 helper（Task 5 在 line 23-38 已建）构造 `Segment` + `ModelSpecificTTSInstruction` 输入，本 task 没动 helper，Task 9 直接用即可。

3. **`_patch_post` 不适用于 integration 测试**：integration 测试要真联网调 `real_critic`，不能用 mock。Task 9 测试函数不应用 `_patch_post`，否则会绕开真实服务调用——`_patch_post` 仅服务于 Task 8 这 4 个 mock 测试。

4. **commit 类型延续**：Task 9 同样是测试代码（虽然 skip-marked），应延续本 task 的 `test(critic):` commit 类型；Task 10/11（TTSRepairAgent 业务代码）回到 `feat(critic):`。

5. **mock 范围检测（避免重蹈 red flag #4）**：本 task 用 `monkeypatch.setattr(mod.requests, "post", fake_post)`——patch 的是 `mod.requests` 模块的 `post` **属性**，不是替换整个 `mod.requests` 模块对象。未来任何 mock 测试都应遵守此约定，否则 plan §Task 8 Acceptance Red flags 第 4 条会判 FAIL。

6. **`base_url="http://fake"` 双重保险模式**：4 个测试即便 monkey-patch 失效也不会真连 `10.50.121.102:8011`（因为 critic 实例的 `base_url` 已被覆盖为 `http://fake`）。未来 mock 测试若 patch 不到目标方法时，此模式是兜底——值得复用。

---

## 9. 一句话总结

Task 8 = 在 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾追加 4 个 robustness 测试 + 3 个 fake response 类 + 1 个 `_patch_post` 辅助函数（共 +95 行），与 plan line 1117-1209 代码块 md5 比对 **BYTE-EQUAL**（md5 `4b4cf0c59abb6cdc13e70412ff8b86c2`，0 字符偏离）；judge 自跑 `pytest -v` 实测 `9 passed in 0.09s`（4 新 + 5 既有，无回归；plan 字面期望 7 passed，多出 2 是 Task 6 既存基线）；plan B smoke 第 2a 条本机直跑通过（不可达端口 fallback 输出 `overall= 0.5`）；commit `1d655b4` 已落盘，scope 严格（仅测试文件 + dev doc 2 文件 / +512 行）；Acceptance A 表 1/1 + B 表 4/4 全过，0 red flag，0 scope creep，**PASS**。
