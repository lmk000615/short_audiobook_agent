# Critic Task 5 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 5
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 5 无独立章节，沿用 plan §Task 5 Acceptance Criteria Full）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-03
> **Task 类型:** 代码型（TDD 红→半红：本 task 因依赖 Task 6 的 `build_critic_prompt`，终态停在 ImportError，故意不绿）
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan Task 5 要求，**追加** evaluate happy-path 测试（mocked HTTP），再**全量替换** `qwen3omni_critic.py` body 落地 `evaluate()` + 私有辅助方法 + JSON 解析三步兜底。终态故意停在 ImportError（依赖 `build_critic_prompt`，是 Task 6 的输入）。

> Plan 原文 Task 5 标题：**Write failing test for evaluate happy path + implement core (mocked)**。本 task 不是经典红绿循环——Step 2 红（无 evaluate 方法）→ Step 4 半红（实现 evaluate，但因依赖未到位仍 ImportError）。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 修改 | `src_next/critic/tests/test_qwen3omni_critic.py` | 追加 `_make_segment_and_instruction` 工厂 + `_FakeOkResponse` mock + `test_evaluate_returns_critic_result_on_success`（保留 Task 4 已有 1 个构造测试） |
| 修改 | `src_next/critic/qwen3omni_critic.py` | 用 plan Step 3 代码块**完整替换** body：`_CODE_FENCE_RE` / `_strip_code_fence` / `_extract_first_json` / `_parse_scoring_json` 模块级函数 + `Qwen3OmniCritic`（含 `__init__` / `evaluate` / `_evaluate_inner` / `_neutral_result`） |

### 1.2 不交付（属于后续 task）

- `src_next/critic/prompts/critic_prompt.py` 的 `build_critic_prompt`（**Task 6** — 这是本 task 终态 ImportError 的原因，**故意不提前实现**）
- `conftest.py` 里的 `good_narration_wav` fixture（Task 7）
- 鲁棒性测试（Task 8）
- 集成测试骨架（Task 9）
- TTSRepairAgent（Task 10/11）

### 1.3 前置条件（Task 1-4 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 4 commit `1da7024`（Qwen3OmniCritic skeleton）+ `2b79004`（dev doc）已落盘 | §4.5 | ✓ |
| `src_next/critic/qwen3omni_critic.py` 此前仅含 `__init__`（Task 4 边界）| §4.5 grep `def ` 输出仅 1 行 | ✓ |
| `src_next.core.data_models.CriticResult.from_json(data, attempt=...)` 签名存在 | §4.6 | ✓ |
| `ModelSpecificTTSInstruction.attempt: int = 1` 有默认值（plan 测试不需要显式传 attempt） | §4.6 | ✓ |
| `src_next/critic/prompts/critic_prompt.py` 此前不存在 | ✓（Task 6 创建） | ✓ |

---

## 2. 执行步骤（按 plan Task 5 Step 1 → 4）

### Step 1: 追加测试函数

**字面量来源：** plan §Task 5 Step 1 给出了完整 Python 代码块（含 `_make_segment_and_instruction` / `_FakeOkResponse` / `test_evaluate_returns_critic_result_on_success`），**逐字追加**到 `src_next/critic/tests/test_qwen3omni_critic.py` 末尾，保留 Task 4 已有的 `test_critic_can_be_constructed_with_defaults`。

**关键断言字面量（不能改）：**
- URL: `http://10.50.121.102:8011/v1/omni/audio_analysis`
- payload 4 字段: `audio` / `task=sound_analysis` / `text` / `return_audio=False` / `max_new_tokens=1024`
- proxies: `{"http": None, "https": None}`
- 分数区间: `0.84 <= quality <= 0.86`, `0.94 <= intelligibility <= 0.96`, `0.0 <= overall <= 1.0`
- fake response text 内嵌 5 维分数 JSON

### Step 2: 跑测试确认 FAIL（RED #1）

**Plan 预期：** `AttributeError: 'Qwen3OmniCritic' object has no attribute 'evaluate'`

**实测：** `AttributeError: module 'src_next.critic.qwen3omni_critic' has no attribute 'requests'`

> **偏离登记（轻微）：** Plan 预期测试在 `critic.evaluate(...)` 调用时炸（AttributeError on instance method），但实际在更早的 `monkeypatch.setattr(mod.requests, "post", ...)` 就炸了——因为 Task 4 实现的 `qwen3omni_critic.py` 还没 `import requests`，模块级没有 `requests` 属性。两者都是 `AttributeError`，RED 状态判定不变（"测试未通过 + 报错原因可识别"）。后续 Step 3 加上 `import requests` 后，此 AttributeError 消失。

