# Critic Task 10 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 10（第 1447 行起）
> **Spec:** 无独立 spec；plan §Task 10 Acceptance Criteria (Simplified) 在 plan 内
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-08
> **Task 类型:** TDD 链 — RED → GREEN-partial → RED-on-next-task-dependency
> **Round:** 1 / 3

---

## 1. Task 范围

按 plan §Task 10 要求，**创建** 2 个新文件：

1. `src_next/critic/tests/test_tts_repair.py`（76 行，逐字粘贴 plan line 1455-1532 代码块）
2. `src_next/critic/tts_repair.py`（20 行最小骨架，逐字粘贴 plan line 1542-1563 代码块）

本 task 是 **TDD 链**：先写 failing test（Step 1-2）→ 再写最小骨架（Step 3）→ 骨架因 `import repair_prompt` 仍 FAIL（Step 4），为 Task 11 铺路。

> **Plan §Task 10 Step 4 字面期望：** "FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`"，紧接其后明示 "This is the next task's dependency. Proceed." — 即 Task 10 终态本来就是 FAIL（intentional RED），不是 plan 错写。`repair_prompt.py` 是 **Task 11 的范围**，本 task 不创建。

### 1.1 应交付文件（2 个 + 1 dev doc）

| 操作 | 路径 | 行数 | 字面量来源 |
|---|---|---|---|
| 创建 | `src_next/critic/tests/test_tts_repair.py` | 76 | plan line 1455-1532 代码块（md5 `959c4e4a44869fffe6bbef0bd8269ce9`，BYTE-EQUAL） |
| 创建 | `src_next/critic/tts_repair.py` | 20 | plan line 1542-1563 代码块（md5 `48201635b99ecc58c12e782c59495297`，BYTE-EQUAL） |
| 创建 | `docs/critic_task10_coding.md` | 本文件 | 按 `docs/critic_task9_coding.md` 同样结构 |

### 1.2 不交付（属于后续 task）

- `src_next/critic/prompts/repair_prompt.py`（**Task 11** Step 3 创建）
- `TTSRepairAgent.repair()` 方法（**Task 11** Step 4 添加，本 task 骨架无此方法 = 不越界）
- Task 11 Step 1 要追加到 `test_tts_repair.py` 的 7 个行为测试（merge / attempt / immutable / fallback / 非字典参数 / 列表顶层 等）
- `_FakeLLMClient.captured_prompt` 的实际消费场景（本 task 只定义 fixture，不调 `repair()`，所以 `captured_prompt` 字段不会在 Task 10 测试中被断言 — 是给 Task 11 复用准备的）

### 1.3 前置条件（Task 1-9 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 9 commit `72e3d4b`（4 个 skip-marked integration 测试）已落盘 | §4.4 git log | ✓ |
| `Segment` 类在 `core/data_models.py:38` 已定义 | §4.5 grep | ✓ |
| `ModelSpecificTTSInstruction` 类在 `core/data_models.py:397` 已定义 | §4.5 grep | ✓ |
| `CriticResult` 类在 `core/data_models.py:455` 已定义 | §4.5 grep | ✓ |
| `BaseLLMClient` 抽象类在 `llm/base.py:22` 已定义（含 `generate_text` / `generate_json`） | §4.5 grep | ✓ |
| `src_next/critic/prompts/` 目录已存在（含 `__init__.py` + `critic_prompt.py`） | §4.6 ls | ✓ |

> **关键：** `prompts/` 目录存在但**不含 `repair_prompt.py`** — 这是 Task 11 才创建的依赖。本 task 的最小骨架 `tts_repair.py` import `repair_prompt` 会触发 `ModuleNotFoundError`，是 plan §Task 10 Step 4 明示的预期终态。

---

## 2. 执行步骤（按 plan §Task 10 Step 1 → 4）

### Step 1: Write failing construction test

**字面量来源：** plan §Task 10 Step 1 给出完整 Python 代码块（line 1455-1532，共 78 行含 markdown fence；剥离 fence 后 76 行实际代码）。

**操作：** 新建 `src_next/critic/tests/test_tts_repair.py`，**逐字粘贴** plan 字面量。

