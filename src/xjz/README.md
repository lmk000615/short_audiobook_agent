# TTS Expressive Workflow

把一篇中文故事 `.txt` 端到端合成一段多角色、有情绪起伏的 `final.wav`。

## 工作流总览

```
sample_story_01.txt
      │
      ▼  step1_split.py (LLM x2)
voice_design.json   voice_clone.json
      │                    │
      ▼                    │
prompt_voices/*.wav       │   (step2_design.py — Qwen3 VoiceDesign)
      │                    │
      └──────┬─────────────┘
             ▼
      segments/*.wav             (step3_clone.py — CosyVoice zero-shot)
             │
             ▼
         final.wav                (step4_merge.py — wave 拼接 + 段间静音)
```

| Stage | 入口脚本 | 干什么 | 调什么 |
|-------|----------|--------|--------|
| 1 | `step1_split.py` | LLM 提取角色 + 切分对话/旁白（≤50 汉字） | DashScope qwen3.6-plus（Anthropic-compatible） |
| 2 | `step2_design.py` | 每个角色生成一个中性参考音色 `prompt_voice.wav` | Qwen3-TTS VoiceDesign HTTP API |
| 3 | `step3_clone.py` | 每段文本克隆对应角色音色 + 叠加该段情绪 | Fun-CosyVoice3 zero-shot/instruct HTTP API |
| 4 | `step4_merge.py` | 按段序拼接所有 wav，段间插 300ms 静音 | Python 标准库 `wave` |

## 依赖

```bash
pip install anthropic requests
```

仅此两项外部依赖（其余用 Python 标准库：`wave` / `json` / `pathlib` / `argparse` / `base64`）。

## 配置

复制 `.env.example`（或自己写）：

```dotenv
LLM_BASE_URL=https://dashscope.aliyuncs.com/apps/anthropic/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=qwen3.6-plus
```

工作流常量（服务 URL、固定中性句子、克隆模式、静音时长等）集中在 `common/config.py`，按需修改。

## 用法

### 一键端到端

```bash
bash run.sh                                          # 默认跑 sample_story_01.txt
bash run.sh F:/akoasm/dataset/text/不懂就要问.txt     # 自定义输入
```

### 单步运行（便于调试/重跑）

```bash
python step1_split.py --input <txt>          [--force]
python step2_design.py --input <txt>
python step3_clone.py --input <txt>          [--mode zero_shot|instruct]
python step4_merge.py --input <txt>          [--silence-ms 300]
```

每一步**幂等**：发现输出文件已存在就跳过；用 `--force`（step1）/删除对应产物强制重跑。

## 目录结构

```
model-test/
├── step1_split.py        # txt → voice_design.json + voice_clone.json
├── step2_design.py       # voice_design.json → prompt_voices/*.wav
├── step3_clone.py        # voice_clone.json → segments/*.wav
├── step4_merge.py        # segments/*.wav → final.wav
├── run.sh                # bash 编排器
├── common/
│   ├── config.py         # 全部常量集中
│   ├── llm_client.py     # DashScope Anthropic-compatible 封装
│   └── tts_client.py     # Qwen3 VoiceDesign + CosyVoice HTTP 客户端
├── prompts/
│   ├── character_extract.txt   # Stage 1 角色提取 system prompt
│   └── segment_split.txt       # Stage 1 段落切分 system prompt
└── outputs/
    └── <story-stem>/     # 每个输入文本一个子目录
        ├── voice_design.json
        ├── voice_clone.json
        ├── prompt_voices/
        │   ├── manifest.json
        │   ├── 旁白.wav
        │   └── ... .wav
        ├── segments/
        │   ├── 0001.wav
        │   └── ... .wav
        └── final.wav
```

## 数据格式

### `voice_design.json`

