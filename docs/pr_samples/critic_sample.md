# Critic 评分样例（基于 mock 数据，待真实服务验证）

> ⚠️ **本样例不是真实 Qwen3-Omni 输出。** 由于本机无法访问 Qwen3-Omni 服务（详见
> `src_next/critic/KNOWN_ISSUES.md`），这里展示的是 prompt 设计的预期 I/O 格式。
> 真实服务可访问后，会跑一次真实评分并替换本文件内容。

## 输入

- **Audio path**: `/server-side/path/to/good_narration.wav`（5-10s TTS 输出；客户端会读取文件 bytes 并 base64 编码后传给 `/v1/omni/chat` 的 `audio` 字段）
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

## 评分维度（每项 0-10 分制，附 A/B/C/D 等级）
1. quality: ...
2. emotion_alignment: ...
3. character_consistency: ...
4. rhythm_naturalness: ...
5. intelligibility: ...
[... 完整 prompt 见 src_next/critic/prompts/critic_prompt.py ...]

## 输出格式（嵌套 JSON）
**只输出严格的 JSON**：
{"scores":{"quality":{"score":8.5,"grade":"A","reason":"...","problems":[]}, ...},
 "overall_score":8.6, "overall_grade":"A",
 "main_problems":[...], "suggestions":[...]}
```

## 期望的 Qwen3-Omni 响应

```json
{
  "request_id": "<generated>",
  "text": "{\"scores\":{\"quality\":{\"score\":8.7,\"grade\":\"A\",\"reason\":\"音质清晰干净\",\"problems\":[]},\"emotion_alignment\":{\"score\":8.2,\"grade\":\"A\",\"reason\":\"情感基本匹配\",\"problems\":[\"忧伤感稍弱\"]},\"character_consistency\":{\"score\":9.1,\"grade\":\"A\",\"reason\":\"符合叙述者定位\",\"problems\":[]},\"rhythm_naturalness\":{\"score\":8.5,\"grade\":\"A\",\"reason\":\"节奏自然\",\"problems\":[]},\"intelligibility\":{\"score\":9.3,\"grade\":\"A\",\"reason\":\"字字清晰\",\"problems\":[]}},\"overall_score\":8.6,\"overall_grade\":\"A\",\"main_problems\":[],\"suggestions\":[\"音质清晰；情感稍弱，建议增强忧伤语气\"]}",
  "inference_time": "..."
}
```

> 嵌套 schema 由 `_normalize_nested_scoring` 处理：每个维度的 `score`（0-10 分制）除以 10 归一化为 0-1，`grade` 字段被丢弃，`main_problems + suggestions` 列表合并去重后取前 3 条用「；」拼接。LLM 自报的 `overall_score` 故意忽略（由 `CriticResult.from_json` 重算 5 维平均，避免 LLM 的冗余信息引入噪声）。

## 解析后的 CriticResult

| 字段 | 值 | 来源 |
|---|---|---|
| segment_id | sample | 调用方传入 |
| quality | 0.87 | `scores.quality.score=8.7` → 8.7/10 |
| emotion_alignment | 0.82 | `scores.emotion_alignment.score=8.2` → 8.2/10 |
| character_consistency | 0.91 | `scores.character_consistency.score=9.1` → 9.1/10 |
| rhythm_naturalness | 0.85 | `scores.rhythm_naturalness.score=8.5` → 8.5/10 |
| intelligibility | 0.93 | `scores.intelligibility.score=9.3` → 9.3/10 |
| **overall** | **0.876** | 5 维平均，由 `CriticResult.from_json` 计算（LLM 的 `overall_score=8.6` 被忽略） |
| suggestions | "音质清晰；情感稍弱，建议增强忧伤语气" | `main_problems + suggestions` 合并去重取前 3 |
| needs_repair(threshold=0.7, overall_floor=0.75) | **False** | min(dims)=0.82 ≥ 0.7 且 overall=0.876 ≥ 0.75 → 无需修复 |

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
