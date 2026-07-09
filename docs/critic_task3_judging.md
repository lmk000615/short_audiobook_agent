# Critic Task 3 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` §Task 3 (Simplified)
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md` §3.3
> **Coding dev doc:** `docs/critic_task3_coding.md`
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-02
> **Task 类型:** 文档型（Simplified acceptance，零业务代码）

---

## 0. Verdict 一句话

**PASS（内容）/ PENDING（commit）** — KNOWN_ISSUES.md 三章节字面量与 plan §Task 3 Step 1 **逐字一致**；Section A 全绿；Section B 静态抽查 3/4 通过；唯一待办是 plan Step 2 的 commit（coding-agent 按 `feedback_commit_control.md` 显式暂停等用户决策，**非失误**）；无 red flag，无 scope creep。

---

## 1. 验收范围

按 plan §Task 3 (Simplified) 的 Acceptance Criteria 两档验收：

- **Section A — coding-Agent Self-check**：2 条命令（文件存在 + H2 章节数 = 3）
- **Section B — judge-Agent 抽查**：4 条（§1 启用步骤 / §2 fallback 代码块 / §3 fixture 方法 / git log commit）
- **额外审查**：字面量逐字比对 + commit 范围核对 + critic 子树边界 + 偏离登记 + red flag 排查

---

## 2. Section A — coding-Agent Self-check

| 项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| A1 `test -f src_next/critic/KNOWN_ISSUES.md && echo OK` | `OK` | `FILE_EXISTS_OK` | PASS |
| A2 `grep -c "^## " src_next/critic/KNOWN_ISSUES.md` | `3` | `3` | PASS |

实测 H2 章节标题原文：

```
## 1. Integration 测试全部 skip（待服务可访问）
## 2. API 端点不确定性：`audio_analysis` 是否接受 `text` 字段
## 3. 测试音频 fixture 未实际准备
```

章节顺序、编号、措辞均与 plan §Task 3 Step 1 字面量一致。

---

## 3. Section B — judge-Agent 抽查

| 抽查点 | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| B1 §1 含启用步骤（搜索串 + 两个环境变量） | 含 `@pytest.mark.skip(reason="awaiting"` + `CRITIC_FIXTURES_ROOT` + `CRITIC_TEST_LLM_PROFILE` | L15 / L16 / L17 三行逐字命中 | PASS |
| B2 §2 含 fallback 代码块（两行改动 + URL 切换） | 含 `audio_analysis` URL → `chat` URL 两个 payload diff | L40 `url = f"{self.base_url}/v1/omni/audio_analysis"` → L51 `url = f"{self.base_url}/v1/omni/chat"` + L41-47 / L52-57 两个完整 payload + L59 "只改两行（URL + payload）" | PASS |
| B3 §3 含 fixture 准备方法（3 段 5-10s wav + 路径） | 含具体生成方法 + 放置路径 | L70 "用现有 TTS pipeline 生成 3 段 5-10s wav（好/坏/情感不匹配）" + L71 fixture 路径 + L72 `conftest.py::_audio_path` 引用 | PASS |
| B4 `git log --oneline -3` 含指定 commit message | 含 `docs(critic): document API risk + integration test gap` | 最近 5 个 commit 无匹配；`git status` 显示 `?? src_next/critic/KNOWN_ISSUES.md`（untracked） | **PENDING** |

完整 git log -5（验收时刻）：

```
a50b3a3 docs(critic): add task 2 coding dev doc
5cbcabf chore(critic): scaffold critic package + pytest config
6e0c502 docs(critic): add intern B critic+repair plan with per-task acceptance criteria
7e204e5 docs: 新增 CLAUDE.md + 重写 README.md 对齐 src_next 重构链路
da125ad feat: Audio-Oscar 改造启动 — 统一数据契约 + 实习生分工文档
```

B4 未达成，但属显式暂停，详见 §5 偏离登记。

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 KNOWN_ISSUES.md 与 plan §Task 3 Step 1 逐字比对

| 章节 | 关键字面量 | plan 期望 | 实测 | 一致 |
|---|---|---|---|---|
| §1 | `@pytest.mark.skip(reason="awaiting"` | 必须精确匹配（grep 用） | L15 逐字命中 | YES |
| §1 | 5 个待启用测试名 | `test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high` 等 5 条 | L21-25 全部逐字命中 | YES |
| §2 | fallback 起点 URL | `f"{self.base_url}/v1/omni/audio_analysis"` | L40 同 | YES |
| §2 | fallback 终点 URL | `f"{self.base_url}/v1/omni/chat"` | L51 同 | YES |
| §2 | payload 字段顺序 | `audio / task / sound_analysis / text / return_audio / max_new_tokens` → `audio / text / return_audio / max_new_tokens` | L41-47 / L52-57 同 | YES |
| §3 | `good_narration_wav` fixture 名 | 不可改（后续 task 固化） | L65 同 | YES |
| §3 | `conftest.py::_audio_path` 引用 | 函数名不可改 | L72 同 | YES |

所有关键串字面量 100% 匹配，未做任何改写或"优化"。dev log §2 显式说明「逐字复制，judge-Agent 静态审查会做字面匹配，不能改写」—— 执行到位。

### 4.2 critic/ 子树边界守住

```
src_next/critic/
├── __init__.py                  （Task 2）
├── prompts/__init__.py          （Task 2）
├── tests/__init__.py            （Task 2）
└── KNOWN_ISSUES.md              ★ 本 task 新增
```

仅 1 个新文档落地。**无任何越界文件**：未提前实现 `qwen3omni_critic.py`（Task 4-6）/ `conftest.py`（Task 7）/ `test_*.py`（Task 5/8/9）/ `tts_repair.py`（Task 10-12）/ 任何 prompt 模块（Task 6/11）—— plan §1.2 边界严格守住。

### 4.3 commit 范围核对（plan Step 2 期望 vs 实测）

| 项 | plan Step 2 期望 | 实测 | 状态 |
|---|---|---|---|
| commit 文件清单 | 仅 `src_next/critic/KNOWN_ISSUES.md` | 文件已在磁盘但 **未 commit** | 待执行 |
| commit message | `docs(critic): document API risk + integration test gap` | — | 待执行 |
| 是否夹带 untracked | 不夹带（plan `git add` 显式单文件） | N/A | 待执行 |

`git status --short src_next/critic/` 输出 `?? src_next/critic/KNOWN_ISSUES.md`，工作区其它 untracked 文件（`docs/intern_b_*`、`output*/`、`input.rar`、`webui_old.py`、`docs/critic_task3_coding.md` 等）均与本 task 无关，**正确地未带入暂存区**（暂存区为空）。

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| commit 执行 | plan §Task 3 Step 2 期望 commit 已落地 | **未 commit**（KNOWN_ISSUES.md 仍 untracked） | B4 验收项暂无法达成 | **接受并等待用户决策** |

### 5.1 commit 暂停的合规性说明

coding-agent 在 dev log §5 显式登记此偏离，并给出 3 个提交策略选项：

- **A.** KNOWN_ISSUES.md + dev doc 一起 commit（commit 范围超出 plan）
- **B.** KNOWN_ISSUES.md 单独 commit，dev doc 走另一个 commit（与 Task 2 先例一致，coding-agent 自荐）
- **C.** 暂不入库，等 judge 审完

此暂停是 memory `feedback_commit_control.md`（「不要默认提交，问清楚再 commit，确认分支目标」）显式覆盖 plan 默认行为，**属用户指令优先级高于 plan 的合理偏离**，不是 coding-agent 失误。详见 [Instructions Priority](https://superpowers.md)：用户指令 > skills > 默认行为。

---

## 6. Red Flags 排查

| 排查项 | 结论 |
|---|---|
| 三章节内容与 plan 字面量不一致 | 无 |
| 章节顺序错乱（如 §1/§2/§3 互换） | 无 |
| §2 fallback 代码块缺 `audio_analysis` 或 `chat` 任一 URL | 无（两个 URL 都在） |
| §1 grep 搜索串被改写（如 `awaiting` 拼错） | 无 |
| §3 fixture 函数名 `_audio_path` 被改名 | 无 |
| critic 子树越界（含后续 task 文件） | 无 |
| KNOWN_ISSUES.md 出现计划外章节（如 §4、附录） | 无 |
| `--no-verify` / 跳过 hooks | 无 |
| 改动 `src/` 旧链路 | 无 |
| 改动 `requirements.txt` / 依赖版本 | 无 |

零 red flag。

---

## 7. Verdict JSON（按 judge-Agent 验收 schema）

```json
{
  "task_id": "Task 3 — Write KNOWN_ISSUES.md documenting API risk + service access gap",
  "verdict": "PASS (content) / PENDING (commit)",
  "mock_tests": {
    "ran": [
      "A1 test -f src_next/critic/KNOWN_ISSUES.md",
      "A2 grep -c '^## ' src_next/critic/KNOWN_ISSUES.md"
    ],
    "result": "2/2 green (FILE_EXISTS_OK + section count = 3)"
  },
  "integration_tests": "N/A (plan Task 3 纯文档，无 integration)",
  "smoke_tests": "N/A (Simplified 档无 smoke)",
  "static_review": {
    "literal_match_plan": true,
    "three_sections_present": true,
    "section1_enable_steps_complete": true,
    "section2_fallback_block_complete": true,
    "section3_fixture_method_complete": true,
    "critic_subtree_boundary_held": true,
    "commit_message_match": false,
    "commit_executed": false,
    "red_flags": []
  },
  "reason": "KNOWN_ISSUES.md 三章节（integration skip / API 端点 / fixture 未准备）字面量与 plan §Task 3 Step 1 逐字一致；§1 含搜索串 + 两个环境变量 + 5 个测试名；§2 含 audio_analysis→chat 完整 fallback payload diff；§3 含 3 段 5-10s wav 生成方法 + _audio_path 引用；critic 子树无越界文件；零 red flag。唯一未达成为 plan Step 2 commit，属 coding-agent 按 feedback_commit_control.md 显式暂停等待用户决策（A/B/C 三选项），非执行失误。",
  "blocking_issues": [
    {
      "item": "B4 commit 未执行",
      "severity": "blocker-for-B4-only",
      "remedy": "用户选定 commit 策略后，judge 补验 git log 出现目标 commit message 即关单"
    }
  ],
  "next_action": "请用户决策 commit 策略（推荐 B：KNOWN_ISSUES.md 单独 commit + dev doc 另起 commit，与 Task 2 先例一致）。Commit 落地后 judge 补验 git log -3 含 'docs(critic): document API risk + integration test gap' 即关 Task 3，进入 Task 4（Qwen3OmniCritic skeleton + 失败 construction 测试）。"
}
```

---

## 8. 给后续 task 的提醒（继承 dev log §6.2）

dev log 已为后续 task 沉淀 4 条强约束（理由：本 task 的 KNOWN_ISSUES.md 字面量已"固化"，后续代码必须与之一致否则 fallback/grep 路径失效）：

- **Task 4-5**（critic 单测）：`@pytest.mark.skip(reason="awaiting ...")` 的 reason 字符串**必须以 `awaiting` 开头** —— 否则 §1 L15 的 grep 串无法一键启用。
- **Task 6**（critic prompt + 实现）：`_evaluate_inner` 方法的 URL **必须用 `/v1/omni/audio_analysis`**（不是 `/v1/omni/chat`）—— §2 fallback 路径以它为起点，URL 反向不一致会让 fallback 文档失效。
- **Task 7**（conftest）：fixture 路径解析函数**必须命名为 `_audio_path`**，且 fixture **`good_narration_wav` 名字不可改** —— §3 已固化引用。
- **Task 9 / 12**（integration skeleton）：测试函数名必须与 §1 L21-25 列出的 5 个测试名**逐字一致**（如 `test_critic_high_quality_audio_scores_high`），否则 grep 不到，无法批量启用。

---

## 9. 一句话总结

文档字面量 100% 达标，commit 等 A/B/C 决策 —— 用户拍板后 1 行 `git add/commit` 即可关单。
