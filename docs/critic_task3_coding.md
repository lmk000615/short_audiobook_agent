# Critic Task 3 — Coding-Agent 开发文档

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` Task 3
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md` §3.3 Simplified
> **分支:** `feature/critic-and-tta`
> **日期:** 2026-07-02
> **Task 类型:** 文档型（Simplified acceptance，无代码）

---

## 1. Task 范围

按 plan Task 3 要求，在 `src_next/critic/` 下创建 `KNOWN_ISSUES.md`，把实施期间的三个已知风险显式落盘，便于未来服务可访问后快速恢复 integration 测试 + 切换 API 端点。

> Plan 原文 ⚠️ 备注：本 task **替代原 4-day plan 的 Task 3（smoke test）**。原因：实习生本机访问不到 Qwen3-Omni / 本地 LLM 服务，无法实际 exercise API，故用文档记录已知风险，给未来 debug 留路标。

### 1.1 应交付文件（1 个）

| 操作 | 路径 | 内容 |
|---|---|---|
| 新增 | `src_next/critic/KNOWN_ISSUES.md` | 三章节 Markdown：integration skip / API 端点不确定性 / fixture 未准备 |

### 1.2 不交付（属于后续 task）

- `qwen3omni_critic.py`（Task 4-6）
- `conftest.py`（Task 7）
- 任何 `test_*.py`（Task 5/8/9）
- `tts_repair.py`（Task 10-12）
- 任何 prompt 模块（Task 6/11）

### 1.3 前置条件（Task 1 + Task 2 已完成 — 自验证通过）

| 检查 | 实测 | 状态 |
|---|---|---|
| 当前分支 | `feature/critic-and-tta` | ✓ |
| `src_next/critic/` 目录存在（Task 2 产物） | ✓ | ✓ |
| `src_next/critic/__init__.py` 存在 | ✓ | ✓ |
| `pytest.ini` 含 `integration` marker（Task 2 产物） | ✓ | ✓ |
| `src_next/critic/KNOWN_ISSUES.md` 此前不存在 | ✓（首次创建） | ✓ |

---

## 2. 执行步骤（按 plan Task 3 Step 1 → 2）

### Step 1: 创建 KNOWN_ISSUES.md

**字面量来源：** plan §Task 3 Step 1 给出了完整 Markdown 内容，**逐字复制**（含中文标点、emoji ⚠️、`@pytest.mark.skip(reason="awaiting"` 的精确字符串）—— judge-Agent 静态审查会做字面匹配，不能改写。

**文件路径：** `src_next/critic/KNOWN_ISSUES.md`

**三章节结构（给 judge-Agent 抽查用）：**

| § | 标题 | 关键证据 |
|---|---|---|
| §1 | Integration 测试全部 skip（待服务可访问） | 启用步骤 + `@pytest.mark.skip(reason="awaiting"` 搜索串 + `CRITIC_FIXTURES_ROOT` / `CRITIC_TEST_LLM_PROFILE` 环境变量 + 5 个待启用测试名 |
| §2 | API 端点不确定性：`audio_analysis` 是否接受 `text` 字段 | (a)/(b)/(c) 三种服务响应场景 + `audio_analysis → chat` 的 fallback 代码块（两个 payload diff）|
| §3 | 测试音频 fixture 未实际准备 | 3 段 5-10s wav 生成方法 + `CRITIC_FIXTURES_ROOT` 环境变量 + `conftest.py::_audio_path` 引用 |

### Step 2: 提交（**待用户确认**，见 §5）

按用户偏好 `feedback_commit_control.md`：「不要默认提交，问清楚再 commit」。本次完成 §3 验收后**先暂停**，向用户确认提交策略再执行。

**plan Step 2 建议命令（待执行）：**
```bash
git add src_next/critic/KNOWN_ISSUES.md
git commit -m "docs(critic): document API risk + integration test gap"
```

---

## 3. Acceptance Criteria 自检（Section A + B）

按 plan §Task 3 Acceptance Criteria Simplified 结构对照。

### A. coding-Agent Self-check

| 命令 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `test -f src_next/critic/KNOWN_ISSUES.md && echo OK` | `OK` | `FILE_EXISTS_OK` | ✓ |
| `grep -c "^## " src_next/critic/KNOWN_ISSUES.md` | `3` | `3` | ✓ |

**章节标题实测：**
```
## 1. Integration 测试全部 skip（待服务可访问）
## 2. API 端点不确定性：`audio_analysis` 是否接受 `text` 字段
## 3. 测试音频 fixture 未实际准备
```

### B. judge-Agent 抽查点（预登记，待 judge 确认）

| 抽查点 | 实测证据 | 状态 |
|---|---|---|
| §1 含启用步骤说明（搜索 `@pytest.mark.skip(reason="awaiting"`，提供 `CRITIC_FIXTURES_ROOT` / `CRITIC_TEST_LLM_PROFILE` 环境变量） | 见 §4.2 grep 输出 B1 行 15-17 | ✓ |
| §2 含 fallback 代码块（明确指出 `audio_analysis` → `chat` 的两行改动 + URL 切换） | 见 §4.2 grep 输出 B2 行 40 / 43 / 51 | ✓ |
| §3 含 fixture 准备方法（生成 3 段 5-10s wav，放到 fixture 路径） | 见 §4.2 grep 输出 B3 行 70-72 | ✓ |
| `git log --oneline -3` 含 `docs(critic): document API risk + integration test gap` | **待提交后验证** | ⏳ |

### C. Pass 条件

- A 全绿 ✓
- B 抽查 3/4 已验证，1/4 待 commit 后验证
- 无 red flag

**判定：** 提交完成且 `git log` 验证通过后 → **PASS**。

