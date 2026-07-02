# Critic Task 4 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 4
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 4 无独立章节，沿用 plan §Task 4 Acceptance Simplified）
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-02
> **Task 类型:** 代码型（Simplified acceptance，TDD 一次写 + 一次跑通）

---

## 1. Task 范围

按 plan Task 4 要求，**用 TDD 一次红-绿循环**搭出 `Qwen3OmniCritic` 的构造骨架：先写一个失败的构造测试，再写最小实现让测试通过。`evaluate()` 方法**故意不写**，留给 Task 5。

> Plan 原文 Task 4 标题：**Write failing test for Qwen3OmniCritic construction**。这一步的目的是「先卡住接口形状」，让 Task 5 的 evaluate 测试可以直接 `from src_next.critic.qwen3omni_critic import Qwen3OmniCritic` 拿到类。

### 1.1 应交付文件（2 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 新增 | `src_next/critic/tests/test_qwen3omni_critic.py` | 1 个测试函数 `test_critic_can_be_constructed_with_defaults`，验证默认 `base_url / timeout / bypass_proxy` |
| 新增 | `src_next/critic/qwen3omni_critic.py` | 顶部 docstring（infer_lock + API 风险警告）+ `Qwen3OmniCritic.__init__`（3 个默认参数）。**不含 `evaluate()`** |

### 1.2 不交付（属于后续 task）

- `evaluate()` 方法（Task 5）
- `_evaluate_inner` / `_neutral_result` / `_parse_scoring_json` 私有方法（Task 5）
- `src_next/critic/prompts/critic_prompt.py`（Task 6）
- `conftest.py`（Task 7）
- 任何 integration / robustness 测试（Task 8/9）

### 1.3 前置条件（Task 1 + 2 + 3 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| Task 1-3 已 commit（`git log --oneline -5` 含 3 个 critic commit） | 见 §4.4 | ✓ |
| `src_next/critic/__init__.py` + `tests/__init__.py` 存在（Task 2 产物） | ✓ | ✓ |
| `src_next/critic/KNOWN_ISSUES.md` 存在（Task 3 产物） | ✓ | ✓ |
| `pytest.ini` 含 `integration` marker（Task 2 产物） | ✓ | ✓ |
| `src_next.core.data_models` 可 import `CriticResult / ModelSpecificTTSInstruction / Segment` | `OK`（见 §4.1） | ✓ |
| `src_next/critic/qwen3omni_critic.py` 此前不存在 | ✓（首次创建） | ✓ |

---

## 2. 执行步骤（按 plan Task 4 Step 1 → 5）

### Step 1: 写失败构造测试

**字面量来源：** plan §Task 4 Step 1 给出了完整 Python 代码块，**逐字复制**到 `src_next/critic/tests/test_qwen3omni_critic.py`，包含：
- 模块 docstring（说明 integration skip 状态）
- `from __future__ import annotations`
- `import pytest`（暂未使用，但保留以匹配 plan 字面量）
- `from src_next.core.data_models import ModelSpecificTTSInstruction, Segment`（暂未使用，但保留以匹配 plan 字面量 — 后续 task 会用）
- `test_critic_can_be_constructed_with_defaults()` 函数，3 条 assert

**文件路径：** `src_next/critic/tests/test_qwen3omni_critic.py`

### Step 2: 跑测试确认 FAIL

**Plan 预期：** `ImportError: cannot import name 'Qwen3OmniCritic' from 'src_next.critic.qwen3omni_critic'`

**实测：** `ModuleNotFoundError: No module named 'src_next.critic.qwen3omni_critic'`

> **偏离登记（轻微）：** Python 3.12 抛 `ModuleNotFoundError`（`ImportError` 的子类）而不是父类 `ImportError`。Plan 预期描述的是父类语义，子类同样满足「模块不存在」的判定条件，**不影响 RED → GREEN 红绿循环判定**。

### Step 3: 写最小实现

**字面量来源：** plan §Task 4 Step 3 给出了完整 Python 代码块，**逐字复制**到 `src_next/critic/qwen3omni_critic.py`：
- 顶部模块 docstring（5 行：endpoint + infer_lock 警告 + API 风险警告 + fallback 指针）
- `from __future__ import annotations`
- `from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment`（暂未使用，但保留以匹配 plan 字面量 — Task 5 会用）
- `class Qwen3OmniCritic:` 含 `__init__`（3 个默认参数）+ docstring

**严格不越界：** 不实现 `evaluate()` 方法（Task 5 边界），不引入 `requests` 依赖（Task 5 边界），不引入 prompt 模块（Task 6 边界）。

### Step 4: 跑测试确认 PASS

**Plan 预期：** `1 passed`

**实测：** `1 passed in 0.02s`

