# Qwen3OmniCritic + TTSRepairAgent Implementation Plan (3-day revised)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Part I of intern B task card — `Qwen3OmniCritic` (5-dim audio evaluation via Qwen3-Omni HTTP service) + `TTSRepairAgent` (LLM-driven parameters repair). Final deliverable: 8 new files committed to `feature/critic-and-tta` branch, ready for Stage 8 integration by 主开发.

**Architecture:** Two-file core (`qwen3omni_critic.py` + `tts_repair.py`) plus two prompt modules, with strict contracts against existing `CriticResult` and `ModelSpecificTTSInstruction` dataclasses (already on `main`). Critic calls Qwen3-Omni HTTP service (`http://10.50.121.102:8011/v1/omni/audio_analysis`) **serially** (infer_lock constraint), returns neutral 0.5 on failure (per task card — NOT 0.0 like Audio-Oscar). Repair uses **parameters merge** (original parameters as base + LLM overlay) with top-level fields (`segment_id / speaker / text / model / voice_ref`) **schema-frozen** — never trusted to LLM output.

**Tech Stack:** Python 3.10+, `requests` (HTTP), `pytest` (testing with `integration` marker), existing `BaseLLMClient` abstraction (in `src_next/llm/base.py`) for repair LLM, existing `core.data_models.CriticResult` / `ModelSpecificTTSInstruction` / `Segment`.

---

## ⚠️ Known constraints (this revision — read before starting)

### 1. 服务可访问性约束

实习生本机**无法实际调用 Qwen3-Omni 服务（`10.50.121.102:8011`）和本地 LLM 服务**进行 integration 测试。运维保证服务存在且正常，但本机访问不到。

**应对策略：**
- Integration 测试**写完整代码骨架**，但用 `@pytest.mark.skip(reason="...")` 标记
- pytest 报告里它们显示为 `SKIPPED` 而不是 `FAILED`，CI 不会被它们阻塞
- 服务可访问后只需删除 `@pytest.mark.skip` 一行就能启用，**不需要重写测试**
- PR 描述必须**明确标注** integration 覆盖缺口和待启用条件
- 任务卡 §3 PR checklist 中"真实 Qwen3-Omni 跑通"一项**改为"测试代码就绪，待服务可访问后启用"**

### 2. API 端点不确定性风险

任务卡 §1.4 推荐 `/v1/omni/audio_analysis` + `text` 字段传评分 prompt。但 `ussage_guide_qwen3_omni.md` 第 8 节的 API 表只列了 `audio / task / return_audio / speaker / max_new_tokens`，**没有 `text`**。

**应对策略：**
- 按任务卡原文走 `audio_analysis + text`（用户决策）
- 在 `qwen3omni_critic.py` 顶部加注释**显式记录这个不确定性**
- 如果服务就绪后 `text` 字段被忽略（critic 只返回通用 sound_analysis 描述而非评分 JSON），**fallback 是一行代码切换到 `/v1/omni/chat`**：payload 几乎相同（`audio + text + return_audio=false + max_new_tokens`），URL 后缀从 `/audio_analysis` 改为 `/chat`，仅此而已
- KNOWN_ISSUES.md 文档里记录这个 fallback 路径，方便未来调试

### 3. 时间节奏（3 天）

由于没有 integration debug 时间（prompt 调优、fixture 准备、服务等待），原 4 天压缩为 3 天：
- Day 1：分支 + Critic 核心（构造 + evaluate + prompt）
- Day 2：Robustness 测试 + integration 骨架 + Repair 实现
- Day 3：Repair integration 骨架 + 全量 mock 验证 + PR

省下的 1 天作为 buffer：应对 review 反馈、API 端点切换、或主开发联调时的代码调整。

---

## Design intent borrowed from Audio-Oscar (see `docs/intern_b_audio_oscar_why.md`)

1. **"Expected vs Actual" pattern** — feed `segment.text + speaker + expected emotion` as control to Critic
2. **Low temperature (0.1) for stable JSON scoring** (虽然这里由 Qwen3-Omni 服务端控制，我们只在 prompt 里强调"严格 JSON")
3. **JSON parsing robustness** — 3-step fallback (strip ```json fence → json.loads → raw_decode first JSON)
4. **Schema-frozen immutable fields** — code-level enforcement, not just prompt
5. **Serial calls only** — infer_lock makes parallelism unsafe
6. **Parameters merge = original base + LLM overlay**（任务卡 §1.5 允许任意 parameters 字段调整，不需要白名单）

## Pre-conditions (Task 1 verifies)

`main` branch has `src_next/core/data_models.py` (commit `da125ad`) defining `CriticResult` / `ModelSpecificTTSInstruction` / `Segment`. Current branch `feature/collab-xjz` does NOT have these.

---

## Day 1: Branch setup + package skeleton + Critic core

### Task 1: Create working branch from main and verify dependencies

**Files:** No file changes; git operations only.

- [ ] **Step 1: Verify current branch is clean**

Run: `git status`
Expected: shows untracked files only (`docs/`, `intern_b_critic_and_tta.md`, `src_next/profiles/`, `webui_old.py`), no modified tracked files.

- [ ] **Step 2: Stash untracked files temporarily**

```bash
git stash push -u -m "wip: docs and explorations before branching"
```
Expected: `git status` shows clean tree.

- [ ] **Step 3: Create branch from main**

```bash
git fetch origin
git checkout main
git pull origin main
git checkout -b feature/critic-and-tta
```
Expected: now on `feature/critic-and-tta`, with `src_next/core/data_models.py` and `src_next/llm/base.py` present (verify with `ls src_next/core/data_models.py src_next/llm/base.py`).

- [ ] **Step 4: Verify data_models imports work**

Run:
```bash
python -c "from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment; print('OK')"
```
Expected: prints `OK`. If ImportError, do NOT proceed — investigate why main doesn't have these classes.

- [ ] **Step 5: Restore stashed docs**

```bash
git stash pop
```
Expected: `docs/`, `intern_b_critic_and_tta.md`, etc. are back as untracked.

- [ ] **Step 6: Verify pytest is available**

Run: `python -m pytest --version`
Expected: prints `pytest 7.x` or higher. If `ModuleNotFoundError: No module named 'pytest'`, run `pip install pytest` (testing-only dependency, allowed by task card section 3 which forbids only runtime deps like openai SDK).

- [ ] **Step 7: Verify requests is available**

Run: `python -c "import requests; print(requests.__version__)"`
Expected: prints version string. If missing, run `pip install requests`.

---

### Acceptance Criteria (Task 1 — Simplified)

**Pre-conditions:** 无（首个 task）。

**A. coding-Agent Self-check:**
```bash
git branch --show-current                              # → feature/critic-and-tta
ls src_next/core/data_models.py src_next/llm/base.py   # → 两个路径都存在
python -c "from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment; print('OK')"
                                                        # → OK
python -m pytest --version                             # → pytest 7.x 或更高
python -c "import requests; print(requests.__version__)"  # → 版本字符串
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `git log --oneline -5` 显示最近 commit 来自 `origin/main`（分支确实从 main 切出）
- [ ] `docs/`、`intern_b_critic_and_tta.md` 等 untracked 文件存在（说明 `git stash pop` 成功）
- [ ] `feature/collab-xjz` 分支上原本的修改**没有跟过来**（stash 干净）

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 2: Create package skeleton

**Files:**
- Create: `src_next/critic/__init__.py`
- Create: `src_next/critic/prompts/__init__.py`
- Create: `src_next/critic/tests/__init__.py`
- Create: `pytest.ini` (project root)

- [ ] **Step 1: Create the package directories and init files**

Run:
```bash
mkdir -p src_next/critic/prompts src_next/critic/tests
```

Create `src_next/critic/__init__.py`:
```python
"""src_next.critic — Qwen3-Omni 音频评估 + LLM 修复子链路（实习生 B 方向3）。"""
```

Create `src_next/critic/prompts/__init__.py`:
```python
"""src_next.critic.prompts — Critic 评分与 Repair 修复的 prompt 模板。"""
```

Create `src_next/critic/tests/__init__.py`:
```python
"""src_next.critic.tests — Critic + Repair 单元测试。"""
```

- [ ] **Step 2: Create pytest.ini with integration marker**

Create `pytest.ini` at project root:
```ini
[pytest]
markers =
    integration: marks tests that hit real external services (Qwen3-Omni, real LLM). Slow — deselect with -m "not integration".
testpaths = src_next
python_files = test_*.py
addopts = -ra
```

- [ ] **Step 3: Verify pytest discovers nothing yet (sanity)**

Run: `python -m pytest src_next/critic/tests/ -v`
Expected: `no tests ran in 0.0Xs` (the directory is empty).

- [ ] **Step 4: Commit**

```bash
git add src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py pytest.ini
git commit -m "chore(critic): scaffold critic package + pytest config"
```

---

### Acceptance Criteria (Task 2 — Simplified)

**Pre-conditions:** Task 1 已完成（在 `feature/critic-and-tta` 分支上）。

**A. coding-Agent Self-check:**
```bash
ls src_next/critic/__init__.py src_next/critic/prompts/__init__.py src_next/critic/tests/__init__.py pytest.ini
                            # → 4 个路径都存在
python -m pytest src_next/critic/tests/ -v
                            # → "no tests ran in 0.0Xs"
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `cat pytest.ini` 含 `markers =` 和 `integration:` 定义
- [ ] `src_next/critic/__init__.py` 不是空文件（含 docstring `"""src_next.critic ..."""`)
- [ ] `git log --oneline -3` 含 `chore(critic): scaffold critic package + pytest config`

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 3: Write KNOWN_ISSUES.md documenting API risk + service access gap

**Files:**
- Create: `src_next/critic/KNOWN_ISSUES.md`

⚠️ This task replaces the original smoke test (Task 3 in the 4-day plan). Since we can't actually exercise the API, we document the known risks explicitly so future debugging is fast.

- [ ] **Step 1: Create the known-issues doc**

Create `src_next/critic/KNOWN_ISSUES.md`:
```markdown
# Critic 模块已知风险与待办（KNOWN_ISSUES）

> 最后更新：实习生 B 实施期间
> 状态：详见下方各项

## 1. Integration 测试全部 skip（待服务可访问）

**状态：** 已写完整代码骨架，全部用 `@pytest.mark.skip` 标记。

**原因：** 实习生本机无法访问 Qwen3-Omni 服务（`10.50.121.102:8011`）和本地 LLM 服务，无法跑真实 integration。

**运维保证：** 服务存在且正常运行，只是本机访问不到。

**启用方法（服务可访问后）：**
1. 全局搜索 `@pytest.mark.skip(reason="awaiting"`，全部删除
2. 准备 3 段测试音频放服务器可读路径，设置 `CRITIC_FIXTURES_ROOT` 环境变量
3. 准备 LLM profile yaml，设置 `CRITIC_TEST_LLM_PROFILE` 环境变量
4. 跑 `pytest src_next/critic/tests/ -m integration -v`（**不要加 `-n auto`**）

涉及测试：
- `test_qwen3omni_critic.py::test_critic_high_quality_audio_scores_high`
- `test_qwen3omni_critic.py::test_critic_low_quality_audio_scores_low`
- `test_qwen3omni_critic.py::test_critic_sorting_good_higher_than_bad`
- `test_qwen3omni_critic.py::test_critic_emotion_mismatch_scores_low_alignment`
- `test_tts_repair.py::test_repair_with_real_llm_adjusts_parameters`

## 2. API 端点不确定性：`audio_analysis` 是否接受 `text` 字段

**状态：** 按 task card §1.4 原文走 `audio_analysis + text`，但 API 文档（`ussage_guide_qwen3_omni.md` 第 8 节）只列了 `audio / task / return_audio / speaker / max_new_tokens` 五个字段，`text` 未列。

**风险：** Qwen3-Omni 服务可能：
- (a) 接受 `text` 字段并作为 prompt 使用 → task card 设想成立，正常工作
- (b) 忽略 `text` 字段，只按 `task=sound_analysis` 返回通用描述 → critic 拿不到评分 JSON，会触发 neutral 0.5 fallback
- (c) 报 400 错误 → 同样触发 neutral 0.5 fallback

**Fallback 路径（如果 (b) 或 (c) 发生）：**

`src_next/critic/qwen3omni_critic.py` 的 `_evaluate_inner` 方法里，把
```python
url = f"{self.base_url}/v1/omni/audio_analysis"
payload = {
    "audio": audio_path,
    "task": "sound_analysis",
    "text": prompt_text,
    "return_audio": False,
    "max_new_tokens": 1024,
}
```
改成
```python
url = f"{self.base_url}/v1/omni/chat"
payload = {
    "audio": audio_path,
    "text": prompt_text,
    "return_audio": False,
    "max_new_tokens": 1024,
}
```
**只改两行（URL + payload）。** 测试里的 URL 断言也要相应更新（grep `audio_analysis` 找到所有引用）。

`/v1/omni/chat` 文档（ussage_guide 第 3 节）明确支持 `audio + text + return_audio`，response 格式与 `audio_analysis` 一致（`return_audio=false` 时返回 `{"request_id":..., "text":..., "inference_time":...}`）。

## 3. 测试音频 fixture 未实际准备

**状态：** `conftest.py` 里的 `good_narration_wav` 等 fixture 只解析路径，不验证文件存在。

**原因：** 服务不可访问时准备 fixture 没意义（测试都 skip）。

**准备方法（服务可访问后）：**
1. 用现有 TTS pipeline 生成 3 段 5-10s wav（好/坏/情感不匹配）
2. 放到服务器可读路径，或设置 `CRITIC_FIXTURES_ROOT` 环境变量
3. 路径解析逻辑见 `conftest.py::_audio_path`
```

- [ ] **Step 2: Commit**

```bash
git add src_next/critic/KNOWN_ISSUES.md
git commit -m "docs(critic): document API risk + integration test gap"
```

---

### Acceptance Criteria (Task 3 — Simplified)

**Pre-conditions:** Task 2 已完成。

**A. coding-Agent Self-check:**
```bash
test -f src_next/critic/KNOWN_ISSUES.md && echo OK   # → OK
grep -c "^## " src_next/critic/KNOWN_ISSUES.md       # → 3（三个章节）
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] §1 含启用步骤说明（搜索 `@pytest.mark.skip(reason="awaiting"`，提供 `CRITIC_FIXTURES_ROOT` / `CRITIC_TEST_LLM_PROFILE` 环境变量）
- [ ] §2 含 fallback 代码块（明确指出 `audio_analysis` → `chat` 的两行改动 + URL 切换）
- [ ] §3 含 fixture 准备方法（生成 3 段 5-10s wav，放到 fixture 路径）
- [ ] `git log --oneline -3` 含 `docs(critic): document API risk + integration test gap`

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 4: Write failing test for Qwen3OmniCritic construction