---

## 4. 文件落盘证据

### 4.1 目录结构（新增部分加 `★`）

```
short_audiobook_agent/
└── src_next/
    └── critic/
        ├── __init__.py                           （Task 2）
        ├── prompts/                              （Task 2）
        ├── tests/                                （Task 2）
        └── KNOWN_ISSUES.md                       ★ 新增（本 task）
```

### 4.2 关键字面量 grep 输出（给 judge-Agent 比对）

**B1：§1 启用步骤证据**
```
15:1. 全局搜索 `@pytest.mark.skip(reason="awaiting"`，全部删除
16:2. 准备 3 段测试音频放服务器可读路径，设置 `CRITIC_FIXTURES_ROOT` 环境变量
17:3. 准备 LLM profile yaml，设置 `CRITIC_TEST_LLM_PROFILE` 环境变量
```

**B2：§2 fallback 代码块证据**
```
33:- (b) 忽略 `text` 字段，只按 `task=sound_analysis` 返回通用描述 → critic 拿不到评分 JSON，会触发 neutral 0.5 fallback
40:url = f"{self.base_url}/v1/omni/audio_analysis"
43:    "task": "sound_analysis",
51:url = f"{self.base_url}/v1/omni/chat"
61:`/v1/omni/chat` 文档（ussage_guide 第 3 节）明确支持 `audio + text + return_audio`...
```

**B3：§3 fixture 准备方法证据**
```
65:**状态：** `conftest.py` 里的 `good_narration_wav` 等 fixture 只解析路径，不验证文件存在。
70:1. 用现有 TTS pipeline 生成 3 段 5-10s wav（好/坏/情感不匹配）
71:2. 放到服务器可读路径，或设置 `CRITIC_FIXTURES_ROOT` 环境变量
72:3. 路径解析逻辑见 `conftest.py::_audio_path`
```

---

## 5. 提交策略（待用户决策）

### 5.1 plan 默认提交

plan Task 3 Step 2 给出的范围仅 `src_next/critic/KNOWN_ISSUES.md` 一个文件（不含本开发文档）。

### 5.2 本开发文档 (`docs/critic_task3_coding.md`) 的归属

这是用户在 task 指令里**额外要求**的产物（"你需要生成一份开发文档，以 critic_task3_coding.md 命名"），plan 未覆盖。

**选项：**
- **A.** 跟随 KNOWN_ISSUES.md 一起进同一个 commit（一次性把 task 3 全部产物入库，但 commit 范围超出 plan）
- **B.** 单独 commit（`docs(critic): add task 3 coding dev doc`），保持 KNOWN_ISSUES.md commit 与 plan 一致
- **C.** 暂不 commit，留在工作区给 judge-Agent 审完再说

**Coding-Agent 推荐：** B（单独 commit）—— 与 Task 2 先例一致（commit `a50b3a3 docs(critic): add task 2 coding dev doc`），保持 plan 描述的 commit 与代码一致，便于 judge-Agent 用 `git log` 精确匹配 plan 步骤。

### 5.3 其他 untracked 文件

`git status` 还显示 `docs/intern_b_*.md`、`output*/`、`webui_old.py`、`input.rar` 等既有 untracked 文件。**这些与 Task 3 无关，本次 commit 一律不带入**（plan Step 2 的 `git add` 也只显式列了一个文件）。

---

## 6. 风险 / 偏离 / 后续提醒

### 6.1 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| 章节顺序 | §1 integration / §2 API / §3 fixture | 同 | 无 | — |
| fallback 代码块字面量 | plan 给出原文字面量 | 逐字复制 | 无 | — |
| 文件位置 | `src_next/critic/KNOWN_ISSUES.md` | 同 | 无 | — |

无任何偏离。

### 6.2 给后续 task 的提醒

- **Task 4-5**（critic 单测）：写 `@pytest.mark.integration` + `@pytest.mark.skip(reason="awaiting ...")` 时，reason 字符串务必以 `awaiting` 开头，与本 doc §1 记录的搜索串一致 —— 未来一键启用只需要 grep 这个串。
- **Task 6**（critic_prompt + 实现）：实现 `_evaluate_inner` 时，URL 必须用 `/v1/omni/audio_analysis`，与本 doc §2 记录的 fallback 起点 URL 一致 —— 否则 fallback 路径无效。
- **Task 7**（conftest）：fixture 路径解析函数必须命名为 `_audio_path`（与 §3 引用一致），且 `good_narration_wav` 这个 fixture 名字不能改（§3 已固化）。
- **Task 9 / 12**（integration skeleton）：测试函数名必须与本 doc §1 列出的 5 个测试名**逐字一致**（包括 `test_critic_high_quality_audio_scores_high` 等），否则 grep 不到。

### 6.3 给 judge-Agent 的提示

- 静态审查时请优先看三章节的**字面量**是否与 plan Task 3 Step 1 一致（章节顺序、emoji、payload 字段名）。
- §2 的 fallback 代码块必须**同时**包含 `audio_analysis` 和 `chat` 两个 URL 字面量 —— 缺任一都说明 fallback 路径记录不完整。
- §1 列出的 5 个待启用测试名，要和后续 Task 9 / 12 实际写的测试函数名**逐字匹配**。如果未来 task 改了测试名，**必须回来更新本 doc**。
- 不要期待本 doc 有任何代码逻辑 —— 它纯粹是知识沉淀文档。

---

## 7. 一句话总结

Task 3 = 1 个文档 + 1 行 commit。代码层面零业务逻辑，纯风险登记。Acceptance Section A 全绿，Section B 静态审查 3/4 已就绪，唯一待办是 commit（待用户确认提交策略）。
