# CLAUDE.md — Short Audiobook Agent

> 本文件是 Claude Code 在本仓库工作时的**操作手册**。每次进入本项目请优先阅读本文件，再阅读 `src_next/README.md`。
>
> 本文件**会随 `src_next/` 大改同步更新**（见 §11 维护规则）。如果你发现本文件描述与实际代码不一致，**以代码为准**，并在完成本次任务后顺手修正本文件。

---

## 1. 项目是什么

把一段**短篇中文故事文本**（300–3000 字，如儿童故事 / 寓言 / 课文）变成一版可播放的**简易有声书音频**。

核心不是"把字读出来"，而是中间的**导演层**：

```
谁在说话？哪部分是旁白？哪部分是真对白？
不同角色应该用什么音色？这句话应该用什么语气读？
```

LLM 先生成导演意图，再据此选音色参考、合成语音、拼接成最终音频。

**当前阶段不追求**：长篇小说、商业级音质、Web UI 富功能、配乐音效、复杂有声剧。

---

## 2. 仓库结构：哪里是主战场

```
short_audiobook_agent/
├── src_next/          ← 当前主战场（重构后的新链路）
├── src/               ← 旧链路，已冻结。可以读，不允许改
├── input/             ← 故事样例 txt
├── output/            ← 历史运行产物
├── output-src-next/   ← src_next 默认输出根（profile 可覆盖）
├── docs/              ← 历史设计文档
├── notes/             ← 项目笔记
├── models/            ← 本地模型权重（不入 git）
├── config/            ← 旧链路配置（src_next 不用）
├── usage_guide_*.md   ← 各后端服务的接入说明（黄区 IP / 端口 / 鉴权）
└── run.py             ← 旧链路入口（不要再扩展）
```

**铁律**：新功能一律进 `src_next/`。`src/` 仅在用户**明确要求**修旧链路时才能动；否则即便发现 bug 也先在 `src_next/` 修。

---

## 3. src_next 分层架构

| 层 | 路径 | 职责一句话 | 不应该知道 |
|---|---|---|---|
| 入口层 | `app/` | CLI / WebUI 启动；读 profile；调 pipeline | 模型请求细节 |
| 编排层 | `core/` | 10 stage 主流程；数据契约；产物落盘 | 模型部署地址 |
| 分析层 | `analysis/` | 引号分类 / 说话人 / 角色档案 / 导演指令 | TTS 是什么、部署在哪 |
| LLM 适配层 | `llm/` | 统一 `BaseLLMClient`；多后端切换 | 故事业务 |
| 音色层 | `voicebank/` | 统一 `BaseVoicebankAdapter`；生成角色参考 wav | 正文合成 |
| 合成层 | `tts/` | 统一 `BaseTTSAdapter`；按指令合成每段 wav | 故事分析逻辑 |
| 配置层 | `profiles/` | 一个 yaml = 一套完整 llm+voicebank+tts+output+pipeline 组合 | 业务逻辑 |
| 工具层 | `utils/` | yaml / 文件 / 时间通用工具 | 当前 pipeline |

**核心设计模式**：`registry + adapter`。每层有 `base.py`（抽象接口）+ `<backend>_xxx.py`（具体实现）+ `registry.py`（懒导入工厂函数）+ profile（决定走哪个 backend）。

**切换后端 = 改 profile yaml，core/analysis 零改动。**

---

## 4. 主链路：一次任务的 10 个 stage

`src_next/core/audiobook_pipeline.py` 集中编排，**所有 stage 在同一个文件里**：

| Stage | 模块 | 产物 |
|---|---|---|
| 1/10 build_segments | `core/segment_builder.py` | `segments_raw.json` |
| 2/10 create_llm_client | `llm/registry.py` | （无落盘） |
| 3/10 quote_classifier | `analysis/quote_classifier.py` | `segments_after_quote_merge.json` + `quote_classifications.json` |
| 4/10 story_resolver | `analysis/story_resolver.py` | `resolved_segments.json` |
| 5/10 character_analyzer | `analysis/character_analyzer.py` | `characters.json` |
| 6/10 voicebank | `voicebank/*_http.py` 或 `mock_voicebank.py` | `voicebank_result.json` + `voicebank/<speaker>.wav` |
| 7/10 story_director | `analysis/story_director.py` | `director_plan.json` |
| 8/10 tts_instruction_builder | `core/tts_instruction_builder.py` | `tts_instructions.json` |
| 9/10 tts_synthesis | `tts/*_http.py` 或 `mock_tts.py` | `audio_segment_results.json` + `audio_segments/<seg_id>.wav` |
| 10/10 audio_merger | `core/audio_merger.py` | `audio_result.json` + `audio_final/<story>.wav` |
| 末尾 | `_build_pipeline_result` | `pipeline_result.json`（汇总，排障首选） |