**Files:**
- Create: `src_next/critic/tests/test_qwen3omni_critic.py`

- [ ] **Step 1: Write the failing construction test**

Create `src_next/critic/tests/test_qwen3omni_critic.py`:
```python
"""Qwen3OmniCritic unit tests.

Integration tests (real Qwen3-Omni service) are written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness tests run by default.
"""
from __future__ import annotations

import pytest

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


def test_critic_can_be_constructed_with_defaults():
    """Qwen3OmniCritic should construct with the documented default base_url."""
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic

    critic = Qwen3OmniCritic()
    assert critic.base_url == "http://10.50.121.102:8011"
    assert critic.timeout == 120
    assert critic.bypass_proxy is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v`
Expected: FAIL with `ImportError: cannot import name 'Qwen3OmniCritic' from 'src_next.critic.qwen3omni_critic'`.

- [ ] **Step 3: Write minimal implementation**

Create `src_next/critic/qwen3omni_critic.py`:
```python
"""Qwen3-Omni 音频评估客户端。

调 Qwen3-Omni 服务的 /v1/omni/audio_analysis 端点（黄区 10.50.121.102:8011），
让模型"听"一段 TTS 合成音频，输出 5 维评分 + 修复建议。

⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。

⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
如果服务返回的不是评分 JSON，按 KNOWN_ISSUES.md §2 切换到 /v1/omni/chat。
"""
from __future__ import annotations

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


class Qwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频质量。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        timeout: int = 120,
        bypass_proxy: bool = True,
    ) -> None:
        """
        Args:
            base_url: Qwen3-Omni 服务地址（默认黄区 8011）。
            timeout: 单次评估超时（秒）。Qwen3-Omni 单请求较慢，建议 120s+。
            bypass_proxy: 是否绕过系统代理（黄区内网 true）。
        """
        self.base_url = base_url
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src_next/critic/qwen3omni_critic.py src_next/critic/tests/test_qwen3omni_critic.py
git commit -m "feat(critic): add Qwen3OmniCritic skeleton with construction test"
```

---

### Acceptance Criteria (Task 4 — Simplified)

**Pre-conditions:** Task 3 已完成。

**A. coding-Agent Self-check:**
```bash
test -f src_next/critic/qwen3omni_critic.py && test -f src_next/critic/tests/test_qwen3omni_critic.py && echo OK
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_can_be_constructed_with_defaults -v
                            # → 1 passed
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `qwen3omni_critic.py` 的 `__init__` 默认参数：`base_url="http://10.50.121.102:8011"`, `timeout=120`, `bypass_proxy=True`
- [ ] 模块顶部 docstring 含「infer_lock」+「API 风险」两点警告（不为空）
- [ ] **此时还没有 `evaluate()` 方法**（Task 5 才加），如果有则说明越界提前实现
- [ ] `git log --oneline -5` 含 `feat(critic): add Qwen3OmniCritic skeleton with construction test`

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 5: Write failing test for evaluate happy path + implement core (mocked)

**Files:**
- Modify: `src_next/critic/tests/test_qwen3omni_critic.py`
- Modify: `src_next/critic/qwen3omni_critic.py`

- [ ] **Step 1: Write failing test for happy path (mocked HTTP)**

Append to `src_next/critic/tests/test_qwen3omni_critic.py`:
```python
def _make_segment_and_instruction():
    seg = Segment(
        segment_id="s1",
        text="窗外下着大雨。",
        speaker="narrator",
        segment_type="narration",
        raw_index=0,
    )
    inst = ModelSpecificTTSInstruction(
        segment_id="s1",
        speaker="narrator",
        text="窗外下着大雨。",
        model="S2Pro",
        parameters={"instruction": "平稳叙述，略带忧伤"},
    )
    return seg, inst


class _FakeOkResponse:
    """Minimal stand-in for requests.Response — 200 with valid scoring JSON."""
    status_code = 200

    def json(self):
        return {
            "request_id": "fake-req-1",
            "text": (
                '{"quality":0.85,"emotion_alignment":0.80,'
                '"character_consistency":0.90,"rhythm_naturalness":0.82,'
                '"intelligibility":0.95,'
                '"suggestions":"音质清晰，情感表达可再增强一些。"}'
            ),
        }

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


def test_evaluate_returns_critic_result_on_success(monkeypatch):
    """Mock 200 + valid scoring JSON → CriticResult with parsed scores."""
    import src_next.critic.qwen3omni_critic as mod

    captured = {}

    def fake_post(url, json=None, proxies=None, timeout=None, **kw):
        captured["url"] = url
        captured["json"] = json
        captured["proxies"] = proxies
        captured["timeout"] = timeout
        return _FakeOkResponse()

    monkeypatch.setattr(mod.requests, "post", fake_post)

    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic()
    seg, inst = _make_segment_and_instruction()

    result = critic.evaluate("/fake/path.wav", seg, inst)

    # Verify HTTP call shape
    assert captured["url"] == "http://10.50.121.102:8011/v1/omni/audio_analysis"
    assert captured["json"]["audio"] == "/fake/path.wav"
    assert captured["json"]["task"] == "sound_analysis"
    assert "text" in captured["json"]  # scoring prompt
    assert captured["proxies"] == {"http": None, "https": None}

    # Verify returned CriticResult
    assert result.segment_id == "s1"
    assert 0.84 <= result.quality <= 0.86  # parsed from JSON
    assert 0.94 <= result.intelligibility <= 0.96
    assert 0.0 <= result.overall <= 1.0
    assert isinstance(result.suggestions, str)
    assert result.suggestions  # non-empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v`
Expected: FAIL with `AttributeError: 'Qwen3OmniCritic' object has no attribute 'evaluate'`.

- [ ] **Step 3: Implement evaluate — happy path only**

