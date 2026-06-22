# tts/ 语音合成适配层

> 本层是 `src_next/` 重构架构中的 TTS 适配层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图看懂 src_next」。

## 一、这一层负责什么

* 接收 tts instructions（每段要合成的文本 + 音色 + 情绪指导）。
* 调用具体 TTS 模型或服务（CosyVoice / IndexTTS / FishPro / 本地 TTS）。
* 为每个 segment 生成对应的音频文件。
* 返回音频片段列表，供 `core/audio_merger.py` 拼接。
* 统计 TTS 阶段耗时。

## 二、这一层不负责什么

* 不判断角色性格、不抽取角色。
* 不生成导演计划。
* 不调用 LLM。
* 不负责 voicebank 生成（那是 `voicebank/` 的事）。
* 不拼接最终完整音频（那是 `core/audio_merger.py` 的事）。
* 不读 profile yaml。

## 三、输入

* tts instructions（带文本、speaker id、情绪、节奏的指令列表）。
* voicebank 结果（每个 speaker 对应的音色参考路径或 id）。
* 输出目录（音频片段保存位置）。
* TTS profile 配置（具体后端、并发数、采样率等）。

## 四、输出

* audio segments（一组音频文件路径，按 segment 顺序）。
* TTS 阶段耗时统计。
* 失败 / 兜底记录（哪些 segment 合成失败、用什么兜底）。

## 五、未来会放的文件

```text
tts/
├── base.py               # 统一接口定义
├── mock_tts.py           # 不依赖服务器的 Mock 实现
├── cosyvoice_adapter.py  # CosyVoice 后端
├── indextts_adapter.py   # IndexTTS 后端
├── fishpro_adapter.py    # FishPro 后端
└── local_tts.py          # 蓝区本地轻量 TTS
```

## 六、和其他层的交互

* **被 `core/` 调用**：主流程在合成阶段调用。
* **依赖 `voicebank/` 结果**：通过 `core/` 间接拿到 voice reference。
* **不直接调用** `analysis/`、`llm/`：本层只关心合成指令，不关心语义。
* **具体后端由 `profiles/` 决定**：app 根据 profile 实例化对应 adapter。
* **使用 `utils/`**：音频时长读取、路径管理。
