# Design: task-code-judge-loop skill

**Date:** 2026-07-02
**Author:** l30083418 + Claude
**Status:** Approved (pending spec review)

## 1. 背景

本项目用「coding-Agent + judge-Agent」双角色模式做 plan 验收（见 memory `project_judge_agent_acceptance_framework`），现有 `task-acceptance-judge` skill 已封装 judge 阶段。但每次跑一个 task 需要：

1. 手动 spawn coding 子 Agent，告诉它去按 plan §Task N 实施 + 写 dev doc
2. 等 coding 回来，再手动 spawn judge 子 Agent 调 task-acceptance-judge skill
3. 读 judging doc 看 verdict
4. 如果 FAIL / CONDITIONAL PASS，把 judging 反馈喂回 coding 子 Agent 让它修
5. 重复直到 PASS 或失去耐心

这个流程每次手跑容易出错（忘记传上轮 judging 反馈、忘记 commit 导致 git-log 检查永远过不了、parallel 误调等）。需要一个 skill 把整个 dev-loop 固化。

## 2. 目标与非目标

**目标**

- 用户说"做 task N 直到验收过"，skill 自动跑完 coding→judge→fix→judge loop
- 默认 3 轮上限（首次 coding + 最多 2 轮 fix），避免死循环
- 每轮自动 commit，让 plan §Task N 里的 git-log 检查能通过
- judge 阶段调用现有 `task-acceptance-judge` skill，不重复造轮子
- 项目内通用（自动发现 plan），但仅服务于本仓库（不到其他 repo 跑）
- PASS 后问用户是否 push，不擅自主张（遵守 memory `feedback_commit_control.md`）

**非目标**

- 不验收 spec doc（spec 是 brainstorming 产物，不是 task）
- 不替 plan 做 task 分解（plan 已经定义了 Task N）
- 不修改 plan / task-acceptance-judge skill（本 skill 只读这两个）
- 不做 integration 测试执行（依赖 judge skill 的能力）
- 不替换 superpowers 的 `subagent-driven-development` / `executing-plans`，而是项目特定的 dev+验收 loop

## 3. 安装位置

项目级：`F:/akoasm/short_audiobook_agent/.claude/skills/task-code-judge-loop/SKILL.md`

理由：依赖本项目三件套（`docs/superpowers/plans/` + `docs/<prefix>_task{N}_coding.md` + `task-acceptance-judge` skill），全局安装到 `~/.claude/skills/` 在其他项目会失效。与 `push-with-output-ignore` / `task-acceptance-judge` 同位置。

## 4. 命名 / 触发 / 输入输出

### 4.1 skill 名

`task-code-judge-loop`

理由：与现有 `task-acceptance-judge` 同前缀，表达"task 的 code+judge 循环"。动词-名词结构对齐项目其他 skill（`push-with-output-ignore`）。

### 4.2 触发关键词（写进 description）

中文：`task N 开发+验收循环` / `dev loop task N` / `code-judge task N` / `跑 task N 的 dev loop` / `做 task N 直到验收过`

英文别名：`code-judge loop task N` / `dev task N`

显式调用：`/task-code-judge-loop 5` 或 `/task-code-judge-loop task 5`

### 4.3 输入

| 参数 | 必填 | 默认 | 来源 |
|---|---|---|---|
| Task 编号 N | ✅ | — | 用户消息中提取（正则 `task\s*(\d+)`，case-insensitive） |
| Plan 路径 | ❌ | 自动发现 | 用户显式指定优先；否则 `glob docs/superpowers/plans/*.md` 取日期最新且含 `### Task N` 的 |
| Prefix | ❌ | 自动推断 | `glob docs/*_task{N}_coding.md` + `glob docs/*_task{N}_judging.md` 唯一匹配则用；多匹配让用户选；零匹配默认 `critic`（当前主线）|

### 4.4 输出