Replace the body of `src_next/critic/qwen3omni_critic.py` with:
```python
"""Qwen3-Omni 音频评估客户端。

调 Qwen3-Omni 服务的 /v1/omni/audio_analysis 端点（黄区 10.50.121.102:8011），
让模型"听"一段 TTS 合成音频，输出 5 维评分 + 修复建议。

⚠️ 服务端有 infer_lock，同一时间只处理一个请求——本客户端不做并发，
上层 pipeline 必须串行调用（不要用 ThreadPoolExecutor 包 evaluate）。

⚠️ API 风险：task card 推荐 audio_analysis + text 字段，但 API 文档未明确支持 text。
如果服务返回的不是评分 JSON，按 KNOWN_ISSUES.md §2 切换到 /v1/omni/chat。
"""
from __future__ import annotations

import json
import re

import requests

from src_next.critic.prompts.critic_prompt import build_critic_prompt
from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)


def _strip_code_fence(raw: str) -> str:
    """Strip leading/trailing ```json ... ``` fences if present."""
    return _CODE_FENCE_RE.sub("", raw.strip())


def _extract_first_json(raw: str) -> dict | None:
    """Find the first balanced {...} block in raw using raw_decode. Returns None if not found."""
    decoder = json.JSONDecoder()
    s = raw.strip()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = decoder.raw_decode(s[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def _parse_scoring_json(raw_text: str) -> dict:
    """Parse Qwen3-Omni's response text into a scoring dict.

    Three-step fallback (borrowed from Audio-Oscar's parse_llm_json_payload):
      1. Strip ```json fences
      2. Try json.loads directly
      3. Fall back to raw_decode scanning for first {...}

    Raises ValueError if no JSON object can be extracted.
    """
    cleaned = _strip_code_fence(raw_text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    obj = _extract_first_json(cleaned)
    if obj is None:
        raise ValueError(f"no JSON object found in response: {raw_text[:200]!r}")
    return obj


class Qwen3OmniCritic:
    """用 Qwen3-Omni 多模态模型评估单段音频质量。"""

    def __init__(
        self,
        base_url: str = "http://10.50.121.102:8011",
        timeout: int = 120,
        bypass_proxy: bool = True,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.bypass_proxy = bypass_proxy
        self._proxies = {"http": None, "https": None} if bypass_proxy else None

    def evaluate(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
    ) -> CriticResult:
        """评估单段音频。失败不抛异常，返回 overall=0.5 中性结果。"""
        try:
            return self._evaluate_inner(audio_path, segment, tts_instruction)
        except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback
            return self._neutral_result(segment.segment_id, tts_instruction.attempt, str(exc))

    def _evaluate_inner(
        self,
        audio_path: str,
        segment: Segment,
        tts_instruction: ModelSpecificTTSInstruction,
    ) -> CriticResult:
        prompt_text = build_critic_prompt(segment, tts_instruction)
        payload = {
            "audio": audio_path,
            "task": "sound_analysis",
            "text": prompt_text,
            "return_audio": False,
            "max_new_tokens": 1024,
        }
        url = f"{self.base_url}/v1/omni/audio_analysis"
        resp = requests.post(
            url,
            json=payload,
            proxies=self._proxies,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"audio_analysis returned HTTP {resp.status_code}: {resp.text[:200]!r}"
            )
        data = resp.json()
        raw_text = str(data.get("text", ""))
        if not raw_text:
            raise RuntimeError("audio_analysis returned empty text field")
        scoring = _parse_scoring_json(raw_text)
        scoring["segment_id"] = segment.segment_id
        scoring["attempt"] = tts_instruction.attempt
        return CriticResult.from_json(scoring, attempt=tts_instruction.attempt)

    @staticmethod
    def _neutral_result(segment_id: str, attempt: int, err_msg: str) -> CriticResult:
        """Neutral 0.5 fallback when evaluation fails — per task card §1.3.1.

        Note: deliberately 0.5 (not 0.0 like Audio-Oscar) so that transient
        failures (network blips) don't force unnecessary repair cascades.
        """
        return CriticResult(
            segment_id=segment_id,
            quality=0.5,
            emotion_alignment=0.5,
            character_consistency=0.5,
            rhythm_naturalness=0.5,
            intelligibility=0.5,
            overall=0.5,
            suggestions=f"评估失败：{err_msg}，建议人工复核",
            attempt=attempt,
        )
```

- [ ] **Step 4: Run test — expect ImportError on `build_critic_prompt`**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v`
Expected: FAIL with `ImportError: cannot import name 'build_critic_prompt' from 'src_next.critic.prompts.critic_prompt'`.

This is the next task's dependency. Proceed to Task 6.

---

### Acceptance Criteria (Task 5 — Full)

**Pre-conditions:** Task 4 已合并（`Qwen3OmniCritic` 类已存在，含构造方法）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- `src_next/critic/qwen3omni_critic.py` 含 `Qwen3OmniCritic.evaluate()` 方法
- 签名: `evaluate(audio_path: str, segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> CriticResult`
- 私有方法 `_evaluate_inner` / `_neutral_result` 已存在

**Self-check 命令（本机可跑，无需服务）:**
```bash
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v
                            # → 1 passed
```

**契约:**
- `evaluate()` 任何异常都不外抛（catch-all → neutral fallback）
- `_neutral_result` 返回 `overall=0.5`（**不是 0.0**）
- HTTP 走 `/v1/omni/audio_analysis`，payload 含 `task=sound_analysis` + `text` 字段
- `proxies={"http": None, "https": None}`（bypass_proxy=True 时）

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试全绿（任何环境都能跑）
python -m pytest src_next/critic/tests/ -m "not integration" -v
# 期望: 至少 1 passed（含 test_evaluate_returns_critic_result_on_success）

# 2. 端到端 smoke（judge 自写脚本，绕过 pytest 直接验证 API；服务可用时跑）
python -c "
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction
critic = Qwen3OmniCritic()
seg = Segment(segment_id='smoke', text='测试', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='smoke', speaker='narrator', text='测试', model='S2Pro', parameters={'instruction':'平稳叙述'}, attempt=1)
r = critic.evaluate('<CRITIC_FIXTURES_ROOT>/good_narration.wav', seg, inst)
print(f'quality={r.quality}, overall={r.overall}, suggestions={r.suggestions!r}')
assert r.quality > 0.5, f'good audio scored too low: {r.quality}'
"
# 期望: 打印数值，quality > 0.5，无 exception

# 3. 失败兜底 smoke（喂不存在的音频 → 验证 neutral fallback）
python -c "
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction
critic = Qwen3OmniCritic()
seg = Segment(segment_id='smoke', text='测试', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='smoke', speaker='narrator', text='测试', model='S2Pro', parameters={'instruction':'平稳叙述'}, attempt=1)
r = critic.evaluate('/nonexistent.wav', seg, inst)
assert r.overall == 0.5, f'failure should return neutral 0.5, got {r.overall}'
print('neutral fallback OK')
"
# 期望: r.overall == 0.5（验证不抛异常 + neutral fallback 正确）
```

**静态审查点（LLM 读代码判断）:**
- [ ] `_parse_scoring_json` 三步兜底完整（剥 fence → json.loads → raw_decode 扫描）
- [ ] `try/except Exception` 范围合理（不是裸 `except:`，不是只 catch 一种）
- [ ] 未引入未要求的依赖（只用 `requests` + 项目内已有模块）
- [ ] 没有提前实现 repair agent 的逻辑（Task 11 才做）

**Red flags（任一出现即 FAIL）:**
- `evaluate()` 抛了未捕获异常
- neutral fallback 返回 `0.0` 而非 `0.5`
- mock 测试里有真实网络调用（`_FakeOkResponse` 之外不应联网）
- `_evaluate_inner` 直接信任 `tts_instruction.text` 作为评分输入（应该是 schema-frozen）

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

---

### Task 6: Write critic_prompt module + complete evaluate test

**Files:**
- Create: `src_next/critic/prompts/critic_prompt.py`
- Modify: `src_next/critic/tests/test_qwen3omni_critic.py` (add prompt test)

- [ ] **Step 1: Write failing test for the prompt builder**

Append to `src_next/critic/tests/test_qwen3omni_critic.py`:
```python
def test_critic_prompt_includes_expected_vs_actual_context():
    """Prompt must contain original text, speaker, expected emotion, and 5-dim schema."""
    from src_next.critic.prompts.critic_prompt import build_critic_prompt

    seg, inst = _make_segment_and_instruction()
    prompt = build_critic_prompt(seg, inst)

    # Expected vs Actual pattern (Audio-Oscar §B.14)
    assert "窗外下着大雨" in prompt  # original text
    assert "narrator" in prompt  # speaker
    assert "平稳叙述" in prompt  # expected emotion from parameters

    # 5 dimensions (task card §1.3.1)
    for dim in ("quality", "emotion_alignment", "character_consistency",
                "rhythm_naturalness", "intelligibility"):
        assert dim in prompt

    # Strict JSON schema embedded (Audio-Oscar §7.2)
    assert "suggestions" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_critic_prompt_includes_expected_vs_actual_context -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'`.

- [ ] **Step 3: Implement the prompt builder**

Create `src_next/critic/prompts/critic_prompt.py`:
```python
"""Critic 评分 prompt 模板。

设计要点（参考 Audio-Oscar §B.6-B.14 + 任务卡 §1.4）：
1. "Expected vs Actual" 对照——把 segment.text / speaker / 期望情感喂给 critic
2. 5 维评分针对 TTS 场景定制（不是 Oscar 的 3 维）
3. 嵌入严格 JSON schema 示例，比抽象描述稳定得多
4. suggestions 限制为中文一句话，避免 repair LLM 信息过载
5. 强调"不要画蛇添足"——只能给修复 parameters 的建议，不能加新内容
"""
from __future__ import annotations

from src_next.core.data_models import ModelSpecificTTSInstruction, Segment


_CRITIC_PROMPT_TEMPLATE = """请仔细听这段 TTS 合成音频，并对照以下信息评分。

## 原文
{text}

## 期望表现
- 说话人: {speaker}
- 段类型: {segment_type}
- TTS 模型: {model}
- 期望情感 / 风格: {expected_emotion}
- 期望语速: {expected_speed}

## 评分维度（每项 0.0-1.0，浮点数保留 2 位）
1. quality: 音质清晰度（有无杂音、截断、失真、爆音）
2. emotion_alignment: 情感是否与"期望情感 / 风格"一致
3. character_consistency: 声音特征是否符合 {speaker} 的角色设定
4. rhythm_naturalness: 语速、停顿、语调是否自然
5. intelligibility: 文本内容是否清晰可辨、有无吞字或含糊

## 建议规则（重要）
- 建议必须只针对 **parameters 字段（如 instruction / speed / emotion_vector）的调整**。
- **绝对不要**建议修改原文 text、speaker、model 或换参考音频——这些字段由上游契约锁定。
- **绝对不要**建议加入新的背景音、音效、配乐——这是语音段，不是音效段。
- 建议用一句中文表达，聚焦最高优先级的 1-2 个问题。

## 输出格式
**只输出严格的 JSON**，不要加任何 markdown 标记、解释性文字或代码块：
{{"quality":0.85,"emotion_alignment":0.80,"character_consistency":0.90,"rhythm_naturalness":0.82,"intelligibility":0.95,"suggestions":"建议内容"}}
"""


def _extract_expected_emotion(parameters: dict) -> str:
    """CosyVoice3 用 instruct_text，S2Pro 用 instruction，IndexTTS 用 emotion_vector。"""
    for key in ("instruct_text", "instruction", "emotion", "emotion_vector", "style"):
        v = parameters.get(key)
        if v:
            return str(v)
    return "未指定"


def _extract_expected_speed(parameters: dict) -> str:
    speed = parameters.get("speed")
    if speed is None:
        return "未指定（用模型默认）"
    return str(speed)


def build_critic_prompt(
    segment: Segment,
    tts_instruction: ModelSpecificTTSInstruction,
) -> str:
    """Build the scoring prompt for audio_analysis's text field.

    Embeds original text + speaker + expected emotion as the "expected" side of the
    Audio-Oscar "Expected vs Actual" pattern, so the Critic can do semantic alignment.
    """
    return _CRITIC_PROMPT_TEMPLATE.format(
        text=segment.text,
        speaker=segment.speaker,
        segment_type=segment.segment_type,
        model=tts_instruction.model,
        expected_emotion=_extract_expected_emotion(tts_instruction.parameters),
        expected_speed=_extract_expected_speed(tts_instruction.parameters),
    )
```

- [ ] **Step 4: Run all critic tests so far — should all pass**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v`
Expected: 3 tests PASS (construction, evaluate success path, prompt structure).

- [ ] **Step 5: Commit**

```bash
git add src_next/critic/prompts/critic_prompt.py src_next/critic/qwen3omni_critic.py src_next/critic/tests/test_qwen3omni_critic.py
git commit -m "feat(critic): implement evaluate happy path + neutral fallback + prompt builder"
```

---

### Acceptance Criteria (Task 6 — Full)

**Pre-conditions:** Task 5 已完成（`evaluate()` 实现 + neutral fallback 就绪）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- `src_next/critic/prompts/critic_prompt.py` 含 `build_critic_prompt(segment, tts_instruction) -> str`
- 测试 `test_critic_prompt_includes_expected_vs_actual_context` 通过

**Self-check 命令（本机可跑）:**
```bash
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
                            # → 3 passed（construction + evaluate success + prompt structure）
```

**契约:**
- prompt 必须含 `segment.text` / `segment.speaker` / 期望情感（从 `parameters.instruction` 等字段提取）
- prompt 必须列出 5 个评分维度（quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility）
- prompt 必须含 `suggestions` 字段说明
- prompt 强调「只输出严格 JSON」

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试全绿
python -m pytest src_next/critic/tests/ -m "not integration" -v
# 期望: 至少 3 passed

# 2. Prompt smoke（服务可用时，发一段真实评分请求看 prompt 是否被 Qwen3-Omni 接受）
python -c "
from src_next.critic.prompts.critic_prompt import build_critic_prompt
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction
seg = Segment(segment_id='smoke', text='窗外下着大雨。', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='smoke', speaker='narrator', text='窗外下着大雨。', model='S2Pro', parameters={'instruction':'平稳叙述'}, attempt=1)
p = build_critic_prompt(seg, inst)
print(p)
# 人工/judge 检查：含 5 维 + JSON schema + 期望情感 + 原文
"
```

**静态审查点（LLM 读代码判断）:**
- [ ] prompt 模板含「Expected vs Actual」pattern（原文 + speaker + 期望情感都进 prompt）
- [ ] 5 维度定义与任务卡 §1.3.1 完全一致（命名、顺序）
- [ ] `_extract_expected_emotion` 兼容多种 parameters key（`instruct_text` / `instruction` / `emotion` / `emotion_vector` / `style`）
- [ ] suggestions 规则段含「绝对不要建议修改原文/speaker/model/voice_ref」的硬约束

**Red flags（任一出现即 FAIL）:**
- prompt 把 `text` / `speaker` / `model` 当成 LLM 可改的字段（应明确锁定）
- 维度命名漂移（如把 `character_consistency` 写成 `character_consistent`）
- 模板里 `{speaker}` 这种 format placeholder 没正确转义（如 JSON schema 示例里的 `{{` `}}` 漏写）
- prompt 长度异常（>3000 字符或 <200 字符）

#### C. Pass 条件 + 输出

A 全绿 + B mock 命令绿 + B smoke 命令绿（服务可用时）+ 静态审查无 red flag → **PASS**

judge-Agent 输出 schema 同 Task 5（`integration_tests: SKIPPED`，`smoke_tests` 视情况）。

---

## Day 2: Robustness + integration skeletons + Repair agent

### Task 7: Write conftest.py with fixtures

**Files:**
- Create: `src_next/critic/tests/conftest.py`

- [ ] **Step 1: Write conftest with fixtures**

Create `src_next/critic/tests/conftest.py`:
```python
"""Pytest fixtures for Qwen3OmniCritic integration tests.

