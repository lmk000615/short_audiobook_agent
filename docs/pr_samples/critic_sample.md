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