附 `python -m py_compile src_next/critic/qwen3omni_critic.py`（CLAUDE.md §10 验证清单第 1 条）→ 0 退出码。

### Step 5: 提交（**待用户确认**，见 §5）

按用户偏好 `feedback_commit_control.md`：「不要默认提交，问清楚再 commit」。本次完成 §3 验收后**先暂停**，向用户确认提交策略再执行。

**plan Step 5 建议命令（待执行）：**
```bash
git add src_next/critic/qwen3omni_critic.py src_next/critic/tests/test_qwen3omni_critic.py
git commit -m "feat(critic): add Qwen3OmniCritic skeleton with construction test"
```

---

## 3. Acceptance Criteria 自检（Section A + B）

按 plan §Task 4 Acceptance Criteria Simplified 结构对照。

### A. coding-Agent Self-check

| 命令 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `test -f src_next/critic/qwen3omni_critic.py && test -f src_next/critic/tests/test_qwen3omni_critic.py && echo OK` | `OK` | 两个文件均存在 | ✓ |
| `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v` | `1 passed` | `1 passed in 0.02s`（见 §4.2） | ✓ |

### B. judge-Agent 抽查点（预登记，待 judge 确认）

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| `__init__` 默认参数：`base_url="http://10.50.121.102:8011"`, `timeout=120`, `bypass_proxy=True` | §4.3 grep 行 22-24 | ✓ |
| 模块顶部 docstring 含「infer_lock」+「API 风险」两点警告（不为空） | §4.3 grep 行 6 + 行 9 | ✓ |
| **此时还没有 `evaluate()` 方法**（Task 5 才加） | §4.3 grep `def ` 输出仅 1 行：`def __init__`（行 20）| ✓（无越界提前实现）|
| `git log --oneline -5` 含 `feat(critic): add Qwen3OmniCritic skeleton with construction test` | **待提交后验证** | ⏳ |

### C. Pass 条件

- A 全绿 ✓
- B 抽查 3/4 已验证，1/4 待 commit 后验证
- 无 red flag

**判定：** 提交完成且 `git log` 验证通过后 → **PASS**。

---

## 4. 文件落盘证据

### 4.1 前置：data_models 可 import（Task 1 Pre-condition 验证）

```
$ python -c "from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment; print('OK')"
OK
```

### 4.2 Step 4 测试输出（GREEN 证据）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 1 item

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [100%]