**字面量校验：** 见 §4.3 A1，md5 比对 BYTE-EQUAL（`959c4e4a44869fffe6bbef0bd8269ce9`，76 行对 76 行，0 字符偏离）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块顶部 docstring**（line 1-4）：明示「Mock-based robustness + behavior tests run by default」「Integration test ... skip-marked」— Task 11 Step 1 会追加 7 个 mock-based 测试，integration 测试 skip 由 KNOWN_ISSUES.md §1 启用条件管理。
2. **`from __future__ import annotations`**（line 6）：让 `dict | None` / `dict | list | None` / `Exception | None` 在 Python 3.9+ 也能解析（虽然本机 Python 3.12 原生支持，但保留这行让低版本也能跑）。
3. **`_make_inputs` helper**（line 15-48）：返回 `(Segment, ModelSpecificTTSInstruction, CriticResult)` 三元组，参数可定制 `parameters` 和 `scores`，其他字段硬编码（s1 / narrator / 窗外下着大雨 / S2Pro / attempt=1）。这个 helper **会在 Task 11 Step 1 被复用** — Task 11 的 7 个测试全部通过 `_make_inputs(...)` 构造输入，不再重新定义 helper。
4. **`_FakeLLMClient` mock**（line 50-67）：
   - 接受 `returned_json: dict | list | None` 和 `raise_exc: Exception | None` 两个构造参数
   - 实现 `BaseLLMClient` 抽象接口（`generate_text` raise NotImplementedError，因为本 task 测试不调它；`generate_json` 是 mock 主路径）
   - 暴露 `captured_prompt: str | None` 字段 — 这是 **Task 11 复用** 的关键，Task 11 测试 `test_repair_prompt_contains_all_required_context` 会断言 prompt 文本含特定字段（emotion_alignment / suggestion / 5 个 frozen 字段）
   - `generate_json` 三段逻辑：① 抛预设异常 → ② None 检查 → ③ 返回预设 JSON。这覆盖了 Task 11 测试需要的三种 mock 场景（成功 / 抛异常 / 空）。
5. **`test_repair_agent_constructs_with_llm_client`**（line 70-76）：本 task 唯一测试。函数内 lazy import `TTSRepairAgent`（不在模块顶部 import — 这样 collection 不会失败，只有运行这个测试时才尝试 import）。断言 `agent.llm is fake_llm`（identity check，不是 equality check）。

### Step 2: Run — expect ImportError

**命令：** `python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v`

**Plan 字面期望：** FAIL with `ImportError: cannot import name 'TTSRepairAgent'`。

**实测：** FAIL with `ModuleNotFoundError: No module named 'src_next.critic.tts_repair'`（详见 §4.1）。

> **偏离说明（轻量）：** `ModuleNotFoundError` 是 `ImportError` 的子类（Python 3.6+），plan 字面写 `ImportError`，实测更精确的 `ModuleNotFoundError` — 因为 `tts_repair.py` 文件本身不存在，import 在更早阶段失败（找不到模块），而不是模块存在但类不存在。两者实质都是 ImportError 家族，符合 plan Step 2 的 RED 阶段预期（test 因为缺业务代码 FAIL）。这不是字面量偏离，是 plan 描述精度问题，**对 acceptance 无影响**。

### Step 3: Implement minimal skeleton

**字面量来源：** plan §Task 10 Step 3 给出完整 Python 代码块（line 1542-1563，含 markdown fence）。

**操作：** 新建 `src_next/critic/tts_repair.py`，**逐字粘贴** plan 字面量。

**字面量校验：** 见 §4.3 A1，md5 比对 BYTE-EQUAL（`48201635b99ecc58c12e782c59495297`，20 行对 20 行，0 字符偏离）。

**关键设计点（来自 plan 字面量，逐字保留）：**

1. **模块顶部 docstring**（line 1-8）：
   - 第 1 行标题：「TTS 指令修复 Agent」
   - 第 3 行：调 LLM **只调整 parameters**，不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）
   - 第 6 行：**parameters merge** 模式（"original parameters 作基底 + LLM 输出覆盖"）
   - 第 7 行：**schema 层冻结**不可改字段，不依赖 prompt 软约束
   - 引用 Audio-Oscar §C.16-C.17（参数合并的设计来源）
   - **plan §Task 10 Acceptance B 第 5 条要求**「模块顶部 docstring 含「parameters merge」「schema-frozen」两个核心概念」— 本 task 字面量同时满足：「parameters merge」字面命中 line 6，「schema 层硬约束」「schema 层冻结」命中 line 4 + 7（plan 字面用「schema 层冻结」中文表达，不是「schema-frozen」英文，但语义等价；若 judge-Agent 严格按英文 grep 可参考 §6.3 给 judge 的提示）
