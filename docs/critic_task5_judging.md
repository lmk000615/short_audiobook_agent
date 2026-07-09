# Critic Task 5 — Judge-Agent 验收报告

> **Plan:** `docs/superpowers/plans/2026-07-01-intern-b-critic-repair.md` §Task 5 (Full)
> **Spec:** `docs/superpowers/specs/2026-07-02-intern-b-critic-repair-acceptance-design.md`（Task 5 无独立章节，沿用 plan §Task 5 Acceptance Full）
> **Coding dev doc:** `docs/critic_task5_coding.md`
> **分支:** `feature/critic-and-tta`
> **验收日期:** 2026-07-03
> **Task 类型:** 代码型（TDD 双 RED 循环：RED#1 AttributeError on requests → RED#2 ImportError on build_critic_prompt，**故意停在半红状态作为 Task 6 的输入**）
> **Round:** 1 / 3

---

## 0. Verdict 一句话

**CONDITIONAL PASS** — Task 5 严格按 plan §Task 5 Step 1→4 顺序执行：evaluate / `_evaluate_inner` / `_neutral_result` / `_parse_scoring_json` 三步兜底全部按 plan 字面量落地（9/9 静态审查通过），commit `48ffea0` 已落盘 3 文件；**Section A self-check 命令实测 `1 failed (ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt')`**——这是 plan §Task 5 Step 4 行 685-690 + 766 设计的**预期半红终态**（明文 "This is the next task's dependency. Proceed to Task 6"），等 Task 6 创建 `build_critic_prompt` 后即转绿。本 task 不构成 FAIL（无 red flag、无 scope creep），但 mock test 未绿，按 skill 判定规则降级为 CONDITIONAL PASS。

---

## 1. 验收范围

按 plan §Task 5 (Full) 的 Acceptance Criteria 三档验收：

- **Section A — coding-Agent Self-check**：1 条命令（evaluate happy-path 测试）
- **Section B — judge-Agent 抽查**：9 条静态审查（4 条来自 plan 行 752-756 + 4 条 Red flags 反向核对 行 758-762 + 1 条边界核对「prompts/critic_prompt.py 不存在」）
- **额外审查**：字面量逐字比对 + scope 边界（critic 子树）+ commit 范围核对 + 偏离登记 + red flag 排查

**关键 plan 内部矛盾记录**（影响判定）：
- plan §Task 5 Acceptance A 行 705-709：self-check 命令期望 `1 passed`
- plan §Task 5 Step 4 行 685-690：明文 "Expected: FAIL with `ImportError: cannot import name 'build_critic_prompt'`... This is the next task's dependency. Proceed to Task 6."

两者互相矛盾。**以 Step 4 为准**——Step 4 是 task 内最终状态描述（含 "Proceed to Task 6" 收尾），Acceptance A `1 passed` 是跨 task 完成态描述（要 Task 6 完成才成立）。

---

## 2. Section A — coding-Agent Self-check

| 项 | 期望 | 实测 | 状态 |
|---|---|---|---|
| A1 `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v` | plan 行 707-709 写 `1 passed`（与 Step 4 行 688 矛盾，以 Step 4 为准） | `1 failed` — `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'` | **PASS（按 Step 4 终态判定）** |

### A1 完整测试输出（judge 独立执行，不抄 coding doc）

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 1 item

src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success FAILED [100%]

================================== FAILURES ===================================
_______________ test_evaluate_returns_critic_result_on_success ________________

    def test_evaluate_returns_critic_result_on_success(monkeypatch):
        """Mock 200 + valid scoring JSON → CriticResult with parsed scores."""
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

**判定理由（A1）**：

- plan §Task 5 Step 4 行 685-690 明确写："Expected: FAIL with `ImportError: cannot import name 'build_critic_prompt' from 'src_next.critic.prompts.critic_prompt'`. This is the next task's dependency. Proceed to Task 6."
- 实测抛 `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'`——`ModuleNotFoundError` 是 `ImportError` 的子类（Python 3.12），与 Task 4 同模式偏离（plan 字面 `ImportError`，实测 `ModuleNotFoundError`）。
- 炸点根因：`src_next/critic/prompts/critic_prompt.py` 文件根本不存在（Task 2 只建了 `prompts/__init__.py`，Task 6 才建文件），所以是 `ModuleNotFoundError`（模块不存在）而非父类 `ImportError`（模块存在但符号不存在）。
- 子类语义同样满足 plan Step 4 预期（"next task's dependency"），**不构成 FAIL**。

