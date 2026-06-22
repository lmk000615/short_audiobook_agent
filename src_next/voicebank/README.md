# voicebank/ 音色库适配层

> 本层是 `src_next/` 重构架构中的音色参考适配层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图看懂 src_next」。

## 一、这一层负责什么

* 接收 `list[CharacterProfile]`，为每个角色（含 narrator）准备音色参考。
* 输出 `VoicebankResult`，核心字段是 `speaker_to_voice`（speaker 名 → voice_ref）。
* 支持多个后端：Mock / QwenVoiceGenerator / 未来 CosyVoice / IndexTTS / FishPro / …
* 后端通过 `registry.create_voicebank_adapter(backend, **config)` 工厂创建。
* 环境差异（蓝区 vs 服务器）通过 `profiles/*.yaml` 配置切换，不写进 adapter。

## 二、这一层不负责什么

* **不合成正文音频**（那是 `tts/` 的事）。
* 不生成 tts instructions（那是 `core/tts_instruction_builder.py` 的事）。
* 不调用故事分析 LLM（那是 `analysis/` 的事）。
* 不抽角色、不分析性格（同上）。
* 不读 profile yaml（profile 由 `app/` 加载后注入构造参数）。
* 不持久化业务中间产物（那是 `core/` 的事）。

## 三、voicebank 和 tts 的区别

| 维度 | voicebank | tts |
|---|---|---|
| 输入 | `list[CharacterProfile]` | `list[TTSInstruction]`（已含 voice_ref） |
| 输出 | `speaker → voice_ref` 映射（每个角色**一个**音色文件） | 每段文本**一个**音频文件 |
| 调用频次 | 每个故事一次（角色数有限） | 每段 segment 一次（数量多） |
| 是否消费 voice_ref | **生产** voice_ref | **消费** voice_ref |
| 类比 | 选演员、定妆照 | 演员念台词 |

voicebank 在 tts 之前，先把每个 speaker 的「音色身份」准备好；tts 拿着这个身份去念每一段台词。两层完全解耦：换 tts 模型不需要重做 voicebank；换 voicebank 模型也不影响 tts 调用接口。

## 四、为什么输出是 `speaker_to_voice`

`VoicebankResult.speaker_to_voice` 是 `dict[str, str]`：

```python
{
    "narrator": "/path/to/voicebank/narrator.wav",
    "小松鼠":    "/path/to/voicebank/小松鼠.wav",
    "老乌龟":    "/path/to/voicebank/老乌龟.wav",
}
```

理由：

1. **speaker 是稳定标识**，segment 引用 speaker 名而不是 voice_ref 路径，让 tts_instruction_builder 只关心「谁说什么」，不关心「声音在哪」。
2. **voice_ref 可以替换**：同一角色换音色时，只动 voicebank 输出，不动 segment / character / director_plan。
3. **多段复用**：一个角色可能念 10 段台词，voice_ref 只生成 1 次，10 段共享。
4. **后端无关**：值可以是 `.wav` 路径、`mock://` 占位、未来的 embedding id，调用方只需要把它原样传给 tts 即可。

## 五、为什么文件按 backend 类型命名，而不是按运行环境命名

❌ **不要** 这样命名：

```text
qwen_voicegenerator_blue.py
qwen_voicegenerator_server.py
```

✅ **要** 这样命名：

```text
qwen_voicegenerator.py
```

理由：

1. **同一模型在两个环境的调用方式相同**：CLI 参数、输入 JSON 格式、输出文件命名规则都一样，差异只在路径。
2. **避免代码重复**：如果按环境拆文件，每次改调用接口都要改两份，且两份 90% 内容相同。
3. **环境是部署概念，不是模型概念**：环境信息（路径、venv）属于配置，不属于代码。
4. **方便扩展**：未来加第 3 个环境（如 CI、容器）只需要新增一份 profile yaml，不需要新增 adapter。

## 六、为什么路径不能写死在 adapter 里

`qwen_voicegenerator.py` 中**没有**任何 `F:/`、`/data3/`、`M:/`、`C:/` 等绝对路径。所有路径只能来自：

1. **构造参数**：`generator_root`、`script_path`、`model_path`、`preset_path`、`python_executable`；
2. **profile 配置**：`app/` 读 yaml 后注入构造参数；
3. **环境变量**：未来如需要可加，但目前不读；
4. **函数参数**：`prepare_voicebank(characters, output_dir, **kwargs)` 的 `output_dir`。

理由：

1. 写死路径 = 把代码绑死在某台机器上，换机器就坏；
2. 写死路径 = git 仓库污染本机绝对路径，PR review 时 reviewer 不知道这是什么；
3. 写死路径 = 测试时无法 mock，CI 永远跑不过；
4. 路径是部署细节，应该在部署时配置，而不是在写代码时决定。

## 七、蓝区和服务器如何通过 profile 区分

两份 yaml，路径不同但 backend 相同：

