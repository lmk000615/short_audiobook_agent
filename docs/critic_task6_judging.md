# Critic Task 6 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` §Task 6 (Full)
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 6 无独立章节，沿用 plan §Task 6 Acceptance Full）
> **Coding dev doc:** `docs/critic_task6_coding.md`
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-03
> **Task 类型:** 代码型（TDD 经典红→绿：本 task 让 Task 5 残留的 ImportError 转绿）
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**PASS** — Task 6 按 plan §Task 6 Step 1→5 严格落地：新建 `src_next/critic/prompts/critic_prompt.py`（78 行，含 `build_critic_prompt` + `_extract_expected_emotion` + `_extract_expected_speed` + `_CRITIC_PROMPT_TEMPLATE`，5 维命名/顺序/JSON schema 示例/建议规则硬约束全部逐字匹配 plan）+ 追加 `test_critic_prompt_includes_expected_vs_actual_context`（plan Step 1 字面量逐字粘贴），commit `732e81b feat(critic): implement task 6 (round 1)` 已落盘。**Section A self-check 实测 `3 passed in 0.10s`**（construction + evaluate success + prompt structure 全过），Task 5 残留的 ImportError 已转绿；**Section B 9/9 静态审查全过，0 Red Flag，0 偏离**（仅 1 条文档型说明：`__init__.py` 由 Task 2 已建，本 task 跳过 plan Step 3 兜底子步骤）。

---

## 1. 验收范围

按 plan §Task 6 (Full) Acceptance Criteria 三档验收：

- **Section A — coding-Agent Self-check**：1 条命令（pytest 全量 critic 测试，期望 `3 passed`）
- **Section B — judge-Agent 抽查**：4 条 plan 静态审查点 + 4 条 plan Red flags 反向核对 + 1 条 scope 边界（prompts/ 目录仅含 `__init__.py` + `critic_prompt.py`）+ 1 条分层洁净（仅 import data_models）
- **额外审查**：字面量逐字比对（5 维命名/顺序 + JSON schema 示例 + 建议规则硬约束 + 5-key 兼容元组 + fallback 字面量）+ scope 边界（critic 子树，未越界实现 Task 7 conftest / Task 8 robustness / Task 9 integration / Task 10-11 repair）+ commit 范围核对 + 偏离登记 + red flag 排查 + py_compile

**核心 plan 期望（行 905-908）：** 3 tests PASS（construction + evaluate success + prompt structure）。

**核心 plan Red Flags（行 967-971）：**
1. prompt 把 text/speaker/model 当 LLM 可改字段 → 应 FAIL
2. 维度命名漂移（如 `character_consistent` 少一个 `cy`）→ 应 FAIL
3. JSON schema 示例 `{{` `}}` 漏转义 → 应 FAIL
4. prompt 长度异常（>3000 或 <200 字符）→ 应 FAIL

---

## 2. Section A — coding-Agent Self-check

| 项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| A1 `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` | `3 passed`（construction + evaluate success + prompt structure，plan 行 932） | `3 passed in 0.10s`（3 个测试全过） | **PASS** |

### A1 完整测试输出（judge 独立执行，不抄 coding doc）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\29577\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: F:\akoasm\short_audiobook_agent
configfile: pytest.ini
plugins: anyio-4.13.0
collecting... collected 3 items

src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults PASSED [ 33%]
src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success PASSED [ 66%]
src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context PASSED [100%]