---

## 3. Section B — judge-Agent 抽查

按 plan §Task 5 Acceptance B 行 752-762 的 4 条静态审查点 + 4 条 Red flags 反向核对 + 1 条边界核对（共 9 条）。

| 抽查点 | 期望 | 实测证据 | 状态 |
|---|---|---|---|
| B1 `_parse_scoring_json` 三步兜底完整（剥 fence → json.loads → raw_decode 扫描） | 3 步顺序执行 + 失败抛 ValueError | `qwen3omni_critic.py` L46-66：L56 `_strip_code_fence` → L58 `json.loads` → L63 `_extract_first_json`；L65 失败抛 `ValueError` | PASS |
| B2 `try/except Exception` 范围合理（不是裸 `except:`，不是只 catch 一种） | `except Exception as exc:` | L92 `except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback`（不是裸 `except:`，不是 `except (TypeError, ValueError):` 等窄范围） | PASS |
| B3 未引入未要求的依赖（只用 `requests` + 项目内已有模块） | imports 仅 `json` / `re` / `requests` / `build_critic_prompt` / `data_models` | L14-20 imports 逐字命中 5 行，无新增第三方包；无 `import openai` / `import httpx` / `import aiohttp` 等 | PASS |
| B4 没有提前实现 repair agent 的逻辑 | 本文件无 `repair` 字眼、无 `TTSRepairAgent` 引用 | `grep "repair"` 无命中（"audio_analysis returned HTTP" 不含 repair）；`grep "TTSRepairAgent"` 无命中 | PASS |
| B5（Red flag 反向）`evaluate()` 抛了未捕获异常 | 应 catch-all → neutral fallback，不外抛 | L90-93 `try: return self._evaluate_inner(...) except Exception as exc: return self._neutral_result(...)`，catch-all 完整 | PASS |
| B6（Red flag 反向）neutral fallback 返回 `0.0` 而非 `0.5` | `_neutral_result` 5 维 + overall 全部 `0.5` | L138-143 共 6 个 `0.5`（quality/emotion_alignment/character_consistency/rhythm_naturalness/intelligibility/overall），L143 `overall=0.5` ✓ | PASS |
| B7（Red flag 反向）mock 测试里有真实网络调用 | `_FakeOkResponse` 之外不应联网 | `test_qwen3omni_critic.py` L75 `monkeypatch.setattr(mod.requests, "post", fake_post)` 拦截 `requests.post`；L84 `http://10.50.121.102:8011` 仅是断言字面量（`assert captured["url"] == ...`）非真实调用 | PASS |
| B8（Red flag 反向）`_evaluate_inner` 直接信任 `tts_instruction.text` | 应走 `build_critic_prompt(segment, tts_instruction)`，schema-frozen | `qwen3omni_critic.py` L101 `prompt_text = build_critic_prompt(segment, tts_instruction)`；`grep "tts_instruction.text"` 无命中（不直接读 `.text` 属性） | PASS |
| B9 边界核对：`src_next/critic/prompts/critic_prompt.py` **不存在**（Task 6 边界未越界） | 仅 `prompts/__init__.py`，无 `critic_prompt.py` | `Glob src_next/critic/prompts/*.py` 仅命中 `__init__.py`；commit `48ffea0` 文件清单不含 `critic_prompt.py` | PASS |

### 3.1 关键字面量 grep 证据

**imports + 模块级辅助函数（B1 + B3）**：

```
$ grep -n "^import\|^from\|^def \|^_CODE_FENCE_RE\|^class " src_next/critic/qwen3omni_critic.py
13:from __future__ import annotations
15:import json
16:import re
18:import requests
20:from src_next.critic.prompts.critic_prompt import build_critic_prompt
21:from src_next.core.data_models import CriticResult, ModelSpecificTTSInstruction, Segment
24:_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)
26:def _strip_code_fence(raw: str) -> str:
31:def _extract_first_json(raw: str) -> dict | None:
46:def _parse_scoring_json(raw_text: str) -> dict:
69:class Qwen3OmniCritic:
```

**方法清单（B4 + B5 + B6，验证 Task 5 边界）**：

```
$ grep -n "^    def \|^    @" src_next/critic/qwen3omni_critic.py
72:    def __init__(
83:    def evaluate(
95:    def _evaluate_inner
130:    def _neutral_result
```

**catch-all 注释 + 0.5 字面量（B2 + B6）**：

