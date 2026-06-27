# src_next 主链路运行及核心模块说明

## 1. 适用场景

本文档适合以下同事阅读：

- 第一次接触 `src_next` 的同事：通过"运行入口 → 执行流程 → 中间产物"建立链路全貌；
- 需要运行链路的开发者：找到正确的命令、profile、样例输入；
- 需要理解核心模块职责的维护者：通过模块表快速定位到关键代码文件；
- 需要排查问题或扩展能力的开发者：通过排障路径和扩展指引找到该改的层。

如果是想先了解整体架构分层，建议先读姊妹文档 `src_next_总体架构说明.md`，再回到本文档看运行细节。

---

## 2. 运行入口

`src_next` 提供两个对等入口，**底层共用同一套 10 stage 编排**：

### 2.1 CLI 入口（适合调试 / 脚本批跑）

```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml
```

完整参数：

| 参数 | 必填 | 默认 | 含义 |
|---|---|---|---|
| `--input` | ✅ | — | 输入故事 txt 路径 |
| `--profile` | ✅（非 mock） | — | profile yaml 路径 |
| `--output-root` | ❌ | 取自 profile | 覆盖 profile 的 output.root |
| `--story-name` | ❌ | 取自文件名 | 覆盖 story name |
| `--mock` | ❌ | false | 走 mock pipeline（离线测试） |
| `--reuse-existing` | ❌ | false | 强制复用 stage 3-9 的中间 JSON |

源码：`src_next/core/audiobook_pipeline.py:main()`

### 2.2 WebUI 入口（适合多人共用 / 可视化）

```bash
# 前台
python -m src_next.app.gradio_webui --host 0.0.0.0 --port 7860

# 后台常驻
nohup python -m src_next.app.gradio_webui \
    --host 0.0.0.0 --port 7860 \
    --concurrency 5 --queue-size 20 \
    > webui.log 2>&1 &
```

完整参数：

| 参数 | 默认 | 含义 |
|---|---|---|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `7860` | 监听端口 |
| `--concurrency` | `5` | 同时运行生成任务上限 |
| `--queue-size` | `20` | 排队上限 |
| `--share` | false | Gradio 公开链接（一般不用） |

源码：`src_next/app/gradio_webui.py:main()`

> WebUI 详细使用方式见 `src_next/app/WEBUI_USAGE.md`（包含启动检查、关闭、输入限制、profile 选择规则、多用户隔离、FAQ 等）。

---

## 3. 一次任务的执行流程

按真实执行顺序，从输入到最终音频：

### 步骤 0：参数解析 + profile 加载

- 文件：`core/audiobook_pipeline.py:run_pipeline()`（第 361 行起）
- 关键函数：`_load_pipeline_profile()`（校验 5 块完整）+ `_prepare_paths()`（计算 output_dir / json_dir / audio_final_dir）
- 中间产物目录在这一步就 mkdir 出来

### 步骤 1：文本读取 + 切分（stage 1）

- 文件：`core/segment_builder.py:build_segments()`
- 输入：`StoryInput`（含全文）
- 输出：`list[Segment]`
- 切分两级：段落切（空行 / 缩进）+ 引号切（智能双引号 / 直角引号）
- 附加：括号注释剥离（如 `托马斯（Thomas）` → `托马斯`）
- 落盘：`json/segments_raw.json`

### 步骤 2：LLM 客户端创建（stage 2）

- 文件：`llm/registry.py:create_llm_client()`
- 输入：profile.llm 块
- 输出：`BaseLLMClient` 实例（`QwenHTTPClient` / `Gemma4HTTPClient` / `MockLLMClient`）
- 无落盘

### 步骤 3：引号语义分类（stage 3）

- 文件：`analysis/quote_classifier.py:classify_and_merge_quotes()`
- 输入：raw segments + LLM
- 输出：merged segments（`segment_type` 标为 narration / dialogue / inner_thought；非真实对白合并回 narration）
- 落盘：`json/segments_after_quote_merge.json` + `json/quote_classifications.json`（调试）

### 步骤 4：说话人识别（stage 4）

- 文件：`analysis/story_resolver.py:resolve_speakers()`
- 输入：merged segments + LLM
- 输出：resolved segments（每个 dialogue segment 的 `speaker` 字段被填好）
- 落盘：`json/resolved_segments.json`