**两个对等入口，共用同一套 stage 编排**：
- CLI：`python -m src_next.core.audiobook_pipeline --input ... --profile ...`
- WebUI：`python -m src_next.app.gradio_webui --host 0.0.0.0 --port 7860`

---

## 5. 关键不变量（修改时必须保持）

这些是分层边界，**破了就乱**：

1. **`TTSInstruction` 是模型无关的通用合成指令**。不带任何 backend 专用字段（如 `indextts_speed` / `cosyvoice_prompt` / `s2pro_emotion_vector`）。backend 专用参数由各 adapter 内部根据通用字段推断。
   - 定义：`core/data_models.py:TTSInstruction`
   - 合并：`core/tts_instruction_builder.py:build_tts_instructions()`

2. **`DirectorInstruction` 也是通用语义层**，不写任何 TTS 后端专用字段。11 个字段：emotion / emotion_intensity / pace / tone / volume / pitch / pause_hint / stress_words / delivery_instruction 等。

3. **core / analysis 不 import 具体 backend**。只能依赖 `BaseLLMClient` / `BaseTTSAdapter` / `BaseVoicebankAdapter` 抽象接口。违反这一条 = 分层崩塌。

4. **一个 `Segment` 只有一个 speaker**。这是 segment_builder 的结构保证，让下游 LLM 调用次数最少。

5. **每个 stage 的中间产物都要可独立加载**。`--reuse-existing` 模式靠的就是这点。新增 stage 时记得同时支持 reuse。

6. **黄区内网调用必须 `bypass_proxy: true`**。`10.50.121.102` / `10.50.121.123` 等内网 IP 如果走全局代理会绕出去再绕回来，导致连接超时 / silent failure。这是黄区 profile 的硬性要求。

---

## 6. 配置与运行

### Profile 5 块结构（必填）

```yaml
llm:        # backend + base_url/base_url_env + model + api_key_env + timeout
voicebank:  # backend + base_url/engine_root + output_subdir
tts:        # backend + base_url/engine_root + output_subdir
output:     # root（输出根目录）
pipeline:   # save_intermediate_json / reuse_existing / stop_on_tts_error
```

可选：`webui.display_name` / `*.extra_args`（如 `max_workers` / `bypass_proxy`）。

### 当前可用 profile

| Profile | 区域 | 组合 |
|---|---|---|
| `yellow_qwen3http_cosyvoicehttp.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + CosyVoice3（**最稳，演示首选**）|
| `yellow_qwen3http_indexttshttp.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + IndexTTS HTTP |
| `yellow_gemma_qwen_s2pro.yaml` | 黄区 | Gemma4 + Qwen3 VoiceDesign + S2Pro（含音色克隆，8010 端口）|
| `blue_qwenvoice_indextts_batch.yaml` | 蓝区 | Qwen + Qwen VoiceDesign subprocess + IndexTTS subprocess |
| `blue_indextts.yaml` / `blue_qwen_voicegenerator.yaml` | 蓝区 | 部分 profile（缺块，仅用于单模块测试，**不进 pipeline**）|

### 常用命令

```bash
# 黄区演示（推荐）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml

# 离线 mock 测试（不依赖任何服务）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --mock

# 复用中间 JSON 跳过 stage 3-9（调试 stage 10 用）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --reuse-existing

# 启 WebUI
python -m src_next.app.gradio_webui --host 0.0.0.0 --port 7860
```

---

## 7. 产物结构

CLI 模式：