```
L92:        except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback
L138:            quality=0.5,
L139:            emotion_alignment=0.5,
L140:            character_consistency=0.5,
L141:            rhythm_naturalness=0.5,
L142:            intelligibility=0.5,
L143:            overall=0.5,
```

**payload + URL（B8 验证不直接信任 tts_instruction.text）**：

```
L101:        prompt_text = build_critic_prompt(segment, tts_instruction)
L102:        payload = {
L103:            "audio": audio_path,
L104:            "task": "sound_analysis",
L105:            "text": prompt_text,
L106:            "return_audio": False,
L107:            "max_new_tokens": 1024,
L108:        }
L109:        url = f"{self.base_url}/v1/omni/audio_analysis"
```

**B9 边界核对（prompts 目录）**：

```
$ Glob src_next/critic/prompts/*.py
src_next\critic\prompts\__init__.py
（仅 1 个文件 — Task 6 的 critic_prompt.py 尚未存在 ✓）
```

**B7 mock 测试无真实网络调用**：

```
test_qwen3omni_critic.py L75:    monkeypatch.setattr(mod.requests, "post", fake_post)
test_qwen3omni_critic.py L84:    assert captured["url"] == "http://10.50.121.102:8011/v1/omni/audio_analysis"
```
（L84 是断言而非真实调用）

**Section B 总结：9/9 全部 PASS，零 red flag。**

---

## 4. 字面量与 scope 核对（额外审查）

### 4.1 涉及文件清单（commit `48ffea0`）

```
$ git show --stat 48ffea0
 docs/critic_task5_coding.md                    | 371 +++++++++++++++++++++++++
 src_next/critic/qwen3omni_critic.py            | 124 ++++++++-
 src_next/critic/tests/test_qwen3omni_critic.py |  76 +++++
 3 files changed, 565 insertions(+), 6 deletions(-)
```

| 路径 | 操作 | 与 plan §Task 5 Files 行 444-446 一致？ |
|---|---|---|
| `src_next/critic/tests/test_qwen3omni_critic.py` | 修改（+76 行：追加 `_make_segment_and_instruction` + `_FakeOkResponse` + `test_evaluate_returns_critic_result_on_success`，保留 Task 4 的 `test_critic_can_be_constructed_with_defaults`） | ✓ |
| `src_next/critic/qwen3omni_critic.py` | 修改（+124-6 行：Task 4 的 skeleton 被 Task 5 全量 body 替换） | ✓ |
| `docs/critic_task5_coding.md` | 新增（371 行 dev doc） | ✓（与用户 task 指令一致，合并到代码 commit） |

### 4.2 关键字面量与 plan §Task 5 Step 1+3 逐字比对

| 字面量 | plan 位置 | 实测位置 | 一致？ |
|---|---|---|---|
| URL `http://10.50.121.102:8011/v1/omni/audio_analysis` | plan 行 513（断言）+ 行 645（`f"{self.base_url}/v1/omni/audio_analysis"`） | `qwen3omni_critic.py` L109；`test_qwen3omni_critic.py` L84 | ✓ |
| payload `"task": "sound_analysis"` | plan 行 515 + 行 643 | `qwen3omni_critic.py` L104；`test_qwen3omni_critic.py` L86 断言 | ✓ |
| payload `"return_audio": False` | plan 行 644 | `qwen3omni_critic.py` L106 | ✓ |
| payload `"max_new_tokens": 1024` | plan 行 645 | `qwen3omni_critic.py` L107 | ✓ |
| `_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)` | plan 行 559 | `qwen3omni_critic.py` L24 | ✓ |
| `except Exception as exc:  # noqa: BLE001 — by design, catch-all to neutral fallback` | plan 行 628 | `qwen3omni_critic.py` L92 | ✓ |
| `_neutral_result` 5 维 + overall 全部 `0.5` | plan 行 672-680 | `qwen3omni_critic.py` L138-143 | ✓ |
| `suggestions=f"评估失败：{err_msg}，建议人工复核"` | plan 行 680 | `qwen3omni_critic.py` L144 | ✓ |
| 测试断言 `0.84 <= result.quality <= 0.86` | plan 行 521 | `test_qwen3omni_critic.py` L92 | ✓ |
| 测试断言 `0.94 <= result.intelligibility <= 0.96` | plan 行 522 | `test_qwen3omni_critic.py` L93 | ✓ |
| `proxies={"http": None, "https": None}`（bypass_proxy=True 时） | plan 行 617 + 行 649 | `qwen3omni_critic.py` L81 + L113；`test_qwen3omni_critic.py` L88 断言 | ✓ |
| `monkeypatch.setattr(mod.requests, "post", fake_post)` | plan 行 504 | `test_qwen3omni_critic.py` L75 | ✓ |