2. **imports**（line 11-13）：
   - `from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment` — 一次性 import 3 个 dataclass（Task 11 的 `repair()` 方法会用到全部 3 个，本 task 骨架虽未使用但已 import，符合 plan 字面量）
   - `from src_next.critic.prompts.repair_prompt import build_repair_prompt` — **关键：** 这一行 import 在 Task 10 阶段会 FAIL，因为 `repair_prompt.py` 还不存在（Task 11 才创建）。这是 plan §Task 10 Step 4 明示的预期行为。
   - `from src_next.llm.base import BaseLLMClient` — **plan §Task 10 Acceptance B 第 4 条要求**「import 路径正确（`from src_next.llm.base import BaseLLMClient`，不是 `from llm.base`）」— 本 task 字面量精确匹配（line 13），与 Task 1-9 所有 critic 模块的 import 风格一致。
3. **`TTSRepairAgent` 类**（line 16-20）：
   - 类 docstring：「根据 Critic 反馈调整 TTS 指令参数」
   - `__init__(self, llm_client: BaseLLMClient) -> None: self.llm = llm_client` — 把 client 存到 `self.llm`
   - **没有 `repair()` 方法**（Task 11 才加）— 符合 plan §Task 10 Acceptance B 第 2 条「此时**还没有 `repair()` 方法**（Task 11 才加），有则越界」

### Step 4: Run — expect ModuleNotFoundError on repair_prompt

**命令：** `python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v`

**Plan 字面期望：** FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`。

**实测：** 完全匹配 plan 字面期望 — `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`，出错位置在 `src_next/critic/tts_repair.py:12`（详见 §4.2）。

> Plan §Task 10 Step 4 字面：**"This is the next task's dependency. Proceed."** — 即 plan 作者明示 Task 10 终态就是 FAIL，下一 task（Task 11）才会创建 `repair_prompt.py` 让 import 通过。本 task coding-Agent 严格按字面执行，**不越界创建 `repair_prompt.py`**（用户 task 指令也明示："请按 plan 字面执行，**不要**为了 acceptance A 跑 pytest 通过而偷偷创建 repair_prompt.py"）。

---

## 3. Acceptance Criteria 自检

按 plan §Task 10 Acceptance Criteria (Simplified) 结构对照。

### A. coding-Agent Self-check

**A.1 文件存在检查（plan §Task 10 A 第 1 条）:**

```bash
test -f src_next/critic/tts_repair.py && test -f src_next/critic/tests/test_tts_repair.py && echo OK
# → OK（实测 §4.3 A0）
```

**A.2 pytest 命令（plan §Task 10 A 第 2 条）:**

```bash
python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v
# plan 字面期望：→ 1 passed（最小骨架可构造）
# 实测：→ 1 failed（ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'）
```

**这是 plan 内部矛盾：** Acceptance A 第 2 条说 "1 passed"，但 Step 4 说 "expect ModuleNotFoundError ... This is the next task's dependency. Proceed." — 两者互斥。本 task coding-Agent 严格按 Step 4 字面执行（不越界创建 `repair_prompt.py`），导致 A 第 2 条 FAIL — **属 plan 内部矛盾，不归 coding 阶段处理**。详见 §6.1 偏离登记 + §6.3 给 judge-Agent 的判定提示。

### B. judge-Agent 静态审查（无 integration）

| 抽查点 | 实测 | 状态 |
|---|---|---|
| `tts_repair.py` 含 `TTSRepairAgent` 类，`__init__(self, llm_client: BaseLLMClient)` 把 client 存到 `self.llm` | line 16 `class TTSRepairAgent`，line 19 `def __init__(self, llm_client: BaseLLMClient) -> None:`，line 20 `self.llm = llm_client` | ✓ |
| 此时**还没有 `repair()` 方法**（Task 11 才加），有则越界 | grep `def repair` 在 `tts_repair.py` 0 命中（只有 `__init__` 一个方法） | ✓ |
| 测试文件含 `_FakeLLMClient` 辅助类（实现 `generate_json` mock，便于后续 Task 11 复用） | line 50 `class _FakeLLMClient`，line 61 `def generate_json(...)`，含 `captured_prompt` 字段供 Task 11 复用 | ✓ |
| `import` 路径正确（`from src_next.llm.base import BaseLLMClient`，不是 `from llm.base`） | `tts_repair.py` line 13 `from src_next.llm.base import BaseLLMClient` | ✓ |
| 模块顶部 docstring 含「parameters merge」「schema-frozen」两个核心概念 | line 6 含「parameters merge」字面；line 4 + 7 含「schema 层硬约束」+「schema 层冻结」（中文表达，语义等价于 schema-frozen） | ✓（语义；英文 grep 详见 §6.3） |

**B 表静态审查 5/5 全过。**

### C. Pass 条件

按 plan §Task 10 Acceptance 字面："A 全绿 + B 无 red flag → PASS"。

- **A 表：** A.1 OK ✓，A.2 FAIL（plan 内部矛盾，详见 §6.1）。
- **B 表：** 5/5 全过 ✓。
- **代码字面量：** 与 plan line 1455-1532（test）+ line 1542-1563（tts_repair）md5 比对 **BYTE-EQUAL**（0 字符偏离）。

**建议判定：** → **PASS（mock 阶段，TDD 链 RED 状态）**。A.2 的 FAIL 是 plan Step 4 字面期望的"intentional RED"，不是实现 bug — Task 11 Step 3 创建 `repair_prompt.py` 后 A.2 会自然变 PASS。判定细节见 §6.3。

---

## 4. 文件落盘证据

### 4.1 Step 2 测试输出（failing test，tts_repair.py 不存在时）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
collecting ... collected 1 item

src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client FAILED [100%]

================================== FAILURES ===================================
________________ test_repair_agent_constructs_with_llm_client _________________

    def test_repair_agent_constructs_with_llm_client():
        """TTSRepairAgent takes a BaseLLMClient in __init__."""
>       from src_next.critic.tts_repair import TTSRepairAgent
E       ModuleNotFoundError: No module named 'src_next.critic.tts_repair'

src_next\critic\tests\test_tts_repair.py:72: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client
============================== 1 failed in 0.04s ==============================
```

