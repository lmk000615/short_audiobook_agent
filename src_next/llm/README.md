# llm/ 大模型适配层

> 本层是 `src_next/` 重构架构中的 LLM 适配层。整体架构图、各层关系、数据流请见 [../README.md](../README.md) 的「〇、一图看懂 src_next」。

## 一、这一层负责什么

* 封装不同 LLM 后端的调用方式（HTTP API / Mock，未来可能加本地推理）。
* 提供统一接口：`generate_text(prompt)` 和 `generate_json(prompt)`。
* 处理 JSON 解析、HTTP 错误、超时、配置缺失，统一抛 `LLMError`。
* 提供并行 batch 工具，加速多段分析（`parallel.py`）。
* 支持多个后端自由切换：Mock / Qwen / Gemma4 / 未来 local。

## 二、这一层不负责什么

* 不理解故事业务（不知道什么是对话者、角色、导演计划）。
* 不知道什么是 TTS、voicebank。
* 不生成 director plan 的业务结构，只返回模型原始 text / json。
* 不保存业务中间产物（那是 `core/` 的事）。
* 不读 profile yaml（profile 由 `app/` 加载后注入构造参数）。
* 不做语义重试（如「JSON 解析失败 → 让模型再试一次」）。第一版只做单次调用，重试策略留给上层或后续迭代。

## 三、为什么 analysis 层不能直接写 Qwen/Gemma4 请求

旧 `src/llm_story_resolver.py` / `src/character_analyzer.py` / `src/story_director.py` 三个文件各自写了一份 `_call_llm` + `_load_env` + `_parse_response`，导致：

* 每次切换模型都要改三个文件；
* 配置变量名散落各处，难统一；
* JSON 解析逻辑稍有差异，bug 修一处漏两处；
* 无法在无服务器环境下做端到端 pipeline 验证。

新架构下，analysis 层**只能**依赖 `BaseLLMClient`：

```python
# 正确姿势（analysis 内）
from src_next.llm import BaseLLMClient

def analyze_characters(segments, client: BaseLLMClient):
    raw = client.generate_json(prompt)
    ...
```

这样：
* 切换 Qwen → Gemma4 只改 `app/` 注入的 client 实例，analysis 一行不动；
* 无服务器时注入 `MockLLMClient`，照样跑通 pipeline；
* 单元测试不需要 mock requests 库，直接换 MockLLMClient。

## 四、BaseLLMClient 是什么

`base.py` 定义的抽象基类，所有后端都要继承它。只暴露两个方法：

```python
class BaseLLMClient(ABC):
    def generate_text(self, prompt: str, **kwargs) -> str: ...
    def generate_json(self, prompt: str, **kwargs) -> dict | list: ...
```

* `generate_text`：返回模型生成的纯字符串。
* `generate_json`：返回已解析的 JSON（dict 或 list），具体后端负责 ```json 代码块剥离 / 首尾解释性文字剔除 / json.loads。
* 失败统一抛 `LLMError`，上层只需 catch 一种异常。

kwargs 是 optional 的，常见字段：`system_prompt` / `max_tokens` / `temperature` / `timeout`。analysis 层不假设 kwargs 一定被使用。

## 五、MockLLMClient 用于什么

`mock_llm.py` 的 `MockLLMClient`：

* 不访问网络、不读 .env、不依赖 GPU；
* `generate_text` 返回固定占位字符串；
* `generate_json` 返回固定 dict（每次浅拷贝，避免污染常量）；
* 所有 kwargs 忽略。

典型用途：
1. 服务器搬迁期间，验证 `core/` 主流程数据流不依赖真实模型；
2. 单元测试中替换真实 LLM，避免 mock requests；
3. CI 环境（无 secret / 无网络）跑通端到端 smoke test。

## 六、QwenHTTPClient 当前如何在蓝区使用

`qwen_http.py` 是**当前蓝区真实可用**的 LLM 后端。

### 环境变量优先级（从明确到通用）

| 变量名（推荐） | 兼容变量名（旧 src/） | 默认值 |
|---|---|---|
| `QWEN_BASE_URL` | `LLM_BASE_URL` | 无（必填） |
| `QWEN_API_KEY`  | `LLM_API_KEY`  | 无（必填） |
| `QWEN_MODEL`    | `LLM_MODEL`    | `qwen3.6-plus` |

读取顺序：构造参数 > `QWEN_*` 环境变量 > `.env` 中的 `QWEN_*` > `LLM_*` 环境变量 > `.env` 中的 `LLM_*` > 内置默认。

### 调用方式

OpenAI-compatible `/v1/chat/completions`：

```python
from src_next.llm.qwen_http import QwenHTTPClient

client = QwenHTTPClient()
text = client.generate_text("你好", system_prompt="你是助手")
obj = client.generate_json('返回 JSON：{"ok": true}')
```

### 重要：端点要换成 compatible-mode

当前项目 `.env` 中 `LLM_BASE_URL=https://dashscope.aliyuncs.com/apps/anthropic/v1` 指向 Anthropic 兼容端点（旧 src/ 用这个）。`QwenHTTPClient` 走 OpenAI 格式，需要切换到：