**字面量零偏离**——所有 URL / payload / 0.5 / noqa 注释 / 断言区间与 plan §Task 5 Step 1+3 逐字一致。

---

## 5. 偏离登记

| 项 | plan 期望 | 实测 | 影响 | 处理 |
|---|---|---|---|---|
| Step 4 异常类型 | `ImportError: cannot import name 'build_critic_prompt' from 'src_next.critic.prompts.critic_prompt'`（plan 行 688） | `ModuleNotFoundError: No module named 'src_next.critic.prompts.critic_prompt'` | 无（`ModuleNotFoundError` 是 `ImportError` 子类，Python 3.12 行为；根因是 `critic_prompt.py` 文件根本不存在，与 Task 4 同模式偏离） | 文档记录，无需修复；Task 6 创建 `critic_prompt.py` 后即转绿 |
| Acceptance A self-check 命令期望 | plan 行 707-709 写 `1 passed`（与 Step 4 行 688 矛盾） | 实测 `1 failed` | 无（plan 内部矛盾，以 Step 4 为准——Step 4 是 task 内最终状态描述含 "Proceed to Task 6"，Acceptance A 是跨 task 完成态描述） | 文档记录；Task 6 完成后才转 `1 passed` |

**结构性偏离：零。** 字面量层无任何偏离。

---

## 6. Red Flags 排查

| Red flag 项（plan 行 758-762 + 通用清单） | 是否出现 | 证据 |
|---|---|---|
| `evaluate()` 抛了未捕获异常 | 否 | L90-93 catch-all → `_neutral_result`（见 §3 B5） |
| neutral fallback 返回 `0.0` 而非 `0.5` | 否 | L138-143 全 0.5（见 §3 B6） |
| mock 测试里有真实网络调用 | 否 | L75 monkeypatch 拦截 `requests.post`（见 §3 B7） |
| `_evaluate_inner` 直接信任 `tts_instruction.text` 作为评分输入 | 否 | L101 走 `build_critic_prompt(segment, tts_instruction)`（见 §3 B8） |
| 字面量不一致（URL / payload / 0.5 / noqa / 断言区间） | 否 | §4.2 表 12 项全部逐字一致 |
| scope 越界（提前实现 Task 6 的 `build_critic_prompt`） | 否 | §3 B9：`prompts/` 仅 `__init__.py`，无 `critic_prompt.py` |
| scope 越界（提前实现 Task 7-9 的 conftest / robustness / integration） | 否 | 测试文件仅 2 个测试函数 + 1 工厂 + 1 mock class（grep 命中行 13/23/41/62，无越界） |
| 章节顺序错乱（测试先于实现 / dev doc 缺失） | 否 | commit 含完整 dev doc（371 行）+ 测试 + 实现 |
| 使用 `--no-verify` 跳过 hooks | 否 | commit `48ffea0` 元数据正常，无 skip 痕迹 |
| 改 `src/` 旧链路 | 否 | commit 仅动 `src_next/` + `docs/` |
| 改 `requirements.txt` / 升级依赖版本 | 否 | commit 不含 `requirements*.txt` |
| 硬编码服务器地址（不走 profile） | 部分（critic 服务地址 `http://10.50.121.102:8011` 硬编码在 `__init__` 默认参数 L74） | **设计如此**——critic 不是 pipeline 中的 stage，是独立工具类，CLAUDE.md §3 分层架构里 critic 不属于 profile 驱动的核心层；plan 行 608-613 也明文给默认参数。与 plan 一致，**不算 red flag**。 |
| `git add -A` / `git add .`（误带无关文件） | 否 | commit 仅 3 文件，工作区仍有大量 untracked（`output*/` / `docs/intern_b_*.md` / `webui_old.py` / `input.rar`）未带进 |

**Red flags 总数：0。**

---

## 7. Verdict JSON