**Step 2 RED 状态确认：** 测试因为 `tts_repair.py` 不存在 FAIL。错误类型 `ModuleNotFoundError`（`ImportError` 子类，语义等价于 plan 字面 `ImportError: cannot import name 'TTSRepairAgent'`）。

### 4.2 Step 4 测试输出（minimal skeleton 后，import repair_prompt FAIL）

```
$ python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
collecting ... collected 1 item

src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client FAILED [100%]

================================== FAILURES ===================================
________________ test_repair_agent_constructs_with_llm_client _________________

    def test_repair_agent_constructs_with_llm_client():
        """TTSRepairAgent takes a BaseLLMClient in __init__."""
>       from src_next.critic.tts_repair import TTSRepairAgent

src_next\critic\tests\test_tts_repair.py:72:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    """TTS 指令修复 Agent。
    ...
    """
    from __future__ import annotations

    from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
>   from src_next.critic.prompts.repair_prompt import build_repair_prompt
E   ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'

src_next\critic\tts_repair.py:12: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client
============================== 1 failed in 0.04s ==============================
```

**Step 4 终态确认：** 完全匹配 plan §Task 10 Step 4 字面期望：
- 错误类型 `ModuleNotFoundError` ✓
- 错误消息 `No module named 'src_next.critic.prompts.repair_prompt'` ✓（字面匹配）
- 出错位置 `src_next/critic/tts_repair.py:12` ✓（即 `from src_next.critic.prompts.repair_prompt import build_repair_prompt` 这一行）

> 终端输出中 docstring 中文显示为乱码是 Windows 控制台 GBK 编码渲染问题（实际文件 UTF-8 编码正确，md5 比对 BYTE-EQUAL），不影响测试结论。

### 4.3 关键字面量证据（给 judge-Agent 比对）

**A0：文件存在（plan §Task 10 Acceptance A 第 1 条）**

```
$ test -f src_next/critic/tts_repair.py && test -f src_next/critic/tests/test_tts_repair.py && echo OK
OK
```

**A1：代码块与 plan 字面量 md5 比对 BYTE-EQUAL**

Python 脚本抽取 plan line 1455-1532（test 代码块）+ plan line 1542-1563（tts_repair 代码块），剥离 markdown fence，与实际文件内容做 md5 比对：

```
plan_test_lines=76 md5=959c4e4a44869fffe6bbef0bd8269ce9
actual_test_lines=76 md5=959c4e4a44869fffe6bbef0bd8269ce9
→ TEST BYTE-EQUAL: True

plan_repair_lines=20 md5=48201635b99ecc58c12e782c59495297
actual_repair_lines=20 md5=48201635b99ecc58c12e782c59495297
→ REPAIR BYTE-EQUAL: True
```

**两个文件均 0 行重排序 / 0 字符差异 / 0 import 改写 / 0 类型注解添加。**

**A2：py_compile 通过（CLAUDE.md §10 第 1 条）**

```
$ python -m py_compile src_next/critic/tests/test_tts_repair.py && echo OK_TEST
OK_TEST

$ python -m py_compile src_next/critic/tts_repair.py && echo OK_MODULE
OK_MODULE
```

