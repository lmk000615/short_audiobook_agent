# Integration 测试交接文档 — AttributeAwareQwen3OmniCritic

> 本文件给**有黄区模型服务访问权限**的机器使用。本机（开发机）无法访问
> `10.50.121.102:8011`，所以 integration 测试在本机默认 skip。
>
> 开发机已经跑过的：14 个 mock 测试全部通过（`python -m pytest
> src_next/critic/tests/test_attribute_critic.py -v`）。Mock 测试覆盖了
> 解析、fallback、契约、持久化的全部逻辑路径，integration 测试只验证
> "真实服务返回的内容能被同一套解析逻辑吃下"。

---

## 1. 你需要什么

| 项 | 要求 |
|---|---|
| 网络 | 能访问黄区内网 `10.50.121.102:8011`（Qwen3-Omni 服务）|
| 代理 | **必须 bypass_proxy**（`HTTP_PROXY` / `HTTPS_PROXY` 环境变量对内网 IP 无效）|
| Python | 3.10+，已 `pip install -r requirements.txt` |
| 环境变量 | `RUN_INTEGRATION=1`（激活 integration 测试）|
| 可选：fixture 音频 | `tests/fixtures/good_narration.wav`（见下方 §3）|
| 可选：fixture 根目录 | `CRITIC_FIXTURES_ROOT=/data/.../critic-fixtures`（服务端音频路径覆盖）|

---

## 2. 运行命令

### 2.1 跑全部 mock + integration

```bash
cd F:/akoasm/short_audiobook_agent

# Windows PowerShell
$env:RUN_INTEGRATION=1
python -m pytest src_next/critic/tests/test_attribute_critic.py -v

# Linux / macOS / Git Bash
RUN_INTEGRATION=1 python -m pytest src_next/critic/tests/test_attribute_critic.py -v
```

**期望**：14 passed + 2 passed（integration）= 16 passed。

### 2.2 只跑 integration

```bash
RUN_INTEGRATION=1 python -m pytest src_next/critic/tests/test_attribute_critic.py -v -m integration
```

**期望**：2 passed, 14 deselected。

### 2.3 跑全套 critic 测试（含回归）

```bash
RUN_INTEGRATION=1 python -m pytest src_next/critic/tests/ -v
```

**期望**：~59 passed, ~0 skipped（如果 fixture 齐全）。

⚠️ **必须串行**：Qwen3-Omni 服务有 `infer_lock`，并发请求会 silent 超时。**不要**
加 `-n auto`（pytest-xdist）或类似并发参数。

---

## 3. Fixture 音频

Integration 测试用到的音频 fixture：

| fixture 名 | 用途 | 默认路径 |
|---|---|---|
| `good_narration_wav` | 高质量叙述音频，验证评分整体偏高 | `tests/fixtures/good_narration.wav` |
| `bad_clipping_wav` | 含爆音/截断的低质量音频，验证 quality 低分 | `tests/fixtures/bad_clipping.wav` |
| `emotion_mismatch_wav` | 情感明显不匹配的音频，验证 emotion_alignment 低分 | `tests/fixtures/emotion_mismatch.wav` |

### 3.1 fixture 路径覆盖

如果音频文件在服务端而非本地（如黄区机器上的 `/data/.../critic-fixtures/`），
用环境变量覆盖：

```bash
export CRITIC_FIXTURES_ROOT=/data/critic-fixtures
RUN_INTEGRATION=1 python -m pytest src_next/critic/tests/test_attribute_critic.py -v -m integration
```

详见 `tests/conftest.py:_audio_path()`。

### 3.2 当前 attribute_critic integration 测试实际用到哪些 fixture

| 测试 | 用到的 fixture |
|---|---|
| `test_integration_evaluate_real_audio` | `good_narration_wav` |
| `test_integration_persistence_round_trip` | `good_narration_wav` |

⚠️ 如果 fixture 文件不存在，测试会 fail（不是 skip）— 这是预期，提醒你准备数据。

---

## 4. 期望输出与断言

### 4.1 `test_integration_evaluate_real_audio`

调用 `AttributeAwareQwen3OmniCritic.evaluate(audio_path, segment, inst, director)`，
断言：

- `result.segment_id == "s1"`
- `0.0 <= result.quality <= 1.0`（其他 4 维同理）
- `0.0 <= result.overall <= 1.0`
- `result.suggestions` 是 str
- `result.extracted_attributes` / `expected_attributes` / `attribute_consistency` 都是 dict
- **关键 invariant**：`result.expected_attributes["emotion"] == di.emotion`
  `result.expected_attributes["intensity"] == di.emotion_intensity`
  （无论 LLM 怎么回填，期望属性永远跟随 DirectorInstruction）