### 步骤 5：角色档案分析（stage 5）

- 文件：`analysis/character_analyzer.py:analyze_characters()`
- 输入：resolved segments + LLM
- 输出：`list[CharacterProfile]`（含 narrator + 各角色；含 `voice_prompt` 字段供 voicebank 用）
- 落盘：`json/characters.json`

### 步骤 6：音色生成（stage 6）

- 文件：`voicebank/qwen3_http.py` / `qwen_voicegenerator.py` / `mock_voicebank.py`
- 输入：characters
- 输出：`VoicebankResult.speaker_to_voice`（speaker → wav 路径映射）
- 落盘：`json/voicebank_result.json` + `voicebank/<speaker>.wav`

### 步骤 7：导演指令（stage 7）

- 文件：`analysis/story_director.py:generate_director_plan()`
- 输入：resolved segments + characters + LLM
- 输出：`list[DirectorInstruction]`（每段一条，11 字段：emotion / emotion_intensity / pace / tone / volume / pitch / pause_hint / stress_words / delivery_instruction 等）
- 落盘：`json/director_plan.json`

### 步骤 8：TTS 指令合并（stage 8）

- 文件：`core/tts_instruction_builder.py:build_tts_instructions()`
- 输入：segments + characters + director_plan + voicebank_result（4 路合并）
- 输出：`list[TTSInstruction]`（每段一条，含 voice_ref + 所有朗读控制字段）
- 字段对齐规则：segment_id 对齐 director；speaker 对齐 character + voicebank
- 落盘：`json/tts_instructions.json`

### 步骤 9：TTS 合成（stage 9）

- 文件：`tts/cosyvoice_http.py` / `indextts_http.py` / `s2pro_adapter.py` / `indextts_adapter.py` / `mock_tts.py`
- 输入：tts_instructions + voicebank_result
- 输出：`list[AudioSegmentResult]`（每段一个 wav 文件）
- 失败段标 `success=False` 但不阻断其他段（除非 profile `stop_on_tts_error: true`）
- 落盘：`json/audio_segment_results.json` + `audio_segments/<seg_id>.wav`

### 步骤 10：音频合并（stage 10）

- 文件：`core/audio_merger.py:merge_audio_segments()`
- 输入：audio_segments + pause_map（来自 director_plan）
- 输出：`AudioResult`（最终拼接 wav，段间插入静音）
- 落盘：`json/audio_result.json` + `audio_final/<story_name>.wav`

### 步骤 11：Summary + PipelineResult

- 文件：`core/audiobook_pipeline.py:_build_pipeline_result()`
- 落盘：`json/pipeline_result.json`（含 `pipeline_summary.stages` 数组，记录每 stage 的 status / elapsed / mode）

### 日志全程伴随

- 文件：`core/logging_utils.py:StageLogger`
- 每 stage 开始 / 完成都通过 StageLogger 写日志
- 终端输出 + `<task_dir>/logs/pipeline.log` 同步落盘（每行带 ISO 时间戳）

---

## 4. 核心模块职责

只列影响主链路理解的关键模块（不全列）：

