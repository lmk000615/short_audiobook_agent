# Critic Task 4 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` §Task 4 (Simplified)
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 4 无独立章节，沿用 plan §Task 4 Acceptance Simplified）
> **Coding dev doc:** `docs/critic_task4_coding.md`
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-02
> **Task 类型:** 代码型（Simplified acceptance，TDD 一次红→绿循环 + commit）

---

## 0. Verdict 一句话

**PASS** — `Qwen3OmniCritic.__init__` 默认参数 + 模块顶部 docstring 警告字面量与 plan §Task 4 Step 3 **逐字一致**；construction 测试一次走通（RED→GREEN）；Section A 全绿（2/2）；Section B 静态抽查 4/4 全部通过（含 commit `1da7024` 已落盘）；零 red flag，零 scope creep，无越界提前实现 Task 5 的 `evaluate()`。

---

## 1. 验收范围

按 plan §Task 4 (Simplified) 的 Acceptance Criteria 两档验收：

- **Section A — coding-Agent Self-check**：2 条命令（双文件存在 + construction 测试 `1 passed`）
- **Section B — judge-Agent 抽查**：4 条（默认参数字面量 / docstring 警告 / 无 `evaluate()` 越界 / git log commit）
- **额外审查**：字面量逐字比对 + scope 边界（critic 子树）+ commit 范围核对 + 偏离登记 + red flag 排查

---

## 2. Section A — coding-Agent Self-check

| 项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| A1 `test -f src_next/critic/qwen3omni_critic.py && test -f src_next/critic/tests/test_qwen3omni_critic.py && echo OK` | `OK` | `OK` | PASS |
| A2 `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v` | `1 passed` | `1 passed in 0.02s` | PASS |

### A2 完整测试输出（judge 独立执行，不抄 coding doc）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\29577\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 1 item

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [100%]

