# profiles/ 运行配置层

> 本层是 `src_next/` 重构架构中的配置层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图看懂 src_next」。

## 一、这一层负责什么

* 用 yaml 描述当前运行使用哪种 LLM。
* 描述当前使用哪种 voicebank backend。
* 描述当前使用哪种 TTS backend。
* 描述输出目录结构。
* 描述并发、batch size、timeout 等运行参数。
* 支持服务器环境和蓝区本地环境通过配置切换。

## 二、这一层不负责什么

* 不包含具体业务逻辑（不知道什么是角色、导演计划）。
* 不调用模型、不发 HTTP 请求。
* 不实现 adapter（adapter 在 `llm/`、`tts/`、`voicebank/` 里）。
* 不参与 pipeline 编排。

## 三、输入

* yaml 配置文件本身。

## 四、输出

* 加载后的配置字典（被 `app/` 读取）。
* 选定的 adapter 组合：`llm` + `tts` + `voicebank` 三个具体后端。
* 输出路径、并发参数等运行时选项。

## 五、未来会放的文件

```text
profiles/
├── mock_debug.yaml            # 全 Mock，不依赖任何服务器（蓝区本地首选）
├── server_gemma4_cosy.yaml    # 服务器 Gemma4 + CosyVoice
├── server_gemma4_index.yaml   # 服务器 Gemma4 + IndexTTS
└── blue_local_light.yaml      # 蓝区本地轻量后端组合
```

### 示例

```yaml
profile_name: server_gemma4_cosy

llm:
  backend: gemma4_http
  base_url: http://10.154.39.83:8000/v1/chat/completions
  model: gemma4-31B
  max_workers: 3
  bypass_proxy: true

voicebank:
  backend: cosyvoice
  output_subdir: voicebank

tts:
  backend: cosyvoice
  output_subdir: audio_segments

output:
  root: output-src-next
```

## 六、和其他层的交互

* **被 `app/` 读取**：app 解析 yaml 后，根据 backend 字段实例化具体 adapter。
* **决定 `llm/`、`tts/`、`voicebank/` 的具体后端**：通过 backend 字段切换。
* **被 `core/` 间接使用**：core 拿到的是已实例化的 adapter，不直接读 yaml。
* **不依赖任何业务层**：本层是纯配置描述。
