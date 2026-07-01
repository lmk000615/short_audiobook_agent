# Short Audiobook Director Agent

面向**短篇中文故事**的有声书导演 Agent 原型。它不是简单把文字读出来，而是先理解文本中的旁白 / 对白 / 角色 / 语境，生成可配音的导演脚本，再调用可插拔的 TTS 后端跑通最小语音生成闭环。

当前聚焦 300–3000 字的中文短篇：儿童故事、寓言、课文、绘本、简短分角色文本。不追求长篇、商业级音质、复杂 UI、配乐音效或完整有声剧。

---

## 核心链路

一次任务经过 10 个 stage，从故事 txt 到最终有声书 wav：

| Stage | 模块 | 产物 |
|---|---|---|
| 1/10 build_segments | `core/segment_builder.py` | `segments_raw.json` |
| 2/10 create_llm_client | `llm/registry.py` | — |
| 3/10 quote_classifier | `analysis/quote_classifier.py` | `segments_after_quote_merge.json` |
| 4/10 story_resolver | `analysis/story_resolver.py` | `resolved_segments.json` |
| 5/10 character_analyzer | `analysis/character_analyzer.py` | `characters.json` |
| 6/10 voicebank | `voicebank/*` adapter | `voicebank_result.json` + `<speaker>.wav` |
| 7/10 story_director | `analysis/story_director.py` | `director_plan.json` |
| 8/10 tts_instruction_builder | `core/tts_instruction_builder.py` | `tts_instructions.json` |
| 9/10 tts_synthesis | `tts/*` adapter | `audio_segment_results.json` + `<seg_id>.wav` |
| 10/10 audio_merger | `core/audio_merger.py` | `audio_final/<story>.wav` |

中间的**导演层**（stage 3–7）是项目核心：
- 谁在说话？哪部分是旁白？哪部分是真对白？
- 不同角色应该用什么音色？
- 这句话应该用什么情绪、语速、音量、语气朗读？

LLM 先生成导演意图，再据此选音色参考、合成语音、拼接成最终音频。

---

## 当前架构

项目正在从旧链路（`src/`）向新链路（`src_next/`）重构。**当前活跃主战场是 `src_next/`**，`src/` 已冻结——可以读、可以引用，但不允许改（除非明确要求修旧链路）。

### 分层

```text
txt + profile
     │
     ▼
   app/          应用入口（CLI / WebUI）
     │
     ▼
   core/         编排层（10 stage 主流程 + 数据契约）
     │
     ├─► analysis/    语义分析（LLM 驱动：引号分类 / 说话人 / 角色 / 导演）
     ├─► llm/         LLM 适配（多后端可插拔）
     ├─► voicebank/   音色参考适配（多后端可插拔）
     └─► tts/         语音合成适配（多后端可插拔）
              │
              ▼
          最终音频 wav

底层支撑：profiles/（yaml 配置）+ utils/（通用工具）
```

**核心设计模式**：registry + adapter。每层有抽象接口（`base.py`）+ 多个 backend 实现 + 工厂函数（`registry.py`）+ profile 决定走哪个 backend。**切换后端 = 改 profile yaml，core / analysis 零改动。**

---

## 当前支持的后端

| 类型 | 已实现 backend |
|---|---|
| LLM | `qwen_http` / `gemma4_http` / `mock_llm` |
| Voicebank | `qwen3_http` / `qwen_voicegenerator`（subprocess）/ `mock_voicebank` |
| TTS | `cosyvoice_http` / `indextts_http` / `indextts`（subprocess）/ `s2pro_http` / `mock_tts` |

**关键不变量**：`TTSInstruction` 是**模型无关的通用合成指令**，不带任何 backend 专用字段（如 `indextts_speed` / `cosyvoice_prompt`）。backend 专用参数由各 adapter 内部根据通用字段推断。这是分层边界的核心保证，破了会让 core / analysis 层被具体后端污染。

### 当前可用 profile