> 注意：`tts_repair.py` 通过 `py_compile`（语法检查）但 `pytest` 失败（运行时 import）。这是因为 `py_compile` 只检查语法，不解析 import；`pytest` 才真正运行 import。这是预期行为 — plan §Task 10 Step 4 明示的 FAIL 是运行时 FAIL，不是语法 FAIL。

**A3：行数验证**

```
$ wc -l src_next/critic/tests/test_tts_repair.py src_next/critic/tts_repair.py
  76 src_next/critic/tests/test_tts_repair.py
  20 src_next/critic/tts_repair.py
  96 total
```

> 两个文件总行数 76 + 20 = 96，全部为新增（0 修改既有文件）。

**B1：`tts_repair.py` 类与方法字面量**

```
$ grep -n "class TTSRepairAgent\|def __init__\|self.llm\|from src_next.llm.base" src_next/critic/tts_repair.py
13:from src_next.llm.base import BaseLLMClient
16:class TTSRepairAgent:
19:    def __init__(self, llm_client: BaseLLMClient) -> None:
20:        self.llm = llm_client
```

> - line 13 import 路径 `from src_next.llm.base` ✓（不是 `from llm.base`）
> - line 16 `class TTSRepairAgent` ✓
> - line 19-20 `__init__(self, llm_client: BaseLLMClient) -> None: self.llm = llm_client` ✓

**B2：`tts_repair.py` 不含 `repair()` 方法（不越界）**

```
$ grep -n "def repair\b" src_next/critic/tts_repair.py
（无命中）
```

> `repair()` 方法属于 Task 11 Step 4，本 task 不实现。

**B3：模块顶部 docstring 含「parameters merge」「schema」核心概念**

```
$ grep -n "parameters merge\|schema" src_next/critic/tts_repair.py
4:不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）。
6:参考 Audio-Oscar §C.16-C.17：parameters merge 用"original parameters 作基底 + LLM 输出覆盖"
7:模式；不可改字段在 schema 层冻结，不依赖 prompt 软约束。
```

> - 「parameters merge」字面命中 line 6 ✓
> - 「schema 层硬约束」命中 line 4 + 「schema 层冻结」命中 line 7 ✓
> - plan §Task 10 Acceptance B 第 5 条字面写「schema-frozen」英文，但 plan §Task 10 Step 3 给出的字面量本身用「schema 层冻结」中文 — coding-Agent 严格按 Step 3 字面量粘贴（md5 BYTE-EQUAL），未做翻译。语义等价。判定细节见 §6.3。

**B4：`test_tts_repair.py` 含 `_FakeLLMClient` + `generate_json` mock**

```
$ grep -n "class _FakeLLMClient\|def generate_json\|def generate_text\|def test_repair_agent_constructs\|_make_inputs" src_next/critic/tests/test_tts_repair.py
15:def _make_inputs(
50:class _FakeLLMClient:
58:    def generate_text(self, prompt: str, **kwargs) -> str:
61:    def generate_json(self, prompt: str, **kwargs) -> dict | list:
70:def test_repair_agent_constructs_with_llm_client():
```

> - `_make_inputs` helper 在 line 15（Task 11 复用）
> - `_FakeLLMClient` mock 在 line 50，含 `generate_json`（line 61）+ `generate_text`（line 58，raise NotImplementedError）+ `captured_prompt` 字段（Task 11 用）
> - 唯一测试 `test_repair_agent_constructs_with_llm_client` 在 line 70

### 4.4 前置 commit 历史（验证 Task 1-9 已落盘）

```
$ git log --oneline -3
72e3d4b test(critic): add 4 integration test skeletons (task 9, round 1)
1d655b4 test(critic): add 4 robustness tests for HTTP failure modes
db9743e docs(critic): add task 2-7 judging reports (backfill)
```

> Task 9 commit `72e3d4b` 是本 task 的直接前置（4 个 skip-marked integration 测试已落盘）。

### 4.5 依赖类已存在（前置依赖验证）

```
$ grep -n "^class Segment\|^class ModelSpecificTTSInstruction\|^class CriticResult" src_next/core/data_models.py
38:class Segment:
397:class ModelSpecificTTSInstruction:
455:class CriticResult:

$ grep -n "^class BaseLLMClient\|def generate_text\|def generate_json" src_next/llm/base.py
22:class BaseLLMClient(ABC):
39:    def generate_text(self, prompt: str, **kwargs: Any) -> str:
43:    def generate_json(self, prompt: str, **kwargs: Any) -> dict | list:
```

