# 为 intern-b-critic-repair plan 增加验收过程（Design）

**日期:** 2026-07-02
**目标 plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md`
**变更类型:** 在 plan 每个 task 末尾追加 Acceptance Criteria 章节；不改动现有 Files / Steps / Expected 结构。

---

## 1. 背景与动机

现有 plan 已经是 TDD 风格（每个 task 写失败测试 → 实现 → 跑测试 → commit），但存在两个缺口：

1. **缺验收闸.** Steps 里的 "Expected" 是预期产出，不是验收判定。比如 Task 5 的 Step 4 写 "Expected: PASS"，但谁来跑、跑失败算谁的、后续 task 能不能开始——都没说。
2. **服务访问鸿沟.** 实习生本机无法访问 Qwen3-Omni 和 LLM 服务，integration 测试只能 skip-marked。但代码质量、契约遵守、prompt 合理性这些**只能在有服务时验证的事情**，需要一个有服务访问的角色来兜底。

## 2. judge-Agent 的角色定义

- **不是**另一个静态代码审查的 LLM。
- **是**一个跑在「可访问 Qwen3-Omni 服务 + 本地 LLM 服务」环境里的 LLM agent。
- 职责范围：
  - 跑 mock 测试（任何环境都能跑）
  - 跑 integration 测试（删 skip 装饰器后，本环境内可跑）
  - 真实端到端 smoke（手动构造请求验证契约）
  - 静态代码审查（读代码、查 anti-pattern、检查契约遵守）

> ⚠️ **不要把 judge-Agent 当 CI**：CI 只能跑命令、判退出码；judge-Agent 还要做语义判断（如「_neutral_result 是否真的返回 0.5 而不是 0.0」「repair 是否真的 schema-frozen」），这些是 LLM 才能做的。

## 3. Acceptance Criteria 章节结构

每个 task 末尾追加 `### Acceptance Criteria` 章节，按 task 重要性分两档：

### 3.1 Full 结构（核心代码 + integration 测试 task）

适用 task: **5, 6, 8, 9, 11, 12**

```markdown
### Acceptance Criteria

**Pre-conditions:** Task X / Y 已合并（其 commit 在 git log 里可见）。

#### A. coding-Agent 完成定义（mock-可验证）
**产出物:**
- <file> 含 <symbol>，签名 <signature>
- <contract>

**Self-check 命令（本机可跑，无需服务）:**
```bash
<command>
```
→ 期望: <output>

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试
<command>
# 2. Integration 测试（启用 skip 后）
<command>
# 3. 端到端 smoke（如适用）
<command>
```

**静态审查点（LLM 读代码判断）:**
- [ ] <check1>
- [ ] <check2>

**Red flags（任一出现即 FAIL）:**
- <anti-pattern1>
- <anti-pattern2>

#### C. Pass 条件
A 全绿 + B mock 命令绿 + B integration 命令绿（服务可用后）+ 静态审查无 red flag → **PASS**

judge-Agent 输出 schema:
```json
{
  "task_id": "Task N",
  "verdict": "PASS|FAIL",
  "mock_tests": "PASS|FAIL",
  "integration_tests": "PASS|FAIL|SKIPPED",
  "smoke_tests": "PASS|FAIL|SKIPPED",
  "static_review": "PASS|FAIL",
  "reason": "<一句话理由>",
  "blocking_issues": ["<issue1>"],
  "next_action": "<修复方向>"
}
```
（`smoke_tests` 仅对 Task 5 / 11 适用，其他 task 一律 `SKIPPED`）
```

### 3.2 Simplified 结构（脚手架 / 文档 / 验证 task）

适用 task: **1, 2, 3, 4, 7, 10, 13, 14, 15, 16**

```markdown
### Acceptance Criteria

**Pre-conditions:** <前置 task 已完成 / 无>

**A. coding-Agent Self-check:**
- <命令> → <期望>

**B. judge-Agent 抽查（无 integration 测试）:**
- [ ] <静态检查点>