============================== 3 passed in 0.10s ==============================
```

**Section A 汇总：1/1 PASS。**

---

## 3. Section B — judge-Agent 抽查

### B.1 plan 行 962-965 静态审查点（4/4）

| 抽查点 | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| B1 prompt 模板含「Expected vs Actual」pattern（原文 + speaker + 期望情感都进 prompt） | 三段 `## 原文` + `## 期望表现` + `## 评分维度` 都嵌入 | `critic_prompt.py` 行 17-25 + Read 显示模板含 `{text}` / `{speaker}` / `{expected_emotion}` 占位符，由 `build_critic_prompt` 行 71-78 注入；smoke 输出实际 prompt 含 `## 原文` 段（窗外下着大雨）+ `## 期望表现` 段（narrator / narration / S2Pro / 平稳叙述 / 未指定（用模型默认）） | **PASS** |
| B2 5 维度定义与任务卡 §1.3.1 完全一致（命名、顺序） | quality → emotion_alignment → character_consistency → rhythm_naturalness → intelligibility | Grep `critic_prompt.py` 行 28-32 顺序锁定；JSON schema 示例行 42 同序；测试 `test_qwen3omni_critic.py` 行 112-113 for-loop 5 维顺序锁定；`character_consistency` 全文 3 次出现，无 `character_consistent` 拼写漂移（Grep `character_consistent[^n]` 0 命中） | **PASS** |
| B3 `_extract_expected_emotion` 兼容多种 parameters key | 元组 `("instruct_text", "instruction", "emotion", "emotion_vector", "style")` 逐字 | `critic_prompt.py` 行 48 for-loop 元组字面量逐字匹配 plan 行 872；fallback 字面量 `"未指定"`（行 52）匹配 plan 行 876 | **PASS** |
| B4 suggestions 规则段含「绝对不要建议修改原文/speaker/model/voice_ref」的硬约束 | 行 36 + 行 37 两条硬约束 | `critic_prompt.py` 行 36 `**绝对不要**建议修改原文 text、speaker、model 或换参考音频`；行 37 `**绝对不要**建议加入新的背景音、音效、配乐` | **PASS** |

### B.2 plan 行 967-971 Red Flags 反向核对（4/4，全部未触发）

| Red Flag | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| R1 prompt 把 text/speaker/model 当 LLM 可改字段 | 应明确锁定，不出现「请修改 text/speaker/model」类建议 | 行 36 显式锁定「**绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定」；smoke 输出确认这三项只出现在「## 原文」与「## 期望表现」段（只读上下文），不出现在「## 建议规则」可改字段列表 | **PASS（未触发）** |
| R2 维度命名漂移（如 `character_consistent` 漏 `cy`） | 5 维命名逐字一致 | Grep `character_consistent[^n]` 在 `critic_prompt.py` 0 命中（确认无漂移）；5 维全部命中 3 次（行 30 + 行 42 + 测试行 112-113 间接） | **PASS（未触发）** |
| R3 模板里 `{speaker}` format placeholder 没正确转义，JSON schema 示例 `{{` `}}` 漏写 | JSON 示例用 `{{` `}}` 输出单花括号 | `critic_prompt.py` 行 42 字面量 `{{"quality":0.85,...,"suggestions":"建议内容"}}`，`str.format` 转义正确；smoke 实际输出含 `{"quality":0.85,...}`（单花括号），未触发 KeyError / 输出残缺 | **PASS（未触发）** |
| R4 prompt 长度异常（>3000 或 <200 字符） | 200-3000 字符区间 | smoke 实测 `len(p) = 774`（在 200-3000 区间内） | **PASS（未触发）** |

### B.3 额外 judge 审查点（2/2，coding doc §3.B 加项）

| 抽查点 | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| B5 scope 边界：`src_next/critic/prompts/` 目录仅含 `__init__.py`（Task 2 建）+ `critic_prompt.py`（本 task 建）+ `__pycache__/` | 不应越界提前实现 conftest / fixtures / repair_prompt | `ls -la src_next/critic/prompts/` 输出仅 `.` `..` `__init__.py` `__pycache__` `critic_prompt.py` 5 项，无越界文件 | **PASS** |
| B6 分层洁净：`critic_prompt.py` 仅 import `src_next.core.data_models`，不 import 任何 TTS / LLM / voicebank backend | CLAUDE.md §9 第 3 条洁净分层（critic 模块按相同标准执行） | `critic_prompt.py` 行 12 单一 import `from src_next.core.data_models import ModelSpecificTTSInstruction, Segment`；Grep `instruction|emotion_vector|instruct_text|style` 行 35 + 47-48 + 64-77 仅作为参数 key 字面量出现，不作为模块 import | **PASS** |