============================== 1 passed in 0.02s ==============================
```

judge 在自己的环境跑出 `1 passed in 0.02s`，与 plan §Task 4 Acceptance A2 期望的 `1 passed` 字面量一致。

---

## 3. Section B — judge-Agent 抽查

| 抽查点 | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| B1 `__init__` 默认参数 | `base_url="http://10.50.121.102:8011"`, `timeout=120`, `bypass_proxy=True` | `qwen3omni_critic.py` L22-24 三行逐字命中（见 §3.1 grep 证据） | PASS |
| B2 模块顶部 docstring 含「infer_lock」+「API 风险」两点警告 | docstring 非空且含两个 ⚠️ 警告 | L6-7 `⚠️ 服务端有 infer_lock...` + L9 `⚠️ API 风险：task card 推荐 audio_analysis + text 字段...` | PASS |
| B3 **此时还没有 `evaluate()` 方法** | 方法清单仅 `__init__` | `grep "^    def "` 命中 1 行：L20 `def __init__(`；无 `def evaluate` / `def _evaluate_inner` / `def _neutral_result` / `def _parse_scoring_json` | PASS |
| B4 `git log --oneline -5` 含指定 commit | `feat(critic): add Qwen3OmniCritic skeleton with construction test` | 第 3 行 `1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test` | PASS |

### 3.1 B1 + B2 字面量证据（Read qwen3omni_critic.py 全文 35 行）

```
L1   """Qwen3-Omni 音频评估客户端。
L2
L3   调 Qwen3-Omni 服务的 /v1/omni/audio_analysis 端点（黄区 10.50.121.102:8011），
L4   让模型"听"一段 TTS 合成音频，输出 5 维评分 + 修复建议。
L5
L6   ⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
L7   上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。
L8
L9   ⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
L10  如果服务返回的不是评分 JSON，按 KNOWN_ISSUES.md §2 切换到 /v1/omni/chat。
L11  """
L12  from __future__ import annotations
L13
L14  from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
L15
L16
L17  class Qwen3OmniCritic:
L18      """用 Qwen3-Omni 多模态模型评估单段音频质量。"""
L19
L20      def __init__(
L21          self,
L22          base_url: str = "http://10.50.121.102:8011",
L23          timeout: int = 120,
L24          bypass_proxy: bool = True,
L25      ) -> None:
```

**B1 字面量核对**：L22-24 与 plan §Task 4 Step 3 代码块 L392-394 **逐字一致**（含黄区 IP `10.50.121.102`、端口 `8011`、超时 `120`、布尔 `True`，无任何改写）。

**B2 字面量核对**：
- 「infer_lock」字面量在 L6 ✓
- 「API 风险」字面量在 L9 ✓
- 两个 ⚠️ 警告均存在，措辞与 plan §Task 4 Step 3 代码块 L376-380 **逐字一致**。

### 3.2 B3 越界检测证据

```
$ grep "^    def " src_next/critic/qwen3omni_critic.py
20:    def __init__(
```

仅 1 个方法定义。Task 5 才应实现的私有方法（`_evaluate_inner` / `_neutral_result` / `_parse_scoring_json`）**全部缺席**。

补充 grep `evaluate|_evaluate_inner|_neutral_result|_parse_scoring_json`：

```
L7:  上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。
```

唯一一处「evaluate」字面量出现在模块顶部 docstring L7（API 使用警告），**不是方法定义**。这是 plan §Task 4 Step 3 代码块 L377 自带的原话，逐字复制合规。

### 3.3 B4 git log 证据

```
$ git log --oneline -5
47a9358 docs(critic): finalize task 4 dev doc with commit hashes
2b79004 docs(critic): add task 4 coding dev doc
1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test
97f880b docs(critic): add task 3 coding dev doc
e288ba5 docs(critic): document API risk + integration test gap
```

`1da7024` 字面匹配 plan §Task 4 Acceptance B 第 4 条 ✓。此外 `2b79004` (dev doc) + `47a9358` (dev doc commit hash 修订) 与 Task 2/3 先例一致——代码 commit 严格匹配 plan，dev doc 走独立 commit。

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 qwen3omni_critic.py 与 plan §Task 4 Step 3 逐字比对

| 元素 | plan 期望 | 实测 | 一致 |
|---|---|---|---|
| 模块 docstring 第 1-10 行 | 5 行：endpoint + infer_lock 警告 + API 风险警告 + fallback 指针 | L1-11 逐字一致 | YES |
| `from __future__ import annotations` | 必须有 | L12 有 | YES |
| `from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment` | 必须字面匹配（3 个类名） | L14 一致 | YES |
| class 名 `Qwen3OmniCritic` | 不可改 | L17 一致 | YES |
| class docstring | `"""用 Qwen3-Omni 多模态模型评估单段音频质量。"""` | L18 一致 | YES |
| `__init__` 3 个默认参数 | `base_url="http://10.50.121.102:8011"`, `timeout=120`, `bypass_proxy=True` | L22-24 一致 | YES |
| `__init__` docstring 3 个 Args | base_url / timeout / bypass_proxy 三段说明 | L26-31 一致 | YES |
| 3 个 `self.` 赋值 | `self.base_url / self.timeout / self.bypass_proxy` | L32-34 一致 | YES |

未做任何"优化"改写，未引入额外 import（如 `requests` / `json` / `re`），未引入类型注解 `Optional` 等额外依赖。**字面量 100% 匹配 plan**。

### 4.2 test_qwen3omni_critic.py 与 plan §Task 4 Step 1 逐字比对

| 元素 | plan 期望 | 实测 | 一致 |
|---|---|---|---|
| 模块 docstring | `"""Qwen3OmniCritic unit tests. ..."""` 3 行 | L1-5 一致 | YES |
| `from __future__ import annotations` | 必须有 | L6 有 | YES |
| `import pytest` | 必须有（暂未使用，但保留） | L8 有 | YES |
| `from src_next.core.data_models import ModelSpecificTTSInstruction, Segment` | 必须字面匹配（2 个类名） | L10 一致 | YES |
| 测试函数名 | `test_critic_can_be_constructed_with_defaults` | L13 一致 | YES |
| 测试 docstring | `"""Qwen3OmniCritic should construct with the documented default base_url."""` | L14 一致 | YES |
| 函数体内 import | `from src_next.critic.qwen3omni_critic import Qwen3OmniCritic` | L15 一致 | YES |
| 3 条 assert | `base_url == "http://10.50.121.102:8011"` / `timeout == 120` / `bypass_proxy is True` | L18-20 一致 | YES |

测试函数数量 = 1。无越界提前写 Task 5/8/9 的测试。

### 4.3 critic/ 子树边界守住

```
src_next/critic/
├── __init__.py                            （Task 2）
├── KNOWN_ISSUES.md                        （Task 3）
├── prompts/__init__.py                    （Task 2）
├── tests/
│   ├── __init__.py                        （Task 2）
│   └── test_qwen3omni_critic.py           ★ 本 task 新增
└── qwen3omni_critic.py                    ★ 本 task 新增
```

仅 2 个新文件落地。**无任何越界文件**：未提前实现 `prompts/critic_prompt.py`（Task 6）/ `conftest.py`（Task 7）/ `_evaluate_inner` 等私有方法（Task 5）/ robustness 测试（Task 8）/ integration skeleton（Task 9）/ `tts_repair.py`（Task 10-12）—— plan §1.2 边界严格守住。

### 4.4 commit 范围核对（plan Step 5 期望 vs 实测）

| 项 | plan Step 5 期望 | 实测 | 状态 |
|---|---|---|---|
| commit 文件清单 | `src_next/critic/qwen3omni_critic.py` + `src_next/critic/tests/test_qwen3omni_critic.py` | `1da7024` 仅含这两个文件（dev doc 走独立 commit） | DONE |
| commit message | `feat(critic): add Qwen3OmniCritic skeleton with construction test` | 字面匹配 | DONE |
| 是否夹带 untracked | 不夹带（plan `git add` 显式 2 文件） | 无夹带 | DONE |

按 `feedback_commit_control.md`「问清楚再 commit」+ 用户选项 B 决策：代码 commit 严格匹配 plan Step 5，dev doc 单独入库（`2b79004`），dev doc 二次修订再入库（`47a9358` 补 commit hash）。3 个 commit 的边界清晰，与 Task 2/3 先例一致。

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| Step 2 异常类型 | `ImportError: cannot import name 'Qwen3OmniCritic' from 'src_next.critic.qwen3omni_critic'` | `ModuleNotFoundError: No module named 'src_next.critic.qwen3omni_critic'` | 无（Python 3.12：模块文件不存在抛 `ModuleNotFoundError`，是 `ImportError` 的子类，语义等价） | 接受，文档登记（coding dev doc §6.1 已记录） |
| commit 数量 | plan Step 5 期望 1 个 commit（2 个代码文件） | 实测 3 个 commit（代码 + dev doc + dev doc 修订） | 无（dev doc 与 dev doc 修订均为 docs 类，与 plan 代码 commit 边界清晰隔离） | 接受，与 Task 2/3 先例一致 |

**无结构性偏离。** Step 2 异常类型偏离是 Python 版本行为差异，不影响 RED→GREEN 循环判定（`ImportError` 是父类语义）。commit 数量偏离是 docs 伴随性入库，不影响 plan 代码 commit 字面量匹配。

---

## 6. Red Flags 排查

| 排查项 | 结论 |
|---|---|
| 默认参数字面量不一致（如改黄区 IP / 端口 / 超时数值） | 无 |
| docstring 警告字面量被改写或缺失 | 无（infer_lock + API 风险两点都在） |
| 越界提前实现 `evaluate()` / `_evaluate_inner` / `_neutral_result` / `_parse_scoring_json` | 无（方法清单仅 `__init__`） |
| 越界提前写 Task 5/8/9 的测试 | 无（测试函数数量 = 1） |
| 引入 Task 5 才需要的 import（`requests` / `json` / `re`） | 无（仅 `from src_next.core.data_models import ...`） |
| 引入 prompt 模块（Task 6 边界） | 无 |
| critic 子树越界（含后续 task 文件） | 无 |
| `--no-verify` / 跳过 hooks | 无 |
| 改动 `src/` 旧链路 | 无 |
| 改动 `requirements.txt` / 依赖版本 | 无 |
| commit 字面量不匹配 plan Step 5 | 无（`1da7024` 字面匹配） |
| commit 夹带 untracked 文件（output*/、input.rar、webui_old.py 等） | 无 |

零 red flag。

---

## 7. Verdict JSON（按 judge-Agent 验收 schema）

```json
{
  "task_id": "Task 4 — Write failing test for Qwen3OmniCritic construction",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "A1 test -f src_next/critic/qwen3omni_critic.py && test -f src_next/critic/tests/test_qwen3omni_critic.py && echo OK",
      "A2 python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v"
    ],
    "result": "2/2 green (OK + 1 passed in 0.02s)"
  },
  "integration_tests": "N/A (plan Task 4 是 TDD 骨架，无 integration 维度)",
  "smoke_tests": "N/A (Simplified 档无 smoke)",
  "static_review": {
    "literal_match_plan": true,
    "default_params_correct": true,
    "docstring_warnings_present": true,
    "no_evaluate_method_premature": true,
    "no_task5plus_tests_premature": true,
    "no_extra_imports": true,
    "critic_subtree_boundary_held": true,
    "commit_message_match": true,
    "commit_executed": true,
    "red_flags": []
  },
  "reason": "Qwen3OmniCritic skeleton + construction test 字面量与 plan §Task 4 Step 1/Step 3 逐字一致；TDD 红→绿循环一次走通（RED: ModuleNotFoundError → GREEN: 1 passed in 0.02s）；方法清单仅 __init__，未越界提前实现 evaluate/_evaluate_inner/_neutral_result/_parse_scoring_json；模块顶部 docstring 双警告（infer_lock + API 风险）字面命中；commit 1da7024 字面匹配 plan Step 5；零 red flag，零 scope creep。",
  "blocking_issues": [],
  "next_action": "Task 4 关单。进入 Task 5（evaluate happy path + _evaluate_inner 实现）：实现时 URL 必须用 /v1/omni/audio_analysis（与 Task 4 模块 docstring L3 + KNOWN_ISSUES.md §2 fallback 起点一致）；引入 from src_next.critic.prompts.critic_prompt import build_critic_prompt 会触发 ImportError（plan Task 5 Step 4 预期），故意留给 Task 6 的依赖。"
}
```

---

## 8. 给后续 task 的提醒（继承 dev log §6.2 + judge 补充）

- **Task 5**（evaluate happy path + mocked 实现）：
  - URL 必须用 `/v1/omni/audio_analysis`（与本 task 模块 docstring L3 + KNOWN_ISSUES.md §2 fallback 起点一致）
  - 故意引入 `from src_next.critic.prompts.critic_prompt import build_critic_prompt` 会 ImportError，这是 plan Task 5 Step 4 预期的 RED，留给 Task 6 解决
  - 引入的依赖（`requests` / `json` / `re`）必须在 Task 5 实现 `_evaluate_inner` 时才入库，不能回填到 Task 4 的 qwen3omni_critic.py
- **Task 6**（critic_prompt）：`build_critic_prompt(segment, tts_instruction) -> str` 函数签名要与 Task 5 调用一致；prompt 必须强制要求 Qwen3-Omni 输出严格 JSON（5 维评分 + suggestions），便于 Task 5 的 `_parse_scoring_json` 解析
- **Task 7**（conftest）：`good_narration_wav` fixture 名不能改（KNOWN_ISSUES.md §3 已固化）；路径解析函数必须命名为 `_audio_path`
- **Task 8/9**（robustness + integration skeleton）：测试函数名必须与 KNOWN_ISSUES.md §1 列出的 5 个测试名**逐字一致**

---

## 9. 一句话总结

代码 commit `1da7024` + dev doc commits `2b79004` / `47a9358` 全部落地，字面量 100% 匹配 plan，TDD 红绿循环一次走通，零越界——直接关单进 Task 5。
