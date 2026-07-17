# Qwen3-Omni-30B-A3B-Instruct 使用指南

## 模型概述

Qwen3-Omni 是阿里通义千问推出的原生端到端多模态全模态基础模型，支持文本、图像、音频、视频输入，并以文本+自然语音进行实时流式响应。

- **模型**: Qwen3-Omni-30B-A3B-Instruct（总参数 30B，激活参数 3B，MoE 架构）
- **架构**: Thinker（理解推理）+ Talker（语音生成）双组件
- **服务地址**: `http://10.50.121.102:8011`
- **Conda 环境**: `qwen3-omni`

### 核心能力

| 能力 | 说明 |
|------|------|
| 语音识别 (ASR) | 支持 19 种语言的语音转文字 |
| 语音翻译 (S2TT/S2ST) | 语音到文本/语音的跨语言翻译 |
| 音乐/声音分析 | 音乐风格、流派、乐器识别；环境声分析 |
| 音频描述 (Audio Caption) | 对任意音频生成详细文字描述 |
| 图像理解 | OCR、视觉问答、目标检测与定位 |
| 视频理解 | 视频描述、场景切换分析、导航指令 |
| 音视频交互 | 同时理解视频画面和声音 |
| 文本转语音 (TTS) | 从文本生成自然语音 |
| 语音函数调用 (Agent) | 通过语音输入触发函数调用 |

### 支持的语言

**语音输入**（19 种）：英语、中文、韩语、日语、德语、俄语、意大利语、法语、西班牙语、葡萄牙语、马来语、荷兰语、印尼语、土耳其语、越南语、粤语、阿拉伯语、乌尔都语

**语音输出**（10 种）：英语、中文、法语、德语、俄语、意大利语、西班牙语、葡萄牙语、日语、韩语

**文本**（119 种）

### 预设音色

| 音色 | 性别 | 描述 |
|------|------|------|
| Ethan | 男 | 明亮活力，温暖亲和 |
| Chelsie | 女 | 柔和丝滑，温润清亮 |
| Aiden | 男 | 随性温和，轻松自然 |

---

## 服务管理

### 启动服务

```bash
source /home/audiotest/miniconda3/bin/activate qwen3-omni
nohup python servers/api_server_qwen3_omni.py --port 8011 > logs/qwen3_omni.log 2>&1 &
```

### 禁用 Talker（节省约 10GB 显存，仅文本输出）

```bash
nohup python servers/api_server_qwen3_omni.py --port 8011 --disable_talker > logs/qwen3_omni.log 2>&1 &
```

### 使用 FlashAttention 2

```bash
nohup python servers/api_server_qwen3_omni.py --port 8011 --attn flash_attention_2 > logs/qwen3_omni.log 2>&1 &
```

### 停止服务

```bash
pkill -f api_server_qwen3_omni
```

### 查看日志

```bash
tail -f logs/qwen3_omni.log
```

### 启动参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `/data3/l00944055/audio_simulation/Qwen3-Omni-30B-A3B-Instruct` | 模型权重路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8011` | 监听端口 |
| `--attn` | `sdpa` | 注意力实现：`sdpa`、`flash_attention_2`、`eager` |
| `--disable_talker` | 否 | 禁用 Talker 组件，不生成音频输出，节省约 10GB 显存 |

---