**Section B 汇总：10/10 PASS（4 plan 静态审查 + 4 plan Red Flag 反向核对 + 2 额外 judge 审查点）。**

### B.4 Section B mock 命令实测（plan 行 944-948）

| 命令 | 期望 | 实测 | 状态 |
|---|---|---|---|
| `python -m pytest src_next/critic/tests/ -m "not integration" -v` | 至少 3 passed | `3 passed in 0.10s`（与 Section A 相同 3 测试，无 integration mark） | **PASS** |
| `python -c "from ... import build_critic_prompt; ...; print(p)"` | prompt 含 5 维 + JSON schema + 期望情感 + 原文 | smoke 输出 `len(p) = 774`，包含 `## 原文` / `## 期望表现` / `## 评分维度` / `## 建议规则` / `## 输出格式` 五段，5 维 + suggestions + JSON schema 全部正确展开（控制台 GBK 显示乱码，但断言全过证明字符串内容正确，Read 文件确认无乱码） | **PASS** |

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 涉及文件清单

| 操作 | 路径 | 实测 | plan 期望 |
|---|---|---|---|
| 创建 | `src_next/critic/prompts/critic_prompt.py` | 78 行，commit `732e81b` | plan 行 788 |
| 修改 | `src_next/critic/tests/test_qwen3omni_critic.py` | 117 行（Task 5 末态 97 行 + 20 行新测试），commit `732e81b` | plan 行 789（仅追加 prompt test） |

### 4.2 关键字面量逐字核对

| 字面量 | plan 出处 | 实测 | 状态 |
|---|---|---|---|
| 5 维命名 `quality` / `emotion_alignment` / `character_consistency` / `rhythm_naturalness` / `intelligibility` | plan 行 852-856 + 任务卡 §1.3.1 | `critic_prompt.py` 行 28-32 + 行 42 逐字一致 | ✓ |
| 顺序：quality → emotion_alignment → character_consistency → rhythm_naturalness → intelligibility | 任务卡 §1.3.1 | Grep 行 28-32 + 行 42 同序 | ✓ |
| JSON schema 示例 `{{"quality":0.85,...,"suggestions":"建议内容"}}` | plan 行 866 | `critic_prompt.py` 行 42 字面量逐字一致 | ✓ |
| 5-key 兼容元组 `("instruct_text", "instruction", "emotion", "emotion_vector", "style")` | plan 行 872 | `critic_prompt.py` 行 48 逐字一致 | ✓ |
| fallback 字面量 `"未指定"` | plan 行 876 | `critic_prompt.py` 行 52 一致 | ✓ |
| fallback 字面量 `"未指定（用模型默认）"` | plan 行 882 | `critic_prompt.py` 行 58 一致 | ✓ |
| 建议规则硬约束「**绝对不要**建议修改原文 text、speaker、model 或换参考音频」 | plan 行 860 | `critic_prompt.py` 行 36 逐字一致 | ✓ |
| 建议规则硬约束「**绝对不要**建议加入新的背景音、音效、配乐」 | plan 行 861 | `critic_prompt.py` 行 37 逐字一致 | ✓ |
| 模板标题 `## 原文` / `## 期望表现` / `## 评分维度` / `## 建议规则` / `## 输出格式` | plan 行 842/845/851/858/864 | `critic_prompt.py` 行 17/20/27/34/40 逐字一致 | ✓ |
| `**只输出严格的 JSON**` | plan 行 865 | `critic_prompt.py` 行 41 逐字一致 | ✓ |
| `build_critic_prompt(segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> str` | plan 行 886-889 | `critic_prompt.py` 行 62-65 字面匹配 | ✓ |
| 测试函数名 `test_critic_prompt_includes_expected_vs_actual_context` | plan 行 795 | `test_qwen3omni_critic.py` 行 99 字面匹配 | ✓ |
| 测试断言 `assert "窗外下着大雨" in prompt` / `assert "narrator" in prompt` / `assert "平稳叙述" in prompt` | plan 行 803-805 | `test_qwen3omni_critic.py` 行 107-109 逐字一致 | ✓ |