| 模块/文件 | 主要职责 | 输入 | 输出 | 上游 | 下游 | 说明 |
|---|---|---|---|---|---|---|
| `core/audiobook_pipeline.py` | 10 stage 编排；CLI/WebUI 共用 helper；异常兜底；产物落盘 | input_path + profile | `PipelineResult` | app/CLI | 所有 stage | 链路核心；`run_pipeline`（同步）和 `run_pipeline_stream`（生成器）共享 helper |
| `core/data_models.py` | 所有 dataclass 集中（数据契约） | — | StoryInput / Segment / CharacterProfile / DirectorInstruction / TTSInstruction / VoicebankResult / AudioSegmentResult / AudioResult / PipelineResult | — | 所有 stage | 模型无关字段约定（TTSInstruction 不带 backend 专用字段） |
| `core/segment_builder.py` | stage 1 文本切分 | StoryInput | list[Segment] | input txt | quote_classifier | 一个 segment 只有一个 speaker，从结构上保证下游 LLM 调用最少 |
| `analysis/quote_classifier.py` | stage 3 引号语义分类 | segments + LLM | segments（含 segment_type） | segment_builder | story_resolver | 区分真实对白 / 心理活动 / 强调词等；非对白合并回 narration |
| `analysis/story_resolver.py` | stage 4 说话人识别 | merged segments + LLM | resolved segments（speaker 字段填好） | quote_classifier | character_analyzer | 按段落分组调 LLM；带跨段 speaker 一致性约束 |
| `analysis/character_analyzer.py` | stage 5 角色档案分析 | resolved segments + LLM | list[CharacterProfile] | story_resolver | voicebank / story_director | 含 narrator；输出 voice_prompt 给 voicebank 用 |
| `analysis/story_director.py` | stage 7 导演指令生成 | resolved segments + characters + LLM | list[DirectorInstruction] | character_analyzer | tts_instruction_builder | 11 字段细粒度控制；prompt 强约束 + 字段清洗 + 细粒度 fallback |
| `voicebank/qwen3_http.py` | stage 6 黄区音色生成（HTTP） | characters | VoicebankResult | character_analyzer | tts_instruction_builder / tts adapter | 黄区用；输出 per-character wav |
| `voicebank/qwen_voicegenerator.py` | stage 6 蓝区音色生成（WSL subprocess） | characters | VoicebankResult | character_analyzer | 同上 | 蓝区用；调本地 fish-speech / qwen3-tts CLI |
| `core/tts_instruction_builder.py` | stage 8 指令合并 | segments + characters + director + voicebank | list[TTSInstruction] | 全部上游 | tts adapter | 4 路对齐 + 范围 clamp + 枚举白名单；metadata 携带调试信息 |
| `tts/cosyvoice_http.py` | stage 9 黄区 CosyVoice 合成 | tts_instructions + voicebank | list[AudioSegmentResult] | tts_instruction_builder | audio_merger | HTTP POST；instruct 模式；4 线程并发；wav 缓存命中跳过 |
| `tts/s2pro_adapter.py` | stage 9 黄区 S2Pro 合成（含音色克隆） | tts_instructions + voicebank | list[AudioSegmentResult] | tts_instruction_builder | audio_merger | HTTP POST 到 8010 端口；multipart 上传 reference_audio；控制信号增强层 |
| `tts/indextts_http.py` / `indextts_adapter.py` | stage 9 IndexTTS 合成（HTTP / subprocess） | 同上 | 同上 | 同上 | 同上 | indextts_http 黄区用；indextts_adapter 蓝区 subprocess 调本地 CLI |
| `core/audio_merger.py` | stage 10 音频合并 | audio_segments + pause_map | AudioResult | tts adapter | 最终输出 | stdlib `wave` 模块按段拼；段间插静音；支持 min_silence 下限 |
| `core/logging_utils.py` | StageLogger 类 | — | — | — | 所有 stage | 终端 print + 文件落盘 + 内存累积三合一；WebUI 取 `get_full_text()` 实时显示 |
| `app/gradio_webui.py` | WebUI 入口 | textbox 文本 + profile 下拉 | 浏览器渲染 | — | run_pipeline_stream | profile 自动扫描（utils/yaml_utils）；输入双重校验；task_id 隔离 |
| `profiles/*.yaml` | 配置层 | — | profile dict | — | pipeline | 5 块必填；一个 yaml = 一套完整 llm+voicebank+tts+output+pipeline 组合 |

---

## 5. 输入、配置与输出说明

### 5.1 输入

#### 输入文件类型
- 单一纯文本 `.txt`
- 编码：UTF-8（首选，含 / 不含 BOM 均可）或 GBK
- WebUI 上传额外限制：≤ 20 KB；字符数 ≤ 3500

#### 输入路径
- CLI：`--input <path>`，绝对 / 相对路径都行
- WebUI：文本框粘贴 或 上传 txt；WebUI 把内容写到 `<task_dir>/input/<story>.txt` 再调 pipeline

#### 样例输入
项目自带：
- `input/sample_story_01.txt`：多角色对话 + 旁白 + 心理活动（小松鼠 / 老乌龟 / 小狐狸）— **推荐用作演示**
- `input/sample_story_02.txt`：另一篇样例
- `input/book_*.txt`、`input/dialogue_*.txt`、`input/fairytale_*.txt`、`input/enqing_*.txt`：更大量语料（需要确认是否在 git 仓库中）