## API 接口总览

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/omni/config` | GET | 模型配置信息 |
| `/v1/omni/chat` | POST | 全模态对话（支持所有输入类型） |
| `/v1/omni/text_only` | POST | 纯文本对话（无音频输出） |
| `/v1/omni/text_to_speech` | POST | 文本转语音 |
| `/v1/omni/speech_recognition` | POST | 语音识别 (ASR) |
| `/v1/omni/speech_translation` | POST | 语音翻译 |
| `/v1/omni/audio_analysis` | POST | 音频分析（描述/音乐/声音） |
| `/v1/omni/image_understanding` | POST | 图像理解 (OCR/VQA) |
| `/v1/omni/video_understanding` | POST | 视频理解 |
| `/v1/omni/audio_visual` | POST | 音视频联合理解 |
| `/v1/omni/function_call` | POST | 语音驱动函数调用 |

---

## API 详细说明

### 1. 健康检查

```bash
curl --noproxy '*' http://10.50.121.102:8011/health
```

**响应示例**:
```json
{"status":"ok","model":"Qwen3-Omni-30B-A3B-Instruct","talker_enabled":true}
```

### 2. 模型配置

```bash
curl --noproxy '*' http://10.50.121.102:8011/v1/omni/config
```

**响应示例**:
```json
{
  "model": "Qwen3-Omni-30B-A3B-Instruct",
  "sampling_rate": 24000,
  "supported_speakers": ["Ethan", "Chelsie", "Aiden"],
  "supported_input_types": ["text", "image", "audio", "video"],
  "talker_enabled": true,
  "supported_speech_output_languages": ["English","Chinese","French","German","Russian","Italian","Spanish","Portuguese","Japanese","Korean"],
  "supported_speech_input_languages": ["English","Chinese","Korean","Japanese","German","Russian","Italian","French","Spanish","Portuguese","Malay","Dutch","Indonesian","Turkish","Vietnamese","Cantonese","Arabic","Urdu"]
}
```

### 3. 全模态对话 `/v1/omni/chat`

这是最通用的接口，支持所有输入模态的任意组合。

#### 简化格式

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/chat \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What can you see and hear?",
    "image": "/path/to/image.jpg",
    "audio": "/path/to/audio.wav",
    "video": "/path/to/video.mp4",
    "system_prompt": "You are a helpful assistant.",
    "speaker": "Ethan",
    "return_audio": true,
    "use_audio_in_video": true,
    "max_new_tokens": 2048
  }' \
  -o response.wav
```

#### 完整消息格式（支持多轮对话）

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "system",
        "content": [{"type": "text", "text": "You are a smart voice assistant."}]
      },
      {
        "role": "user",
        "content": [
          {"type": "audio", "audio": "/path/to/audio.wav"},
          {"type": "image", "image": "/path/to/image.jpg"},
          {"type": "text", "text": "Analyze this audio and image together."}
        ]
      }
    ],
    "speaker": "Chelsie",
    "return_audio": true,
    "max_new_tokens": 2048
  }' \
  -o response.wav
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 否* | - | 文本输入（简化格式） |
| `image` | string | 否* | - | 图像路径（简化格式） |
| `audio` | string | 否* | - | 音频路径（简化格式） |
| `video` | string | 否* | - | 视频路径（简化格式） |
| `system_prompt` | string | 否 | - | 系统提示词（简化格式） |
| `messages` | array | 否* | - | 完整消息列表（与简化格式二选一） |
| `speaker` | string | 否 | `"Ethan"` | 语音输出音色：`Ethan`、`Chelsie`、`Aiden` |
| `return_audio` | bool | 否 | `true` | 是否返回音频输出 |
| `use_audio_in_video` | bool | 否 | `true` | 是否使用视频中的音轨 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |
| `temperature` | float | 否 | 模型默认 | 采样温度 |
| `top_p` | float | 否 | 模型默认 | Nucleus 采样 cutoff |
| `top_k` | int | 否 | 模型默认 | Top-K 采样 |
| `repetition_penalty` | float | 否 | 模型默认 | 重复惩罚 |

*至少需要一个内容项（text/image/audio/video）

#### 响应

- **有音频时** (`return_audio=true`)：返回 `audio/wav` 流，文本内容在 `X-Text-Response` 响应头中
- **无音频时** (`return_audio=false`)：返回 JSON `{"request_id": "...", "text": "...", "inference_time": "..."}`

### 4. 纯文本对话 `/v1/omni/text_only`