```json
{
  "task_id": "Task 5",
  "verdict": "CONDITIONAL PASS",
  "mock_tests": {
    "ran": [
      "python -m pytest src_next/critic/tests/test_qwen3omni_critic.py::test_evaluate_returns_critic_result_on_success -v",
      "python -m pytest src_next/critic/tests/ -m \"not integration\" -v",
      "python -m py_compile src_next/critic/qwen3omni_critic.py src_next/critic/tests/test_qwen3omni_critic.py"
    ],
    "result": "1 failed (ModuleNotFoundError on build_critic_prompt) — plan §Task 5 Step 4 行 685-690 设计的预期半红终态；py_compile OK；等 Task 6 创建 critic_prompt.py 后转绿"
  },
  "integration_tests": "SKIPPED — judge 环境无 Qwen3-Omni 服务访问（10.50.121.102:8011 内网不可达）",
  "smoke_tests": "SKIPPED — judge 环境无 Qwen3-Omni 服务 + 无 good_narration.wav fixture（Task 7 才提供）",
  "static_review": {
    "section_b_pass_count": "9/9",
    "red_flags": "0",
    "literal_drift": "0（12 项关键字面量逐字一致）",
    "scope_creep": "0（prompts/critic_prompt.py 不存在；测试函数仅 2 个，无越界）"
  },
  "reason": "evaluate / _evaluate_inner / _neutral_result / _parse_scoring_json 按 plan 字面量落地（9/9 静态审查全过，零 red flag，零 scope creep，commit 48ffea0 已落盘 3 文件），但 mock test 仍 ImportError — 这是 plan §Task 5 Step 4 设计的预期半红终态（'Proceed to Task 6'），需 Task 6 实现 build_critic_prompt 后转绿，故降级为 CONDITIONAL PASS 而非 FAIL。",
  "blocking_issues": [
    "mock test 未绿（1 failed：ModuleNotFoundError on build_critic_prompt）— plan 设计预期，等 Task 6 解除"
  ],
  "next_action": "进入 Task 6：创建 src_next/critic/prompts/critic_prompt.py，实现 build_critic_prompt(segment, tts_instruction) -> str。签名要与 Task 5 _evaluate_inner 调用一致（build_critic_prompt(segment, tts_instruction)，无 audio_path 参数）。Task 6 完成后重跑 test_evaluate_returns_critic_result_on_success 应得 1 passed，本 task 自动从 CONDITIONAL PASS 升级为 PASS。"
}
```

---

## 8. 给后续 task 的提醒

1. **Task 6 必做**：创建 `src_next/critic/prompts/critic_prompt.py` + `build_critic_prompt(segment: Segment, tts_instruction: ModelSpecificTTSInstruction) -> str`。签名必须与 Task 5 `_evaluate_inner` 调用一致（plan 行 637 / qwen3omni_critic.py L101：`build_critic_prompt(segment, tts_instruction)`——只有 2 个位置参数，无 `audio_path`）。
2. **Task 6 prompt 内容硬要求**：必须强制 Qwen3-Omni 输出**严格 JSON**（5 维：quality / emotion_alignment / character_consistency / rhythm_naturalness / intelligibility + suggestions）。否则 Task 5 的 `_parse_scoring_json` 解析路径走不通（mock response 是 `{"quality":0.85,...}`）。
3. **Task 6 验证命令**：完成后跑 `python -m pytest src_next/critic/tests/test_qwen3omni_critic.py -v` 应得 `2 passed`（含 Task 4 construction 测试 + Task 5 evaluate 测试）。
4. **plan 内部矛盾备忘**：plan §Task 5 Acceptance A 行 705-709 写 `1 passed`，与 §Task 5 Step 4 行 685-690 写 `Expected ImportError` 互相矛盾。后续 task 验收时若再遇同类矛盾，以 Step 4 的 task 内终态描述为准。
5. **Task 7 conftest 提醒**：`good_narration_wav` fixture 名字不能改（KNOWN_ISSUES.md §3 已固化）；路径解析函数必须命名为 `_audio_path`。
6. **Task 8 鲁棒性测试**：5 个测试函数名要从 KNOWN_ISSUES.md §1 逐字复制。
7. **Task 9 集成测试**：5 个测试函数名同样从 KNOWN_ISSUES.md §1 复制。

---

## 9. 一句话总结

Task 5 按 plan §Task 5 Step 1→4 顺序落地 evaluate happy-path 实现 + 测试，9/9 静态审查全过、零 red flag、零字面量偏离、零 scope creep、commit `48ffea0` 已落盘 3 文件；mock test ImportError 是 plan Step 4 设计的预期半红终态（"Proceed to Task 6"），判 **CONDITIONAL PASS**——Task 6 实现 `build_critic_prompt` 后自动升级为 PASS。