> `Segment` / `ModelSpecificTTSInstruction` / `CriticResult` 在 `data_models.py` line 38 / 397 / 455 已定义。`BaseLLMClient` 在 `llm/base.py` line 22 已定义，含 `generate_text`（line 39）+ `generate_json`（line 43）抽象方法。`_FakeLLMClient` 实现这两个方法（line 58 raise NotImplementedError / line 61 mock 返回）符合 `BaseLLMClient` 接口契约。

### 4.6 `src_next/critic/prompts/` 目录已存在（前置依赖验证）

```
$ ls src_next/critic/prompts/
__init__.py
__pycache__
critic_prompt.py
```

> `prompts/` 目录已存在（含 `__init__.py` + `critic_prompt.py`），但**不含 `repair_prompt.py`**（Task 11 才创建）。这是 plan §Task 10 Step 4 字面期望的预期状态。

### 4.7 文件落盘汇总

| 文件 | 操作 | 行数 | Task 10 commit |
|---|---|---|---|
| `src_next/critic/tests/test_tts_repair.py` | 新建 | 76 | 含（feat commit） |
| `src_next/critic/tts_repair.py` | 新建 | 20 | 含（feat commit） |
| `docs/critic_task10_coding.md` | 新建 | 本文件 | 含（feat commit） |
| **合计** | — | **96 + 本 dev doc** | — |

> 本 task 严格"只创建 2 个新文件 + 1 dev doc"，**0 行修改既有文件**（与 plan §Task 10 Files 表 "Create: src_next/critic/tests/test_tts_repair.py" + "Create: src_next/critic/tts_repair.py" 完全一致，未越界动 `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` / `prompts/critic_prompt.py` 等既有文件）。

---

## 5. 提交策略

### 5.1 本 task commit 范围

按用户 task 指令（"收尾 commit"章节明确列出 3 个文件路径，合并 1 commit 模式，与 Task 5 / 6 / 7 / 8 / 9 一致）：

```bash
git add src_next/critic/tests/test_tts_repair.py
git add src_next/critic/tts_repair.py
git add docs/critic_task10_coding.md
git commit -m "feat(critic): implement task 10 (round 1)"
```

> **commit 类型为 `feat(critic):`**——Task 10 起回到业务代码 commit（`tts_repair.py` 是 TTSRepairAgent 业务模块的最小骨架，不是测试代码），延续 Task 5 / 6 的 `feat(critic):` 前缀。Task 7 / 8 / 9 是 `test(critic):` 因为只动测试文件，本 task 同时动业务模块 + 测试文件，主类型是 `feat`。
> **commit message 使用用户 task 指令字面量** `feat(critic): implement task 10 (round 1)`——与 Task 5 / 6 同模板（`feat(critic): implement task N (round 1)`）。

**严禁 `git add -A` / `git add .`**——工作区有大量无关 untracked（`output*/` / `output-src-next*/` / `docs/intern_b_*.md` / `docs/superpowers/specs/2026-07-*.md` / `webui_old.py` / `input.rar` / `src_next/profiles/server_qwen_voicegenerator.yaml` / `docs/critic_task8_judging.md` / `docs/critic_task9_judging.md`），全部不带进本 commit。

### 5.2 与 Task 5 / 6 / 7 / 8 / 9 提交模式对比

