# VoxCPM2 使用指南

## 概述

VoxCPM2 是 OpenBMB 出品的 tokenizer-free TTS 模型（2B 参数），基于 MiniCPM-4 骨干网络，训练数据超过 200 万小时，支持：

* 30 种语言多语言合成（无需语言标签）
* Voice Design（自然语言描述生成全新音色）
* 可控语音克隆（参考音频 + 风格控制指令）
* 终极克隆（参考音频 + 转录文本，完美复刻）
* 48kHz 高品质音频输出
* 流式推理

---

## 服务信息

| 项目           | 值                           |
| ------------ | --------------------------- |
| **服务地址**     | `http://10.50.121.102:8012` |
| **模型**       | VoxCPM2 (openbmb/VoxCPM2)   |
| **采样率**      | 48000 Hz                    |
| **显存需求**     | ~8 GB                       |
| **Conda 环境** | `voxcpm2`                   |

---

## 启动服务

```bash
source ~/miniconda3/bin/activate voxcpm2
export LD_LIBRARY_PATH=$HOME/cuda-12.9/lib64:$LD_LIBRARY_PATH
nohup python servers/api_server_voxcpm2.py --port 8012 --device cuda:0 > logs/voxcpm2.log 2>&1 &
```

停止服务：

```bash
pkill -f api_server_voxcpm2
```

---

## API 接口

### 1. 健康检查

```bash
curl http://localhost:8012/health
```

**响应示例**:

```json
{"status":"ok","model":"VoxCPM2","device":"cuda:0","sample_rate":48000}
```

### 2. 模型配置

```bash
curl http://localhost:8012/v1/tts/config
```

### 3. 语音合成

```bash
curl -X POST http://localhost:8012/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，欢迎使用VoxCPM2语音合成系统。"}' \
  -o output.wav
```

---

## 参数说明

### 核心参数

| 参数                    | 类型     | 必填    | 默认值  | 说明                             |
| --------------------- | ------ | ----- | ---- | ------------------------------ |
| `text`                | string | **是** | -    | 要合成的文本，支持 30 种语言               |
| `reference_audio`     | string | 否     | null | 参考音频路径（用于音色克隆）                 |
| `prompt_audio`        | string | 否     | null | 提示音频路径（终极克隆模式，需配合 prompt_text） |
| `prompt_text`         | string | 否     | null | 提示音频的文本转录（终极克隆模式）              |
| `cfg_value`           | float  | 否     | 2.0  | 引导系数，越高越贴合文本                   |
| `inference_timesteps` | int    | 否     | 10   | 推理步数，越多质量越好但越慢                 |
| `output_path`         | string | 否     | null | 服务端保存路径（可选）                    |

---

## 功能用法

### 1. Voice Design（音色设计）

无需参考音频，通过自然语言描述创建全新音色。格式：在文本开头用括号描述音色。

```python
import requests

response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "(年轻女性，温柔甜美的声音)你好，欢迎使用VoxCPM2！",
    }
)

with open("voice_design.wav", "wb") as f:
    f.write(response.content)
print("音频已生成: voice_design.wav")
```

使用 curl：

```bash
curl -X POST http://localhost:8012/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"(年轻女性，温柔甜美的声音)你好，欢迎使用VoxCPM2！"}' \
  -o voice_design.wav
```

**Voice Design 描述示例**：

| 风格   | text 示例                    |
| ---- | -------------------------- |
| 温柔女声 | `(年轻女性，温柔甜美的声音)你好呀`        |
| 磁性男声 | `(低沉磁性的男性声音，语速缓慢)大家好`      |
| 活泼少女 | `(活泼开朗的少女声音)今天真开心！`        |
| 新闻播报 | `(专业播音员，吐字清晰，语调平稳)各位观众晚上好` |

---

### 2. 可控语音克隆

上传参考音频克隆音色，可用控制指令调整风格。

```python
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "这是使用VoxCPM2克隆的声音。",
        "reference_audio": "/path/to/voice.wav",
    }
)

with open("clone.wav", "wb") as f:
    f.write(response.content)
```

带风格控制：

```python
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "(稍快，愉快的语气)这是带风格控制的克隆声音。",
        "reference_audio": "/path/to/voice.wav",
        "cfg_value": 2.0,
    }
)
```

使用 curl：