无音频输出的文本对话，速度更快。

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/text_only \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Who are you?",
    "system_prompt": "You are a helpful assistant.",
    "max_new_tokens": 512
  }'
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 文本输入 |
| `system_prompt` | string | 否 | - | 系统提示词 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 5. 文本转语音 `/v1/omni/text_to_speech`

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/text_to_speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! How are you doing today?",
    "speaker": "Chelsie",
    "system_prompt": "You are a friendly assistant.",
    "max_new_tokens": 2048
  }' \
  -o speech.wav
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 要转为语音的文本 |
| `speaker` | string | 否 | `"Ethan"` | 音色选择 |
| `system_prompt` | string | 否 | - | 系统提示词，可控制语气风格 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 6. 语音识别 `/v1/omni/speech_recognition`

```bash
# 中文语音识别
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/speech_recognition \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/chinese_audio.wav",
    "language": "Chinese"
  }'

# 英文语音识别
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/speech_recognition \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/english_audio.wav",
    "language": "English"
  }'

# 自定义 prompt
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/speech_recognition \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/audio.wav",
    "prompt": "Transcribe the song lyrics into text without any punctuation."
  }'
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | - | 音频文件路径 |
| `language` | string | 否 | 自动 | 语言名称，用于生成语言特定的识别 prompt |
| `prompt` | string | 否 | 自动生成 | 自定义识别 prompt，优先级高于 language |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 7. 语音翻译 `/v1/omni/speech_translation`

```bash
# 中译英（文本输出）
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/speech_translation \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/chinese_speech.wav",
    "source_language": "Chinese",
    "target_language": "English"
  }'

# 英译中（语音输出）
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/speech_translation \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/english_speech.wav",
    "source_language": "English",
    "target_language": "Chinese",
    "return_audio": true,
    "speaker": "Chelsie"
  }' \
  -o translated.wav
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | - | 源语言音频文件路径 |
| `source_language` | string | 否 | 自动 | 源语言 |
| `target_language` | string | 否 | `"English"` | 目标语言 |
| `return_audio` | bool | 否 | `false` | 是否返回语音输出（语音到语音翻译） |
| `speaker` | string | 否 | `"Ethan"` | 音色（return_audio=true 时有效） |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 8. 音频分析 `/v1/omni/audio_analysis`

```bash
# 音频描述
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/audio_analysis \
  -H "Content-Type: application/json" \
  -d '{"audio": "/path/to/audio.wav", "task": "caption"}'

# 音乐分析
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/audio_analysis \
  -H "Content-Type: application/json" \
  -d '{"audio": "/path/to/music.wav", "task": "music_analysis"}'

# 声音分析
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/audio_analysis \
  -H "Content-Type: application/json" \
  -d '{"audio": "/path/to/sound.wav", "task": "sound_analysis"}'

# 分析结果以语音回复
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/audio_analysis \
  -H "Content-Type: application/json" \
  -d '{"audio": "/path/to/audio.wav", "task": "caption", "return_audio": true, "speaker": "Aiden"}' \
  -o analysis_response.wav
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | - | 音频文件路径 |
| `task` | string | 否 | `"caption"` | 任务类型：`caption`（音频描述）、`music_analysis`（音乐分析）、`sound_analysis`（声音分析） |
| `return_audio` | bool | 否 | `false` | 是否返回语音输出 |
| `speaker` | string | 否 | `"Ethan"` | 音色 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 9. 图像理解 `/v1/omni/image_understanding`

```bash
# 图像描述
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/image_understanding \
  -H "Content-Type: application/json" \
  -d '{"image": "/path/to/image.jpg", "text": "Describe this image."}'

# OCR
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/image_understanding \
  -H "Content-Type: application/json" \
  -d '{"image": "/path/to/document.png", "text": "Read all the text in this image."}'

# 图像数学
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/image_understanding \
  -H "Content-Type: application/json" \
  -d '{"image": "/path/to/math.png", "text": "Solve the math problem in this image step by step."}'

# 目标检测
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/image_understanding \
  -H "Content-Type: application/json" \
  -d '{"image": "/path/to/photo.jpg", "text": "Locate all the cars in this image."}'