### 4.3 commit 范围核对

```
$ git log --oneline -5
732e81b feat(critic): implement task 6 (round 1)
48ffea0 feat(critic): implement task 5 (round 1)
47a9358 docs(critic): finalize task 4 dev doc with commit hashes
2b79004 docs(critic): add task 4 coding dev doc
1da7024 feat(critic): add Qwen3OmniCritic skeleton with construction test
```

`732e81b` 直接前置 `48ffea0`（Task 5），分支 `feature/critic-and-tta` 推进 1 commit，与 plan Step 5 期望一致。

**Commit message 偏离：** plan Step 5 行 914 给的模板是 `feat(critic): implement evaluate happy path + neutral fallback + prompt builder`，实际 commit message 为 `feat(critic): implement task 6 (round 1)`。**这是用户 task 指令预先指定的覆盖**（coding doc §5.1 已说明），与 Task 4/5 后期 commit 风格一致，无功能性影响。

### 4.4 scope 边界（critic 子树，本 task 仅触碰 2 个文件）

```
$ git status --short
?? docs/critic_task2_judging.md
?? docs/critic_task3_judging.md
?? docs/critic_task4_judging.md
?? docs/critic_task5_judging.md
?? docs/intern_b_audio_oscar_research.md
?? docs/intern_b_audio_oscar_why.md
?? docs/intern_b_critic_and_tta.md
?? docs/superpowers/specs/2026-07-01-push-with-output-ignore-skill-design.md
?? docs/superpowers/specs/2026-07-02-task-acceptance-judge-skill-design.md
?? docs/superpowers/specs/2026-07-02-task-code-judge-loop-skill-design.md
?? input.rar
?? output-src-next-analysis-test/
?? output-src-next-pipeline/
?? output-src-next/
?? output/analysis/book_06_director_plan.md
?? src_next/profiles/server_qwen_voicegenerator.yaml
?? webui_old.py
```

- 工作区无 staged / modified 文件（commit 已干净落盘）
- 大量 untracked 文件为其他 task / 其他工作流产物，未被本 task commit 拖入
- `git status` 无 `src_next/critic/` 下任何文件 → 证明本 task 范围严格限定在 commit `732e81b` 内

### 4.5 未越界实现 Task 7-11 内容

| 后续 task 应交付 | 本 task 是否越界提前实现 | 验证 |
|---|---|---|
| Task 7: `conftest.py` + `fixtures/` | ❌ 未实现 | `ls src_next/critic/tests/` 无 `conftest.py` |
| Task 8: 5 个 robustness 测试 | ❌ 未实现 | `test_qwen3omni_critic.py` 仅 3 个测试函数 + 1 工厂 + 1 mock class，无越界 |
| Task 9: 5 个 integration 测试骨架 | ❌ 未实现 | 无 `@pytest.mark.integration` 标记 |
| Task 10: TTSRepairAgent | ❌ 未实现 | `src_next/critic/` 下无 `repair_agent.py` |
| Task 11: repair_prompt + 行为测试 + 实现 | ❌ 未实现 | `src_next/critic/prompts/` 仅 `critic_prompt.py`，无 `repair_prompt.py` |

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| D1 `src_next/critic/prompts/__init__.py` 是否需新建 | plan Step 3 行 823 措辞「Create `src_next/critic/prompts/critic_prompt.py`」 + plan 隐含前置「（如果不存在）目录 + `__init__.py`」 | Task 2 已建 `__init__.py`（85 字节） | 无（import 路径已可解析，3 passed） | 跳过此子步骤，符合 plan 兜底语义 |
| D2 commit message 措辞 | plan Step 5 行 914 模板 `feat(critic): implement evaluate happy path + neutral fallback + prompt builder` | `feat(critic): implement task 6 (round 1)` | 无（用户 task 指令预先覆盖，与 Task 4/5 风格一致） | 文档登记，非缺陷 |