**Pass:** A 绿 + B 抽查无 red flag → **PASS**
```

## 4. Task 分级映射

| Task | 类型 | 结构 | judge 端到端 smoke | skip-marked integration 测试 |
|---|---|---|---|---|
| 1. 创建分支 | git ops | Simplified | — | — |
| 2. 包骨架 | 目录脚手架 | Simplified | — | — |
| 3. KNOWN_ISSUES.md | 文档 | Simplified | — | — |
| 4. Critic 构造测试 | 单元测试 | Simplified | — | — |
| 5. Critic evaluate happy path | 核心代码 | **Full** | **有**（judge 手写 evaluate 调用脚本） | — |
| 6. critic_prompt 模块 | 核心代码 | **Full** | — | — |
| 7. conftest.py | 测试基建 | Simplified | — | — |
| 8. Critic 鲁棒性测试 | 核心代码 | **Full** | — | — |
| 9. Critic integration skeleton | 测试骨架 | **Full** | — | **有**（4 个） |
| 10. Repair 构造测试 | 单元测试 | Simplified | — | — |
| 11. Repair 完整实现 | 核心代码 | **Full** | **有**（judge 手写 repair 调用脚本） | — |
| 12. Repair integration skeleton | 测试骨架 | **Full** | — | **有**（1 个） |
| 13. py_compile 验证 | 命令 | Simplified | — | — |
| 14. 全 mock 测试套件 | 命令 | Simplified | — | — |
| 15. mock sample 文档 | 文档 | Simplified | — | — |
| 16. PR 创建 | git ops | Simplified | — | — |

> **"端到端 smoke" vs "integration 测试" 区分：**
> - **Integration 测试**: plan 里 `@pytest.mark.integration` + `@pytest.mark.skip` 标记的 pytest 用例（Task 9 / 12 产出）。judge-Agent 启用后跑 `pytest -m integration`。
> - **端到端 smoke**: judge-Agent 自己写的一段 `python -c "..."` 内联脚本，绕过 pytest 直接调用 `evaluate()` / `repair()`，验证 API 端点和契约——主要服务于 Task 5 / 11 这种「实现核心代码但 integration 骨架还没写」的早期 task。
>
> **"服务可用"的定义：** judge-Agent 的运行环境可访问 `http://10.50.121.102:8011`（Qwen3-Omni）且能 import `src_next.llm.qwen_http.QwenHTTPClient` 并指向有效 base_url。

## 5. 设计决策记录

### 5.1 为什么用 task 级而非 step 级验收

考虑过把验收塞到每个 step 的 Expected 里。否决理由：
- Step 太细（~80 个），judge-Agent 评审成本太高
- Step 之间天然耦合（先写失败测试 → 再实现），单独验收意义不大
- Task 级刚好对应"一个可独立 review 的成果单元"

### 5.2 为什么不单独写 acceptance matrix 文档

考虑过把所有验收标准集中到一个独立文件。否决理由：
- 与主 plan 分离后，judge-Agent 需要 cross-reference，容易遗漏
- 现 plan 已有 16 个 task，追加章节就地维护更直观

### 5.3 为什么把 mock/integration/smoke 命令都列出来

judge-Agent 在自己的环境里跑这些命令，必须给确定的命令 + 期望输出，不能让 LLM 自己猜。这把 judge 从"主观评价"约束回"机械执行 + 语义判断"两条腿。

### 5.4 为什么 judge-Agent 输出用固定 JSON schema

judge-Agent 输出会被 plan 执行框架（subagent-driven-development 等）消费。固定 schema 让框架能解析、聚合、决策（如"Task 5 FAIL → 不允许开始 Task 6"）。schema 字段精挑：
- `verdict`: 主结论
- `mock_tests` / `integration_tests` / `static_review`: 三维度独立判定，便于定位是哪一类问题
- `blocking_issues`: 列表，便于追溯
- `next_action`: 给 coding-Agent 一个明确的修复方向，闭环

### 5.5 为什么 Pre-conditions 显式列出

现有 plan 通过 task 编号暗示依赖。但 judge-Agent 不一定按顺序跑（可能并行、可能跳读）。显式 Pre-conditions 让 judge-Agent 知道「跑这个验收前，必须确认 X 已完成」。

## 6. 修改策略

在 plan 文件中，对每个 task 的最后一个 step 之后、下一个 task 标题之前插入 `### Acceptance Criteria` 章节。**不修改原 step 的 Expected 文字**——它们是 coding-Agent 的操作指引，验收章节是 judge-Agent 的判定依据，两者职责不重叠。

预计 plan 长度变化：
- 6 个 Full task × ~50 行/个 = ~300 行
- 10 个 Simplified task × ~12 行/个 = ~120 行
- 总计 +420 行（现 plan ~1900 行 → ~2320 行）

## 7. 验收章节模板示例

### Full 示例（Task 5）