⚠️ Integration tests must run SERIALLY (no -n auto / no pytest-xdist) because
Qwen3-Omni service has an infer_lock — concurrent requests will queue and timeout.

⚠️ Integration tests are skip-marked by default — see KNOWN_ISSUES.md.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def real_critic():
    """Real Qwen3OmniCritic pointing at the yellow-zone service. Session-scoped to amortize."""
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    return Qwen3OmniCritic(base_url="http://10.50.121.102:8011")


def _audio_path(filename: str) -> str:
    """Resolve a fixture audio path. Server-side override via env var."""
    root = os.environ.get("CRITIC_FIXTURES_ROOT")
    if root:
        # Server-side absolute path (e.g., /data/.../critic-fixtures/good_narration.wav)
        return str(Path(root) / filename)
    # Local fallback — only works if you're on the same host as the Qwen3-Omni service
    return str(FIXTURES_DIR / filename)


@pytest.fixture(scope="session")
def good_narration_wav():
    return _audio_path("good_narration.wav")


@pytest.fixture(scope="session")
def bad_clipping_wav():
    return _audio_path("bad_clipping.wav")


@pytest.fixture(scope="session")
def emotion_mismatch_wav():
    return _audio_path("emotion_mismatch.wav")


@pytest.fixture(scope="session")
def real_llm():
    """Real LLM client via the project's standard profile mechanism.

    Skips if no profile is available (CI without LLM access).
    See KNOWN_ISSUES.md §1 for activation steps.
    """
    try:
        from src_next.llm.qwen_http import QwenHTTPClient  # noqa: F401
    except ImportError:
        pytest.skip("LLM backend not importable — skipping integration test")

    profile_path = os.environ.get("CRITIC_TEST_LLM_PROFILE")
    if not profile_path:
        pytest.skip("CRITIC_TEST_LLM_PROFILE env var not set — skipping real-LLM integration test")

    # Lazy import — only needed when actually running
    import yaml
    from src_next.llm.qwen_http import QwenHTTPClient
    from src_next.llm.gemma4_http import Gemma4HTTPClient

    with open(profile_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    llm_cfg = cfg.get("llm", cfg)
    backend = llm_cfg.get("type", "qwen_http").lower()
    if backend in ("gemma4", "gemma4_http"):
        return Gemma4HTTPClient(base_url=llm_cfg["base_url"])
    return QwenHTTPClient(base_url=llm_cfg["base_url"])
```

- [ ] **Step 2: Verify conftest loads**

Run: `python -m pytest src_next/critic/tests/ --collect-only -q`
Expected: lists existing 3 tests, no errors.

- [ ] **Step 3: Commit**

```bash
git add src_next/critic/tests/conftest.py
git commit -m "test(critic): add conftest with real_critic + audio path + real_llm fixtures"
```

---

### Acceptance Criteria (Task 7 — Simplified)

**Pre-conditions:** Task 6 已完成。

**A. coding-Agent Self-check:**
```bash
test -f src_next/critic/tests/conftest.py && echo OK
python -m pytest src_next/critic/tests/ --collect-only -q
                            # → 列出现有 3 个测试，无 collection error
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `conftest.py` 含 5 个 fixture：`real_critic` / `good_narration_wav` / `bad_clipping_wav` / `emotion_mismatch_wav` / `real_llm`
- [ ] `_audio_path()` 函数读取 `CRITIC_FIXTURES_ROOT` 环境变量，未设置时 fallback 到本地 `FIXTURES_DIR`
- [ ] `real_llm` fixture 含 `pytest.skip(...)` 分支（profile 找不到时优雅 skip 而非抛错）
- [ ] 模块 docstring 含「integration 测试必须 serially（不要 -n auto）」警告
- [ ] `git log --oneline -3` 含 `test(critic): add conftest with real_critic + audio path + real_llm fixtures`

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 8: Write robustness tests for HTTP failure modes (mock)

**Files:**
- Modify: `src_next/critic/tests/test_qwen3omni_critic.py`

- [ ] **Step 1: Write failing tests for HTTP 500, non-JSON, empty text, request exception**

Append to `src_next/critic/tests/test_qwen3omni_critic.py`:
```python
class _FakeHttp500Response:
    status_code = 500
    text = "internal server error"

    def json(self):
        raise ValueError("not JSON")


class _FakeJsonBadResponse:
    """200 but body is plain text, no JSON extractable."""
    status_code = 200

    def json(self):
        return {"text": "Sorry, I cannot evaluate this audio."}

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


class _FakeEmptyTextFieldResponse:
    """200 but text field is empty string."""
    status_code = 200

    def json(self):
        return {"text": ""}

    @property
    def text(self):
        import json as _json
        return _json.dumps(self.json())


def _patch_post(monkeypatch, response_obj):
    import src_next.critic.qwen3omni_critic as mod
    def fake_post(*a, **kw):
        return response_obj()
    monkeypatch.setattr(mod.requests, "post", fake_post)


def test_evaluate_http_500_returns_neutral(monkeypatch):
    """500 error → neutral 0.5 result, no exception."""
    _patch_post(monkeypatch, _FakeHttp500Response)
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic(base_url="http://fake")
    seg, inst = _make_segment_and_instruction()
    result = critic.evaluate("/nonexistent.wav", seg, inst)
    assert result.overall == 0.5
    for v in (result.quality, result.emotion_alignment, result.character_consistency,
              result.rhythm_naturalness, result.intelligibility):
        assert v == 0.5
    assert ("失败" in result.suggestions
            or "error" in result.suggestions.lower()
            or "500" in result.suggestions)


def test_evaluate_non_json_text_returns_neutral(monkeypatch):
    """200 but text is plain English with no JSON → neutral fallback."""
    _patch_post(monkeypatch, _FakeJsonBadResponse)
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic(base_url="http://fake")
    seg, inst = _make_segment_and_instruction()
    result = critic.evaluate("/x.wav", seg, inst)
    assert result.overall == 0.5


def test_evaluate_empty_text_field_returns_neutral(monkeypatch):
    """200 but text field is empty → neutral fallback."""
    _patch_post(monkeypatch, _FakeEmptyTextFieldResponse)
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic(base_url="http://fake")
    seg, inst = _make_segment_and_instruction()
    result = critic.evaluate("/x.wav", seg, inst)
    assert result.overall == 0.5


def test_evaluate_request_exception_returns_neutral(monkeypatch):
    """requests.post raises (e.g., connection refused / timeout) → neutral fallback."""
    import src_next.critic.qwen3omni_critic as mod

    def raising_post(*a, **kw):
        raise mod.requests.exceptions.ConnectTimeout("simulated timeout")

    monkeypatch.setattr(mod.requests, "post", raising_post)
    from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
    critic = Qwen3OmniCritic(base_url="http://fake")
    seg, inst = _make_segment_and_instruction()
    result = critic.evaluate("/x.wav", seg, inst)
    assert result.overall == 0.5
    assert ("失败" in result.suggestions
            or "error" in result.suggestions.lower()
            or "timeout" in result.suggestions.lower())
```

- [ ] **Step 2: Run all robustness tests — should pass (Task 5 already implemented neutral fallback)**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v`
Expected: 7 tests PASS (construction, evaluate success, prompt structure + 4 robustness).

- [ ] **Step 3: Commit**

```bash
git add src_next/critic/tests/test_qwen3omni_critic.py
git commit -m "test(critic): add 4 robustness tests for HTTP failure modes"
```

---

### Acceptance Criteria (Task 8 — Full)

**Pre-conditions:** Task 7 已完成（conftest 可加载）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- 4 个新测试：`test_evaluate_http_500_returns_neutral` / `test_evaluate_non_json_text_returns_neutral` / `test_evaluate_empty_text_field_returns_neutral` / `test_evaluate_request_exception_returns_neutral`
- 4 个 fake response 类：`_FakeHttp500Response` / `_FakeJsonBadResponse` / `_FakeEmptyTextFieldResponse`

**Self-check 命令（本机可跑）:**
```bash
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
                            # → 7 passed（construction + evaluate success + prompt + 4 robustness）
```

**契约:**
- 每个失败场景都断言 `result.overall == 0.5`
- mock 用 `monkeypatch.setattr(mod.requests, "post", ...)`，不真联网

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试全绿
python -m pytest src_next/critic/tests/ -m "not integration" -v
# 期望: 7 passed

# 2. Robustness smoke（服务可用时，制造真实失败场景）
# 2a. 喂不存在的 base_url 触发 ConnectError
python -c "
from src_next.critic.qwen3omni_critic import Qwen3OmniCritic
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction
critic = Qwen3OmniCritic(base_url='http://127.0.0.1:1')  # 不可达端口
seg = Segment(segment_id='s', text='t', speaker='n', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='s', speaker='n', text='t', model='S2Pro', parameters={}, attempt=1)
r = critic.evaluate('/any.wav', seg, inst)
assert r.overall == 0.5, f'connection failure should fall to neutral, got {r.overall}'
print('connection-fail fallback OK')
"
```

**静态审查点（LLM 读代码判断）:**
- [ ] 4 个测试覆盖 4 种**正交**失败模式（HTTP 500 / 200+非 JSON / 200+空 text / 网络异常），无重复
- [ ] 每个测试的 fake response 实现了 `status_code` + `text` 属性 + `json()` 方法（避免 AttributeError）
- [ ] `_patch_post` 辅助函数复用，不重复 monkey patch 模板
- [ ] 断言除了 `overall == 0.5` 还检查了 `suggestions` 含错误信息（部分测试）

**Red flags（任一出现即 FAIL）:**
- 任一 robustness 测试用真实 HTTP 调用（应该全部 mock）
- 断言写错（如 `assert result.overall != 0.5`）
- 4 个测试覆盖的是同一种失败模式（如都是 500）
- mock 范围过宽（如 monkey patch 整个 `requests` 模块）

#### C. Pass 条件 + 输出

A 全绿 + B mock 命令绿 + B smoke 命令绿（服务可用时）+ 静态审查无 red flag → **PASS**

judge-Agent 输出 schema 同 Task 5（`integration_tests: SKIPPED`）。

---

### Task 9: Write integration test skeletons (skip-marked, ready for future activation)

**Files:**
- Modify: `src_next/critic/tests/test_qwen3omni_critic.py`

⚠️ These tests are written exactly as if the service were available, but skip-marked. When service access is granted, removing the `@pytest.mark.skip` lines is the only change needed.

- [ ] **Step 1: Add skip-marked integration tests for all 3 cases + sorting**

Append to `src_next/critic/tests/test_qwen3omni_critic.py`:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — skip-marked. See KNOWN_ISSUES.md §1 to activate.
# ─────────────────────────────────────────────────────────────────────────────

_INTEGRATION_SKIP_REASON = (
    "awaiting Qwen3-Omni service access — see src_next/critic/KNOWN_ISSUES.md §1"
)


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_critic_high_quality_audio_scores_high(real_critic, good_narration_wav):
    """Integration: good_narration.wav should get all 5 dims >= 0.7."""
    seg, inst = _make_segment_and_instruction()
    inst.parameters = {"instruction": "平稳叙述"}

    result = real_critic.evaluate(good_narration_wav, seg, inst)

    assert result.segment_id == "s1"
    assert 0.0 <= result.quality <= 1.0
    assert 0.0 <= result.overall <= 1.0
    assert result.quality >= 0.7, f"quality too low for good audio: {result.quality}"
    assert result.intelligibility >= 0.7, f"intelligibility too low: {result.intelligibility}"
    assert isinstance(result.suggestions, str)


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_critic_low_quality_audio_scores_low(real_critic, bad_clipping_wav):
    """Integration: bad_clipping.wav should get quality < 0.6."""
    seg, inst = _make_segment_and_instruction()
    result = real_critic.evaluate(bad_clipping_wav, seg, inst)
    assert result.quality < 0.6, f"quality too high for bad audio: {result.quality}"


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_critic_sorting_good_higher_than_bad(real_critic, good_narration_wav, bad_clipping_wav):
    """Integration: relative ordering is more stable than absolute values.

    Good audio's quality MUST be higher than bad audio's quality. This sidesteps
    LLM scoring drift (a 0.05 wiggle is OK as long as relative order holds).
    """
    seg, inst = _make_segment_and_instruction()

    good_result = real_critic.evaluate(good_narration_wav, seg, inst)
    bad_result = real_critic.evaluate(bad_clipping_wav, seg, inst)

    assert good_result.quality > bad_result.quality, (
        f"sorting violated: good={good_result.quality} <= bad={bad_result.quality}"
    )
    assert good_result.overall > bad_result.overall


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_critic_emotion_mismatch_scores_low_alignment(real_critic, emotion_mismatch_wav):
    """Integration: neutral-tone audio scored against 'sad' expected → emotion_alignment < 0.6."""
    seg, inst = _make_segment_and_instruction()
    inst.parameters = {"instruction": "极度悲伤，哭泣感"}

    result = real_critic.evaluate(emotion_mismatch_wav, seg, inst)

    assert result.emotion_alignment < 0.6, (
        f"emotion_alignment too high for mismatched audio: {result.emotion_alignment}"
    )
```

- [ ] **Step 2: Verify the tests collect and are skip-marked (not failed)**

Run: `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v`
Expected: 7 PASS + 4 SKIPPED. The 4 skipped tests should show the `_INTEGRATION_SKIP_REASON`.

- [ ] **Step 3: Commit**

```bash
git add src_next/critic/tests/test_qwen3omni_critic.py
git commit -m "test(critic): add 4 integration test skeletons (skip-marked, pending service access)"
```

---

### Acceptance Criteria (Task 9 — Full)

**Pre-conditions:** Task 8 已完成（critic mock 测试全绿）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- 4 个 skip-marked integration 测试：`test_critic_high_quality_audio_scores_high` / `test_critic_low_quality_audio_scores_low` / `test_critic_sorting_good_higher_than_bad` / `test_critic_emotion_mismatch_scores_low_alignment`
- 共享常量 `_INTEGRATION_SKIP_REASON` 提取出来，不重复硬编码

**Self-check 命令（本机可跑）:**
```bash
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v
                            # → 7 passed + 4 skipped（SKIPPED 不是 FAILED）
python -m pytest src_next/critic/tests/ -m integration -v
                            # → 4 skipped（确认全部 skip，没有意外 FAIL）
```

**契约:**
- 每个 integration 测试同时有 `@pytest.mark.integration` **和** `@pytest.mark.skip(reason=...)` 两个装饰器
- skip reason 文字与 KNOWN_ISSUES.md §1 启用条件互相引用

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Skip 状态确认（任何环境都能跑）
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -m integration -v
# 期望: 4 skipped，0 failed

# 2. 启用 integration 测试（judge 操作）
#    全局搜索 `@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)` 并删除该行
grep -n "_INTEGRATION_SKIP_REASON" src_next/critic/tests/test_qwen3omni_critic.py
# → 显示所有要删的行

# 3. 删除 skip 装饰器后跑（需要服务可用 + 3 个 fixture 音频）
python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -m integration -v
# 期望: 4 passed
#    - test_critic_high_quality_audio_scores_high: quality >= 0.7
#    - test_critic_low_quality_audio_scores_low: quality < 0.6
#    - test_critic_sorting_good_higher_than_bad: good.quality > bad.quality
#    - test_critic_emotion_mismatch_scores_low_alignment: emotion_alignment < 0.6
```