| Profile | 区域 | 组合 |
|---|---|---|
| `yellow_qwen3http_cosyvoicehttp.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + CosyVoice3（**最稳，演示首选**）|
| `yellow_qwen3http_indexttshttp.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + IndexTTS HTTP |
| `yellow_gemma_qwen_s2pro.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + S2Pro（含音色克隆，8010 端口）|
| `blue_qwenvoice_indextts_batch.yaml` | 蓝区 | Qwen + Qwen VoiceDesign subprocess + IndexTTS subprocess |

---

## 快速开始

### 环境准备

```bash
pip install -r requirements.txt
```

### 黄区演示（推荐）

```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml
```

预期耗时 3–5 分钟。产物落到 `output-src-next/yellow_qwen3http_cosyvoicehttp/sample_story_01/`。

### 离线 mock 测试（不依赖任何服务）

```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --mock
```

### 启 WebUI

```bash
python -m src_next.app.gradio_webui --host 0.0.0.0 --port 7860
```

详细参数见 `src_next_主链路运行及核心模块说明.md` 第 2 节。

---

## 项目原则

### 1. 不把分析层写成万能正则

中文文本中的引号不一定都是对白：

```
桂花成熟时，就应当"摇"。
童年时代的"摇花乐"。
```

这里的引号是强调或概念，不是人物对白。因此分析层由 LLM 判断引号类型 / 说话人 / 语义关系，规则层只做切分和结构整理。

### 2. segment 是送给 TTS 的最小单位

每个 segment 应只对应一个说话人和一个音色。例：

```
小松鼠笑着递给他一个篮子，说："当然来得及，只要你愿意开始。"
```

不能整句作为一个 TTS segment，应该拆成：

```
旁白：小松鼠笑着递给他一个篮子，
小松鼠：当然来得及，只要你愿意开始。
```

这样旁白用旁白音色、角色对白用角色音色才能实现。`src_next/core/segment_builder.py` 在结构上保证"一个 segment 一个 speaker"。

### 3. 先做最小闭环，再逐步增强

优先级：文本切分 → 旁白/对白区分 → 说话人识别 → 角色档案 → 音色生成 → 导演指令 → TTS 合成 → 音频拼接。

暂不优先：Web UI 富功能、背景音乐、环境音效、长篇支持、商业级音质、大规模语音库管理。

---

## 项目边界

当前是原型，验证「文本理解 → 声音导演 → TTS 生成 → 音频输出」最小闭环是否可行。不要求：完美识别所有说话人、完美处理所有课文、完美情绪控制、商业级音质、完整有声剧。

---

## 文档

| 文档 | 用途 |
|---|---|
| `CLAUDE.md` | Claude Code 操作手册（开发约束 / 验证清单 / 维护规则）|
| `src_next/README.md` | src_next 分层设计总览 |
| `src_next_总体架构说明.md` | 全链路 + 数据契约 + 中间产物关系 |
| `src_next_主链路运行及核心模块说明.md` | 运行命令 / 排障路径 / 扩展指引 |
| `src_next/app/WEBUI_USAGE.md` | WebUI 使用细节 |
| `src_next/tts/S2PRO_ADAPTER_README.md` | S2Pro adapter 内部实现（含 8010 端口 / 音色克隆）|
| `usage_guide_*.md`（项目根）| 各后端服务的接入细节（IP / 端口 / 鉴权 / curl 示例）|

---

## Claude Code 协作要求

1. **一次只改一个 stage / 一个层**，每次改动后都要能运行
2. **不要一次性生成全部功能**，不要过度针对某一篇文本写死规则
3. **新功能一律进 `src_next/`**，`src/` 已冻结
4. 不要随意修改无关文件，不要把本项目代码写进 TTS 引擎源码目录
5. 涉及环境 / 依赖 / 网络问题时，先判断是代码问题、环境问题、网络问题还是配置问题，再处理
6. 详细开发约束、验证清单、维护规则见 `CLAUDE.md`

---

## 一句话总结

> 面向短篇中文故事的有声书导演 Agent：它不只是把文字读出来，而是尝试把文本理解成可配音、可表演、可编辑的有声书制作脚本，并用可插拔的 LLM / voicebank / TTS 后端跑通最小语音生成闭环。