#### 输入格式要求
- 段落之间用空行隔开（连续两个 `\n`），或用段首 2+ 空格 / 制表符缩进
- 引号用中文智能双引号 `""` 或直角引号 `「」`，必须成对
- 不成对引号会留在 narration 里

详见 `core/segment_builder.py` 模块 docstring。

### 5.2 配置

#### 配置文件路径
- 目录：`src_next/profiles/`
- 当前完整 profile（满足 5 块）：
  - `blue_qwenvoice_indextts_batch.yaml`（蓝区：Qwen LLM + Qwen VoiceDesign + IndexTTS subprocess）
  - `yellow_qwen3http_cosyvoicehttp.yaml`（黄区：Gemma4 LLM + Qwen3 VoiceDesign + CosyVoice HTTP）
  - `yellow_qwen3http_indexttshttp.yaml`（黄区：Gemma4 LLM + Qwen3 VoiceDesign + IndexTTS HTTP）
  - `yellow_gemma_qwen_s2pro.yaml`（黄区：Gemma4 LLM + Qwen3 VoiceDesign + S2Pro HTTP 含音色克隆）
- 部分 profile（缺块，仅用于单模块测试，不进 pipeline）：
  - `blue_indextts.yaml`、`blue_qwen_voicegenerator.yaml`、`server_qwen_voicegenerator.yaml`

#### 关键配置项

每个 profile 必填 5 块：

| 块 | 必填字段 | 用途 |
|---|---|---|
| `llm` | `backend`、`base_url`/`base_url_env`、`model`/`api_key_env` | LLM 后端选择 |
| `voicebank` | `backend`、`base_url` 或 `engine_root`、`output_subdir` | 音色生成后端 |
| `tts` | `backend`、`base_url` 或 `engine_root`、`output_subdir` | TTS 合成后端 |
| `output` | `root` | 输出根目录 |
| `pipeline` | `save_intermediate_json`、`reuse_existing`、`stop_on_tts_error` | 流程开关 |

可选：
- `webui.display_name` / `webui.description`：WebUI 下拉框友好显示
- `*.extra_args`：各 backend 自定义参数（如 `max_workers` / `temperature` / `bypass_proxy`）

#### 配置在哪里被读取和使用
- 加载：`core/audiobook_pipeline.py:_load_pipeline_profile()` → `yaml.safe_load` + 5 块校验
- 使用：每个 stage 从 `profile_dict` 取自己需要的块
- WebUI 发现：`utils/yaml_utils.py:discover_profiles()` 启动时扫描 `src_next/profiles/*.yaml`，按规则过滤（缺块 / `webui.enabled: false` / 蓝区 profile 都不显示）

### 5.3 输出

#### 最终输出文件
- `<output_root>/<story_name>/audio_final/<story_name>.wav` — 最终有声书音频（44100 Hz / 16-bit mono）

#### 中间 JSON（11 个）
全部在 `<output_root>/<story_name>/json/`：
- `segments_raw.json` — stage 1 输出
- `segments_after_quote_merge.json` — stage 3 输出
- `quote_classifications.json` — stage 3 调试产物（LLM 原始分类）
- `resolved_segments.json` — stage 4 输出
- `characters.json` — stage 5 输出
- `voicebank_result.json` — stage 6 输出
- `director_plan.json` — stage 7 输出
- `tts_instructions.json` — stage 8 输出
- `audio_segment_results.json` — stage 9 输出（含每段成败）
- `audio_result.json` — stage 10 输出
- `pipeline_result.json` — 最终汇总（排障首选）

#### 日志
- `<output_root>/<story_name>/logs/pipeline.log` — 完整 stage 日志（含 ISO 时间戳）
- WebUI 模式额外有项目根的 `webui.log`（Gradio 进程日志）

#### 音频文件
- `<output_root>/<story_name>/voicebank/<speaker>.wav` — 每角色音色参考
- `<output_root>/<story_name>/audio_segments/<seg_id>.wav` — 每段合成音频
- `<output_root>/<story_name>/audio_final/<story_name>.wav` — 最终合并音频

#### WebUI 模式的目录差异
- WebUI 强制 task_id 隔离：`<output_root>/<story_name>/<task_id>/...`（避免多用户互相覆盖）
- CLI 不带 task_id：`<output_root>/<story_name>/...`

---