| Task | 代码 commit | dev doc commit | 模式 | commit 类型 |
|---|---|---|---|---|
| Task 5 | `48ffea0` `feat(critic): implement task 5 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 6 | `732e81b` `feat(critic): implement task 6 (round 1)` | （合并到代码 commit） | 合并 1 commit | `feat` |
| Task 7 | `0e74e9b` `test(critic): add conftest with real_critic + audio path + real_llm fixtures` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 8 | `1d655b4` `test(critic): add 4 robustness tests for HTTP failure modes` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 9 | `72e3d4b` `test(critic): add 4 integration test skeletons (task 9, round 1)` | （合并到代码 commit） | 合并 1 commit | `test` |
| Task 10 | （本 task）`feat(critic): implement task 10 (round 1)` | （合并到代码 commit） | 合并 1 commit | **`feat`** |

> Task 10 回到 `feat(critic):` 模式（与 Task 5 / 6 一致），因为本 task 同时创建业务代码（`tts_repair.py`）+ 测试代码（`test_tts_repair.py`），主交付物是业务模块。后续 Task 11（TTSRepairAgent 完整实现）继续 `feat(critic):`。

### 5.3 不 push

按用户 task 指令：commit 后**不 push**（push 由主 session 在 PASS 后用 push-with-output-ignore skill 处理）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| test 代码块与 plan 字面量一致性 | 逐字一致 | md5 比对 `BYTE-EQUAL`（`959c4e4a44869fffe6bbef0bd8269ce9`，76 行对 76 行） | 无 | — |
| tts_repair 代码块与 plan 字面量一致性 | 逐字一致 | md5 比对 `BYTE-EQUAL`（`48201635b99ecc58c12e782c59495297`，20 行对 20 行） | 无 | — |
| Step 2 错误类型 | plan 字面 `ImportError: cannot import name 'TTSRepairAgent'` | 实测 `ModuleNotFoundError: No module named 'src_next.critic.tts_repair'` | 类型名差异 | **不处理**——`ModuleNotFoundError` 是 `ImportError` 子类（Python 3.6+），语义等价。差异根源：plan 假设 `tts_repair.py` 已存在但 `TTSRepairAgent` 类不存在（`ImportError: cannot import name 'X'`），实际 `tts_repair.py` 文件本身不存在（`ModuleNotFoundError: No module named 'X'`）。Step 2 是 RED 阶段，目的就是确认测试在没有业务代码时 FAIL — 两种错误类型都达到该目的。 |
| Step 4 终态 | plan 字面 FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'` | 完全匹配 | 无 | — |
| **Acceptance A.2 vs Step 4 矛盾** | A.2 说 "1 passed"；Step 4 说 FAIL | 实测 FAIL（与 Step 4 一致） | A 表 A.2 项不绿 | **不处理（plan 内部矛盾）**——详见 §6.3 给 judge 的判定提示。本 task coding-Agent 严格按用户 task 指令"不要为了 acceptance A 跑 pytest 通过而偷偷创建 repair_prompt.py"执行，让 A.2 自然 FAIL，留给 judge-Agent / 人工判定。 |
| docstring 「schema-frozen」英文表达 | plan Acceptance B 第 5 条字面 "schema-frozen" | plan Step 3 字面量用「schema 层冻结」中文 | 字面差异 | **不处理**——plan Step 3 字面量本身就是中文「schema 层冻结」（md5 BYTE-EQUAL），coding-Agent 不翻译。语义等价。判定细节见 §6.3。 |
| commit message 与 plan 字面量 | plan §Task 10 未给 commit 字面量（Step 1-4 没列 commit 命令） | 用户 task 指令字面 `feat(critic): implement task 10 (round 1)` | 无 | **本 task 按用户指令字面**——延续 Task 5 / 6 模板（`feat(critic): implement task N (round 1)`）。 |

**无结构性偏离。** 两个代码文件与 plan 字面量 md5 比对 BYTE-EQUAL，0 行重排序、0 字符差异、0 import 改写、0 类型注解添加。唯一实质偏离是 Acceptance A.2 的"1 passed"期望与 Step 4 的"FAIL with ModuleNotFoundError"期望互斥（plan 内部矛盾），本 task 按 Step 4 + 用户 task 指令字面执行。

### 6.2 给 Task 11 的提醒

- **Task 11 范围（plan §Task 11 line 1596 起）：**
  - 创建 `src_next/critic/prompts/repair_prompt.py`（Step 3）
  - 修改 `src_next/critic/tts_repair.py` 添加 `repair()` 方法（Step 4）
  - 修改 `src_next/critic/tests/test_tts_repair.py` 追加 7 个行为测试（Step 1）
- **Task 11 完成后，本 task 的 acceptance A.2 会自然变 PASS**（因为 `repair_prompt.py` 创建后，`tts_repair.py` 的 import 链不再 FAIL）。
- **`_FakeLLMClient` 与 `_make_inputs` helper 在 Task 11 复用**：Task 11 Step 1 的 7 个测试全部通过 `_make_inputs(parameters=..., scores=...)` 构造输入，`_FakeLLMClient(returned_json=..., raise_exc=...)` 构造 mock LLM。这两个 helper 的字段（`captured_prompt` / `returned_json` / `raise_exc`）已为本 task 字面量给 Task 11 准备就绪。
- **`test_repair_agent_constructs_with_llm_client` 在 Task 11 完成后应仍 PASS**：本 task 这个测试只测构造（不调 `repair()`），Task 11 添加 `repair()` 不影响构造逻辑。

### 6.3 给 judge-Agent 的提示