| 产物 | 路径 | 频率 |
|---|---|---|
| 代码改动 | 按 plan §Task N 规定 | 每轮 |
| Coding dev doc | `docs/<prefix>_task{N}_coding.md` | 每轮覆写 |
| Judging doc | `docs/<prefix>_task{N}_judging.md` | 每轮覆写（judge 写）；**不进 coding 每轮 commit**，PASS 后由主 session 批量 commit 所有累积的同 prefix judging doc |
| Commit | 1 个 / 轮 | 每轮 coding 末尾 |

## 5. 主流程

### 5.1 前置检查（loop 前）

并行做：

1. **解析 N**：正则从用户消息提取。未提取到 → 报错"请说明要做哪个 task"，中止
2. **找 plan**：用户给路径用之；否则 glob 取日期最新且含 `### Task N` 的。未找到 → 报错列候选，中止
3. **推断 prefix**：glob `docs/*_task{N}_coding.md` + `docs/*_task{N}_judging.md`
   - 0 个 → 默认 `critic`
   - 1 个 → 用之
   - 多个 → 列出让用户选（不同 plan 主线撞 prefix 时）
4. **当前分支检查**：`git branch --show-current` 若为 `main` / `master` → 报错中止（要求先切 feature 分支）

完成后向用户报"plan=X, task=N, prefix=Y, 分支=Z，最多 3 轮，每轮自动 commit，PASS 后问 push"，等用户 Y 继续（**仅这一次确认**，loop 中不再问）。

### 5.2 Loop（最多 3 轮）

```
for round in 1..=3:

  # === coding 阶段 ===
  coding_prompt = build_coding_prompt(N, plan_path, prefix, round, prev_judging)
  spawn Agent(subagent_type="general-purpose", prompt=coding_prompt)  # 同步等结果

  coding prompt 必含：
    - role: "你是 coding 助手"
    - 任务范围: plan §Task N 的所有 Step
    - dev doc 输出: 更新 docs/<prefix>_task{N}_coding.md（按现有 critic_task{N}_coding.md 结构）
    - round > 1 时附: 上一轮 judging doc 的 §7 Verdict JSON.reason +
                      §2/§3 中 FAIL 项 + §5 偏离登记 + §6 Red Flags
                      指令: "本轮重点修这些，不要做无关重构"
    - 硬约束（CLAUDE.md §9 提炼）:
        * 不动 src/
        * 不跳 hooks (--no-verify)
        * 不改 requirements.txt
        * 不在 analysis/ 或 core/ 里 import 具体 backend
        * 一次只改本 task 范围
    - 收尾 commit（coding-Agent 自己做）:
        * **只 add 本 task 相关文件**（plan §Task N Files 列出的 + 写出的 coding doc）
        * 严禁 `git add -A` / `git add .`（会扫进无关改动）
        * 严禁 `--no-verify`（除非用户显式说）
        * round 1 消息: "feat(<prefix>): implement task N (round 1)"
        * round 2+ 消息: "fix(<prefix>): address task N judging feedback (round <round>)"
    - 返回主 session: 改了哪些文件 + commit hash

  # 主 session 校验
  - `git status` 确认工作区只剩**与本 task 无关**的改动（如有 task 相关残留 → 报错中止）
  - `git log -1 --name-only` 确认 commit 含本 task 应改文件、不含无关文件
  - 若 coding-Agent 没自己 commit → 主 session 用相同 add 列表 + 消息模板补一次
  - 若 commit 是空 commit（无文件改动）→ 报错中止本轮

  # === judging 阶段 ===
  judge_prompt = build_judge_prompt(N, plan_path, prefix, round)
  spawn Agent(subagent_type="general-purpose", prompt=judge_prompt)  # 同步等结果

  judge prompt 必含:
    - role: "你是 judge 助手"
    - 任务: "调用 Skill 工具，skill 名为 task-acceptance-judge，args 传 'task N'"
    - 关键覆盖指令: "如果 task-acceptance-judge skill 在 Step 2 问你
                      'judging doc 已存在'，选'覆盖'，不要中止
                      （本 loop 内 round 2+ 必然已存在）"
    - 返回主 session: §7 Verdict JSON 完整内容 + 一句话总结

  # 主 session 解析 verdict
  Read docs/<prefix>_task{N}_judging.md
  grep 提取 §7 "Verdict JSON" 代码块
  解析 verdict 字段（PASS / CONDITIONAL PASS / FAIL）

  if verdict == "PASS":
    break

  # CONDITIONAL PASS 或 FAIL → 继续 fix
  if round < 3:
    把本轮 judging 路径记下来，下一轮传给 coding-Agent
    continue

  # round == 3 还没 PASS → 退出
```