**静态审查点（LLM 读代码判断）:**
- [ ] 4 个测试断言相对排序（`good > bad`）而不仅是绝对阈值——避免 LLM 评分漂移导致测试 flaky
- [ ] 高质量音频的断言阈值合理（`>= 0.7` 不是 `> 0.9`，留出 LLM 主观空间）
- [ ] 低质量音频的断言用 `< 0.6` 而不是 `< 0.5`（避免与 neutral fallback 混淆）
- [ ] emotion_mismatch 测试用「极度悲伤，哭泣感」这种强对比 prompt，不是「略带忧伤」这种弱对比
- [ ] skip reason 字符串与 KNOWN_ISSUES.md §1 标题对应（方便交叉查找）

**Red flags（任一出现即 FAIL）:**
- 任一 integration 测试漏掉 `@pytest.mark.skip`（会在 CI 上 FAIL）
- skip reason 写死字符串而不是用 `_INTEGRATION_SKIP_REASON` 常量
- 测试断言用 `==` 而不是范围比较（如 `assert result.quality == 0.85`，LLM 不会稳定输出固定值）
- sorting 测试只比 `quality` 不比 `overall`（漏掉综合维度）

#### C. Pass 条件 + 输出

A 全绿（含 4 个 skip 确认）+ B 静态审查无 red flag → **PASS（mock 阶段）**
+ B 启用后 integration 命令绿（服务可用时）→ **PASS（full）**

judge-Agent 输出 schema 同 Task 5（`integration_tests` 在 mock 阶段为 `SKIPPED`，启用后为 `PASS/FAIL`）。

---

### Task 10: Write failing test for TTSRepairAgent construction

**Files:**
- Create: `src_next/critic/tests/test_tts_repair.py`

- [ ] **Step 1: Write failing construction test**

Create `src_next/critic/tests/test_tts_repair.py`:
```python
"""TTSRepairAgent unit tests.

Integration test (real LLM via profile) is written but skip-marked — see
KNOWN_ISSUES.md. Mock-based robustness + behavior tests run by default.
"""
from __future__ import annotations

from src_next.core.data_models import (
    CriticResult,
    ModelSpecificTTSInstruction,
    Segment,
)


def _make_inputs(
    parameters: dict | None = None,
    scores: dict | None = None,
):
    seg = Segment(
        segment_id="s1",
        text="窗外下着大雨。",
        speaker="narrator",
        segment_type="narration",
        raw_index=0,
    )
    inst = ModelSpecificTTSInstruction(
        segment_id="s1",
        speaker="narrator",
        text="窗外下着大雨。",
        model="S2Pro",
        parameters=parameters or {"instruction": "平稳叙述", "speed": 1.0},
        voice_ref="/voicebank/narrator_v1.wav",
        attempt=1,
    )
    s = scores or {}
    critic = CriticResult(
        segment_id="s1",
        quality=s.get("quality", 0.5),
        emotion_alignment=s.get("emotion_alignment", 0.4),
        character_consistency=s.get("character_consistency", 0.9),
        rhythm_naturalness=s.get("rhythm_naturalness", 0.6),
        intelligibility=s.get("intelligibility", 0.85),
        overall=s.get("overall", 0.65),
        suggestions="情感表达偏弱，建议增强悲伤语气，降低语速至 0.85。",
        attempt=1,
    )
    return seg, inst, critic


class _FakeLLMClient:
    """Mock BaseLLMClient for testing repair merge logic."""

    def __init__(self, returned_json: dict | list | None, raise_exc: Exception | None = None):
        self._returned = returned_json
        self._raise = raise_exc
        self.captured_prompt: str | None = None

    def generate_text(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

    def generate_json(self, prompt: str, **kwargs) -> dict | list:
        self.captured_prompt = prompt
        if self._raise:
            raise self._raise
        if self._returned is None:
            raise RuntimeError("no mock return value configured")
        return self._returned


def test_repair_agent_constructs_with_llm_client():
    """TTSRepairAgent takes a BaseLLMClient in __init__."""
    from src_next.critic.tts_repair import TTSRepairAgent

    fake_llm = _FakeLLMClient(returned_json={})
    agent = TTSRepairAgent(llm_client=fake_llm)
    assert agent.llm is fake_llm
```

- [ ] **Step 2: Run — expect ImportError**

Run: `python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v`
Expected: FAIL with `ImportError: cannot import name 'TTSRepairAgent'`.

- [ ] **Step 3: Implement minimal skeleton**

Create `src_next/critic/tts_repair.py`:
```python
"""TTS 指令修复 Agent。

根据 CriticResult.suggestions 调 LLM，让 LLM 只调整 ModelSpecificTTSInstruction.parameters，
不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）。

参考 Audio-Oscar §C.16-C.17：parameters merge 用"original parameters 作基底 + LLM 输出覆盖"
模式；不可改字段在 schema 层冻结，不依赖 prompt 软约束。
"""
from __future__ import annotations

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
from src_next.critic.prompts.repair_prompt import build_repair_prompt
from src_next.llm.base import BaseLLMClient


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client
```

- [ ] **Step 4: Run — expect ImportError on build_repair_prompt**

Run: `python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src_next.critic.prompts.repair_prompt'`.

This is the next task's dependency. Proceed.

---

### Acceptance Criteria (Task 10 — Simplified)

**Pre-conditions:** Task 9 已完成（critic 全部测试就绪）。

**A. coding-Agent Self-check:**
```bash
test -f src_next/critic/tts_repair.py && test -f src_next/critic/tests/test_tts_repair.py && echo OK
python -m pytest src_next/critic/tests/test_tts_repair.py::test_repair_agent_constructs_with_llm_client -v
                            # → 1 passed（最小骨架可构造）
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `tts_repair.py` 含 `TTSRepairAgent` 类，`__init__(self, llm_client: BaseLLMClient)` 把 client 存到 `self.llm`
- [ ] 此时**还没有 `repair()` 方法**（Task 11 才加），有则越界
- [ ] 测试文件含 `_FakeLLMClient` 辅助类（实现 `generate_json` mock，便于后续 Task 11 复用）
- [ ] `import` 路径正确（`from src_next.llm.base import BaseLLMClient`，不是 `from llm.base`）
- [ ] 模块顶部 docstring 含「parameters merge」「schema-frozen」两个核心概念

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 11: Write repair_prompt module + behavior tests + full repair implementation

**Files:**
- Create: `src_next/critic/prompts/repair_prompt.py`
- Modify: `src_next/critic/tts_repair.py` (full repair method)
- Modify: `src_next/critic/tests/test_tts_repair.py`

This is a bigger task — combines prompt + repair + tests because they're tightly coupled.

- [ ] **Step 1: Write failing tests for prompt + merge + immutability + fallback**

Append to `src_next/critic/tests/test_tts_repair.py`:
```python
def test_repair_prompt_contains_all_required_context():
    """Prompt must include original params, current params, critic scores, suggestions, AND
    the explicit 'do not touch these fields' constraint."""
    from src_next.critic.prompts.repair_prompt import build_repair_prompt

    seg, inst, critic = _make_inputs()
    prompt = build_repair_prompt(original=inst, segment=seg, critic=critic)

    # Audio-Oscar §C.18 dual-anchor pattern: original AND current parameters
    assert "instruction" in prompt  # current parameter visible
    assert "1.0" in prompt  # current speed visible

    # Critic feedback (Audio-Oscar §C.20 — show scores + suggestions)
    assert "emotion_alignment" in prompt
    assert "0.40" in prompt or "0.4" in prompt  # emotion_alignment score visible
    assert "情感表达偏弱" in prompt  # suggestion text visible

    # Audio-Oscar §C.19 strong "exactly" language for immutable fields
    for frozen_field in ("segment_id", "speaker", "text", "model", "voice_ref"):
        assert frozen_field in prompt


def test_repair_merges_llm_output_into_parameters():
    """LLM returns partial parameters → result.parameters = original + LLM overlay."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs(
        parameters={"instruction": "平稳叙述", "speed": 1.0, "voice_character": "calm"}
    )
    # LLM only changes speed — instruction and voice_character must be preserved
    fake_llm = _FakeLLMClient(returned_json={"parameters": {"speed": 0.85}})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    assert result.parameters["speed"] == 0.85  # LLM change applied
    assert result.parameters["instruction"] == "平稳叙述"  # original preserved
    assert result.parameters["voice_character"] == "calm"  # original preserved


def test_repair_increments_attempt():
    """Result.attempt must be original.attempt + 1."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    inst.attempt = 1
    fake_llm = _FakeLLMClient(returned_json={"parameters": {}})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)
    assert result.attempt == 2