```markdown
### Acceptance Criteria

**Pre-conditions:** Task 4 已合并（`Qwen3OmniCritic` 类已存在，含构造方法）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- `src_next/critic/qwen3omni_critic.py` 含 `Qwen3OmniCritic.evaluate()` 方法
- 签名: `evaluate(audio_path: str, segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> CriticResult`

**Self-check 命令（本机可跑，无需服务）:**
```bash
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v
```
→ 期望: `1 passed`

**契约:**
- `evaluate()` 任何异常都不外抛（catch-all → neutral fallback）
- `_neutral_result` 返回 `overall=0.5`（不是 0.0）
- HTTP 端点 `/v1/omni/audio_analysis`，payload 含 `task=sound_analysis` + `text` 字段

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试全绿（任何环境都能跑）
python -m pytest src_next/critic/tests/ -m "not integration" -v
# 期望: 至少 3 passed（含 test_evaluate_returns_critic_result_on_success）

# 2. 端到端 smoke（judge 自写脚本，绕过 pytest 直接验证 API）
python -c "
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction
critic = Qwen3OmniCritic()
seg = Segment(segment_id='smoke', text='测试', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='smoke', speaker='narrator', text='测试', model='S2Pro', parameters={'instruction':'平稳叙述'}, attempt=1)
r = critic.evaluate('/path/to/good_narration.wav', seg, inst)
print(f'quality={r.quality}, overall={r.overall}, suggestions={r.suggestions!r}')
assert r.quality > 0.5, f'good audio scored too low: {r.quality}'
"
# 期望: 打印数值，quality > 0.5，无 exception

# 3. 失败兜底 smoke（喂不存在的音频）
python -c "
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
# ... 同上构造 seg / inst
r = critic.evaluate('/nonexistent.wav', seg, inst)
assert r.overall == 0.5, f'failure should return neutral 0.5, got {r.overall}'
"
# 期望: r.overall == 0.5（验证不抛异常 + neutral fallback 正确）
```

**静态审查点（LLM 读代码判断）:**
- [ ] `_parse_scoring_json` 三步兜底完整（剥 fence → json.loads → raw_decode）
- [ ] `try/except Exception` 范围合理（不是裸 `except:`）
- [ ] 未引入未要求的依赖（只用 `requests` + 项目内已有模块）
- [ ] 没有提前实现后续 task 的功能（如 repair agent 的逻辑）

**Red flags（任一出现即 FAIL）:**
- `evaluate()` 抛了未捕获异常
- neutral fallback 返回 `0.0` 而非 `0.5`
- 测试用 `_FakeOkResponse` 之外的真实网络调用（mock 测试不该真联网）

#### C. Pass 条件 + 输出

A 全绿 + B mock 命令绿 + B smoke 命令绿（服务可用时）+ 静态审查无 red flag → **PASS**

judge-Agent 输出:
```json
{
  "task_id": "Task 5",
  "verdict": "PASS|FAIL",
  "mock_tests": "PASS|FAIL",
  "integration_tests": "SKIPPED",
  "smoke_tests": "PASS|FAIL|SKIPPED",
  "static_review": "PASS|FAIL",
  "reason": "<一句话>",
  "blocking_issues": ["<issue>"],
  "next_action": "<修复方向>"
}
```

### Simplified 示例（Task 2 包骨架）

```markdown
### Acceptance Criteria

**Pre-conditions:** Task 1 已完成（feature/critic-and-tta 分支存在）。

**A. coding-Agent Self-check:**
```bash
ls src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py pytest.ini
python -m pytest src_next/critic/tests/ -v
```
→ 期望: 4 个文件路径都存在；pytest 输出 `no tests ran in 0.0Xs`

**B. judge-Agent 抽查:**
- [ ] `pytest.ini` 含 `integration` marker 定义
- [ ] `src_next/critic/__init__.py` 不是空文件（含 docstring）
- [ ] git log 含 commit `chore(critic): scaffold critic package + pytest config`

**Pass:** A 绿 + B 抽查无 red flag → **PASS**
```

## 8. 不做的事（Out of scope）

- ❌ 不重新组织现有 task 结构
- ❌ 不修改 step 内的 Expected 文字
- ❌ 不增加新 task
- ❌ 不改动 Day 1/2/3 的日程安排
- ❌ 不写 judge-Agent 的实现（那是另一个 spec 的事，本次只产出验收标准本身）

## 9. 后续工作（不在本 spec 范围）

- judge-Agent 的实现（一个 LLM agent 跑 shell + 读代码 + 输出 JSON）
- 验收结果聚合工具（读多个 judge output → dashboard）
- 主开发联调时的 Stage 8 验收（用同一框架）