### Step 3: 全量替换 `qwen3omni_critic.py` body

**字面量来源：** plan §Task 5 Step 3 给出了完整 Python 代码块，**完整替换** `src_next/critic/qwen3omni_critic.py` body（从模块 docstring `"""Qwen3-Omni 音频评估客户端。` 开始到文件结尾）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **`_CODE_FENCE_RE` 正则**：`r"^```(?:json)?\s*\n?|\n?\s*```\s*$"` + `re.MULTILINE` flag——剥 ```` ```json ... ``` ```` 围栏。
2. **`_extract_first_json` 扫描算法**：从左往右扫，遇 `{` 或 `[` 就试 `JSONDecoder.raw_decode`，第一个 dict 命中即返回；list 跳过；解析失败继续。
3. **`_parse_scoring_json` 三步兜底**：剥 fence → `json.loads` 直接试 → `_extract_first_json` 兜底；全失败抛 `ValueError`。
4. **`evaluate` catch-all**：`try: ... except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback`。注释必须保留（plan 字面量）。
5. **`_evaluate_inner` payload**：5 个 key，`task` 字面量是 `"sound_analysis"`（**不是** `"audio_analysis"`），`return_audio=False`，`max_new_tokens=1024`。
6. **`_evaluate_inner` URL**：`f"{self.base_url}/v1/omni/audio_analysis"`。
7. **`_evaluate_inner` 错误处理**：HTTP != 200 抛 `RuntimeError(f"audio_analysis returned HTTP {resp.status_code}: {resp.text[:200]!r}")`；空 text 抛 `RuntimeError("audio_analysis returned empty text field")`。
8. **`_neutral_result` 字面量**：所有 5 维 + overall 都是 **0.5**（不是 0.0），suggestions 文案 `f"评估失败：{err_msg}，建议人工复核"`，`@staticmethod`。
9. **import 顺序**：标准库（`json` / `re`）→ 第三方（`requests`）→ 项目内（`build_critic_prompt` / `data_models`）。

### Step 4: 再跑测试 — 期望 ImportError（RED #2，**预期半红状态**）

**Plan 预期：** `ImportError: cannot import name 'build_critic_prompt' from 'src_next.critic.prompts.critic_prompt'`

**实测：** `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'`

> **偏离登记（轻微，与 Task 4 同模式）：** Python 3.12 抛 `ModuleNotFoundError`（`ImportError` 子类）而非父类 `ImportError`，因为 `src_next/critic/prompts/critic_prompt.py` 文件本身不存在（Task 2 只建了 `prompts/` 目录，没建文件）。子类语义同样满足 plan 预期。

**重要：这是 plan 设计的预期终态——Task 5 完成时测试仍在 ImportError 状态，是 Task 6 的输入。** Task 6 创建 `critic_prompt.py` 后，此测试才会转绿。

---

## 3. Acceptance Criteria 自检

按 plan §Task 5 Acceptance Criteria Full 结构对照。

### A. coding-Agent 完成定义（mock-可验证）

| 检查项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `evaluate()` 方法存在 | ✓ | §4.3 grep `def evaluate` 命中 | ✓ |
| 签名 `(audio_path, segment, tts_instruction) -> CriticResult` | ✓ | §4.3 字面匹配 | ✓ |
| 私有方法 `_evaluate_inner` / `_neutral_result` 存在 | ✓ | §4.3 grep 命中 | ✓ |
| `python -m pytest ... -v` 跑通 | `1 passed` | **`1 failed (ImportError)`** | ⚠️ **预期半红**（见 §3.C） |

> **关键说明：** Plan §Task 5 Acceptance A 的 "self-check 命令" 写的是 `1 passed`，但 **Plan Step 4 明确写"Expected: FAIL with ImportError... Proceed to Task 6"**。这是 plan 内部矛盾——以 Step 4 的明确指令为准（Plan Step 4 是本 task 的最终状态判定，Acceptance A 的 self-check 是 Task 6 完成后的状态）。本 task 不强行让测试变绿。