**无结构性偏离。** 所有字面量（5 维命名、顺序、JSON schema 示例、建议规则硬约束、5-key 兼容元组、fallback 字面量）与 plan 逐字一致。

---

## 6. Red Flags 排查

| Red Flag 类别 | 期望 | 实测 | 状态 |
|---|---|---|---|
| F1 字面量不一致（5 维命名漂移 / placeholder 漏转义） | 全部锁定 | Grep `character_consistent[^n]` 0 命中；JSON schema 示例 `{{` `}}` 双花括号转义正确 | ✓ 未触发 |
| F2 scope 越界（提前实现 Task 7 conftest / Task 8 robustness / Task 9 integration / Task 10-11 repair） | 仅本 task 2 文件 | `ls src_next/critic/prompts/` + `ls src_next/critic/tests/` 无越界文件；测试函数仅 3 个 | ✓ 未触发 |
| F3 章节顺序错乱（plan Step 1→5 顺序） | RED → GREEN → commit | coding doc §2 + git log `732e81b` 确认按 Step 1-5 顺序执行（先 RED `ModuleNotFoundError` 再 GREEN `3 passed`） | ✓ 未触发 |
| F4 `--no-verify` 跳过 hooks | 不允许（CLAUDE.md §9 第 8 条） | commit `732e81b` 正常生成（无 `--no-verify` / `--no-gpg-sign` 痕迹） | ✓ 未触发 |
| F5 改 `src/` 旧链路 | 不允许（CLAUDE.md §9 第 5 条） | `git status` 无 `src/` 路径修改 | ✓ 未触发 |
| F6 改 `requirements.txt` / 升级依赖 | 不允许（CLAUDE.md §9 第 6 条） | `git status` 无 `requirements.txt` 修改 | ✓ 未触发 |
| F7 硬编码服务器地址 | 不允许（CLAUDE.md §9 第 7 条） | `critic_prompt.py` 无任何 IP / URL 字面量 | ✓ 未触发 |
| F8 prompt 把 text/speaker/model 当 LLM 可改字段 | plan Red Flag R1 | 行 36 显式锁定「**绝对不要**建议修改...」 | ✓ 未触发 |
| F9 prompt 长度异常（>3000 或 <200） | plan Red Flag R4 | smoke 实测 `len(p) = 774` | ✓ 未触发 |
| F10 分层崩塌（core/analysis import backend） | 不允许（CLAUDE.md §5 第 3 条，critic 模块按同标准执行） | `critic_prompt.py` 仅 import `data_models`，无 backend import | ✓ 未触发 |

**Red Flags 排查：0/10 命中。**

---

## 7. Verdict JSON