def test_repair_preserves_immutable_top_level_fields():
    """Schema-frozen fields (segment_id/speaker/text/model/voice_ref) must equal original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    # LLM tries to break the contract by changing everything
    fake_llm = _FakeLLMClient(returned_json={
        "parameters": {"speed": 0.85},
        "segment_id": "HACKED",
        "speaker": "HACKED",
        "text": "HACKED",
        "model": "HACKED",
        "voice_ref": "HACKED",
    })
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    assert result.segment_id == "s1"
    assert result.speaker == "narrator"
    assert result.text == "窗外下着大雨。"
    assert result.model == "S2Pro"
    assert result.voice_ref == "/voicebank/narrator_v1.wav"


def test_repair_returns_original_plus_one_when_llm_raises():
    """LLM exception → fallback to original (attempt+1), no raise."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    inst.attempt = 1
    fake_llm = _FakeLLMClient(returned_json=None, raise_exc=RuntimeError("LLM down"))
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Fallback: same parameters, attempt bumped
    assert result.parameters == inst.parameters
    assert result.attempt == 2
    assert result.segment_id == inst.segment_id
    assert result.model == inst.model


def test_repair_handles_llm_returning_non_dict_parameters():
    """LLM returns {"parameters": "garbage"} → ignore garbage, keep original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    fake_llm = _FakeLLMClient(returned_json={"parameters": "not a dict"})
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Original parameters preserved, no crash
    assert result.parameters == inst.parameters


def test_repair_handles_llm_returning_non_dict_top_level():
    """LLM returns a list instead of dict → fallback to original."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs()
    fake_llm = _FakeLLMClient(returned_json=["unexpected", "list"])
    agent = TTSRepairAgent(llm_client=fake_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)
    assert result.parameters == inst.parameters
    assert result.attempt == inst.attempt + 1
```

- [ ] **Step 2: Run — expect 8 failures**

Run: `python -m pytest src_next/critic/tests/test_tts_repair.py -v`
Expected: 1 PASS (construction) + 7 FAIL (prompt + repair behavior).

- [ ] **Step 3: Implement repair_prompt.py**

Create `src_next/critic/prompts/repair_prompt.py`:
```python
"""Repair prompt 模板。

设计要点（参考 Audio-Oscar §C.18-C.20 + 任务卡 §1.5）：
1. 双锚点：original_parameters（不可漂移） + current_parameters（当前要改的）
2. Critic 反馈完整透传：5 维分数 + suggestions
3. "preserve ... exactly" 强烈措辞，明确列出禁改字段
4. 输出 schema 严格：只输出 parameters JSON
"""
from __future__ import annotations

import json

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment


_REPAIR_PROMPT_TEMPLATE = """你是 TTS 合成指令的修复专家。根据 Critic 反馈，调整 parameters 字段以改善合成质量。

## 任务规则（必须严格遵守）

**你只能修改 parameters 字段内的内容。** 以下字段由 schema 硬约束，**绝对不能修改**：
- segment_id（段编号）
- speaker（说话人）
- text（原文，是用户资产）
- model（TTS 模型，跨模型音色不一致）
- voice_ref（参考音频，同一角色必须用同一 voice_ref）

parameters 内的字段（如 instruction / instruct_text / speed / emotion_vector 等）你可以自由调整。

## 输入

### 段信息
- segment_id: {segment_id}
- text: {text}
- speaker: {speaker}
- model: {model}

### 当前 parameters（attempt={attempt}）
{current_parameters_json}

### Critic 评分
- quality: {quality}
- emotion_alignment: {emotion_alignment}
- character_consistency: {character_consistency}
- rhythm_naturalness: {rhythm_naturalness}
- intelligibility: {intelligibility}
- overall: {overall}

### Critic 修复建议
{suggestions}

## 你的任务

参考 Critic 建议，调整 parameters 字段。**保留原 parameters 中你没改的字段**
（merge 而不是 replace）。

## 输出格式

**只输出严格的 JSON 对象**，不要加 markdown 标记、解释性文字或代码块。格式：
{{"parameters": {{"field1": "value1", "field2": "value2", ...}}}}
"""


def build_repair_prompt(
    original: ModelSpecificTTSInstruction,
    segment: Segment,
    critic: CriticResult,
) -> str:
    """Build the repair prompt.

    Note: `original` here is the current instruction (we merge into its parameters).
    The "frozen original" semantics (Audio-Oscar §D.23) is enforced at the loop level
    by the 主开发 integration in Stage 8 — for now, the caller passes the current
    instruction and we merge LLM output into its parameters.
    """
    return _REPAIR_PROMPT_TEMPLATE.format(
        segment_id=segment.segment_id,
        text=segment.text,
        speaker=segment.speaker,
        model=original.model,
        attempt=original.attempt,
        current_parameters_json=json.dumps(original.parameters, ensure_ascii=False, indent=2),
        quality=f"{critic.quality:.2f}",
        emotion_alignment=f"{critic.emotion_alignment:.2f}",
        character_consistency=f"{critic.character_consistency:.2f}",
        rhythm_naturalness=f"{critic.rhythm_naturalness:.2f}",
        intelligibility=f"{critic.intelligibility:.2f}",
        overall=f"{critic.overall:.2f}",
        suggestions=critic.suggestions,
    )
```

- [ ] **Step 4: Implement full repair method**

Replace `src_next/critic/tts_repair.py` contents with:
```python
"""TTS 指令修复 Agent。

根据 CriticResult.suggestions 调 LLM，让 LLM 只调整 ModelSpecificTTSInstruction.parameters，
不改 segment_id / speaker / text / model / voice_ref（schema 层硬约束）。

参考 Audio-Oscar §C.16-C.17：parameters merge 用"original parameters 作基底 + LLM 输出覆盖"
模式；不可改字段在 schema 层冻结，不依赖 prompt 软约束。
"""
from __future__ import annotations

import copy
import logging

from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
from src_next.critic.prompts.repair_prompt import build_repair_prompt
from src_next.llm.base import BaseLLMClient, LLMError

logger = logging.getLogger(__name__)


class TTSRepairAgent:
    """根据 Critic 反馈调整 TTS 指令参数。"""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm = llm_client

    def repair(
        self,
        original: ModelSpecificTTSInstruction,
        segment: Segment,
        critic: CriticResult,
    ) -> ModelSpecificTTSInstruction:
        """根据低分维度和 suggestions，调整 parameters。

        契约：
        - 返回新的 ModelSpecificTTSInstruction，**不改 segment_id / speaker /
          text / model / voice_ref**（避免声音不一致）。
        - attempt 字段 +1。
        - parameters 由 LLM 重写（保留原 parameters 中 LLM 没动的字段）。
        - LLM 失败 → 返回 original（attempt +1），不抛异常。
        """
        next_attempt = original.attempt + 1
        try:
            llm_output = self.llm.generate_json(build_repair_prompt(original, segment, critic))
        except (LLMError, Exception) as exc:  # noqa: BLE001 — by design, any failure → fallback
            logger.warning("repair LLM call failed: %s. Falling back to original parameters.", exc)
            return self._fallback(original, next_attempt)

        new_parameters = self._merge_parameters(original.parameters, llm_output)
        return ModelSpecificTTSInstruction(
            segment_id=original.segment_id,  # frozen
            speaker=original.speaker,         # frozen
            text=original.text,                # frozen
            model=original.model,              # frozen
            parameters=new_parameters,         # merged
            voice_ref=original.voice_ref,      # frozen
            attempt=next_attempt,
        )

    @staticmethod
    def _merge_parameters(original_parameters: dict, llm_output) -> dict:
        """Merge LLM output into original parameters.

        Pattern (Audio-Oscar §C.16 adapted): original as base, LLM overlay.
        Unlike Oscar we don't whitelist against model_configs (task card §1.5 allows
        any parameters field), so we accept any key the LLM provides — but only
        if it's inside the LLM's "parameters" sub-dict.
        """
        if not isinstance(llm_output, dict):
            return copy.deepcopy(original_parameters)

        llm_params = llm_output.get("parameters")
        if not isinstance(llm_params, dict):
            return copy.deepcopy(original_parameters)

        merged = copy.deepcopy(original_parameters)
        merged.update(llm_params)
        return merged

    @staticmethod
    def _fallback(original: ModelSpecificTTSInstruction, next_attempt: int) -> ModelSpecificTTSInstruction:
        """Return original with attempt+1. Used when LLM call fails or output is unusable."""
        return ModelSpecificTTSInstruction(
            segment_id=original.segment_id,
            speaker=original.speaker,
            text=original.text,
            model=original.model,
            parameters=copy.deepcopy(original.parameters),
            voice_ref=original.voice_ref,
            attempt=next_attempt,
        )
```

- [ ] **Step 5: Run all repair tests — should pass**

Run: `python -m pytest src_next/critic/tests/test_tts_repair.py -v`
Expected: all 8 tests PASS (construction + prompt + 6 behavior).

- [ ] **Step 6: Commit**

```bash
git add src_next/critic/prompts/repair_prompt.py src_next/critic/tts_repair.py src_next/critic/tests/test_tts_repair.py
git commit -m "feat(critic): implement TTSRepairAgent with merge + schema-frozen immutable fields"
```

---

### Acceptance Criteria (Task 11 — Full)

**Pre-conditions:** Task 10 已完成（`TTSRepairAgent` 骨架 + 测试 mock 框架就绪）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- `src_next/critic/prompts/repair_prompt.py` 含 `build_repair_prompt(original, segment, critic) -> str`
- `src_next/critic/tts_repair.py` 实现 `TTSRepairAgent.repair()` + `_merge_parameters()` + `_fallback()`
- 测试 8 个 PASS：construction + prompt + merge + attempt++ + immutability + LLM raise fallback + non-dict parameters + non-dict top-level

**Self-check 命令（本机可跑）:**
```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -v
                            # → 8 passed
```

**契约:**
- `repair()` 不抛异常（任何 LLM 失败 → fallback 到 original+1）
- 返回值的 `segment_id / speaker / text / model / voice_ref` **必须**等于 `original` 对应字段
- 返回值的 `attempt == original.attempt + 1`
- `parameters` = `original.parameters` 作基底 + LLM 输出 overlay（merge 而非 replace）

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Mock 测试全绿
python -m pytest src_next/critic/tests/test_tts_repair.py -v
# 期望: 8 passed

# 2. Schema-frozen smoke（喂恶意 LLM 输出，验证 top-level 字段不动）
python -c "
from src_next.critic.tts_repair import TTSRepairAgent
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction, CriticResult

class HackLLM:
    def generate_json(self, prompt, **kw):
        return {'parameters': {'speed': 0.5}, 'segment_id': 'HACKED', 'speaker': 'HACKED', 'text': 'HACKED', 'model': 'HACKED', 'voice_ref': 'HACKED'}

seg = Segment(segment_id='s1', text='原 文', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='s1', speaker='narrator', text='原 文', model='S2Pro', parameters={'instruction':'平'}, voice_ref='/v.wav', attempt=1)
critic = CriticResult(segment_id='s1', quality=0.3, emotion_alignment=0.2, character_consistency=0.5, rhythm_naturalness=0.5, intelligibility=0.5, overall=0.4, suggestions='弱', attempt=1)

agent = TTSRepairAgent(llm_client=HackLLM())
r = agent.repair(original=inst, segment=seg, critic=critic)
assert r.segment_id == 's1' and r.speaker == 'narrator' and r.text == '原 文' and r.model == 'S2Pro' and r.voice_ref == '/v.wav'
assert r.attempt == 2 and r.parameters.get('speed') == 0.5
print('schema-frozen + merge OK')
"

# 3. 端到端 smoke（服务可用时，调真实 LLM）
python -c "
import os, yaml
from src_next.critic.tts_repair import TTSRepairAgent
from src_next.llm.qwen_http import QwenHTTPClient
from src_next.core.data_models import Segment, ModelSpecificTTSInstruction, CriticResult

cfg = yaml.safe_load(open(os.environ['CRITIC_TEST_LLM_PROFILE']))
llm = QwenHTTPClient(base_url=cfg['llm']['base_url'])
seg = Segment(segment_id='s', text='窗外下着大雨。', speaker='narrator', segment_type='narration', raw_index=0)
inst = ModelSpecificTTSInstruction(segment_id='s', speaker='narrator', text='窗外下着大雨。', model='S2Pro', parameters={'instruction':'平稳叙述','speed':1.0}, voice_ref='/v.wav', attempt=1)
critic = CriticResult(segment_id='s', quality=0.4, emotion_alignment=0.3, character_consistency=0.9, rhythm_naturalness=0.6, intelligibility=0.85, overall=0.6, suggestions='情感偏弱，建议增强悲伤语气', attempt=1)
r = TTSRepairAgent(llm_client=llm).repair(original=inst, segment=seg, critic=critic)
print(f'attempt={r.attempt} params_delta={ {k:v for k,v in r.parameters.items() if v != inst.parameters.get(k)} }')
assert r.attempt == 2
"
```