### B. judge-Agent 静态审查点（预登记）

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| `_parse_scoring_json` 三步兜底完整（剥 fence → json.loads → raw_decode 扫描） | §4.3 grep 行 50-71 | ✓ |
| `try/except Exception` 范围合理（不是裸 `except:`，不是只 catch 一种） | §4.3 `except Exception as exc:  # noqa: BLE001` | ✓ |
| 未引入未要求的依赖（只用 `requests` + 项目内已有模块） | §4.3 imports 仅 `json` / `re` / `requests` / `build_critic_prompt` / `data_models` | ✓ |
| 没有提前实现 repair agent 的逻辑 | 本文件无 `repair` 字眼 | ✓ |
| neutral fallback 返回 `0.5` 而非 `0.0` | §4.3 `_neutral_result` 6 个 0.5 | ✓ |
| mock 测试无真实网络调用 | `monkeypatch.setattr(mod.requests, "post", fake_post)` 拦截 | ✓ |
| `_evaluate_inner` 不直接信任 `tts_instruction.text`（走 `build_critic_prompt`） | §4.3 `prompt_text = build_critic_prompt(...)` | ✓ |
| HTTP 走 `/v1/omni/audio_analysis`，payload 含 `task=sound_analysis` + `text` | §4.3 | ✓ |
| `proxies={"http": None, "https": None}`（bypass_proxy=True 时） | §4.3 `__init__` 末行 + `_evaluate_inner` proxies 传参 | ✓ |

### C. Pass 条件 + 偏离说明

- A 表中 mock test "1 passed" — **不满足**（ImportError），但这是 plan Step 4 明确设计的预期终态。
- B 表 9 项静态审查全部通过。
- 无 red flag（无抛异常越界、无 0.0 中性分、无未声明依赖、无提前实现 repair）。

**判定逻辑：**
- 本 task 严格按 plan Step 1 → 4 顺序执行，4 个 Step 的 expected 全部命中（含 Step 4 的"Expected FAIL with ImportError"）。
- 测试 PASS 需要等 Task 6 实现 `build_critic_prompt`。这是 plan 的**故意设计**（plan Step 4 末尾明文："This is the next task's dependency. Proceed to Task 6."）。
- 因此本 task 的 acceptance 不以 mock test 绿为前提，而以"完成 evaluate 实现 + 触发预期的 ImportError"为前提。

**建议判定：** → 待 judge 决断。coding-Agent 视角认为是 **PASS（按 plan Step 4 预期终态）**，因为：
1. evaluate / _evaluate_inner / _neutral_result / _parse_scoring_json 全部按 plan 字面量落地。
2. ImportError 字面匹配 plan Step 4 预期（"build_critic_prompt" 不可 import）。
3. 静态审查 9/9 全过。
4. plan Acceptance A 的 "1 passed" 与 Step 4 的 "Expected ImportError" 互相矛盾，以 Step 4 为准（Step 4 是 task 内最终状态描述，Acceptance A 是跨 task 完成态描述）。

---

## 4. 文件落盘证据

### 4.1 Step 2 测试输出（RED #1 — AttributeError on requests）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 1 item

src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success FAILED [100%]

================================== FAILURES ===================================
_______________ test_evaluate_returns_critic_result_on_success ________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x...>

>       monkeypatch.setattr(mod.requests, "post", fake_post)
                            ^^^^^^^^^^^^
E       AttributeError: module 'src_next.critic.qwen3omni_critic' has no attribute 'requests'

src_next\critic\tests\test_qwen3omni_critic.py:75: AttributeError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
============================== 1 failed in 0.05s ==============================
```

### 4.2 Step 4 测试输出（RED #2 — ImportError on build_critic_prompt，**plan 预期终态**）

```
>       import src_next.critic.qwen3omni_critic as mod
src_next\critic\tests\test_qwen3omni_critic.py:64:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    """Qwen3-Omni 音频评估客户端。 ...（模块 docstring）..."""
    from __future__ import annotations

    import json
    import re

    import requests

>   from src_next.critic.prompts.critic_prompt import build_critic_prompt
E   ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'

