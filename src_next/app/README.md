# app/ 应用入口层

> 本层是 `src_next/` 重构架构中的一层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图懂 src_next」。

## 一、这一层负责什么

* 提供命令行入口，让用户能从 shell 启动有声书生成流程。
* 提供 WebUI pipeline 入口（未来接入）。
* 读取用户选择的 profile 配置。
* 把用户输入文件、profile 配置传递给 `core/` 主流程。
* 展示最终结果路径，给 WebUI 返回可展示的 result 字典。

## 二、这一层不负责什么

* 不直接调用 LLM。
* 不直接调用 TTS。
* 不直接解析故事结构、不抽取角色。
* 不直接拼接音频。
* 不硬编码任何具体模型后端（Gemma4 / CosyVoice 等）。
* 不写业务流程主干（那是 `core/` 的事）。

## 三、输入

* 用户输入的 txt 文件路径（或 WebUI 文本框内容）。
* 用户选择的运行 profile 名称（例如 `mock_debug`、`server_gemma4_cosy`）。
* WebUI 上传的文件 / 表单参数。

## 四、输出

* 控制台日志（启动信息、STAGE 进度）。
* 最终生成结果路径（最终音频、中间 JSON 目录）。
* WebUI 可展示的 `result` 字典。

## 五、未来会放的文件

```text
app/
├── run.py            # 真实模型入口（接 Gemma4 / CosyVoice 等）
├── run_mock.py       # Mock 链路入口（不依赖服务器）
├── pipeline.py       # 把 profile + txt 组装成 core pipeline 调用
└── webui.py          # WebUI 入口（最后阶段才接）
```

## 六、和其他层的交互

* **读取** `profiles/`：根据用户传入的 profile 名加载 yaml。
* **调用** `core/audiobook_pipeline.py`：把 txt、profile、adapters 交给主流程。
* **不直接调用** `llm/`、`tts/`、`voicebank/`、`analysis/`：这些由 `core/` 在内部组织。
* **使用** `utils/`：路径、日志等通用工具。