**不**断言具体分数（LLM 输出有抖动），只断言结构 + 真相源 invariant。

### 4.2 `test_integration_persistence_round_trip`

调用 `evaluate` + `save_attribute_critic_session`，断言 `scoring.json` 含：

- `extracted_attributes` / `expected_attributes` / `attribute_consistency` 三个新键
- 5 维分数字段：`quality` / `emotion_alignment` / `character_consistency` /
  `rhythm_naturalness` / `intelligibility`
- `overall` / `suggestions`

---

## 5. 排障指南

### 5.1 HTTP 错误

| 错误 | 原因 | 排查 |
|---|---|---|
| `HTTP 404` | 端点路径错 | 确认 url = `http://10.50.121.102:8011/v1/omni/chat`（不是 `/audio_analysis`）|
| `HTTP 500` | 服务端推理失败 | 重试 1-2 次；持续 500 联系运维 |
| `ConnectTimeout` | 网络不通 / 代理泄漏 | 检查 `bypass_proxy=True`、ping `10.50.121.102` |
| `ReadTimeout` | 服务推理慢 | 调大 `timeout=180`，或检查服务负载 |

### 5.2 JSON 解析错误

错误信息 `no JSON object found in response`：

- 看 `raw_text` 实际内容（错误日志前 200 字符）
- 常见原因：LLM 返回了自然语言（"Sorry, I cannot..."）、被审查拒绝、返回空字符串
- 此时 `evaluate` 会走 neutral fallback，**不抛异常**，返回 `overall=0.5`

### 5.3 字段缺失错误

如果 LLM 返回的 JSON 缺了 `extracted_attributes` / `attribute_consistency`：

- 不抛异常，`result.extracted_attributes` 或 `attribute_consistency` 会是 `{}`
- 5 维评分仍正常解析（因为 `_normalize_nested_scoring` 是宽容的）

### 5.4 测试 fail 但 mock 全过

如果 mock 全过但 integration fail：

- 99% 是 LLM 输出 schema 不稳定 — 让 LLM 重试 2-3 次
- 1% 是 fixture 音频问题 — 用 `pytest -s` 看 stderr
- 不要为了过 integration 而 weaken mock 测试断言

---

## 6. 产物检查

跑完 integration 后，应检查 `output/critic/<audio_stem>/scoring.json`：

```bash
# Linux/macOS
ls output/critic/good_narration/
python -c "
import json
d = json.load(open('output/critic/good_narration/scoring.json'))
assert 'extracted_attributes' in d, 'missing extracted_attributes'
assert 'expected_attributes' in d, 'missing expected_attributes'
assert 'attribute_consistency' in d, 'missing attribute_consistency'
print('OK: scoring.json has all 3 new keys')
print('overall_verdict:', d['attribute_consistency'].get('overall_verdict'))
print('inconsistency_summary:', d['attribute_consistency'].get('inconsistency_summary'))
print('extracted evidence:', d['extracted_attributes'].get('evidence'))
"
```

期望输出包含：
- `overall_verdict` 是 `high` / `medium` / `low` 之一
- `inconsistency_summary` 是非空中文一句话
- `extracted_attributes.evidence` 是非空中文一句话（critic 必填）

---

## 7. 回归保护

跑完 integration 后，**必须再跑一次 mock 全套**确保没有 integration 副作用污染：

```bash
# 不带 RUN_INTEGRATION，确保 integration 不会污染 mock 结果
unset RUN_INTEGRATION  # Linux/macOS
Remove-Item Env:RUN_INTEGRATION  # PowerShell

python -m pytest src_next/critic/tests/ -v
```

期望：51 passed + 8 skipped（与开发机一致）。

---

## 8. 已知限制

1. **服务有 infer_lock**：integration 测试串行调用，每个 evaluate ~5-15 秒。两个 integration 测试总耗时 ~30 秒。
2. **LLM 输出有抖动**：相同音频多次评估，分数会有 ±0.05 波动，属于正常。所以 integration 测试只断言结构 + invariant，不断言具体分数。
3. **fixture 不在 git 仓库**：音频文件体积大，需要单独准备。详见 `src_next/critic/KNOWN_ISSUES.md §3`。
4. **DirectorInstruction 在 integration 中是测试 mock 数据**（`emotion="sad"`,
   `emotion_intensity=0.8` 等），不来自真实 director_plan。要测真实 director 链路
   需要先跑一遍 main pipeline 拿到 director_plan.json，再加载进来。