src_next\critic\qwen3omni_critic.py:19: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success
============================== 1 failed in 0.15s ==============================
```

> `ModuleNotFoundError` 是 `ImportError` 子类（Python 3.12 行为，与 Task 4 同模式偏离）。

### 4.3 关键字面量 grep 输出（给 judge-Agent 比对）

**B1：模块级 imports + 私有辅助函数**
```
$ grep -n "^import\|^from\|^def \|^_CODE_FENCE_RE" src_next/critic/qwen3omni_critic.py
13:from __future__ import annotations
15:import json
16:import re
18:import requests
20:from src_next.critic.prompts.critic_prompt import build_critic_prompt
21:from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
24:_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)
27:def _strip_code_fence(raw: str) -> str:
32:def _extract_first_json(raw: str) -> dict | None:
42:def _parse_scoring_json(raw_text: str) -> dict:
```

**B2：方法清单（验证 Task 5 边界——含 `evaluate` / `_evaluate_inner` / `_neutral_result`，无越界提前实现 repair）**
```
$ grep -n "^    def \|^    @" src_next/critic/qwen3omni_critic.py
46:    def __init__(
63:    def evaluate(
72:    def _evaluate_inner(
94:    @staticmethod
95:    def _neutral_result(segment_id: str, attempt: int, err_msg: str) -> CriticResult:
```

**B3：`_evaluate_inner` payload + URL**
```
75:        payload = {
76:            "audio": audio_path,
77:            "task": "sound_analysis",
78:            "text": prompt_text,
79:            "return_audio": False,
80:            "max_new_tokens": 1024,
81:        }
82:        url = f"{self.base_url}/v1/omni/audio_analysis"
```

**B4：catch-all 注释（noqa 字面量）**
```
68:        except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback
```

**B5：neutral fallback 6 个 0.5（不是 0.0）**
```
100:            quality=0.5,
101:            emotion_alignment=0.5,
102:            character_consistency=0.5,
103:            rhythm_naturalness=0.5,
104:            intelligibility=0.5,
105:            overall=0.5,
```

**B6：proxies 字面量**
```
60:        self._proxies = {"http": None, "https": None} if bypass_proxy else None
85:            proxies=self._proxies,
```

**B7：py_compile 验证（CLAUDE.md §10 验证清单第 1 条）**
```
$ python -m py_compile src_next/critic/qwen3omni_critic.py && echo OK
OK
```

### 4.4 测试文件方法清单（验证 Task 5 边界——2 个测试 + 1 个工厂 + 1 个 mock class）

```
$ grep -n "^def \|^class " src_next/critic/tests/test_qwen3omni_critic.py
13:def test_critic_can_be_constructed_with_defaults():
26:def _make_segment_and_instruction():
44:class _FakeOkResponse:
65:def test_evaluate_returns_critic_result_on_success(monkeypatch):
```

> 含 Task 4 的 `test_critic_can_be_constructed_with_defaults`（保留）+ Task 5 的 `test_evaluate_returns_critic_result_on_success`（新增）+ 工厂 `_make_segment_and_instruction` + mock `_FakeOkResponse`。无越界提前实现 Task 8/9 的 robustness/integration 测试。

### 4.5 前置 commit 历史（验证 Task 1-4 已落盘）

```
$ git log --oneline -5
47a9358 docs(critic): finalize task 4 dev doc with commit hashes
2b79004 docs(critic): add task 4 coding dev doc
1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test
97f880b docs(critic): add task 3 coding dev doc
e288ba5 docs(critic): document API risk + integration test gap
```

> 含 Task 4 代码 commit `1da7024` + dev doc commits `2b79004` / `47a9358`，前置链已就位。

### 4.6 前置：data_models 关键签名（验证 Task 5 调用可行）

```
$ python -c "from src_next.core.data_models import ModelSpecificTTSInstruction, CriticResult; import inspect; print('attempt default:', ModelSpecificTTSInstruction.__dataclass_fields__['attempt'].default); print('from_json sig:', inspect.signature(CriticResult.from_json))"
attempt default: 1
from_json sig: (data: dict[str, typing.Any], attempt: int = 1) -> CriticResult
```

> 关键：`ModelSpecificTTSInstruction.attempt` 默认值是 `1`，所以 plan Step 1 测试函数 `_make_segment_and_instruction` 不显式传 `attempt` 时也能构造（attempt=1）。`CriticResult.from_json(data, attempt=...)` 签名与 `_evaluate_inner` 调用一致。

---

## 5. 提交策略

### 5.1 plan 默认提交

plan Task 5 Step 5（实际无独立 Step 5，提交按 Task 4 先例 + 用户 task 指令）= 3 个文件：2 个代码文件 + 1 个 dev doc。

### 5.2 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 3 个文件）：

```bash
git add src_next/critic/qwen3omni_critic.py src_next/critic/tests/test_qwen3omni_critic.py docs/critic_task5_coding.md
git commit -m "feat(critic): implement task 5 (round 1)"
```

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `docs/intern_b_*.md` / `webui_old.py` / `input.rar` / 其他 specs / judging docs），全部不带进本 commit。

### 5.3 与 Task 4 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 |
|---|---|---|---|
| Task 4 | `1da7024` `feat(critic): add Qwen3OmniCritic skeleton...` | `2b79004` `docs(critic): add task 4 coding dev doc` | 分 2 commit |
| Task 5 | （本 task）`feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | **合并 1 commit**（按用户 task 指令明确要求） |

> Task 5 改用合并模式是用户 task 指令明确指定的（指令里只给了一个 commit 模板，且 add 列表含 dev doc）。Task 4 是当时用户在交互中选 B（分两 commit）；Task 5 是用户在 task 指令里预先指定（合并）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| Step 2 异常 | `AttributeError: 'Qwen3OmniCritic' object has no attribute 'evaluate'` | `AttributeError: module 'src_next.critic.qwen3omni_critic' has no attribute 'requests'` | 无（同样 AttributeError；炸点更早，因 monkeypatch 比 evaluate 调用先执行） | 文档记录，无需修复 |
| Step 4 异常类型 | `ImportError: cannot import name 'build_critic_prompt'` | `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'` | 无（子类语义；文件根本不存在 vs 文件存在但函数不存在，都是 ImportError 家族） | 文档记录 |
| Acceptance A self-check | `1 passed` | `1 failed (ImportError)` | ⚠️ plan 内部矛盾：Acceptance A 描述的是跨 task 完成态；Step 4 描述的是本 task 终态。以 Step 4 为准 | 文档说明 + 等 Task 6 完成后转绿 |

无结构性偏离。所有字面量（URL / payload / 0.5 / noqa 注释 / 变量名 / 函数名）与 plan 逐字一致。

### 6.2 给 Task 6 的提醒（关键！）

Task 5 已完成的部分（不需要 Task 6 重做）：
- `Qwen3OmniCritic.evaluate` / `_evaluate_inner` / `_neutral_result`
- `_parse_scoring_json` 三步兜底
- `_CODE_FENCE_RE` / `_strip_code_fence` / `_extract_first_json`

Task 6 必须做的（让 Task 5 测试转绿）：
- 创建 `src_next/critic/prompts/critic_prompt.py`
- 实现 `build_critic_prompt(segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> str`
- **签名要与 Task 5 `_evaluate_inner` 调用一致**（§4.3 行 73：`prompt_text = build_critic_prompt(segment, tts_instruction)`）
- prompt 内容应强制要求 Qwen3-Omni 输出**严格 JSON**（5 维：quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility + suggestions），否则 Task 5 的 mock JSON 解析路径走不通。
- Task 6 完成后跑 `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v` 应得 `1 passed`。

### 6.3 给 Task 7-9 的提醒

- **Task 7（conftest）**：`good_narration_wav` fixture 名字不能改（KNOWN_ISSUES.md §3 已固化）；路径解析函数必须命名为 `_audio_path`。
- **Task 8（鲁棒性测试）**：5 个测试函数名要与 KNOWN_ISSUES.md §1 列出的**逐字一致**。
- **Task 9（集成测试）**：5 个测试函数名同样要从 KNOWN_ISSUES.md §1 复制。

### 6.4 给 judge-Agent 的提示

- **静态审查重点：** 9 项静态抽查（§3.B）全部应通过。
- **mock test 状态说明：** 本 task 完成时 `test_evaluate_returns_critic_result_on_success` 仍 ImportError——**这不是 FAIL，是 plan Step 4 设计的预期终态**。请优先核对 plan §Task 5 Step 4 原文："Expected: FAIL with `ImportError: cannot import name 'build_critic_prompt'`... This is the next task's dependency. Proceed to Task 6."
- **不要要求本 task 让测试转绿**——这会逼迫越界提前实现 Task 6 的 `build_critic_prompt`，违反 task 边界。
- **越界检测：** `src_next/critic/prompts/` 目录此时应仍只有 Task 2 建目录时留下的状态（无 `critic_prompt.py` 文件，或只有空目录）。如果出现 `critic_prompt.py`，说明越界提前实现 Task 6。

---

## 7. 一句话总结

Task 5 = 追加 evaluate happy-path 测试 + 全量替换 `qwen3omni_critic.py` body（含 evaluate / _evaluate_inner / _neutral_result / _parse_scoring_json 三步兜底）。TDD 走 RED#1（AttributeError on requests）→ RED#2（**plan 设计的预期终态**：ImportError on build_critic_prompt），故意停在半红状态作为 Task 6 的输入。所有字面量（URL / payload / 0.5 中性分 / noqa 注释）与 plan 逐字一致，静态审查 9/9 全过。**测试当前在 ImportError 状态，是 Task 6 的输入。**