- **判定核心（重要）：** 本 task 的 Acceptance A.2 (`pytest ... -v` → "1 passed") 与 Step 4 (`expect ModuleNotFoundError ... Proceed.`) **plan 内部矛盾**。两种判定路径：
  - **路径 A（按 Acceptance A 字面）：** A.2 FAIL → 不达 PASS 条件 → 判 FAIL。
  - **路径 B（按 Step 4 字面 + TDD 链理解）：** Task 10 是 TDD 链的"为 Task 11 铺路"环节，intentional RED 是设计目的，B 表 5/5 全过 + 代码字面量 BYTE-EQUAL → 判 PASS（mock 阶段，TDD RED 状态）。
  - **建议：** 路径 B。理由：① plan Step 4 字面 "This is the next task's dependency. Proceed." 明示 intentional RED；② Task 11 Step 3 创建 `repair_prompt.py` 后 A.2 自然变 PASS，所以 A.2 FAIL 是临时状态；③ 本 task 代码与 plan 字面量 BYTE-EQUAL（md5 双双匹配），无实现 bug。
- **静态审查重点：** B 表 5 项全部应通过；用 md5 比对两个代码文件与 plan line 1455-1532（test）+ line 1542-1563（tts_repair）是最强证据（§4.3 A1 输出 BYTE-EQUAL + md5 `959c4e4a44869fffe6bbef0bd8269ce9` / `48201635b99ecc58c12e782c59495297`）。
- **越界检测：** 本 task 只创建 2 个新文件（`src_next/critic/tests/test_tts_repair.py` + `src_next/critic/tts_repair.py`）+ 1 dev doc，**不应**：
  - 创建 `src_next/critic/prompts/repair_prompt.py`（Task 11 范围）
  - 修改 `qwen3omni_critic.py` / `conftest.py` / `pytest.ini` / `prompts/critic_prompt.py` 等既有文件
  - 添加 `TTSRepairAgent.repair()` 方法（Task 11 Step 4 范围）
  - `git status` 应只显示 2 个 untracked 新文件 + dev doc，无既有文件 modified。
- **commit 类型检测：** 本 task commit message 是 `feat(critic): ...`（业务代码 commit），不是 `test(critic): ...`——因为同时创建业务模块 `tts_repair.py` + 测试文件，主交付物是业务模块（延续 Task 5 / 6 模式）。
- **docstring「schema-frozen」字面 grep 提示：** plan Acceptance B 第 5 条字面"schema-frozen"是英文，plan Step 3 字面量本身用中文「schema 层冻结」+「schema 层硬约束」。若 judge-Agent 严格按英文 grep `schema-frozen` 会 0 命中，但按中文 grep `schema` 会命中 line 4 + 6 + 7（3 处），按 `parameters merge` grep 会命中 line 6。**语义等价，建议判 PASS**（coding-Agent 严格按 Step 3 字面量粘贴，未做翻译，md5 BYTE-EQUAL）。
- **mock test 状态：** 本 task 完成时 `1 failed in 0.04s`（intentional RED，详见 §4.2 + §6.1 偏离登记）。Task 11 完成后会变 `8 passed`（1 construction + 7 行为测试，详见 plan §Task 11 Step 2 字面期望 "1 PASS (construction) + 7 FAIL" 是 Task 11 RED 阶段；Task 11 GREEN 阶段后全 PASS）。
- **integration test 状态：** 本 task 不涉及 integration 测试（`test_tts_repair.py` 顶部 docstring 说"Integration test ... skip-marked"，但 Task 10 字面量本身没有 integration 测试 — 是 Task 11+ 才会加 integration 测试骨架）。

---

## 7. 一句话总结

Task 10 = TDD 链的"为 Task 11 铺路"环节：创建 `src_next/critic/tests/test_tts_repair.py`（76 行，含 `_make_inputs` helper + `_FakeLLMClient` mock + 唯一 construction 测试，与 plan line 1455-1532 代码块 md5 BYTE-EQUAL `959c4e4a44869fffe6bbef0bd8269ce9`）+ `src_next/critic/tts_repair.py`（20 行最小骨架，含 `TTSRepairAgent` 类 + `__init__` 存 `self.llm`，与 plan line 1542-1563 代码块 md5 BYTE-EQUAL `48201635b99ecc58c12e782c59495297`）。Step 4 终态为 intentional RED：`pytest` FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`（出错位置 `tts_repair.py:12`），与 plan §Task 10 Step 4 字面期望完全匹配。Acceptance A.2（"1 passed"）与 Step 4（FAIL）是 plan 内部矛盾，coding-Agent 严格按用户 task 指令"不创建 repair_prompt.py 越界"执行，0 行修改既有文件，0 字符偏离 plan 字面量。commit 类型为 `feat(critic):`（业务模块），commit message 按用户 task 指令字面量 `feat(critic): implement task 10 (round 1)`。建议 **PASS（mock 阶段，TDD 链 RED 状态）**。