**静态审查点（LLM 读代码判断）:**
- [ ] `_merge_parameters` 用 `copy.deepcopy(original_parameters)` 作基底，然后 `update(llm_params)`
- [ ] `llm_params = llm_output.get("parameters")` 取出来后**类型检查** `isinstance(llm_params, dict)`，不是 dict 时直接 fallback
- [ ] prompt 模板含「preserve exactly」强烈措辞，明确列出 5 个禁改字段
- [ ] prompt 含 Critic 完整反馈：5 维分数（带具体数值，如 `0.40`）+ suggestions 原文
- [ ] `except (LLMError, Exception)` 范围合理（catch-all 是 design，但要 log warning）

**Red flags（任一出现即 FAIL）:**
- LLM 输出的 `segment_id / speaker / text / model / voice_ref` 出现在返回值里（即使 LLM 输出的是「正确」值，也说明代码信任了 LLM）
- `_merge_parameters` 直接返回 LLM 输出（不 merge 进 original 基底）
- prompt 把 `attempt=1` 当成「这是第一次尝试，可以从头改」（应是「当前状态，调整即可」）
- `repair()` 在 LLM 失败时抛异常（应 fallback 到 original+1）
- `_fallback` 返回 `attempt=original.attempt`（应 +1）

#### C. Pass 条件 + 输出

A 全绿 + B mock 命令绿 + B smoke 命令绿（服务可用时）+ 静态审查无 red flag → **PASS**

judge-Agent 输出 schema 同 Task 5（`integration_tests: SKIPPED`，`smoke_tests: PASS|FAIL|SKIPPED`）。

---

### Task 12: Add repair integration skeleton (skip-marked)

**Files:**
- Modify: `src_next/critic/tests/test_tts_repair.py`

- [ ] **Step 1: Add skip-marked integration test**

Append to `src_next/critic/tests/test_tts_repair.py`:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Integration test — skip-marked. See KNOWN_ISSUES.md §1 to activate.
# ─────────────────────────────────────────────────────────────────────────────

import pytest  # noqa: E402 — top of file already imports pytest, but be defensive


_INTEGRATION_SKIP_REASON = (
    "awaiting real LLM service access — see src_next/critic/KNOWN_ISSUES.md §1"
)


@pytest.mark.integration
@pytest.mark.skip(reason=_INTEGRATION_SKIP_REASON)
def test_repair_with_real_llm_adjusts_parameters(real_llm):
    """Integration: real LLM should change at least one parameter when given a low emotion_alignment score."""
    from src_next.critic.tts_repair import TTSRepairAgent

    seg, inst, critic = _make_inputs(
        parameters={"instruction": "平稳叙述", "speed": 1.0}
    )
    # Critic says emotion_alignment is weak → LLM should adjust instruction
    agent = TTSRepairAgent(llm_client=real_llm)

    result = agent.repair(original=inst, segment=seg, critic=critic)

    # Contract: immutable fields untouched
    assert result.segment_id == "s1"
    assert result.speaker == "narrator"
    assert result.text == "窗外下着大雨。"
    assert result.model == "S2Pro"
    assert result.voice_ref == inst.voice_ref
    assert result.attempt == 2

    # Behavior: at least one parameter changed (most likely instruction or speed)
    changed_keys = [
        k for k in result.parameters
        if result.parameters[k] != inst.parameters.get(k)
    ]
    assert len(changed_keys) > 0, (
        f"real LLM did not change any parameter. before={inst.parameters}, after={result.parameters}"
    )
```

- [ ] **Step 2: Verify it collects as SKIPPED**

Run: `python -m pytest src_next/critic/tests/test_tts_repair.py -v`
Expected: 8 PASS + 1 SKIPPED.

- [ ] **Step 3: Commit**

```bash
git add src_next/critic/tests/test_tts_repair.py
git commit -m "test(critic): add repair integration test skeleton (skip-marked)"
```

---

### Acceptance Criteria (Task 12 — Full)

**Pre-conditions:** Task 11 已完成（`TTSRepairAgent.repair()` 实现完整）。

#### A. coding-Agent 完成定义（mock-可验证）

**产出物:**
- 1 个 skip-marked integration 测试：`test_repair_with_real_llm_adjusts_parameters`
- 共享常量 `_INTEGRATION_SKIP_REASON` 与 critic 文件保持一致风格

**Self-check 命令（本机可跑）:**
```bash
python -m pytest src_next/critic/tests/test_tts_repair.py -v
                            # → 8 passed + 1 skipped
python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
                            # → 1 skipped（确认 skip 状态）
```

**契约:**
- 测试同时含 `@pytest.mark.integration` **和** `@pytest.mark.skip(reason=...)` 两个装饰器
- 测试断言 immutable 字段（5 个）保持不变 + 至少一个 parameter 改变

#### B. judge-Agent 验证（在可访问服务的环境里跑）

**服务-可验证命令:**
```bash
# 1. Skip 状态确认（任何环境都能跑）
python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
# 期望: 1 skipped

# 2. 启用 integration 测试（删除 @pytest.mark.skip 装饰器那一行）
grep -n "_INTEGRATION_SKIP_REASON" src_next/critic/tests/test_tts_repair.py

# 3. 启用后跑（需要服务可用 + LLM profile）
python -m pytest src_next/critic/tests/test_tts_repair.py -m integration -v
# 期望: 1 passed
#    - immutable 字段全等
#    - 至少 1 个 parameter 改变（changed_keys 非空）
```

**静态审查点（LLM 读代码判断）:**
- [ ] 测试用 `_make_inputs(parameters={"instruction":"平稳叙述","speed":1.0})` 准备场景（emotion_alignment 低 → LLM 应改 instruction 或 speed）
- [ ] `changed_keys` 列表推导式正确：`result.parameters[k] != inst.parameters.get(k)`
- [ ] 断言失败信息含 `before=` / `after=` dump，方便 debug
- [ ] `agent = TTSRepairAgent(llm_client=real_llm)` 用 conftest 的 fixture，不是自己 new

**Red flags（任一出现即 FAIL）:**
- 漏 `@pytest.mark.skip`（会在 CI FAIL）
- 断言只检查「至少一个字段变了」但不检查 immutable 字段（漏掉 schema-frozen 验证）
- 测试用 mock LLM 而不是 `real_llm` fixture（不再是 integration 测试）

#### C. Pass 条件 + 输出

A 全绿（含 skip 确认）+ B 静态审查无 red flag → **PASS（mock 阶段）**
+ B 启用后 integration 命令绿（服务可用时）→ **PASS（full）**

judge-Agent 输出 schema 同 Task 5（`integration_tests` 在 mock 阶段为 `SKIPPED`）。

---

## Day 3: Full verification + PR

### Task 13: Verify py_compile + count files

**Files:** No changes; verification only.

- [ ] **Step 1: Compile every new Python file**

Run:
```bash
python -m py_compile \
    src_next/critic/__init__.py \
    src_next/critic/qwen3omni_critic.py \
    src_next/critic/tts_repair.py \
    src_next/critic/prompts/__init__.py \
    src_next/critic/prompts/critic_prompt.py \
    src_next/critic/prompts/repair_prompt.py \
    src_next/critic/tests/__init__.py \
    src_next/critic/tests/conftest.py \
    src_next/critic/tests/test_qwen3omni_critic.py \
    src_next/critic/tests/test_tts_repair.py
```
Expected: no output (success). Any syntax error → fix before proceeding.

- [ ] **Step 2: Verify 8 new files match task card §1.2 manifest**

Run: `git diff --name-only main...HEAD -- src_next/critic/`
Expected: at least the 8 task-card-listed files:

```
src_next/critic/__init__.py
src_next/critic/prompts/__init__.py
src_next/critic/prompts/critic_prompt.py
src_next/critic/prompts/repair_prompt.py
src_next/critic/qwen3omni_critic.py
src_next/critic/tests/__init__.py
src_next/critic/tests/test_qwen3omni_critic.py
src_next/critic/tests/test_tts_repair.py
```

Plus auxiliary: `pytest.ini`, `src_next/critic/KNOWN_ISSUES.md`, `src_next/critic/tests/conftest.py`.

---

### Acceptance Criteria (Task 13 — Simplified)

**Pre-conditions:** Task 12 已完成（所有源码 + 测试已提交）。

**A. coding-Agent Self-check:**
```bash
python -m py_compile \
    src_next/critic/__init__.py \
    src_next/critic/qwen3omni_critic.py \
    src_next/critic/tts_repair.py \
    src_next/critic/prompts/__init__.py \
    src_next/critic/prompts/critic_prompt.py \
    src_next/critic/prompts/repair_prompt.py \
    src_next/critic/tests/__init__.py \
    src_next/critic/tests/conftest.py \
    src_next/critic/tests/test_qwen3omni_critic.py \
    src_next/critic/tests/test_tts_repair.py \
  && echo "py_compile OK"
                            # → py_compile OK（无任何输出 = 成功）
git diff --name-only main...HEAD -- src_next/critic/ | wc -l
                            # → >= 8（任务卡 §1.2 manifest）
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] `git diff --name-only main...HEAD -- src_next/critic/` 输出含任务卡 §1.2 的全部 8 个文件
- [ ] 输出**不含** `output*` 路径下的文件（不能误提交合成产物）
- [ ] 输出**不含** `.env` / `credentials` / 任何疑似 secret 文件
- [ ] auxiliary 文件（pytest.ini / KNOWN_ISSUES.md / conftest.py）也在 diff 里

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 14: Run full mock test suite (must be green)

- [ ] **Step 1: Run all non-integration tests**

Run: `python -m pytest src_next/critic/tests/ -m "not integration" -v`
Expected: ALL listed tests PASS. Should be at least:
- 3 critic mock tests (construction, evaluate success, prompt structure)
- 4 critic robustness tests (HTTP 500, non-JSON, empty text, request exception)
- 2 repair mock tests (construction, prompt structure)
- 6 repair behavior tests (merge, attempt++, immutability, LLM raise fallback, non-dict params, non-dict top-level)

= 15 mock tests, all green.

- [ ] **Step 2: Run with -m integration to confirm all SKIPPED (not FAILED)**

Run: `python -m pytest src_next/critic/tests/ -m integration -v`
Expected: 5 SKIPPED tests (4 critic + 1 repair). NO failures.

If any integration test FAILS instead of SKIP — fix the skip decorator. The whole point is they should be inert until service access is granted.

---

### Acceptance Criteria (Task 14 — Simplified)

**Pre-conditions:** Task 13 已完成（py_compile + 文件清单确认）。

**A. coding-Agent Self-check:**
```bash
python -m pytest src_next/critic/tests/ -m "not integration" -v
                            # → 15 passed（3 critic mock + 4 robustness + 2 repair mock + 6 repair behavior）
python -m pytest src_next/critic/tests/ -m integration -v
                            # → 5 skipped（4 critic + 1 repair），0 failed
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] mock 测试断言里有具体阈值（如 `quality >= 0.7`），不是空断言（如 `assert result`）
- [ ] `pytest src_next/critic/tests/ -v`（不带 -m 过滤）输出 15 passed + 5 skipped + 0 failed
- [ ] **没有** unexpected warning（如 DeprecationWarning / ResourceWarning）污染输出

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 15: Write mock sample for PR description

**Files:**
- Create: `docs/pr_samples/critic_sample.md`

⚠️ Replaces the original "real sample" task. Since we can't run real Qwen3-Omni, we provide a sample of the EXPECTED I/O format based on what the prompt + parser are designed to handle. PR description must mark this clearly.

- [ ] **Step 1: Write the mock sample**

Create `docs/pr_samples/critic_sample.md`:
```markdown
# Critic 评分样例（基于 mock 数据，待真实服务验证）