### 5.3 Post-loop

```
if verdict == "PASS":
  # Step 2.A.1: commit 累积的 judging docs（必做）
  git ls-files --others --exclude-standard 'docs/<prefix>_task*_judging.md'
  若非空：
    git add docs/<prefix>_task*_judging.md
    git commit -m "docs(<prefix>): track task <N> judging docs"
  # 设计取舍：judging doc 不每轮 commit（会让 git log 翻倍且污染每轮 commit 语义），
  # 改为 PASS 后一次性 commit 累积的所有同 prefix judging doc

  # Step 2.A.2: push
  Skill(skill="push-with-output-ignore", args="")
  # 用户调本 skill = 同意 push，不再加 AskUserQuestion 问 push

else:  # 3 轮全 FAIL / CONDITIONAL
  报告:
    - 最后 verdict
    - 最后轮 judging doc 的 §7 blocking_issues
    - 3 轮累计改了哪些文件、哪些 commit
    - 建议: "查看 docs/<prefix>_task{N}_judging.md，人工分析卡点"
  不抛异常退出，把控制权交还用户
```

> **设计演进记录**：早期版本在 PASS 后用 AskUserQuestion 问 push 策略（3 选项），后改为"用户调用本 skill = 显式同意 push，不再问"。同时新增"PASS 后先 commit 累积 judging doc 再 push"。具体行为以 `SKILL.md` 为准。

## 6. 边界情况

| 情况 | 处理 |
|---|---|
| 用户没给 N | §5.1 报错中止 |
| plan 里没 Task N | §5.1 报错，列 plan 所有 task 编号 |
| 当前分支 = main/master | §5.1 报错中止 |
| `docs/<prefix>_task{N}_coding.md` round 1 前已存在（前次跑残留） | §5.1 问用户：覆盖 / 备份后覆盖 / 中止 |
| `docs/<prefix>_task{N}_judging.md` round 2+ 已存在（必然） | judge prompt 内置"覆盖"指令，不再问用户 |
| coding-Agent 没自己 commit | 主 session `git status` 检测后补一次 commit |
| coding-Agent 空 commit（无文件改动） | 报错中止本轮，跳出 loop 报告 |
| judge-Agent 没产出 judging doc 或 verdict 解析失败 | 报错中止，让用户看 judge-Agent 完整输出 |
| judge skill 内部 SKIP（环境缺依赖） | verdict = CONDITIONAL PASS，继续 fix loop |
| 3 轮全 FAIL | §5.3 报告 + 不抛异常退出 |
| 用户中途 Ctrl+C | 保留工作区状态；下次重跑会触发"coding/judging doc 已存在"分支 |
| plan §Task N 没有 `### Acceptance Criteria` 章节 | judge-Agent 报错（task-acceptance-judge skill 处理）；本 skill 不预检 |

## 7. Common Mistakes（skill 红线）