## 6. 现场演示建议

### 6.1 推荐样例输入

```bash
input/sample_story_01.txt
```

理由：多角色（小松鼠 / 老乌龟 / 小狐狸）+ 旁白 + 心理活动 + 对白，能覆盖 stage 3-7 的所有分支。文本 ~700 字，黄区完整跑 ~3-5 分钟，会议节奏可控。

### 6.2 推荐运行命令

```bash
# 黄区演示（推荐 cosyvoice_http，最稳定）
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml
```

预期耗时：~3-5 分钟（取决于 LLM 速度）。

如果会议时间紧张，可加 `--reuse-existing` 复用之前跑过的中间 JSON，跳过 stage 3-9 的耗时部分。

### 6.3 推荐展示的中间文件（按数据流顺序）

```bash
OUTPUT="output-src-next/yellow_qwen3http_cosyvoicehttp/sample_story_01"

# 1. 文本切分结果（看 segment_id / type / speaker / text）
cat $OUTPUT/json/segments_raw.json | python -m json.tool | head -60

# 2. 引号分类 + 说话人识别后的 segments（看 type / speaker 已填）
cat $OUTPUT/json/resolved_segments.json | python -m json.tool | head -60

# 3. 角色档案（narrator + 3 角色，看 voice_prompt）
cat $OUTPUT/json/characters.json | python -m json.tool

# 4. 导演指令（每段的 emotion / pace / volume / pitch / pause_hint / stress_words / delivery_instruction）
cat $OUTPUT/json/director_plan.json | python -m json.tool | head -80

# 5. TTS 指令（最终送给 adapter 的完整数据，含 voice_ref / metadata）
cat $OUTPUT/json/tts_instructions.json | python -m json.tool | head -80

# 6. 合成结果（每段 wav 成败 + 路径）
cat $OUTPUT/json/audio_segment_results.json | python -m json.tool

# 7. 最终汇总（重点看 pipeline_summary.stages 数组 + rtf + total_time_sec）
cat $OUTPUT/json/pipeline_result.json | python -m json.tool

# 8. 完整日志（10 个 stage 的执行时间）
tail -100 $OUTPUT/logs/pipeline.log

# 9. 最终音频（让听众听效果）
ls -lh $OUTPUT/audio_final/sample_story_01.wav
```

### 6.4 推荐打开的关键代码文件

| 文件 | 打开看什么 | 推荐停留时间 |
|---|---|---|
| `src_next/core/audiobook_pipeline.py` | 10 个 stage 注释 + run_pipeline 主结构（第 361 行起） | 5 min |
| `src_next/core/data_models.py` | 8 个 dataclass 定义（数据契约） | 3 min |
| `src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml` | 5 块结构 + extra_args 设计 | 3 min |
| `src_next/core/segment_builder.py` | 切分两级逻辑 + 括号注释剥离 | 2 min |
| `src_next/analysis/story_director.py` | LLM prompt + 字段清洗 + fallback | 2 min（只看 _DIRECTOR_SYSTEM_PROMPT） |
| `src_next/tts/registry.py` | 工厂模式 + 懒导入 | 1 min |

### 6.5 不建议在会上展开的细节

- LLM adapter 的 HTTP 错误重试 / 超时处理（`llm/qwen_http.py` / `gemma4_http.py`）
- analysis 层各模块的 prompt 工程细节（内容多，建议单独 session）
- `audio_merger.py` 的 stdlib `wave` 模块 PCM 字节拼接细节
- Gradio 版本兼容（`queue()` API 3.x vs 4.x 的 try/except）
- WebUI 的 13 输出组件 generator yield 顺序
- voicebank WSL subprocess 包装细节（蓝区专用）
- S2Pro 的内联标签转换规则表（15000+ 标签）

---

## 7. 常见问题与排障路径

### 7.1 通用排查顺序

遇到任何任务失败，按以下顺序定位：

1. **看入口参数**：确认 `--input` 和 `--profile` 路径正确；profile yaml 5 块齐全
2. **看配置加载**：profile 解析报错信息（缺块 / 缺 backend / 缺 output.root）
3. **看中间产物**：`<task_dir>/json/` 哪个 JSON 写到一半停了 → 上一个 stage 就是失败点
4. **看日志**：`<task_dir>/logs/pipeline.log` 找 `[N/10] <stage> ... failed in N.NNs — <错误>` 行
5. **看汇总**：`<task_dir>/json/pipeline_result.json` 的 `pipeline_summary.stages` 数组找 `status: failed`
6. **定位模块代码**：根据失败 stage 名定位到对应模块文件