> ⚠️ **本样例不是真实 Qwen3-Omni 输出。** 由于本机无法访问 Qwen3-Omni 服务（详见
> `src_next/critic/KNOWN_ISSUES.md`），这里展示的是 prompt 设计的预期 I/O 格式。
> 真实服务可访问后，会跑一次真实评分并替换本文件内容。

## 输入

- **Audio path**: `/server-side/path/to/good_narration.wav`（5-10s TTS 输出）
- **Original text**: 窗外下着大雨。
- **Speaker**: narrator
- **TTS model**: S2Pro
- **Expected emotion (`parameters.instruction`)**: 平稳叙述，略带忧伤

## Critic 发送的 prompt（节选）

```
请仔细听这段 TTS 合成音频，并对照以下信息评分。

## 原文
窗外下着大雨。

## 期望表现
- 说话人: narrator
- 段类型: narration
- TTS 模型: S2Pro
- 期望情感 / 风格: 平稳叙述，略带忧伤
- 期望语速: 未指定（用模型默认）

## 评分维度（每项 0.0-1.0，浮点数保留 2 位）
1. quality: ...
2. emotion_alignment: ...
3. character_consistency: ...
4. rhythm_naturalness: ...
5. intelligibility: ...
[... 完整 prompt 见 src_next/critic/prompts/critic_prompt.py ...]

## 输出格式
**只输出严格的 JSON**：
{"quality":0.85,"emotion_alignment":0.80,...,"suggestions":"..."}
```

## 期望的 Qwen3-Omni 响应

```json
{
  "request_id": "<generated>",
  "text": "{\"quality\":0.87,\"emotion_alignment\":0.82,\"character_consistency\":0.91,\"rhythm_naturalness\":0.85,\"intelligibility\":0.93,\"suggestions\":\"音质清晰；情感稍弱，建议增强忧伤语气。\"}",
  "inference_time": "..."
}
```

## 解析后的 CriticResult

| 字段 | 值 |
|---|---|
| segment_id | sample |
| quality | 0.87 |
| emotion_alignment | 0.82 |
| character_consistency | 0.91 |
| rhythm_naturalness | 0.85 |
| intelligibility | 0.93 |
| **overall** | **0.876**（5 维平均，由 `CriticResult.from_json` 计算） |
| suggestions | "音质清晰；情感稍弱，建议增强忧伤语气。" |
| needs_repair(threshold=0.7, overall_floor=0.75) | **False**（无需修复） |

## 解析鲁棒性（mock 测试已覆盖）

`_parse_scoring_json` 三步兜底：
1. 剥 ` ```json ... ``` ` 代码块
2. 直接 `json.loads`
3. `JSONDecoder.raw_decode` 从第一个 `{` 贪婪匹配

mock 测试覆盖了以下输入变形：
- ✅ 标准 JSON（如上）
- ✅ ` ```json ` 包裹的 JSON
- ✅ 带前后解释文字的 JSON（如 "评分如下：{...} 以上"）
- ✅ HTTP 500 → neutral 0.5 fallback
- ✅ 200 但 text 字段空 → neutral 0.5 fallback
- ✅ 200 但 text 不是 JSON → neutral 0.5 fallback
- ✅ requests 异常（timeout / connection refused）→ neutral 0.5 fallback
```

- [ ] **Step 2: Commit**

```bash
git add docs/pr_samples/critic_sample.md
git commit -m "docs(critic): add mock I/O sample for PR (real sample pending service access)"
```

---

### Acceptance Criteria (Task 15 — Simplified)

**Pre-conditions:** Task 14 已完成。

**A. coding-Agent Self-check:**
```bash
test -f docs/pr_samples/critic_sample.md && echo OK
grep -c "^## " docs/pr_samples/critic_sample.md
                            # → >= 4（输入 / Critic prompt / 期望响应 / 解析后 CriticResult / 解析鲁棒性）
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] 文件顶部含 `⚠️ **本样例不是真实 Qwen3-Omni 输出**` 显著警告
- [ ] 含 mock 输入（audio path / text / speaker / model / expected emotion）
- [ ] 含 Critic 发送的 prompt 节选（含 5 维度定义 + JSON schema）
- [ ] 含期望的 Qwen3-Omni response（`text` 字段是 JSON 字符串）
- [ ] 含解析后的 CriticResult 表格（5 维分数 + overall + suggestions + needs_repair 判定）
- [ ] 含解析鲁棒性说明（3 步 fallback + 已覆盖的输入变形列表）
- [ ] `git log --oneline -3` 含 `docs(critic): add mock I/O sample for PR (real sample pending service access)`

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

### Task 16: Write PR description and push branch

**Files:** No code changes; PR creation only.

- [ ] **Step 1: Push the branch (use the push-with-output-ignore skill or follow its guidance)**

⚠️ This repo has a configured skill `push-with-output-ignore` — invoke it before pushing to avoid accidentally committing output* folders.

```bash
git push -u origin feature/critic-and-tta
```

- [ ] **Step 2: Create PR with the required sections**

Use `gh pr create` with this body:

```markdown
## Summary

Implements Part I of intern B task card (方向3 - Critic 评估-修复机制):
- `Qwen3OmniCritic` evaluates TTS audio via Qwen3-Omni service on 5 dimensions
- `TTSRepairAgent` adjusts parameters via LLM when Critic flags low scores
- Schema-frozen immutable fields (segment_id / speaker / text / model / voice_ref)
- Failure fallback returns neutral 0.5 (per task card — not 0.0 like Audio-Oscar)

## Files added (8 per task card §1.2)

- `src_next/critic/__init__.py`
- `src_next/critic/qwen3omni_critic.py`
- `src_next/critic/tts_repair.py`
- `src_next/critic/prompts/__init__.py`
- `src_next/critic/prompts/critic_prompt.py`
- `src_next/critic/prompts/repair_prompt.py`
- `src_next/critic/tests/test_qwen3omni_critic.py`
- `src_next/critic/tests/test_tts_repair.py`

Plus auxiliary: `pytest.ini`, `conftest.py`, `KNOWN_ISSUES.md`, mock sample.

## ⚠️ Testing gap (read before merging)

**Integration tests are written but skip-marked.** 实习生本机无法访问 Qwen3-Omni 服务和本地 LLM 服务，无法跑真实 integration。

- ✅ 15 mock 测试全绿（构造 / 解析 / 兜底 / merge / 契约）
- ⏸️ 5 integration 测试 skip（4 critic + 1 repair），代码就绪
- 📋 启用条件见 `src_next/critic/KNOWN_ISSUES.md §1`

任务卡 §3 PR checklist 中的"真实 Qwen3-Omni 跑通"一项**改为"测试代码就绪，待服务可访问后启用"**。

## Mock sample (real sample pending service access)

See `docs/pr_samples/critic_sample.md` — 展示 prompt 设计的预期 I/O 格式 + 解析鲁棒性覆盖。真实评分样例待服务可访问后补充。

## Test plan

- [x] `python -m py_compile` on all new files — clean
- [x] `pytest src_next/critic/tests/ -m "not integration"` — 15 mock tests green
- [x] `pytest src_next/critic/tests/ -m integration` — 5 tests SKIPPED (not failed)
- [x] Qwen3OmniCritic.evaluate signature matches task card §1.3.1
- [x] TTSRepairAgent.repair signature matches task card §1.3.2
- [x] Critic never raises (always returns neutral 0.5 on failure)
- [x] Repair never modifies segment_id / speaker / text / model / voice_ref (mock-verified)
- [x] No new runtime dependencies (uses `requests` + `BaseLLMClient`)

## Notes for 主开发

### Service activation (when Qwen3-Omni + LLM are reachable)

1. Global search `@pytest.mark.skip(reason="awaiting` and remove those decorator lines
2. Set up 3 audio fixtures, point `CRITIC_FIXTURES_ROOT` env var at them
3. Set up LLM profile yaml, point `CRITIC_TEST_LLM_PROFILE` env var at it
4. Run `pytest src_next/critic/tests/ -m integration -v` (NO `-n auto` — infer_lock!)

### API endpoint risk

`qwen3omni_critic.py` 用 `/v1/omni/audio_analysis + text` 字段（per task card §1.4）。如果真实服务不认 text 字段（返回通用 sound_analysis 描述而非评分 JSON），按 `KNOWN_ISSUES.md §2` 一行切换到 `/v1/omni/chat`。

### Stage 8 integration

- Critic must be called **serially** (no ThreadPoolExecutor) — infer_lock
- Repair's `original` parameter currently means "current instruction"; if you want frozen-original semantics (Audio-Oscar §D.23), wrap the call site to pass the attempt=1 instruction
- The `needs_repair()` method already lives on `CriticResult` (in data_models.py), uses `min(dims) < threshold OR overall < overall_floor`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 3: Push and create PR**

```bash
git push -u origin feature/critic-and-tta
gh pr create --title "feat(critic): Part I — Qwen3OmniCritic + TTSRepairAgent (mock tests; integration pending)" --body "$(cat <<'EOF'
[paste the body above]
EOF
)"
```

- [ ] **Step 4: Verify PR is created and CI runs**

Run: `gh pr view --web`
Expected: PR page opens, CI starts running.

---

### Acceptance Criteria (Task 16 — Simplified)

**Pre-conditions:** Task 15 已完成（mock sample 文档已提交）；本机已配置 `gh` CLI 并登录。

**A. coding-Agent Self-check:**
```bash
git rev-parse --abbrev-ref HEAD
                            # → feature/critic-and-tta
git log --oneline origin/feature/critic-and-tta..HEAD
                            # → 空（已全部 push）
gh pr list --head feature/critic-and-tta --state open
                            # → 显示 1 个 open PR
```

**B. judge-Agent 抽查（无 integration）:**
- [ ] PR title 含 `feat(critic):` 前缀 + `Part I` + `(mock tests; integration pending)`
- [ ] PR body 含以下 section：`## Summary` / `## Files added` / `## ⚠️ Testing gap` / `## Mock sample` / `## Test plan` / `## Notes for 主开发`
- [ ] Testing gap section **明确标注** integration 测试 skip 的状态 + 启用条件（指向 KNOWN_ISSUES.md §1）
- [ ] Test plan section 全部 checkbox 已勾（`[x]`），不只是列了清单
- [ ] Notes for 主开发 section 含「serial 调用」「API 端点 fallback 路径」「Stage 8 集成注意」三点
- [ ] PR 不含 `output*` 路径下的任何文件（push 前已用 push-with-output-ignore skill 检查）

**Pass:** A 全绿 + B 无 red flag → **PASS**

---

## Self-review notes

**Spec coverage check (task card §3 Part I PR checklist, adjusted for service-access gap):**
- [x] 8 files added → Tasks 2, 4, 5, 6, 10, 11
- [x] Critic evaluate signature → Task 5
- [x] Repair signature → Task 11
- [x] Critic never raises → Task 5 (try/except + neutral fallback)
- [x] Repair doesn't modify frozen fields → Task 11 (schema-frozen at construction; mock-verified)
- [~] Critic integration tests (3 cases + sorting) → Task 9 — **written but skip-marked, pending service**
- [x] Critic robustness tests (500, non-JSON) → Task 8
- [~] Repair integration test → Task 12 — **written but skip-marked, pending service**
- [x] Repair robustness test → Task 11 (LLM raise fallback test)
- [x] py_compile + mock pytest green → Tasks 13, 14
- [x] No new dependencies → uses only `requests` and `BaseLLMClient`
- [~] PR description with real sample → Task 15 — **mock sample provided, real sample pending**

**Adjusted checklist items (marked ~):** documented in `KNOWN_ISSUES.md` and PR description. When service becomes available, activation is mechanical (delete skip decorators + provide fixtures/profile).

**Placeholder scan:** clean — every step has complete code or exact commands.

**Type consistency:** `Qwen3OmniCritic` / `evaluate` / `TTSRepairAgent` / `repair` / `build_critic_prompt` / `build_repair_prompt` — all used consistently across tasks.
