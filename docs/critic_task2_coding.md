# Critic Task 2 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 2
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md` §3.2 Simplified
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-02
> **Task 类型:** 目录脚手架（Simplified acceptance）

---

## 1. Task 范围

按 plan Task 2 要求，搭建 `src_next/critic/` 包骨架 + 项目根 `pytest.ini`，为后续 Critic / Repair 模块（Task 5/6/8/9/11/12）准备目录与测试基建。

### 1.1 应交付文件（4 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 新增 | `src_next/critic/__init__.py` | 包初始化 docstring |
| 新增 | `src_next/critic/prompts/__init__.py` | 子包 docstring |
| 新增 | `src_next/critic/tests/__init__.py` | 子包 docstring |
| 新增 | `pytest.ini` | 项目根 pytest 配置（含 `integration` marker） |

### 1.2 不交付（属于后续 task）

- 任何 `qwen3omni_critic.py` / `tts_repair.py` / `*_prompt.py` / `test_*.py` 代码
- KNOWN_ISSUES.md（Task 3）
- 任何 conftest.py（Task 7）

### 1.3 前置条件（Task 1 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| `src_next/core/data_models.py` 存在 | ✓ | ✓ |
| `src_next/llm/base.py` 存在 | ✓ | ✓ |
| `from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment` | `imports OK` | ✓ |
| `pytest --version` | `pytest 9.0.3` | ✓（plan 写 7.x+，本机 9.0.3 也满足） |
| `requests.__version__` | `2.33.1` | ✓ |

> **注：** plan §Task 1 Step 6 期望 `pytest 7.x`，本机为 `9.0.3`。plan 文字为「7.x or higher」，9.0.3 满足更高版本要求，无兼容性问题（本次仅用 `pytest.ini` 基础配置 + marker，未用任何 8.x/9.x 新特性）。

---

## 2. 执行步骤（按 plan Task 2 Step 1 → 4）

### Step 1: 创建包目录

**命令：**
```bash
mkdir -p src_next/critic/prompts src_next/critic/tests
```

**实测：**
```
$ ls -la src_next/critic/
drwxr-xr-x prompts
drwxr-xr-x tests
```

### Step 2: 创建 3 个 `__init__.py`

按 plan 原文字面量创建（docstring 文字保持一致，便于 judge-Agent 静态匹配）：

**`src_next/critic/__init__.py`：**
```python
"""src_next.critic — Qwen3-Omni 音频评估 + LLM 修复子链路（实习生 B 方向3）。"""
```

**`src_next/critic/prompts/__init__.py`：**
```python
"""src_next.critic.prompts — Critic 评分与 Repair 修复的 prompt 模板。"""
```

**`src_next/critic/tests/__init__.py`：**
```python
"""src_next.critic.tests — Critic + Repair 单元测试。"""
```

### Step 3: 创建 `pytest.ini`（项目根）

**`pytest.ini`：**
```ini
[pytest]
markers =
    integration: marks tests that hit real external services (Qwen3-Omni, real LLM). Slow — deselect with -m "not integration".
testpaths = src_next
python_files = test_*.py
addopts = -ra
```

**字段说明（给 judge-Agent 静态审查）：**
- `markers =` 声明 `integration` marker — Task 9 / 12 产出的 skip-marked integration 测试需要它
- `testpaths = src_next` — 让 pytest 自动发现 `src_next/` 下的测试，不会误触 `src/`（旧链路冻结）
- `python_files = test_*.py` — 标准命名
- `addopts = -ra` — 显示所有 skip/expected failure 原因，便于 judge 排查

### Step 4: 验证 pytest 空发现（不写测试，只是 sanity check）

**命令：**
```bash
python -m pytest src_next/critic/tests/ -v
```

**实测输出：**
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 0 items

============================ no tests ran in 0.02s ============================

Exit code 5
```

**判定：** plan 期望 `no tests ran in 0.0Xs`，实测 `0.02s` —— 匹配 ✓。
Exit code 5 = pytest「no tests collected」标准退出码，对空目录是预期行为。

**额外观察：** `configfile: pytest.ini` 说明 pytest 已正确加载新配置（rootdir 下找到了 `pytest.ini`）。这避免了未来 Task 4/5 写测试后因配置缺失导致的 marker 未注册警告（`PytestUnknownMarkWarning`）。

### Step 5: 提交（**待用户确认**，见 §5）

按用户偏好 `feedback_commit_control.md`：「不要默认提交，问清楚再 commit」。本次完成 §3 验收后**先暂停**，向用户确认提交策略再执行。

**plan Step 4 建议命令（待执行）：**
```bash
git add src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py pytest.ini
git commit -m "chore(critic): scaffold critic package + pytest config"
```

---