### 7.2 典型问题对照表

| 现象 | 可能原因 | 排查路径 |
|---|---|---|
| **任务一开始就退出** | 输入文件不存在 / profile 路径错 / profile 缺块 | 看终端 stderr；运行 `python -c "from src_next.utils.yaml_utils import discover_profiles; ..."` 确认 profile 能被发现 |
| **stage 2 失败** | LLM 服务不可达 / API key 错 / 超时 | `curl <llm.base_url>`；检查 `.env`（`QWEN_BASE_URL` / `QWEN_API_KEY`） |
| **stage 3-5 / 7 失败** | LLM 返回非 JSON / JSON 字段缺失 / LLM 超时 | 看 `<task_dir>/logs/pipeline.log` 的 traceback；查对应 analysis 模块的 `_clean_*` 函数（清洗逻辑）和 `_extract_*` 函数（解析逻辑） |
| **stage 6 失败** | voicebank HTTP 服务不可达 / WSL venv 路径错 / GPU OOM | 检查 `<voicebank backend>.base_url`；`ls voicebank/` 看哪些 wav 没生成 |
| **stage 9 大量失败** | TTS 服务不可达 / voice_ref 路径错 / 音频编码失败 / GPU OOM | 看 `audio_segment_results.json` 每段的 `error` 字段；逐段 curl TTS 服务 |
| **stage 10 失败 / 最终音频为空** | 所有 stage 9 都失败 / wav 格式不一致 | 看 `audio_segment_results.json` 有没有 success=true 的段；`ls audio_segments/` 看实际生成的 wav |
| **WebUI 下拉框空** | profile 扫描失败 / 启动 cwd 错 / yaml 缺块 | 看 `webui.log` 的 `[gradio_webui]` 错误行；UI 上方也会显示具体错误 |
| **WebUI 任务目录找不到** | task_id 路径错 / output.root 不在项目根 | 看 WebUI 结果栏的「任务目录」字段；`find <output_root> -name "<task_id>" -type d` |
| **reuse_existing 不生效** | 中间 JSON 不存在 / 文件路径不对 / story_name 不一致 | 检查 `<task_dir>/json/<expected>.json` 是否存在；reuse 是按 stage 名匹配 JSON 文件名 |
| **同一角色不同段音色不一致** | voicebank 跨调用不稳定 / TTS adapter 没用 voice_ref | 看 `tts_instructions.json` 每段的 `voice_ref` 是否指向同一 wav；查 TTS adapter 是否真的把 wav 当 reference |

### 7.3 关键日志位置速查

```bash
TASK_DIR="<output_root>/<profile_name>/<story_name>"

# pipeline 全程日志（首选）
tail -100 $TASK_DIR/logs/pipeline.log

# 失败 stage 的错误详情
grep -A 5 "failed in" $TASK_DIR/logs/pipeline.log

# WebUI 进程日志（看启动错误 / Gradio 异常）
tail -100 webui.log

# 单 stage 中间产物
cat $TASK_DIR/json/<stage_output>.json | python -m json.tool
```

---

## 8. 后续扩展方式

### 8.1 新增 TTS 后端

需要改 3 处：

1. **新建 adapter**：`src_next/tts/<new>_adapter.py`
   - 继承 `BaseTTSAdapter`（`tts/base.py`）
   - 实现 `synthesize(instructions, voicebank_result, output_dir, ...) -> list[AudioSegmentResult]`
   - 单段失败不阻断其他段
   - 参考 `tts/cosyvoice_http.py`（HTTP 模式）或 `tts/indextts_adapter.py`（subprocess 模式）

2. **注册到工厂**：`src_next/tts/registry.py`
   ```python
   if backend == "<new>_http":
       from .<new>_adapter import <New>Adapter
       return <New>Adapter(**config)
   ```

3. **新建 profile yaml**：`src_next/profiles/<region>_<llm>_<voicebank>_<new>.yaml`
   - 5 块齐全
   - `tts.backend: <new>_http`