```
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=<同 LLM_API_KEY>
QWEN_MODEL=qwen3.6-plus
```

如果检测到 BASE_URL 含 `/anthropic/`，客户端会打 warning 提示，但不阻止构造（留给真实调用自然失败，便于排错）。

### 可选手动测试

```bash
python -m src_next.llm.qwen_http
```

不会在 import 阶段发请求；只有显式作为 `__main__` 运行才调真实 API。

## 七、Gemma4HTTPClient 为什么暂时只保留结构

`gemma4_http.py` 是服务器恢复后才会启用的后端。当前：

* 服务器正在搬迁，地址未知；
* **不在本阶段做真实测试**（避免误联失败地址污染日志）；
* 只确保 `import` 时不报错（不在模块顶层发请求）；
* 默认模型 `gemma4-31B`，可通过 `GEMMA4_MODEL` 覆盖。

### 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `GEMMA4_BASE_URL` | 是 | 无 | 服务器恢复后在 .env 配置 |
| `GEMMA4_API_KEY`  | 否 | 空  | Gemma4 内网部署通常不需要 |
| `GEMMA4_MODEL`    | 否 | `gemma4-31B` | |

### 设计要点

* Authorization header **可选**（只有配了 key 才带），适配内网无鉴权部署；
* 默认 `bypass_proxy=True`，绕过开发机的全局代理；
* 复用 `qwen_http.py` 的 `_extract_text` / `_parse_json_from_text` / `_load_env_file`，避免重复代码。

服务器恢复后只需要在 `.env` 配置 `GEMMA4_BASE_URL`，本客户端即可工作，不需要改 core / analysis 层。

## 八、parallel.py 的作用

LLM 调用是典型 IO 密集型操作。一段故事切 20 个 segment，逐个调用要串行 20 次；用 `parallel.run_batches_parallel` 可以并发处理，整体耗时接近最慢的一次调用。

### 接口

```python
from src_next.llm.mock_llm import MockLLMClient
from src_next.llm.parallel import run_batches_parallel, BatchResult

client = MockLLMClient()
prompts = ["prompt1", "prompt2", "prompt3", ...]

def worker(p: str):
    return client.generate_json(p)

results: list[BatchResult] = run_batches_parallel(prompts, worker, max_workers=3)
for r in results:
    if r.success:
        print(r.batch_index, r.result, r.elapsed_seconds)
    else:
        print(r.batch_index, "FAILED", r.error)
```

### 设计要点

* `ThreadPoolExecutor`，不是 `ProcessPool`（LLM 调用是 IO 等待，不需要多进程）；
* **单个 batch 异常不影响其他**，失败信息记录在 `BatchResult.error`；
* 返回严格按输入顺序（按 `batch_index` 排列，不是按完成时间）；
* 工具本身不依赖具体后端，Qwen / Gemma4 / Mock 都可以复用；
* 实际并发会被 clamp 到 `[1, len(batch_inputs)]`，避免空池或过度创建线程。

## 九、未来扩展：新增本地 LLM 怎么办

如果后续在蓝区部署了本地 LLM（如 vLLM / Ollama 跑某个开源模型），**只新增 `local_llm.py`**：

```python
# src_next/llm/local_llm.py
from .base import BaseLLMClient

class LocalLLMClient(BaseLLMClient):
    def generate_text(self, prompt, **kwargs): ...
    def generate_json(self, prompt, **kwargs): ...
```

然后在 `__init__.py` 导出，在 `app/` 的 profile 工厂里加一个分支。

**不要**：
* 改 `core/`（它只依赖 `BaseLLMClient`，不感知后端）；
* 改 `analysis/`（同上）；
* 改 `base.py`（接口稳定后不应该再变）。

## 十、当前实现状态

```text
src_next/llm/
├── __init__.py        # ✅ 统一导出
├── base.py            # ✅ BaseLLMClient + LLMError
├── mock_llm.py        # ✅ MockLLMClient（离线可用）
├── qwen_http.py       # ✅ QwenHTTPClient（蓝区真实可用，OpenAI-compatible）
├── gemma4_http.py     # ✅ Gemma4HTTPClient（结构完整，服务器恢复后启用）
├── parallel.py        # ✅ run_batches_parallel + BatchResult
└── README.md          # 本文件
```

### 哪些已完成

* 接口抽象和异常统一；
* Mock 实现（无外部依赖）；
* Qwen HTTP 真实可用（依赖 `.env` 配置）；
* Gemma4 结构就绪（等服务器）；
* 并行 batch 工具。

### 哪些未做（留给后续迭代）

* JSON 解析失败时的自动重试（当前只抛 `LLMError`）；
* 限流 / 429 退避；
* token 用量统计；
* 真实本地 LLM 接入（`local_llm.py` 暂不创建）。