```bash
curl -X POST http://localhost:8012/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"这是克隆的声音。","reference_audio":"/path/to/voice.wav"}' \
  -o clone.wav
```

---

### 3. 终极克隆

提供参考音频和其精确转录，完美复刻音色、节奏、情感等所有细节。

```python
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "这是终极克隆的演示文本。",
        "prompt_audio": "/path/to/voice.wav",
        "prompt_text": "参考音频的转录文本。",
        "reference_audio": "/path/to/voice.wav",
    }
)

with open("ultimate_clone.wav", "wb") as f:
    f.write(response.content)
```

使用 curl：

```bash
curl -X POST http://localhost:8012/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"这是终极克隆的演示文本。","prompt_audio":"/path/to/voice.wav","prompt_text":"参考音频的转录文本。","reference_audio":"/path/to/voice.wav"}' \
  -o ultimate_clone.wav
```

**说明**：

* `prompt_audio` + `prompt_text`：提供音频-文本对，模型从参考音频继续生成
* `reference_audio`：可选，额外提供同一音频作为音色参考，可提高相似度

---

### 4. 多语言合成

VoxCPM2 支持 30 种语言，无需语言标签，直接输入文本即可：

```python
# 英文
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={"text": "Hello, this is a multilingual speech synthesis test."}
)

# 日文
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={"text": "こんにちは、VoxCPM2の多言語音声合成テストです。"}
)

# 韩文
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={"text": "안녕하세요, 다국어 음성 합성 테스트입니다."}
)
```

**支持语言**：阿拉伯语、缅甸语、中文、丹麦语、荷兰语、英语、芬兰语、法语、德语、希腊语、希伯来语、印地语、印尼语、意大利语、日语、高棉语、韩语、老挝语、马来语、挪威语、波兰语、葡萄牙语、俄语、西班牙语、斯瓦希里语、瑞典语、他加禄语、泰语、土耳其语、越南语

**中文方言**：四川话、粤语、吴语、东北话、河南话、陕西话、山东话、天津话、闽南话

---

### 5. 参数调优

```python
# 高质量（更多推理步数）
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "高质量语音合成示例。",
        "cfg_value": 3.0,
        "inference_timesteps": 20,
    }
)

# 快速（较少步数）
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "快速语音合成示例。",
        "cfg_value": 1.5,
        "inference_timesteps": 5,
    }
)

# 固定种子复现（需 voxcpm >= 2.1）
response = requests.post(
    "http://localhost:8012/v1/tts/synthesize",
    json={
        "text": "可复现的语音合成。",
        "seed": 42,
    }
)
```

**参数说明**：

* `cfg_value`：引导系数，越高越贴合文本描述，过低可能发散，建议 1.5-3.0
* `inference_timesteps`：推理步数，越多质量越好但越慢，建议 5-20
* `seed`：固定种子可复现结果（需 voxcpm >= 2.1，当前版本 2.0.3 暂不支持）

---

## 与其他 TTS 模型对比

| 特性           | VoxCPM2     | IndexTTS-2  | CosyVoice   | Qwen3-TTS |
| ------------ | ----------- | ----------- | ----------- | --------- |
| 采样率          | 48000 Hz    | 22050 Hz    | 24000 Hz    | 24000 Hz  |
| 参数量          | 2B          | 1.5B        | 0.3B        | 1.7B      |
| 语言支持         | 30 种        | 中英文         | 9 种 + 方言    | 10 种      |
| Voice Design | 支持          | 不支持         | 不支持         | 支持        |
| 音色克隆         | 可控克隆 + 终极克隆 | 零样本克隆       | 零样本克隆       | 设计生成      |
| 情感控制         | 自然语言描述      | 8维向量 + 参考音频 | instruct 指令 | 自然语言指令    |
| 显存需求         | ~8 GB       | ~12 GB      | ~4 GB       | ~6 GB     |

---

## 注意事项

1. **参考音频质量**：建议 5-15 秒清晰无噪声的音频，16kHz 以上
2. **Voice Design 稳定性**：结果可能因运行而异，建议生成 1-3 次选取最佳
3. **输出采样率**：48kHz，内置超分辨率，无需外部上采样器
4. **LD_LIBRARY_PATH**：启动服务前必须设置 `export LD_LIBRARY_PATH=$HOME/cuda-12.9/lib64:$LD_LIBRARY_PATH`
5. **首次加载**：模型加载需要约 30 秒，首次推理会有 warm-up