# 语音回复图像分析
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/image_understanding \
  -H "Content-Type: application/json" \
  -d '{"image": "/path/to/image.jpg", "text": "What do you see?", "return_audio": true, "speaker": "Chelsie"}' \
  -o response.wav
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | string | 是 | - | 图像文件路径 |
| `text` | string | 否 | `"Describe this image."` | 问题或指令 |
| `return_audio` | bool | 否 | `false` | 是否返回语音输出 |
| `speaker` | string | 否 | `"Ethan"` | 音色 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 10. 视频理解 `/v1/omni/video_understanding`

```bash
# 视频描述（含音轨）
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/video_understanding \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "text": "Describe what happens in this video.",
    "use_audio_in_video": true
  }'

# 视频场景切换分析
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/video_understanding \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "text": "Analyze the scene transitions in this video."
  }'

# 视频导航指令
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/video_understanding \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/pov_video.mp4",
    "text": "Generate navigation commands from this first-person video."
  }'

# 不使用视频音轨
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/video_understanding \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "text": "What do you see?",
    "use_audio_in_video": false
  }'
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `video` | string | 是 | - | 视频文件路径 |
| `text` | string | 否 | `"Describe what happens in this video."` | 问题或指令 |
| `use_audio_in_video` | bool | 否 | `true` | 是否使用视频中的音轨 |
| `return_audio` | bool | 否 | `false` | 是否返回语音输出 |
| `speaker` | string | 否 | `"Ethan"` | 音色 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

### 11. 音视频联合理解 `/v1/omni/audio_visual`

与视频理解接口参数相同，语义上强调音视频联合建模场景。

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/audio_visual \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "text": "What can you see and hear in this video?",
    "use_audio_in_video": true,
    "return_audio": true,
    "speaker": "Ethan"
  }' \
  -o response.wav
```

### 12. 语音函数调用 `/v1/omni/function_call`

```bash
curl --noproxy '*' -X POST http://10.50.121.102:8011/v1/omni/function_call \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "/path/to/voice_command.wav",
    "text": "Execute the command described in the audio.",
    "return_audio": false,
    "max_new_tokens": 2048
  }'
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | - | 语音命令音频路径 |
| `text` | string | 否 | `"Execute the command described in the audio."` | 辅助指令 |
| `return_audio` | bool | 否 | `false` | 是否返回语音输出 |
| `speaker` | string | 否 | `"Ethan"` | 音色 |
| `max_new_tokens` | int | 否 | `2048` | 最大生成 token 数 |

---

## Python 客户端调用

### 安装依赖

```bash
pip install requests soundfile
```

### 全模态对话示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/chat"

# 多模态输入 + 音频输出
data = {
    "text": "What can you see and hear?",
    "image": "/path/to/image.jpg",
    "audio": "/path/to/audio.wav",
    "speaker": "Ethan",
    "return_audio": True,
    "max_new_tokens": 2048,
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})

if response.status_code == 200:
    # 文本在响应头中
    text = response.headers.get("X-Text-Response", "")
    print(f"Text: {text}")
    # 音频在响应体中
    with open("response.wav", "wb") as f:
        f.write(response.content)
    print("Audio saved: response.wav")
else:
    print(f"Error: {response.status_code}, {response.text}")
```

