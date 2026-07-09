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

## 2. API 端点已敲定：`/v1/omni/chat` + base64 音频

> **2026-07-09 更新：** 经真实服务测试，`audio_analysis` 端点不接受本地文件路径形式的 `audio` 字段（task card §1.4 设想的 (a) 路径不成立，实际触发了下方风险场景 (b)）。已切换到 `/v1/omni/chat + base64 音频`，验证可行。下方 fallback 路径已转正为正式实现，本节作为历史决策记录保留。

**当前状态：** `qwen3omni_critic.py::_evaluate_inner` 已使用：
```python
audio_b64 = base64.b64encode(Path(audio_path).read_bytes()).decode("ascii")
payload = {
    "audio": audio_b64,           # base64 字符串，不再是文件路径
    "text": prompt_text,
    "return_audio": False,
    "max_new_tokens": 1024,
}
url = f"{self.base_url}/v1/omni/chat"
```

`/v1/omni/chat` 文档（ussage_guide 第 3 节）明确支持 `audio + text + return_audio`，response 格式与 `audio_analysis` 在 `return_audio=false` 时一致（`{"request_id":..., "text":..., "inference_time":...}`）。响应解析链路（`_parse_scoring_json` / `_normalize_nested_scoring` / `CriticResult.from_json`）零改动。

---

**历史记录（task card §1.4 原设想，已失效）：**

原按 task card §1.4 走 `audio_analysis + text`，但 API 文档（`ussage_guide_qwen3_omni.md` 第 8 节）只列了 `audio / task / return_audio / speaker / max_new_tokens` 五个字段，`text` 未列。曾预判三种风险：
- (a) 接受 `text` 字段并作为 prompt 使用 → task card 设想成立，正常工作 ❌ 实测不成立
- (b) 忽略 `text` 字段，只按 `task=sound_analysis` 返回通用描述 → critic 拿不到评分 JSON，会触发 neutral 0.5 fallback ✅ **实测命中此场景，且服务端不接受文件路径形式的 audio 字段**
- (c) 报 400 错误 → 同样触发 neutral 0.5 fallback

原 fallback 建议（"只改两行 URL + payload"）未涵盖 base64 编码需求，实际改动量约 10 行（含 base64 编码 + import 调整 + docstring + 测试断言）。

## 3. 测试音频 fixture 未实际准备

**状态：** `conftest.py` 里的 `good_narration_wav` 等 fixture 只解析路径，不验证文件存在。

**原因：** 服务不可访问时准备 fixture 没意义（测试都 skip）。

**准备方法（服务可访问后）：**
1. 用现有 TTS pipeline 生成 3 段 5-10s wav（好/坏/情感不匹配）
2. 放到服务器可读路径，或设置 `CRITIC_FIXTURES_ROOT` 环境变量
3. 路径解析逻辑见 `conftest.py::_audio_path`