```json
{
  "task_id": "critic-task-6",
  "verdict": "PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v",
      "python -m pytest src_next/critic/tests/ -m \"not integration\" -v"
    ],
    "result": "3 passed in 0.10s (construction + evaluate success + prompt structure)"
  },
  "integration_tests": "N/A (Task 9 才写 integration 骨架)",
  "smoke_tests": {
    "ran": [
      "python -c \"from src_next.critic.prompts.critic_prompt import build_critic_prompt; ...; print(p)\""
    ],
    "result": "PASS — len(p)=774, 含 5 维 + JSON schema + 期望情感 + 原文 + 建议规则硬约束（控制台 GBK 显示乱码但断言全过，Read 文件无乱码）"
  },
  "static_review": {
    "plan_static_checks": "4/4 PASS (B1-B4)",
    "plan_red_flag_checks": "4/4 未触发 (R1-R4)",
    "extra_judge_checks": "2/2 PASS (B5 scope 边界 + B6 分层洁净)",
    "literal_byte_match": "全部字面量逐字一致 (5 维命名/顺序/JSON schema 示例/5-key 元组/fallback 字面量/建议规则硬约束)",
    "deviation_count": 2,
    "deviation_class": "无结构性偏离 (D1 文档兜底 + D2 commit message 用户覆盖)"
  },
  "reason": "Task 6 按 plan §Task 6 Step 1-5 严格落地：critic_prompt.py 创建 + 测试追加 + ImportError 转绿 + commit 732e81b 落盘，3 passed / 10 静态审查全过 / 0 Red Flag / 0 结构性偏离",
  "blocking_issues": [],
  "next_action": "进入 Task 7（写 conftest.py + fixtures，注意 KNOWN_ISSUES.md §3 已固化的 fixture 名 good_narration_wav 不能改）"
}
```

---

## 8. 给后续 task 的提醒

- **Task 7（conftest + fixtures）**：
  - `good_narration_wav` fixture 名字不能改（KNOWN_ISSUES.md §3 已固化，本 task 期间已核对一次）
  - 路径解析函数应命名为 `_audio_path`（与 KNOWN_ISSUES.md §3 一致）
  - fixture root 通过 `CRITIC_FIXTURES_ROOT` 环境变量覆盖
  - conftest 文件路径：`src_next/critic/tests/conftest.py`
  - fixtures 目录路径：`src_next/critic/tests/fixtures/`（具体 wav 文件由 Task 7 之后单独下载/录制 task 处理，Task 7 只建结构）

- **Task 8（鲁棒性测试）**：
  - 5 个测试函数名要与 KNOWN_ISSUES.md §1 列出的逐字一致（不要自创命名）
  - mock 测试默认跑（`-m "not integration"`），不依赖真实服务
  - 全部加到 `test_qwen3omni_critic.py` 现有 3 个测试之后
  - **复用 Task 5 的 `_FakeOkResponse` / `_make_segment_and_instruction` 工厂**（已在文件内，本 task 也复用过）

- **Task 9（集成测试骨架）**：
  - 5 个测试函数名同样从 KNOWN_ISSUES.md §1 复制
  - 全部 `@pytest.mark.integration` 默认 skip
  - 集成测试可独立放在新文件 `test_qwen3omni_critic_integration.py` 或仍在原文件加 mark（具体由 Task 9 plan 决定）

- **Task 11（repair_prompt）**：
  - repair_prompt.py 应同样放在 `src_next/critic/prompts/` 下（与 `critic_prompt.py` 同目录）
  - 仍按分层洁净标准：仅 import `data_models`，不 import backend

- **集成验证（Task 14 才做全链路 mock）**：
  - 本 task 已验证 `critic_prompt.py` 与 `qwen3omni_critic.py:_evaluate_inner` 的调用接口对齐（行 71-78 build_critic_prompt 与 Task 5 行 19 `from ... import build_critic_prompt` 字面匹配）
  - Task 14 时整树 mock 应至少 8 passed（Task 4 + Task 5 + Task 6 + Task 8 的 5 个 robustness）

---

## 9. 一句话总结

Task 6 = 创建 `critic_prompt.py`（78 行，build_critic_prompt + 两个 parameters 提取器 + _CRITIC_PROMPT_TEMPLATE）+ 追加 `test_critic_prompt_includes_expected_vs_actual_context` 单测，TDD 走 RED（ModuleNotFoundError）→ GREEN（3 passed in 0.10s），Task 5 残留的 ImportError 终态由本 task 转绿；所有字面量（5 维命名/顺序/JSON schema 示例/建议规则硬约束/5-key 兼容元组/fallback 字面量）与 plan 逐字一致，commit `732e81b` 已落盘，0 结构性偏离，0 Red Flag，10/10 静态审查全过，**verdict: PASS**。