1. **并行 spawn coding 和 judge** — 必须串行；judge 看 coding 产出
2. **round 2+ 忘记把上轮 judging 反馈传给 coding-Agent** — 必须附 §7 reason + blocking_issues + §5 偏离登记
3. **让 coding-Agent 改 judging doc** — judge 专属产出
4. **让 judge-Agent 改代码或 coding doc** — judge 只读源文档（task-acceptance-judge skill 规定）
5. **每轮跳过 commit** — plan §Task N 的 git-log 检查会 FAIL，loop 永远不收敛
6. **coding-Agent 用 `git add -A` / `git add .`** — 会扫进工作区无关改动；必须只 add 本 task 文件
7. **把 CONDITIONAL PASS 当 PASS** — CONDITIONAL PASS 视为"还需修"，进入下一轮
8. **改 plan / 改 task-acceptance-judge skill** — 本 skill 只读这两个
9. **PASS 后擅自 push** — 违反 memory `feedback_commit_control.md`，必须问用户
10. **多 prefix 撞车时不让用户选** — glob 返回多个必须列出让用户选
11. **3 轮上限报成异常** — 这是预期路径，应正常退出报告
12. **PASS 后忘记 commit judging doc** — judge-Agent 每轮产出 judging doc 但不自己 commit；若主 session 不在 push 前主动 commit，judging doc 会一直留在工作区累积。必须 commit `docs/<prefix>_task*_judging.md` 再 push

## 8. 与现有 skill 的关系

| 现有 skill | 关系 |
|---|---|
| `task-acceptance-judge` | **被调用**：本 skill 的 judge 阶段 spawn 子 Agent 调它 |
| `push-with-output-ignore` | **可选调用**：PASS 后用户选"调 push skill"时调用 |
| `superpowers:subagent-driven-development` | **不冲突**：本 skill 是项目特定 dev+验收 loop，subagent-driven-development 是通用方法论 |
| `superpowers:executing-plans` | **不冲突**：本 skill 走的是"按 task 一轮轮验收"，executing-plans 走的是"按 plan 全跑"，粒度不同 |
| `superpowers:test-driven-development` | coding-Agent 自己决定是否走 TDD（按 plan §Task N 要求） |

## 9. 验证清单（写完 skill 后做一次）

1. 在 `feature/critic-and-tta` 分支上调 `/task-code-judge-loop 5`，应自动跑完一轮 coding + judge，产出 `docs/critic_task5_coding.md` + `docs/critic_task5_judging.md` + 1 个 commit
2. 故意让 round 1 FAIL（如改 plan 让 acceptance 更严），应自动进入 round 2 fix
3. 在 main 分支调，应报错中止
4. 不给 N 调（如 `/task-code-judge-loop`），应报错要 N
5. 给一个 plan 里没有的 N（如 `/task-code-judge-loop 99`），应报错列所有 task 编号
6. 已有 `docs/critic_task5_coding.md` 残留时调，应在 round 1 前问覆盖 / 备份 / 中止
7. 3 轮全 FAIL 时应正常退出报告，不抛异常
8. PASS 后应直接调 push-with-output-ignore skill（不再 AskUserQuestion）
9. PASS 后 `docs/<prefix>_task*_judging.md` 应全部 tracked；`git status` 工作区无未追踪的同 prefix judging md

## 10. 不变量（修改 skill 时必须保持）

1. **3 轮上限不可改**（除非用户显式说改）— 防死循环
2. **每轮必 commit** — git-log 检查依赖
3. **judge 必须独立 spawn**（不能让 coding-Agent 自审）
4. **Verdict 解析必须从 judging doc 读 §7 JSON**，不能从 judge-Agent 自报告抄
5. **PASS 后必问用户** — memory `feedback_commit_control.md`
6. **不改 plan / task-acceptance-judge skill 源文件** — 只读

## 11. 与 memory 的关系

- `feedback_commit_control.md`「默认不 commit」→ 本 skill 是**显式例外**：用户调用 = 选择每轮 commit；PASS 后仍问 push（不擅自 push）
- `project_judge_agent_acceptance_framework.md`「9 字段 Verdict JSON schema」→ 本 skill 通过 task-acceptance-judge skill 间接遵守，不重复定义