**core / analysis 层完全不动。**

### 8.2 新增 LLM 后端

类似 TTS 模式：

1. 新建 `src_next/llm/<new>_http.py` 继承 `BaseLLMClient`（`llm/base.py`）
2. `llm/registry.py` 加分支
3. profile `llm.backend: <new>_http`

### 8.3 新增 voicebank 后端

类似 TTS 模式：

1. 新建 `src_next/voicebank/<new>.py` 继承 `BaseVoicebankAdapter`（`voicebank/base.py`）
2. `voicebank/registry.py` 加分支
3. profile `voicebank.backend: <new>`

### 8.4 新增 / 调整分析模块

如果新加分析能力（如语气分析、修辞识别等）：

1. 在 `analysis/` 新建模块（参考 `story_director.py` 模式）
2. 在 `core/audiobook_pipeline.py` 加一个新 stage（注意更新 stage 总数注释 `[N/10]` → `[N/11]`）
3. 在 `core/data_models.py` 加新 dataclass（如果输出是新结构）
4. 在 `core/tts_instruction_builder.py` 把新分析结果合并进 `TTSInstruction`（如果需要）

**注意**：新加 stage 会改变 stage 总数，会影响所有 profile 的 `pipeline.save_intermediate_json` 兼容性，需要谨慎。建议优先在不增加 stage 数的前提下扩展（如把新能力塞进现有 stage 内部）。

### 8.5 新增配置项

- profile 级别：直接在 yaml `extra_args` 加字段，adapter 内部读取（无需改 core）
- 全局级别：当前**没有全局 config**（设计如此），如需引入需要团队讨论

### 8.6 新增输出格式

当前输出固定 wav。如需新增（如 mp3 / ogg）：

- 短期：在 `core/audio_merger.py` 加可选参数控制输出格式（需要 ffmpeg / pydub）
- 长期：改 `AudioResult` dataclass 支持多格式（需要确认是否值得）

### 8.7 新增测试样例

- 输入样例放 `input/` 目录
- 跑 pipeline 验证：`python -m src_next.core.audiobook_pipeline --input input/<new>.txt --profile <yaml>`
- 中间产物会自动落到 `<output_root>/<profile>/<new>/`，可以人工核验切分 / 角色 / 导演指令是否符合预期

### 8.8 扩展时的代码改动量参考

| 扩展类型 | 必改文件数 | 是否动 core / analysis |
|---|---|---|
| 新 TTS backend | 3（adapter + registry + yaml） | ❌ |
| 新 LLM backend | 3 | ❌ |
| 新 voicebank backend | 3 | ❌ |
| 新 profile（同 backend 组合） | 1（yaml） | ❌ |
| 新 analysis 能力（新 stage） | 4-5 | ✅（pipeline + data_models + builder） |
| 调整切分规则 | 1（segment_builder） | ✅（core） |
| 新输出格式 | 1-2 | ✅（audio_merger + 可能 data_models） |

---

## 9. 需要确认的点

以下信息本文档无法从代码直接确定，需要团队补充：

1. **`input/` 目录下的非 sample 文件是否在 git 仓库**：`book_*.txt` / `dialogue_*.txt` / `fairytale_*.txt` / `enqing_*.txt` 数量很多，本文档不确定它们是否已提交。需要确认（运行 `git ls-files input/ | head`）。
2. **黄区各 HTTP 服务的真实可用性**：`yellow_qwen3http_cosyvoicehttp.yaml` 中 base_url 指向的服务器（10.50.121.102 / 10.50.121.123）当前是否在线？需要运维确认。
3. **黄区 S2Pro 8010 端口的部署状态**：`api_server_s2pro_8010.py` 是用户在服务器上独立扩展的版本，本文档不确定它是否已纳入自动化部署 / 重启策略。
4. **典型故事的实测耗时与 RTF**：本文档建议演示 3-5 分钟，但实际数字需要从历史任务的 `pipeline_result.json` 中提取。
5. **WebUI 在生产环境的部署形态**：是否走 systemd / supervisor？是否需要 nginx 反向代理？需要运维确认。
6. **测试样例的回归基线**：当前是否有"标准样例 + 标准输出"用于回归测试？`src_next/analysis/test_analysis_qwen.py` 是冒烟测试脚本，但似乎没有断言基线。需要确认。