```
<output_root>/<story_name>/
├── input/<story>.txt                # WebUI 才写；CLI 直接用原文件
├── json/
│   ├── segments_raw.json            # stage 1
│   ├── segments_after_quote_merge.json  # stage 3
│   ├── quote_classifications.json   # stage 3 调试
│   ├── resolved_segments.json       # stage 4
│   ├── characters.json              # stage 5
│   ├── voicebank_result.json        # stage 6
│   ├── director_plan.json           # stage 7
│   ├── tts_instructions.json        # stage 8
│   ├── audio_segment_results.json   # stage 9（含每段成败）
│   ├── audio_result.json            # stage 10
│   └── pipeline_result.json         # 汇总（排障首选）
├── voicebank/<speaker>.wav
├── audio_segments/<seg_id>.wav
├── audio_final/<story>.wav
└── logs/pipeline.log                # 含 ISO 时间戳
```

WebUI 模式额外有 task_id 隔离：`<output_root>/<story_name>/<task_id>/...`。

---

## 8. 常见扩展场景

| 场景 | 改动范围 | core/analysis 是否动 |
|---|---|---|
| 新增 TTS 后端 | `tts/<new>_adapter.py` + `tts/registry.py` 一行 + 新 profile yaml | ❌ |
| 新增 LLM 后端 | `llm/<new>_http.py` + `llm/registry.py` 一行 + 新 profile yaml | ❌ |
| 新增 voicebank 后端 | `voicebank/<new>.py` + `voicebank/registry.py` 一行 + 新 profile yaml | ❌ |
| 新增 profile（同 backend 组合） | 仅 yaml | ❌ |
| 调整切分规则 | `core/segment_builder.py` | ✅ |
| 调整导演指令逻辑 | `analysis/story_director.py` | ✅（analysis）|
| 新增 analysis 能力（新 stage） | `analysis/*.py` + `core/audiobook_pipeline.py`（注意 stage 总数注释 `[N/10]` → `[N/11]`）+ 可能 `core/data_models.py` + 可能 `core/tts_instruction_builder.py` | ✅ |

详细扩展步骤见 `src_next_主链路运行及核心模块说明.md` 第 8 节。

---

## 9. 开发硬约束

承接 `src_next/README.md` §9 的约束，并补充：

1. **一次只改一个 stage / 一个层**。改之前先说"要动哪个文件、为什么"。
2. **每次改动后 `py_compile` 通过**，再考虑跑 pipeline。
3. **绝不在 `analysis/` 或 `core/` 里 import 具体 backend**（如 `from src_next.tts.cosyvoice_http import ...`）。违反 = 分层崩塌。
4. **绝不在 `core/data_models.py` 加 backend 专用字段**。新字段加在 adapter 内部。
5. **绝不改 `src/`**（除非用户明确要求修旧链路）。
6. **绝不改 `requirements.txt` / 升级依赖版本**（除非用户明确要求）。
7. **绝不硬编码服务器地址**进任何模块。所有地址走 profile。
8. **绝不跳过 hooks / `--no-verify`**（除非用户明确要求）。
9. **删除文件 / 跨目录批量移动前必须先请求确认**。
10. **任何"看起来完成了"必须有验证证据**（跑通的命令 + 输出摘要）。不允许肉眼扫一眼就说 DONE。

---

## 10. 验证清单

每次改完代码，按需选跑：

```bash
# 1. 语法检查（最低门槛）
python -m py_compile src_next/<changed_file>.py

# 2. 离线 mock 端到端（最快验证主链路没断）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt --mock

# 3. 单 stage smoke test（不重跑 analysis，从已有 JSON 复现下游）
python -m src_next.core.test_tts_from_artifacts
python -m src_next.core.test_audio_merger_from_artifacts
python -m src_next.core.test_tts_instruction_builder

# 4. analysis 冒烟测试
python -m src_next.analysis.test_analysis_qwen

# 5. 真实 profile 端到端（最贵，仅在需要时跑）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml
```

完成后**汇报**：
- 改了哪些文件 + 每个文件为什么改
- 跑了上面哪几条验证 + 实际输出摘要（PASS/FAIL）
- 是否有遗留问题

---

## 11. 维护规则（重要）

> **本项目当前处于活跃重构期，`src_next/` 链路不是最终版本，会持续大改。**