============================== 1 passed in 0.02s ==============================
```

### 4.3 关键字面量 grep 输出（给 judge-Agent 比对）

**B1：默认参数 + 警告字面量**
```
6:⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
9:⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
22:        base_url: str = "http://10.50.121.102:8011",
23:        timeout: int = 120,
24:        bypass_proxy: bool = True,
```

**B2：方法清单（验证 Task 5 边界——只有 `__init__`，无 `evaluate`）**
```
20:    def __init__(
```
> 仅 1 个方法定义。如果出现 `def evaluate` / `def _evaluate_inner` / `def _neutral_result` 等，说明越界提前实现 Task 5 内容。

### 4.4 前置 commit 历史（验证 Task 1-3 已落盘）

```
$ git log --oneline -8
97f880b docs(critic): add task 3 coding dev doc
e288ba5 docs(critic): document API risk + integration test gap
a50b3a3 docs(critic): add task 2 coding dev doc
5cbcabf chore(critic): scaffold critic package + pytest config
6e0c502 docs(critic): add intern B critic+repair plan with per-task acceptance criteria
7e204e5 docs: 新增 CLAUDE.md + 重写 README.md 对齐 src_next 重构链路
da125ad feat: Audio-Oscar 改造启动 — 统一数据契约 + 实习生分工文档
a8052e8 docs: src_next 团队 wiki 两份文档 + 架构图
```
> 含 `chore(critic): scaffold critic package + pytest config`（Task 2）+ `docs(critic): document API risk + integration test gap`（Task 3），前置链已就位。

### 4.5 目录结构（新增部分加 `★`）

```
short_audiobook_agent/
└── src_next/
    └── critic/
        ├── __init__.py                           （Task 2）
        ├── KNOWN_ISSUES.md                       （Task 3）
        ├── prompts/                              （Task 2）
        ├── tests/
        │   ├── __init__.py                       （Task 2）
        │   └── test_qwen3omni_critic.py          ★ 新增（本 task）
        └── qwen3omni_critic.py                   ★ 新增（本 task）
```

---

## 5. 提交策略（待用户决策）

### 5.1 plan 默认提交

plan Task 4 Step 5 给出的范围 = 2 个文件（`qwen3omni_critic.py` + `tests/test_qwen3omni_critic.py`），不含本开发文档。

### 5.2 本开发文档 (`docs/critic_task4_coding.md`) 的归属

这是用户在 task 指令里**额外要求**的产物（"你需要生成一份开发文档，以 critic_task4_coding.md 命名"），plan 未覆盖。

**选项：**
- **A.** 跟随两个代码文件一起进同一个 commit（一次性把 task 4 全部产物入库，但 commit 范围超出 plan）
- **B.** 单独 commit（`docs(critic): add task 4 coding dev doc`），保持代码 commit 与 plan 一致，便于 judge-Agent 用 `git log` 精确匹配 plan 步骤
- **C.** 暂不 commit，留在工作区给 judge-Agent 审完再说

**Coding-Agent 推荐：** B（单独 commit）—— 与 Task 2 / Task 3 先例一致（commit `a50b3a3` / `97f880b`），保持 plan 描述的 commit 与代码一致，便于 judge-Agent 用 `git log` 精确匹配 plan 步骤。

### 5.3 其他 untracked 文件

`git status` 还显示 `docs/intern_b_*.md`、`output*/`、`webui_old.py`、`input.rar`、`docs/superpowers/specs/2026-07-01-push-with-output-ignore-skill-design.md`、`docs/superpowers/specs/2026-07-02-task-acceptance-judge-skill-design.md`、`docs/critic_task2_judging.md`、`docs/critic_task3_judging.md` 等既有 untracked 文件。**这些与 Task 4 无关，本次 commit 一律不带入**（plan Step 5 的 `git add` 也只显式列了 2 个文件）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| Step 2 异常类型 | `ImportError: cannot import name 'Qwen3OmniCritic'` | `ModuleNotFoundError: No module named 'src_next.critic.qwen3omni_critic'` | 无（`ModuleNotFoundError` 是 `ImportError` 子类，模块文件不存在时 Python 3.12 默认抛子类） | 文档记录，无需修复 |
| 文件路径 | `src_next/critic/qwen3omni_critic.py` + `tests/test_qwen3omni_critic.py` | 同 | 无 | — |
| 默认参数字面量 | `base_url="http://10.50.121.102:8011"`, `timeout=120`, `bypass_proxy=True` | 同（逐字复制） | 无 | — |
| docstring 字面量 | infer_lock + API 风险两点警告 | 同（逐字复制） | 无 | — |

无结构性偏离。

### 6.2 给后续 task 的提醒

- **Task 5**（evaluate happy path）：实现 `_evaluate_inner` 时 URL 必须用 `/v1/omni/audio_analysis`，与本 task 模块 docstring 第 4 行 + KNOWN_ISSUES.md §2 的 fallback 起点一致；导入 `from src_next.critic.prompts.critic_prompt import build_critic_prompt` 会触发 ImportError（plan Task 5 Step 4 预期），这是**故意留给 Task 6 的依赖**。
- **Task 6**（critic_prompt）：`build_critic_prompt(segment, tts_instruction) -> str` 函数签名要与 Task 5 调用一致；返回的 prompt 必须强制要求 Qwen3-Omni 输出严格 JSON（5 维评分 + suggestions）。
- **Task 7**（conftest）：`good_narration_wav` fixture 名字不能改（KNOWN_ISSUES.md §3 已固化）；路径解析函数必须命名为 `_audio_path`。
- **Task 8/9**（robustness + integration skeleton）：测试函数名必须与 KNOWN_ISSUES.md §1 列出的 5 个测试名**逐字一致**。

### 6.3 给 judge-Agent 的提示

- **静态审查重点：** 默认参数 3 个字面量 + 顶部 docstring 两条警告，必须与 plan §Task 4 Step 3 代码块**逐字一致**（不能改写黄区 IP / 端口 / timeout 数值）。
- **越界检测：** 用 `grep "^    def " src_next/critic/qwen3omni_critic.py` 检查方法清单，**只允许出现 `__init__`**。如果出现 `evaluate` / `_evaluate_inner` / `_neutral_result` 等，说明越界提前实现 Task 5。
- **import 检测：** 当前文件可以 import `requests` / `json` / `re` 等 Task 5 才需要的依赖吗？**答案：不能**——本 task 实现里只有 `from src_next.core.data_models import ...`，没有标准库 / 第三方 import。如果 judge 看到多余 import，说明越界。
- **测试数量：** 本 task 只 1 个测试（`test_critic_can_be_constructed_with_defaults`）。如果文件里还有其他 test 函数，说明越界提前写 Task 5/8/9 的测试。

---

## 7. 一句话总结

Task 4 = 1 个失败测试 + 1 个最小实现 + 1 行 commit。TDD 红绿循环一次走通（RED: `ModuleNotFoundError` → GREEN: `1 passed`），故意不写 `evaluate()`，把 Task 5 的接口边界卡死。Acceptance Section A 全绿，Section B 静态审查 3/4 已就绪，唯一待办是 commit（待用户确认提交策略）。