### 语音识别示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/speech_recognition"
data = {
    "audio": "/path/to/audio.wav",
    "language": "Chinese",
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    result = response.json()
    print(f"Transcription: {result['text']}")
```

### 文本转语音示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/text_to_speech"
data = {
    "text": "你好，欢迎使用Qwen3-Omni语音合成！",
    "speaker": "Chelsie",
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("Audio saved: output.wav")
```

### 语音翻译示例（语音到语音）

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/speech_translation"
data = {
    "audio": "/path/to/chinese_speech.wav",
    "source_language": "Chinese",
    "target_language": "English",
    "return_audio": True,
    "speaker": "Ethan",
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    with open("translated.wav", "wb") as f:
        f.write(response.content)
    print("Translated audio saved: translated.wav")
```

### 音频分析示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/audio_analysis"
data = {
    "audio": "/path/to/music.wav",
    "task": "music_analysis",
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    result = response.json()
    print(f"Analysis: {result['text']}")
```

### 图像理解示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/image_understanding"
data = {
    "image": "/path/to/document.png",
    "text": "Read all the text in this image.",
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    result = response.json()
    print(f"OCR result: {result['text']}")
```

### 视频理解示例

```python
import requests

url = "http://10.50.121.102:8011/v1/omni/video_understanding"
data = {
    "video": "/path/to/video.mp4",
    "text": "Describe what happens in this video.",
    "use_audio_in_video": True,
}

response = requests.post(url, json=data, proxies={"http": None, "https": None})
if response.status_code == 200:
    result = response.json()
    print(f"Video description: {result['text']}")
```

---

## 推荐的 System Prompt

### 音视频交互场景

在音视频多模态交互中（如语音助手），建议使用以下 system prompt 以获得更自然的对话体验：

```python
system_prompt = """You are Qwen-Omni, a smart voice assistant created by Alibaba Qwen.
You are a virtual voice assistant with no gender or age.
You are communicating with the user.
In user messages, "I/me/my/we/our" refer to the user and "you/your" refer to the assistant.
In your replies, address the user as "you/your" and yourself as "I/me/my"; never mirror the user's pronouns.
Keep original pronouns only in direct quotes.
Interact with users using short (no more than 50 words), brief, straightforward language, maintaining a natural tone.
Never use formal phrasing, mechanical expressions, bullet points, overly structured language.
Your output must consist only of the spoken content you want the user to hear.
Do not include any descriptions of actions, emotions, sounds, or voice changes.
Do not use asterisks, brackets, parentheses, or any other symbols to indicate tone or actions.
You must answer users' audio or text questions, do not directly describe the video content.
You should communicate in the same language strictly as the user unless they request otherwise.
When you are uncertain, use appropriate questions to guide the user to continue the conversation.
Keep replies concise and conversational, as if talking face-to-face."""
```

---

## 显存需求参考

| 场景 | 精度 | 显存 |
|------|------|------|
| Instruct (Thinker+Talker), 15s 视频 | BF16 | ~78 GB |
| Instruct (Thinker+Talker), 30s 视频 | BF16 | ~88 GB |
| Instruct (Thinker+Talker), 60s 视频 | BF16 | ~107 GB |
| 禁用 Talker (--disable_talker), 15s 视频 | BF16 | ~68 GB |
| 纯文本/音频输入（无视频） | BF16 | ~70 GB |

模型使用 `device_map="auto"` 自动分配到多张 GPU。

---

## 注意事项

1. **`--noproxy` 参数**: 使用 `curl` 时必须加 `--noproxy '*'`，否则会被代理拦截
2. **Python proxies**: 使用 `requests` 时设置 `proxies={"http": None, "https": None}` 禁用代理
3. **音频输出**: 当 `return_audio=true` 时，文本内容在 `X-Text-Response` 响应头中返回（最多 500 字符），音频在响应体中；当 `return_audio=false` 时，返回 JSON 格式
4. **`use_audio_in_video`**: 多轮对话中该参数必须保持一致，否则可能出现异常结果
5. **服务端口**: 默认 8011，确保端口未被占用
6. **模型加载**: 首次请求前需要等待模型加载完成（约 2-3 分钟），可通过 `/health` 检查状态
7. **并发限制**: 服务使用推理锁 (`infer_lock`)，同一时间只处理一个请求
8. **base64 输入**: 图像/音频/视频支持 base64 编码输入（支持 `data:<mime>;base64,<data>` 格式或纯 base64 字符串）
9. **不要修改 `/data3/l00944055/audio_simulation/` 目录下的文件**，本地脚本仍可独立使用