- 顶层：`source_file` / `language` / `neutral_sample_text` / `characters[]`
- 每个角色含 7 个字段：`name` / `role` / `gender` / `age_group` / `personality` / `voice_profile` / `emotion_for_design`，代码再补 `control_rule`
- **关键约束**：`voice_profile` 只描述静态音色（性别、年龄、声线高度、音色厚薄、吐字、基础语速），**禁止**时序词（"前期/后期/渐渐/逐渐"），剧情弧线信息只放在 `personality`

### `voice_clone.json`

- 顶层：`source_file` / `language` / `total_segments` / `segments[]`
- 每段含 `segment_id`（全局递增、连续）/ `paragraph_id` / `type`(`narration`/`dialogue`) / `speaker` / `text`（≤50 汉字）/ `emotion` / `instruct`
- `instruct` 只描述情绪/语速/语调，不描述音色（音色由 `prompt_voice` 决定）

### `prompt_voices/manifest.json`

Stage 2 生成的索引，供 Stage 3 查询每个角色的参考音频和对应的转写文本：

```json
{
  "旁白": {"wav_path": "prompt_voices/旁白.wav", "sample_text": "大家好，今天我来跟你们说几句话。"},
  "小松鼠": {"wav_path": "prompt_voices/小松鼠.wav", "sample_text": "..."}
}
```

## 设计要点

- **为什么用 zero-shot 而不是 instruct 模式做 VoiceClone**：zero-shot 既克隆了 Stage 2 设计出来的音色，又通过 `prompt_text` 前段的指令叠加每段情绪，音色相似度和情绪可控性两者兼得。`step3_clone.py --mode instruct` 可以切换为纯 instruct 模式（牺牲音色相似度换更纯粹的情绪控制），便于做 A/B 对比
- **为什么每角色一个 `prompt_voice`**：多角色故事中角色音色需要稳定可区分，单一参考音色无法表达。Stage 3 按段查 `manifest` 找对应参考音频
- **为什么用固定中性句子做 VoiceDesign 采样**：参考音频若带强情绪（如愤怒的台词），后续 zero-shot 克隆会被该情绪污染。中性句子作为参考，把情绪控制权完全交给 Stage 3 的 `instruct`
- **为什么不加字数/关键词二次校验**：约束集中在 `prompts/*.txt`，给清晰示例，信任 LLM 输出，避免代码层叠堆防御性逻辑
- **段间为什么加 300ms 静音**：CosyVoice 单段输出本身已含自然停顿，但段与段之间直接拼会很赶；300ms 既不打断节奏又让对话切换更分明。`--silence-ms 0` 可关闭

## 端到端验证清单

在有网络联通 `10.154.39.97` 的环境里：

```bash
curl --noproxy '*' http://10.154.39.97:8007/health   # Qwen3 VoiceDesign
curl --noproxy '*' http://10.154.39.97:8005/health   # CosyVoice
bash run.sh
```

预期：`outputs/sample_story_01/final.wav` 是一段约 1-2 分钟、4 个角色音色稳定且情绪起伏明显的故事音频。

## 常见问题

**Q: step1 LLM 返回的不是合法 JSON 怎么办？**
`common/llm_client._parse_json_lenient` 会先剥 ```` ```json ... ``` ```` 围栏，再退化为抓取最外层 `{...}` 子串。若仍失败，会在该步抛 `json.JSONDecodeError`，重新跑或调小输入文本长度即可。

**Q: Stage 2/3 请求超时？**
两个 TTS 服务都设了 300s 超时。若实际更慢，改 `common/config.HTTP_TIMEOUT`。

**Q: 怎么只重跑某一步？**
删掉对应产物即可：
- 重跑 Stage 2 某个角色：删 `prompt_voices/<角色名>.wav`
- 重跑 Stage 3 某段：删 `segments/<id:04d>.wav`
- 重跑 Stage 4：删 `final.wav`

**Q: 想给段间加更长/更短的停顿？**
`python step4_merge.py --input <txt> --silence-ms 500`（设为 0 关闭）。