## 3. Acceptance Criteria 自检（Section A + B）

按 spec §3.2 Simplified 结构对照。

### A. coding-Agent Self-check

| 命令 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `ls src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py pytest.ini` | 4 个路径都存在 | 4 个路径都列出 | ✓ |
| `python -m pytest src_next/critic/tests/ -v` | `no tests ran in 0.0Xs` | `no tests ran in 0.02s` | ✓ |

### B. judge-Agent 抽查点（预登记，待 judge 确认）

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| `pytest.ini` 含 `markers =` 和 `integration:` 定义 | §2 Step 3 内容 + §4 文件落盘 | ✓ |
| `src_next/critic/__init__.py` 不是空文件（含 docstring） | `cat` 输出 docstring 一行 | ✓ |
| `git log --oneline -3` 含 `chore(critic): scaffold critic package + pytest config` | **待提交后验证** | ⏳ |

### C. Pass 条件

- A 全绿 ✓
- B 抽查 2/3 已验证，1/3 待 commit 后验证
- 无 red flag

**判定：** 提交完成且 `git log` 验证通过后 → **PASS**。

---

## 4. 文件落盘证据

### 4.1 目录结构（新增部分加 `★`）

```
short_audiobook_agent/
├── pytest.ini                                    ★ 新增
└── src_next/
    └── critic/                                   ★ 新增包
        ├── __init__.py                           ★ 新增（docstring）
        ├── prompts/
        │   └── __init__.py                       ★ 新增（docstring）
        └── tests/
            └── __init__.py                       ★ 新增（docstring）
```

### 4.2 文件内容 hash（供 judge 比对）

```
$ ls -la pytest.ini src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py
-rw-r--r-- pytest.ini
-rw-r--r-- src_next/critic/__init__.py
-rw-r--r-- src_next/critic/prompts/__init__.py
-rw-r--r-- src_next/critic/tests/__init__.py
```

文件均非空，内容见 §2。

---

## 5. 提交策略（待用户决策）

### 5.1 plan 默认提交

plan Task 2 Step 4 给出的范围仅 4 个 scaffolding 文件（不含本开发文档）。

### 5.2 本开发文档 (`docs/critic_task2_coding.md`) 的归属

这是用户在 task 指令里**额外要求**的产物（"你需要生成一份开发文档，以 critic_task2_coding.md 命名"），plan 未覆盖。

**选项：**
- **A.** 跟随 scaffolding 一起进同一个 commit（一次性把 task 2 全部产物入库，但 commit 范围超出 plan）
- **B.** 单独 commit（`docs(critic): add task 2 coding dev doc`），保持 scaffolding commit 与 plan 一致
- **C.** 暂不 commit，留在工作区给 judge-Agent 审完再说

**Coding-Agent 推荐：** B（单独 commit）—— 保持 plan 描述的 commit 与代码一致，便于 judge-Agent 用 `git log` 精确匹配 plan 步骤。

### 5.3 其他 untracked 文件

`git status` 还显示 `docs/intern_b_*.md`、`output*/`、`webui_old.py`、`input.rar` 等既有 untracked 文件。**这些与 Task 2 无关，本次 commit 一律不带入**（plan Step 4 的 `git add` 也只显式列了 4 个文件）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| pytest 版本 | 7.x+ | 9.0.3 | 无（未用 8/9 新特性） | 接受 |
| Python 版本 | 3.10+（plan §Tech Stack） | 3.12.10 | 无 | 接受 |

### 6.2 给后续 task 的提醒

- **Task 3** 写 `KNOWN_ISSUES.md` 时记得引用本 task 创建的 `pytest.ini` marker 定义（解释为何 `@pytest.mark.integration` 不会触发 `PytestUnknownMarkWarning`）。
- **Task 4-12** 写测试时直接放进 `src_next/critic/tests/test_*.py`，pytest 会自动发现（`testpaths = src_next`）。
- **Task 9 / 12** integration 测试用 `@pytest.mark.integration` + `@pytest.mark.skip(reason=...)` 双标记。

### 6.3 给 judge-Agent 的提示

- 静态审查时请优先看 4 个文件的**字面量**是否与 plan Task 2 Step 1-3 一致（docstring 文字、ini 字段）。
- 如果发现 docstring 里多了「实习生 B 方向3」之外的额外修饰，那是偏离 — 本 task 不应有任何超出 plan 的内容。
- `pytest.ini` 不应有 `filterwarnings` / `markers` 之外的额外字段（plan 没要求）。

---

## 7. 一句话总结

Task 2 = 4 个空骨架文件 + 1 行 commit。代码层面零业务逻辑，纯脚手架。Acceptance Section A 全绿，Section B 静态审查点已就绪，唯一待办是 commit（待用户确认提交策略）。