| profile | 用途 | adapter |
|---|---|---|
| `blue_qwen_voicegenerator.yaml` | 蓝区本地路径 | `qwen_voicegenerator.py` |
| `server_qwen_voicegenerator.yaml` | 服务器路径 | `qwen_voicegenerator.py`（**同一个文件**） |

切换环境的流程：

1. `app/` 读 `profiles/blue_qwen_voicegenerator.yaml`；
2. 取 `voicebank` 段的字段，调用 `create_voicebank_adapter("qwen_voicegenerator", **voicebank_config)`；
3. 拿到 adapter 后注入 core pipeline。

切到服务器：把第 1 步换成 `server_qwen_voicegenerator.yaml`，**其余代码一行不动**。

## 八、MockVoicebankAdapter 的作用

`mock_voicebank.py` 的 `MockVoicebankAdapter`：

* 不调用真实模型、不访问网络、不依赖 GPU；
* 不创建文件、不创建目录；
* 为每个 character 返回 `mock://<name>` 占位 voice_ref；
* `success=True`，让 pipeline 可以无障碍继续走。

典型用途：
1. 没装 Qwen VoiceGenerator 的开发机做 core pipeline 联调；
2. 单元测试替换真实 voicebank；
3. CI 环境（无 GPU、无模型）跑端到端 smoke test。

## 九、QwenVoiceGeneratorAdapter 的作用

`qwen_voicegenerator.py` 的 `QwenVoiceGeneratorAdapter`：

* 蓝区 / 服务器**共用**这一个 adapter 文件；
* 构造函数只接受配置参数，不读任何本机路径；
* `prepare_voicebank` 完成所有「不依赖模型」的准备工作：
  1. 创建 `output_dir/voicebank/`；
  2. 写 `voicegenerator_input.json`（每个角色的 voice_prompt 等）；
  3. 写 `adapter_config.json`（保存本次使用的路径快照）；
  4. 写 `NEXT_STEPS.md`（给出预期 subprocess 命令，方便手动执行）。

### v1 不真实调用 subprocess

理由：voicegenerator 项目的 CLI 接口还没敲定，先不绑死。

默认行为（`dry_run=False`）：抛 `VoicebankError`，清晰说明下一步怎么走，**不假装生成成功**。

`dry_run=True`：完成 prep 工作，返回 `VoicebankResult(success=False, speaker_to_voice=预期路径)`，用于下游 pipeline 联调（tts 层会看到这些路径但 wavs 实际不存在）。

### v2 接入 subprocess 的方式（未来）

只需要在 `prepare_voicebank` 里把 `_build_command()` 的结果传给 `subprocess.run`，路径全部来自构造参数，**adapter 代码改动最小**。NEXT_STEPS.md 里给出的命令格式就是 v2 会真实执行的那条。

## 十、未来如何新增 IndexTTS / FishPro / CosyVoice 等 backend

按以下步骤：

1. **新建 adapter 文件**：`src_next/voicebank/indextts_voicebank.py`，实现 `BaseVoicebankAdapter`；
2. **在 registry 注册**：在 `registry.create_voicebank_adapter` 加一个分支：
   ```python
   if backend == "indextts":
       from .indextts_voicebank import IndexTTSVoicebankAdapter
       return IndexTTSVoicebankAdapter(**config)
   ```
3. **新增 profile yaml**：`profiles/blue_indextts.yaml` 等，填路径；
4. **不改 core / 不改 analysis / 不改其他 backend**。

**不要**：
* 改 `core/`（它只依赖 `BaseVoicebankAdapter`）；
* 改 `analysis/`（同上）；
* 改 `base.py`（接口稳定后不应该再变）；
* 改其他已有 backend 文件（互不影响）。

## 十一、当前实现状态

```text
src_next/voicebank/
├── __init__.py                # ✅ 轻量入口（只导出 BaseVoicebankAdapter + VoicebankError）
├── base.py                    # ✅ BaseVoicebankAdapter + VoicebankError
├── mock_voicebank.py          # ✅ MockVoicebankAdapter（离线占位）
├── qwen_voicegenerator.py     # ✅ QwenVoiceGeneratorAdapter（通用，v1 不真实调用）
├── registry.py                # ✅ create_voicebank_adapter 工厂
└── README.md                  # 本文件

src_next/profiles/
├── blue_qwen_voicegenerator.yaml   # ✅ 蓝区路径占位
└── server_qwen_voicegenerator.yaml # ✅ 服务器路径占位
```

### 哪些已完成

* 接口抽象和异常统一；
* Mock 实现（无外部依赖）；
* Qwen 通用 adapter 结构完整，prep 工作可执行；
* 蓝区 / 服务器 profile 模板就绪。

### 哪些未做（留给后续迭代）

* `QwenVoiceGeneratorAdapter` v2：真实 subprocess 调用；
* IndexTTS / FishPro / CosyVoice 等 backend；
* voice_ref 复用机制（同一角色跨 story 复用，避免重复生成）；
* 失败重试和超时控制。