每次在 `src_next/` 完成代码改动后，**必须同步检查并按需更新本 CLAUDE.md**：

| 改动类型 | 是否需要更新本文件 | 更新位置 |
|---|---|---|
| 新增 / 删除 / 重命名 stage | ✅ 必更新 | §4 表格 + §5 不变量 |
| 新增 / 删除 TTS / LLM / voicebank backend | ✅ 必更新 | §6 profile 表 + §8 扩展表 |
| 新增 / 删除 profile yaml | ✅ 必更新 | §6 profile 表 |
| 改动 `core/data_models.py` 的字段 | ✅ 必更新 | §5 不变量（如果动了 backend 专用字段约束）|
| 改动 stage 落盘 JSON 文件名 | ✅ 必更新 | §4 表格 + §7 产物结构 |
| 调整目录分层（新增 / 重命名子目录） | ✅ 必更新 | §2 + §3 |
| 修复单个 adapter 内部 bug | ❌ 不需要 | — |
| 新增 input 样例 / 临时调试脚本 | ❌ 不需要 | — |

**自检方法**：完成本次任务前，对照上表扫一遍本次改动，命中即更新对应章节。更新后在 commit message 里加一行 `docs: sync CLAUDE.md with src_next changes`。

### 11.1 CLAUDE.md 更新时必须同步 README.md

README.md 是 GitHub 仓库首页展示文件，必须与项目实际状态保持同步。CLAUDE.md 按上表更新时，**必须同时检查 README.md 对应章节是否需要同步更新**。

**章节对应关系**（CLAUDE.md → README.md）：

| CLAUDE.md 章节 | README.md 对应章节 |
|---|---|
| §1 项目是什么 | 「首段描述」+「一句话总结」 |
| §2 仓库结构 | 「当前架构」开头一句（src_next 主战场 / src 冻结） |
| §3 分层架构 | 「当前架构」→「分层」图 |
| §4 主链路 10 stage | 「核心链路」10 stage 表 |
| §5 关键不变量 | 「当前支持的后端」末尾的不变量说明（提炼 1 条即可）|
| §6 配置与运行 | 「快速开始」命令 + 「当前可用 profile」表 |
| §9 开发硬约束 | 「Claude Code 协作要求」（精简到 5–6 条）|
| §12 参考文档 | 「文档」表 |

**README 不同步的内容**（这些是 Claude Code 操作细节，README 不展开）：
- §7 产物结构、§8 扩展场景、§10 验证清单、§11 维护规则本身

**定位差异**：
- README 是 GitHub 面向访客的入口文档，**比 CLAUDE.md 更精简**，突出「项目是什么 / 怎么试 / 文档在哪」。
- CLAUDE.md 是 Claude Code 操作手册，**更详细**，突出「怎么改 / 不能做什么 / 怎么验证」。

**自检**：CLAUDE.md 改完后扫一遍上面对应的 README 章节，命中即同步。commit message 加 `docs: sync README.md with CLAUDE.md`（可与上一条合并为 `docs: sync CLAUDE.md and README.md with src_next changes`）。

---

## 12. 参考文档（按优先级）

| 文档 | 何时读 |
|---|---|
| **本文件（CLAUDE.md）** | 每次进入项目先读 |
| `src_next/README.md` | 第一次接触 src_next 分层设计 |
| `src_next_总体架构说明.md` | 需要全链路 + 数据契约全景 |
| `src_next_主链路运行及核心模块说明.md` | 需要运行命令 / 排障 / 扩展指引 |
| `src_next/app/WEBUI_USAGE.md` | WebUI 部署 / 使用细节 |
| `src_next/tts/S2PRO_ADAPTER_README.md` | S2Pro adapter 内部实现（含 8010 端口 / 音色克隆）|
| `usage_guide_*.md`（项目根）| 各后端服务的接入细节（IP / 端口 / 鉴权 / curl 示例）|

---

## 13. 一句话总结

**面向短篇中文故事的有声书导演 Agent**：先把文本理解成可配音的导演脚本（谁在说、什么语气、什么音色），再用可插拔的 LLM / voicebank / TTS 后端跑通最小语音生成闭环。当前活跃在 `src_next/`，分层严格、配置驱动、可观测性强，但仍在持续重构。
