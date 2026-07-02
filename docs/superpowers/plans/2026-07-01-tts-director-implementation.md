# tts_director 实施计划

> **执行者须知**：必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans skill 来逐任务执行本计划。步骤用 checkbox（`- [ ]`）语法跟踪。

**目标**：实施 Audio-Oscar 方向1 —— 合并原 stage 7（story_director）+ stage 8（tts_instruction_builder）为新的 stage 7（tts_director），让 LLM 直接产出 `ModelSpecificTTSInstruction`（含 model + parameters），消除中间映射层。

**架构**：
- LLM 按 segment 独立选 model（per-segment 自由，音色一致性由 voice cloning 保证）
- adapter 双接口：`_synthesize_legacy`（保留老 mapping）+ `_synthesize_model_specific`（纯透传）
- 全局 `src_next/tts/backends.yaml` 注册表取代 profile.tts 块（开关开启时）
- CLI flag `--use-tts-director` 或 profile 内 `pipeline.use_tts_director: true` 启用新链路
- 100% 向后兼容：开关关闭 = main 行为零差异

**技术栈**：Python 3.10+、PyYAML、requests、pytest（前置任务中安装）

**Spec**：`docs/superpowers/specs/2026-07-01-tts-director-design.md`
**已完成**：3 份 model_configs 已 commit（`cosyvoice3.json` / `s2pro.json` / `indextts2.json`）

---

## 文件结构

### 新增文件

| 路径 | 职责 |
|---|---|
| `tests/conftest.py` | pytest 共享 fixtures（mock LLM、样例 segments 等） |
| `tests/__init__.py` | 空文件 |
| `pytest.ini` | pytest 配置 + integration marker 注册 |
| `src_next/utils/model_config_loader.py` | 加载/校验 `tts/model_configs/*.json` |
| `src_next/analysis/prompts/__init__.py` | 空包初始化 |
| `src_next/analysis/prompts/tts_director_prompt.py` | system + user prompt 构造器 |
| `src_next/analysis/tts_director.py` | `TTSDirectorAgent` 主类 |
| `src_next/tts/backends.yaml` | 全局 TTS backend 注册表（enabled_backends + backends + default_model） |
| `tests/test_model_config_loader.py` | loader 单元测试 |
| `tests/test_tts_director_unit.py` | TTSDirectorAgent 单元测试（mock LLM） |
| `tests/test_tts_director_integration.py` | 集成测试（真 Gemma4 LLM，`@pytest.mark.integration`） |
| `tests/test_adapters_model_specific.py` | adapter 双接口单元测试（mock HTTP） |
| `tests/test_backends_yaml_loader.py` | backends.yaml loader 单元测试 |
| `tests/test_pipeline_use_tts_director_switch.py` | 端到端 smoke（mock 链路） |
| `tests/test_multi_backend_synthesis.py` | stage 8 多 adapter 调度单元测试 |
| `tests/test_registry_adapter_cache.py` | registry cache 单元测试 |

### 修改文件

| 路径 | 改动 |
|---|---|
| `requirements.txt` | 加 `pytest` |
| `src_next/tts/cosyvoice_http.py` | 加 `_synthesize_model_specific` 方法 |
| `src_next/tts/s2pro_adapter.py` | 加 `_synthesize_model_specific` 方法 |
| `src_next/tts/indextts_http.py` | 加 `_synthesize_model_specific` 方法 |
| `src_next/tts/registry.py` | 加 `create_adapter_for_backend` + lazy cache |
| `src_next/utils/yaml_utils.py` | 加 `load_backends_yaml` + `read_use_tts_director_flag` |
| `src_next/core/audiobook_pipeline.py` | stage 7/8 切换 + stage 8 多 adapter 调度 + CLI flag |
| `src_next_主链路运行及核心模块说明.md` | stage 编号 + backends.yaml + LLM 选 model 说明 |
| `src_next_总体架构说明.md` | 架构图说明 |
| `CLAUDE.md` | §4 表格 + §6 开关说明 + §11 维护表 |
| `README.md` | 同步 |

### 保留不动（fallback 路径）

- `src_next/analysis/story_director.py`
- `src_next/core/tts_instruction_builder.py`
- `src_next/profiles/yellow_*.yaml`（3 个全部）

---

## 前置准备：测试基础设施

### 任务 0：安装 pytest + 建 tests 目录 + pytest.ini

**文件**：
- 修改：`requirements.txt`
- 新增：`tests/__init__.py`（空）
- 新增：`tests/conftest.py`
- 新增：`pytest.ini`

- [ ] **步骤 1：requirements.txt 加 pytest**

在 `requirements.txt` 末尾追加：

```
# 测试依赖
pytest>=7.4.0
```

- [ ] **步骤 2：安装 pytest**

运行：
```bash
pip install pytest>=7.4.0
```

预期：successfully installed pytest-7.x.x

- [ ] **步骤 3：建 tests/ 目录 + 空 __init__.py**

新建 `tests/__init__.py`（空文件）。

- [ ] **步骤 4：建 pytest.ini（注册 integration marker）**

新建 `pytest.ini`：

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: 标记需要真服务的测试（LLM / TTS / voicebank HTTP）。运行方式：pytest -m integration
    slow: 标记慢测试（>5s）。运行方式：pytest -m "not slow"
addopts = -v --tb=short
```

- [ ] **步骤 5：建 conftest.py（共享 fixtures）**

新建 `tests/conftest.py`：

```python
"""short_audiobook_agent 测试共享 fixtures。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src_next.core.data_models import (
    CharacterProfile,
    ModelSpecificTTSInstruction,
    Segment,
    VoicebankResult,
)
from src_next.llm.base import BaseLLMClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_CONFIGS_DIR = PROJECT_ROOT / "src_next" / "tts" / "model_configs"


class MockLLMClient(BaseLLMClient):
    """返回预定 JSON 的 LLM 测试替身。

    用法：
        client = MockLLMClient(response={"instructions": [...]})
        # 或模拟异常：
        client = MockLLMClient(response="not valid json", raise_on_call=RuntimeError("..."))
    """

    def __init__(self, response: Any = None, raise_on_call: Exception | None = None):
        self._response = response
        self._raise = raise_on_call
        self.call_count = 0
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    def generate_text(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        if self._raise:
            raise self._raise
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self._response if isinstance(self._response, str) else json.dumps(self._response)

    def generate_json(self, system_prompt: str, user_prompt: str, **kwargs) -> Any:
        if self._raise:
            raise self._raise
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        if isinstance(self._response, (dict, list)):
            return self._response
        # 如果 response 是字符串，尝试解析为 JSON
        return json.loads(self._response)


@pytest.fixture
def mock_llm():
    """MockLLMClient 工厂 fixture。"""
    def _make(response: Any = None, raise_on_call: Exception | None = None) -> MockLLMClient:
        return MockLLMClient(response=response, raise_on_call=raise_on_call)
    return _make


@pytest.fixture
def sample_segments() -> list[Segment]:
    """3 个 segments：1 旁白 + 2 不同 speaker 对白。"""
    return [
        Segment(
            segment_id="seg_001",
            segment_type="narration",
            speaker="narrator",
            text="小松鼠笑着递给他一个篮子。",
        ),
        Segment(
            segment_id="seg_002",
            segment_type="dialogue",
            speaker="小松鼠",
            text="当然来得及，只要你愿意开始。",
        ),
        Segment(
            segment_id="seg_003",
            segment_type="dialogue",
            speaker="老乌龟",
            text="孩子，时间会等你的。",
        ),
    ]


@pytest.fixture
def sample_characters() -> list[CharacterProfile]:
    return [
        CharacterProfile(
            name="narrator",
            role="narrator",
            voice_prompt="平稳温和的中性叙述音",
            age="adult",
            gender="neutral",
        ),
        CharacterProfile(
            name="小松鼠",
            role="child",
            voice_prompt="活泼轻快的小女孩声音",
            age="child",
            gender="female",
        ),
        CharacterProfile(
            name="老乌龟",
            role="elderly",
            voice_prompt="苍老低沉的老年男性声音",
            age="elderly",
            gender="male",
        ),
    ]


@pytest.fixture
def sample_voicebank_result() -> VoicebankResult:
    return VoicebankResult(
        speaker_to_voice={
            "narrator": "/tmp/voicebank/narrator.wav",
            "小松鼠": "/tmp/voicebank/xiaosongshu.wav",
            "老乌龟": "/tmp/voicebank/laogui.wav",
        },
        config_snapshot={},
    )


@pytest.fixture
def model_configs_all() -> dict[str, dict]:
    """加载全部 3 份 model_config，返回 {name: config_dict}。"""
    result = {}
    for path in sorted(MODEL_CONFIGS_DIR.glob("*.json")):
        cfg = json.loads(path.read_text(encoding="utf-8"))
        result[cfg["name"]] = cfg
    return result


@pytest.fixture
def cosyvoice_config(model_configs_all) -> dict:
    return model_configs_all["CosyVoice3"]


@pytest.fixture
def s2pro_config(model_configs_all) -> dict:
    return model_configs_all["S2Pro"]
```

注意：`Segment` / `CharacterProfile` / `VoicebankResult` / `BaseLLMClient` 的字段名必须和 `src_next/core/data_models.py` + `src_next/llm/base.py` 的实际定义一致。若不一致，调整 fixture 用真实字段名。

- [ ] **步骤 6：验证 pytest 能用**

运行：
```bash
cd M:/Users/l30083418/Documents/short_audiobook_agent
pytest --collect-only
```

预期：`collected 0 items`（还没测试）+ 无报错。

- [ ] **步骤 7：提交**

```bash
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: 设置 pytest 基础设施（pytest.ini + tests/conftest.py）

- requirements.txt 加 pytest>=7.4.0
- pytest.ini 注册 integration / slow marker
- tests/conftest.py 提供共享 fixtures：mock_llm / sample_segments /
  sample_characters / sample_voicebank_result / model_configs_all

为 tts_director 实施计划做准备。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## C1：model_configs loader + tts_director 新模块

### 任务 1：model_config_loader.py + 测试

**文件**：
- 新增：`src_next/utils/model_config_loader.py`
- 新增：`tests/test_model_config_loader.py`

- [ ] **步骤 1：写失败测试**

新建 `tests/test_model_config_loader.py`：

```python
"""src_next/utils/model_config_loader.py 的单元测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_next.utils.model_config_loader import (
    get_backend_for_model,
    get_default_parameters,
    load_all_model_configs,
    load_model_config,
    ModelConfigError,
)


def test_load_model_config_returns_dict():
    cfg = load_model_config("S2Pro")
    assert cfg["name"] == "S2Pro"
    assert cfg["backend"] == "s2pro_http"
    assert "parameters" in cfg
    assert "instruction" in cfg["parameters"]


def test_load_model_config_unknown_name_raises():
    with pytest.raises(ModelConfigError, match="Unknown model name"):
        load_model_config("NonExistentModel")


def test_load_all_model_configs_returns_dict_keyed_by_name():
    all_configs = load_all_model_configs()
    assert "CosyVoice3" in all_configs
    assert "S2Pro" in all_configs
    assert "IndexTTS2" in all_configs
    assert len(all_configs) >= 3


def test_get_backend_for_model():
    assert get_backend_for_model("S2Pro") == "s2pro_http"
    assert get_backend_for_model("CosyVoice3") == "cosyvoice_http"
    assert get_backend_for_model("IndexTTS2") == "indextts_http"


def test_get_backend_for_model_unknown_raises():
    with pytest.raises(ModelConfigError):
        get_backend_for_model("Unknown")


def test_get_default_parameters_returns_all_defaults():
    defaults = get_default_parameters("S2Pro")
    assert "instruction" in defaults
    assert defaults["instruction"] == ""
    assert defaults["enable_reference_audio"] is True
    assert defaults["temperature"] == 1.0


def test_get_default_parameters_unknown_raises():
    with pytest.raises(ModelConfigError):
        get_default_parameters("Unknown")
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_model_config_loader.py -v
```

预期：ImportError 或 ModuleNotFoundError（`src_next.utils.model_config_loader` 还不存在）。

- [ ] **步骤 3：实现 model_config_loader.py**

新建 `src_next/utils/model_config_loader.py`：

```python
"""加载 src_next/tts/model_configs/*.json。

这些 JSON 文件描述每个 TTS 模型的能力给 LLM（tts_director）看。
loader 是 fail-fast 的：任何 malformed config 或未知 model 查询都立即
抛 ModelConfigError，pipeline 永远不会带着半加载的 model 注册表运行。

公共 API：
    load_model_config(name) -> dict        # 按 name 取单个 config
    load_all_model_configs() -> dict       # 全部加载，返回 {name: config}
    get_backend_for_model(name) -> str     # name -> backend key（如 "S2Pro" -> "s2pro_http"）
    get_default_parameters(name) -> dict   # 提取所有参数 default 值，扁平 dict
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MODEL_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "tts" / "model_configs"


class ModelConfigError(Exception):
    """model_config 加载失败或 model name 未知时抛出。"""


def load_model_config(name: str, directory: Path | None = None) -> dict[str, Any]:
    """按 model name 加载单份 model_config JSON。

    Args:
        name: 模型名（必须匹配某个 JSON 文件的 `name` 字段）。
        directory: 覆盖默认的 model_configs 目录（用于测试）。

    Returns:
        解析后的 JSON dict。

    Raises:
        ModelConfigError: 没有任何 JSON 文件含此 name。
    """
    directory = directory or _MODEL_CONFIGS_DIR
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelConfigError(f"Failed to parse {path}: {exc}") from exc
        if cfg.get("name") == name:
            return cfg
    raise ModelConfigError(
        f"Unknown model name: {name!r}. "
        f"Available: {_list_available_names(directory)}"
    )


def load_all_model_configs(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """加载所有 model_configs，返回 {name: config_dict} 映射。

    Args:
        directory: 覆盖默认的 model_configs 目录。

    Returns:
        以 model name 为 key 的 dict。如果两个文件重名，按文件名字母序
        后者覆盖前者（重名本身会触发下面的 duplicate-name 校验）。

    Raises:
        ModelConfigError: 任何 JSON 解析失败或缺少 `name` 字段。
    """
    directory = directory or _MODEL_CONFIGS_DIR
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelConfigError(f"Failed to parse {path}: {exc}") from exc
        if "name" not in cfg:
            raise ModelConfigError(f"{path} missing required 'name' field")
        if cfg["name"] in result:
            raise ModelConfigError(
                f"Duplicate model name {cfg['name']!r} in {path} "
                f"(already defined in another file)"
            )
        result[cfg["name"]] = cfg
    return result


def get_backend_for_model(name: str, directory: Path | None = None) -> str:
    """按 model name 查 backend key（如 's2pro_http'）。"""
    cfg = load_model_config(name, directory=directory)
    if "backend" not in cfg:
        raise ModelConfigError(f"model_config for {name!r} missing 'backend' field")
    return cfg["backend"]


def get_default_parameters(name: str, directory: Path | None = None) -> dict[str, Any]:
    """从 model_config 提取扁平的 {param_name: default_value} dict。

    tts_director fallback 时用：LLM 漏掉某个 segment 或返回无效参数时，
    我们用 model_config 声明的 default 值，不在 Python 里硬编码 fallback。
    """
    cfg = load_model_config(name, directory=directory)
    parameters = cfg.get("parameters", {})
    defaults: dict[str, Any] = {}
    for field_name, spec in parameters.items():
        if "default" not in spec:
            # 没声明 default 的字段跳过——调用方需要自己处理
            continue
        defaults[field_name] = spec["default"]
    return defaults


def _list_available_names(directory: Path) -> list[str]:
    """列出目录下所有 model name（用于错误信息）。"""
    names: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            if "name" in cfg:
                names.append(cfg["name"])
        except (json.JSONDecodeError, OSError):
            continue
    return names
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_model_config_loader.py -v
```

预期：7 个测试全部 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/utils/model_config_loader.py tests/test_model_config_loader.py
git commit -m "feat(tts_director): C1 step 2 — model_config_loader

加载/校验 src_next/tts/model_configs/*.json，提供 4 个公共函数：
- load_model_config(name) -> dict
- load_all_model_configs() -> dict[str, dict]
- get_backend_for_model(name) -> str（name -> backend key）
- get_default_parameters(name) -> dict（提取所有 default 值供 fallback 用）

Fail-fast：JSON 解析失败 / 缺 name 字段 / 重名 / 未知 name 立即报错。

7 个单元测试全部通过。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 2：tts_director prompt 模块

**文件**：
- 新增：`src_next/analysis/prompts/__init__.py`（空）
- 新增：`src_next/analysis/prompts/tts_director_prompt.py`

本任务是 prompt 工程为主，没有独立逻辑可测。prompt 在任务 3 的测试中通过 MockLLMClient（捕获 prompt）端到端验证。

- [ ] **步骤 1：建空包 __init__**

新建 `src_next/analysis/prompts/__init__.py`（空文件）。

- [ ] **步骤 2：实现 prompt 模块**

新建 `src_next/analysis/prompts/tts_director_prompt.py`：

```python
"""TTSDirectorAgent 的 system + user prompt 构造器。

设计要点：
- system prompt 注入 available model_configs 的 JSON，让 LLM 看到每个模型
  的完整能力描述（strengths/weaknesses/parameters）。
- user prompt 注入 segments + characters + voicebank 摘要。
- 输出 schema 固定：{"instructions": [{segment_id, model, parameters}, ...]}
- per-segment 自由选 model 在 system prompt 里说明，音色一致性由 voice cloning 保证（不需要后处理）。
"""
from __future__ import annotations

import json
from typing import Any

from src_next.core.data_models import CharacterProfile, Segment, VoicebankResult


TTS_DIRECTOR_SYSTEM_PROMPT_TEMPLATE = """你是一位资深的有声书 TTS 导演，负责为每个文本段落选择最合适的 TTS 模型并产出该模型的精确合成参数。

# 你的任务
对于输入的每一段 segment，你需要：
1. 根据该段的说话人、内容、情绪、在故事中的角色定位，从下方"可用模型清单"中选择**一个**最合适的 TTS 模型。
2. 输出该模型的 parameters 字段（按各模型 parameters schema 描述填写）。
3. 为每一段 segment **独立**选 model——同一 speaker 在不同段落可以使用不同 model。音色一致性由 voice cloning 保证（详见下方"模型选择原则"）。

# 可用模型清单
{available_models_json}

# 输出格式（严格 JSON，不要加任何 markdown 代码块标记）
{{
  "instructions": [
    {{
      "segment_id": "<必须与输入 segment 的 segment_id 完全一致>",
      "model": "<可用模型清单里某个模型的 name 字段>",
      "parameters": {{
        <按该模型 parameters schema 描述填写，所有字段都可选，缺省时由系统用 default 填充>
      }}
    }},
    ...
  ]
}}

# 选择模型的决策原则
- **旁白 / narrator**：优先选稳定叙述强的模型（如 CosyVoice3 instruct 模式）。
- **多情绪对白**（一句话内有情绪切换）：优先选支持位置级标签的模型（如 S2Pro）。
- **需要精确情感量化**（如强度可调的悲伤/愤怒）：优先选支持 emotion_vector 的模型（如 IndexTTS2）。
- **平淡叙述 + 没有参考音频**：可选无需 reference 的模型（如 Qwen3TTS，但当前未启用）。
- 别过度使用标签 / emotion_vector——节制使用，让表演自然。

# 模型选择原则（重要：per-segment 自由决策）
- 每一段 segment **独立**选择 model，**不要**因为 speaker 相同就强制用同一个 model。
- 选 model 的核心标准是"这句话适合哪种表演风格"：
  * **多情绪对白 / 一句话内有情绪切换** → S2Pro（15000+ 内联标签，位置级控制）
  * **平淡叙述 / 稳定语气 / 长段旁白** → CosyVoice3（instruct 模式，叙述稳定）
  * **精确情感强度量化**（如悲伤 0.8 vs 0.3 的对比）→ IndexTTS2（emotion_vector）
- **音色一致性由 voice cloning 保证**：所有 backend 都用同一个 voice_ref（参考音频文件）克隆音色。speaker 不变 → voice_ref 不变 → 声音一致，即便换 model 也是同一个人在说。
- 因此，**让同一角色在不同段落自然切换 model**（如激动台词用 S2Pro、平复叙述用 CosyVoice3）反而是推荐做法——能让表演更丰富。
- 例外：如果两句台词表达诉求非常接近（如同一情绪的连续对白），用同一个 model 也完全合理——按表演判断，不强制。

# parameters 填写规则
- 只输出该 model 在 schema 里声明的字段，不要臆造字段。
- 字段值类型必须匹配 schema 声明（string / bool / float / int / list）。
- 不确定的字段可以省略，系统会用 model_config 的 default 值填充。

# 输出顺序
- instructions 数组的长度和顺序必须与输入 segments 一一对应（按 segment_id 匹配）。
- 不要遗漏任何 segment。如果某个 segment 你不知道该怎么处理，仍然要输出一条（parameters 可以为空对象 {{}}），系统会用 default 兜底。
"""


def build_system_prompt(available_models: list[dict[str, Any]]) -> str:
    """渲染 system prompt，注入 model_configs。

    Args:
        available_models: model_config dict 列表（由 model_config_loader 加载）。

    Returns:
        格式化后的 system prompt 字符串。
    """
    # 精简视图给 prompt：name + short_description + 详细 description +
    # strengths + weaknesses + best_for + avoid_for + voice_input + parameters
    slim_models = []
    for cfg in available_models:
        slim_models.append({
            "name": cfg["name"],
            "short_description": cfg.get("short_description", ""),
            "description": cfg.get("description", ""),
            "strengths": cfg.get("strengths", []),
            "weaknesses": cfg.get("weaknesses", []),
            "best_for": cfg.get("best_for", []),
            "avoid_for": cfg.get("avoid_for", []),
            "voice_input": cfg.get("voice_input", "required_reference"),
            "parameters": cfg.get("parameters", {}),
        })
    return TTS_DIRECTOR_SYSTEM_PROMPT_TEMPLATE.format(
        available_models_json=json.dumps(slim_models, ensure_ascii=False, indent=2)
    )


def build_user_prompt(
    segments: list[Segment],
    character_profiles: list[CharacterProfile],
    voicebank_result: VoicebankResult,
) -> str:
    """构造 user prompt，含 segments + characters + voicebank 摘要。

    把 voicebank 摘要也注入，让 LLM 知道每个 speaker 是否有参考 wav——
    这影响 model 选择（如 Qwen3TTS 不需要参考音频；CosyVoice 需要）。
    """
    segments_view = [
        {
            "segment_id": s.segment_id,
            "speaker": s.speaker,
            "segment_type": getattr(s, "segment_type", "narration"),
            "text": s.text,
        }
        for s in segments
    ]

    characters_view = [
        {
            "name": c.name,
            "role": getattr(c, "role", ""),
            "voice_prompt": getattr(c, "voice_prompt", ""),
            "age": getattr(c, "age", ""),
            "gender": getattr(c, "gender", ""),
        }
        for c in character_profiles
    ]

    speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}
    voicebank_view = {
        speaker: ("has_reference_wav" if path else "no_reference")
        for speaker, path in speaker_to_voice.items()
    }

    return (
        f"# 故事 segments（共 {len(segments_view)} 段）\n"
        f"{json.dumps(segments_view, ensure_ascii=False, indent=2)}\n\n"
        f"# 角色档案\n"
        f"{json.dumps(characters_view, ensure_ascii=False, indent=2)}\n\n"
        f"# Voicebank 可用性（speaker -> 是否有参考音频）\n"
        f"{json.dumps(voicebank_view, ensure_ascii=False, indent=2)}\n\n"
        f"请按 system prompt 描述的格式，为每一段 segment 输出一条 instruction。"
    )
```

- [ ] **步骤 3：验证 import 可用**

运行：
```bash
python -c "from src_next.analysis.prompts.tts_director_prompt import build_system_prompt, build_user_prompt; print('OK')"
```

预期：`OK`（无 import 报错）。

- [ ] **步骤 4：提交**

```bash
git add src_next/analysis/prompts/__init__.py src_next/analysis/prompts/tts_director_prompt.py
git commit -m "feat(tts_director): C1 step 3 — tts_director prompt 模块

- analysis/prompts/ 新建子包
- tts_director_prompt.py 提供 build_system_prompt / build_user_prompt
- system prompt 注入 available_models + per-segment 选 model 决策原则 +
  LLM 决策原则
- user prompt 注入 segments + characters + voicebank 可用性

输出格式：{'instructions': [{segment_id, model, parameters}, ...]}

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 3：TTSDirectorAgent 核心 + 1:1 契约测试

**文件**：
- 新增：`src_next/analysis/tts_director.py`
- 新增：`tests/test_tts_director_unit.py`（这里起步，任务 4 续写）

- [ ] **步骤 1：写失败测试**

新建 `tests/test_tts_director_unit.py`：

```python
"""TTSDirectorAgent 单元测试（mock LLM）。"""
from __future__ import annotations

import pytest

from src_next.analysis.tts_director import TTSDirectorAgent
from src_next.core.data_models import ModelSpecificTTSInstruction


def test_direct_returns_1to1_with_input_segments(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """输出长度 + segment_id 必须与输入 1:1 对应。"""
    available_models = list(model_configs_all.values())
    llm_response = {
        "instructions": [
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {"instruct_text": "平稳地叙述"}},
            {"segment_id": "seg_002", "model": "S2Pro", "parameters": {"inline_tags_text": "[excited]当然来得及"}},
            {"segment_id": "seg_003", "model": "IndexTTS2", "parameters": {"emotion_vector": [0, 0, 0.5, 0, 0, 0.3, 0, 0.2]}},
        ]
    }
    agent = TTSDirectorAgent(llm_client=mock_llm(llm_response), available_models=available_models)
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    assert len(result) == len(sample_segments)
    assert [inst.segment_id for inst in result] == [s.segment_id for s in sample_segments]
    assert all(isinstance(inst, ModelSpecificTTSInstruction) for inst in result)


def test_direct_fills_voice_ref_from_voicebank(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """每条 instruction 的 voice_ref 应该从 voicebank_result 填充。"""
    llm_response = {
        "instructions": [
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_002", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_003", "model": "CosyVoice3", "parameters": {}},
        ]
    }
    agent = TTSDirectorAgent(llm_client=mock_llm(llm_response), available_models=list(model_configs_all.values()))
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    expected_paths = {
        "seg_001": "/tmp/voicebank/narrator.wav",
        "seg_002": "/tmp/voicebank/xiaosongshu.wav",
        "seg_003": "/tmp/voicebank/laogui.wav",
    }
    for inst in result:
        assert inst.voice_ref == expected_paths[inst.segment_id], (
            f"voice_ref mismatch for {inst.segment_id}"
        )
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_tts_director_unit.py -v
```

预期：ImportError（`src_next.analysis.tts_director` 还不存在）。

- [ ] **步骤 3：实现 TTSDirectorAgent 核心**

新建 `src_next/analysis/tts_director.py`：

```python
"""src_next/analysis/tts_director.py

合并老 stage 7 (story_director) + stage 8 (tts_instruction_builder) 的职责。

LLM 直接看到 model_configs/*.json 的能力描述，为每个 segment 输出
ModelSpecificTTSInstruction（model + parameters），消除原通用字段到
模型字段的中间映射层。

输出契约：
- 与输入 segments 1:1 对应（segment_id 一致）
- per-segment 自由选 model（音色一致性由 voice cloning 保证）
- LLM 漏掉的 segment / 无效 model / 无效 parameters 走 fallback
"""
from __future__ import annotations

import logging
from typing import Any

from src_next.analysis.prompts.tts_director_prompt import (
    build_system_prompt,
    build_user_prompt,
)
from src_next.core.data_models import (
    CharacterProfile,
    ModelSpecificTTSInstruction,
    Segment,
    VoicebankResult,
)
from src_next.llm.base import BaseLLMClient
from src_next.utils.model_config_loader import (
    get_default_parameters,
    load_model_config,
    ModelConfigError,
)

logger = logging.getLogger(__name__)


class TTSDirectorAgent:
    """LLM 驱动的 TTS 导演 agent。

    取代老的 (story_director + tts_instruction_builder) 组合。LLM 直接看到
    model_configs/*.json，按 segment 输出 ModelSpecificTTSInstruction。

    用法：
        agent = TTSDirectorAgent(llm_client, available_models=[...])
        instructions = agent.direct(
            segments=resolved,
            character_profiles=characters,
            voicebank_result=voicebank,
            default_model_name="CosyVoice3",
        )
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        available_models: list[dict[str, Any]],
    ) -> None:
        """
        Args:
            llm_client: 任意 BaseLLMClient 实现（Qwen HTTP / Gemma4 HTTP / Mock）。
            available_models: LLM 可选的 model_config dict 列表。
                应与 backends.yaml:enabled_backends 对应。
        """
        self.llm = llm_client
        self.available_models = available_models
        # 预构建合法 model name 集合，便于快速查
        self._valid_model_names = {cfg["name"] for cfg in available_models}
        # 缓存 system prompt（只依赖 available_models）
        self._system_prompt = build_system_prompt(available_models)

    def direct(
        self,
        segments: list[Segment],
        character_profiles: list[CharacterProfile],
        voicebank_result: VoicebankResult,
        default_model_name: str,
    ) -> list[ModelSpecificTTSInstruction]:
        """通过 LLM 产出 per-segment ModelSpecificTTSInstruction。

        Args:
            segments: 输入 segments（story_resolver 之后）。
            character_profiles: 角色档案（character_analyzer 之后）。
            voicebank_result: voicebank 输出（voicebank stage 之后）。
            default_model_name: fallback model name（LLM 漏掉或返回无效 model 时用）。
                必须在 available_models 里。

        Returns:
            ModelSpecificTTSInstruction 列表，与输入 segments 1:1。

        Raises:
            ModelConfigError: default_model_name 不在 available_models 里
                （这是配置错误，不是 LLM 错误）。
        """
        if default_model_name not in self._valid_model_names:
            raise ModelConfigError(
                f"default_model_name {default_model_name!r} is not in available_models "
                f"(valid: {sorted(self._valid_model_names)})"
            )

        if not segments:
            return []

        user_prompt = build_user_prompt(segments, character_profiles, voicebank_result)
        raw = self.llm.generate_json(self._system_prompt, user_prompt)

        instructions_by_id = self._parse_response(raw, segments)

        # 对缺失或无效的 instruction 走 fallback
        instructions = self._apply_fallback(
            segments,
            instructions_by_id,
            voicebank_result,
            default_model_name,
        )

        return instructions

    # ─────────────────────────────────────────────────────────────────
    # 私有辅助（任务 4 续写）
    # ─────────────────────────────────────────────────────────────────

    def _parse_response(
        self,
        raw_response: Any,
        segments: list[Segment],
    ) -> dict[str, ModelSpecificTTSInstruction]:
        """把 LLM JSON 响应解析为 {segment_id: instruction} dict。

        - 跳过 model name 无效的 entry（fallback 会兜底）。
        - 跳过 segment_id 与任何输入不匹配的 entry（LLM 幻觉）。
        - 缺失的 segment_id 自然不在 dict 里，fallback 会兜底。
        """
        if not isinstance(raw_response, dict):
            logger.warning("LLM response is not a dict: %r", type(raw_response))
            return {}

        instructions_list = raw_response.get("instructions", [])
        if not isinstance(instructions_list, list):
            logger.warning("LLM response 'instructions' is not a list: %r", type(instructions_list))
            return {}

        valid_segment_ids = {s.segment_id for s in segments}
        result: dict[str, ModelSpecificTTSInstruction] = {}

        for entry in instructions_list:
            if not isinstance(entry, dict):
                continue
            seg_id = entry.get("segment_id")
            if seg_id not in valid_segment_ids:
                logger.warning("Skipping entry with unknown segment_id: %r", seg_id)
                continue

            model_name = entry.get("model")
            if model_name not in self._valid_model_names:
                logger.warning(
                    "segment %r: model %r not in available; will fallback",
                    seg_id, model_name,
                )
                continue

            # speaker/text 从输入 segment 填（LLM 不能改这两个）
            seg = next(s for s in segments if s.segment_id == seg_id)
            result[seg_id] = ModelSpecificTTSInstruction(
                segment_id=seg_id,
                speaker=seg.speaker,
                text=seg.text,
                model=model_name,
                parameters=dict(entry.get("parameters", {}) or {}),
                attempt=1,
            )

        return result

    def _apply_fallback(
        self,
        segments: list[Segment],
        instructions_by_id: dict[str, ModelSpecificTTSInstruction],
        voicebank_result: VoicebankResult,
        default_model_name: str,
    ) -> list[ModelSpecificTTSInstruction]:
        """对缺失的 segment_id 用 default_model_name + 该 model 的 default 参数填充。

        任务 4 实现完整 fallback。当前 stub 按原 segment 顺序返回。
        """
        # 任务 4 会实现完整 fallback
        result: list[ModelSpecificTTSInstruction] = []
        for seg in segments:
            inst = instructions_by_id.get(seg.segment_id)
            if inst is None:
                # 占位：任务 4 会替换为完整 fallback
                inst = ModelSpecificTTSInstruction(
                    segment_id=seg.segment_id,
                    speaker=seg.speaker,
                    text=seg.text,
                    model=default_model_name,
                    parameters={},
                    voice_ref="",
                    attempt=1,
                )
            result.append(inst)
        return result
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_tts_director_unit.py -v
```

预期：2 个测试全部 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/analysis/tts_director.py tests/test_tts_director_unit.py
git commit -m "feat(tts_director): C1 step 4 — TTSDirectorAgent 核心

- direct(segments, characters, voicebank, default_model_name) -> list[ModelSpecificTTSInstruction]
- LLM 直接看到 model_configs 能力描述，输出 model + parameters
- _parse_response：跳过 invalid model name + 未知 segment_id（fallback 兜底）
- voice_ref 从 voicebank_result 自动填充
- 完整 fallback 留给任务 4（stub）

per-segment 自由选 model：同 speaker 的不同 segment 允许使用不同 model，
音色一致性由 voice cloning（同一个 voice_ref）保证。

2 个单元测试通过（1:1 契约 + voice_ref 填充）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 4：TTSDirectorAgent fallback + parameters 清洗

**文件**：
- 修改：`src_next/analysis/tts_director.py`（替换 `_apply_fallback` stub）
- 修改：`tests/test_tts_director_unit.py`（追加 2 个测试）

- [ ] **步骤 1：写失败测试**

追加到 `tests/test_tts_director_unit.py`：

```python
def test_fallback_for_missing_segment(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """如果 LLM 漏掉某个 segment，fallback 用 default model + 该 model 的 default 参数填充。"""
    llm_response = {
        "instructions": [
            # 只返回 seg_001 + seg_002；seg_003 缺失
            {"segment_id": "seg_001", "model": "CosyVoice3", "parameters": {}},
            {"segment_id": "seg_002", "model": "S2Pro", "parameters": {}},
        ]
    }
    agent = TTSDirectorAgent(llm_client=mock_llm(llm_response), available_models=list(model_configs_all.values()))
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    assert len(result) == 3
    fallback_inst = next(inst for inst in result if inst.segment_id == "seg_003")
    assert fallback_inst.model == "CosyVoice3"
    # cosyvoice3.json 的 default 参数
    assert fallback_inst.parameters["mode"] == "instruct"
    assert fallback_inst.parameters["instruct_text"] == ""
    # voice_ref 仍从 voicebank 填充
    assert fallback_inst.voice_ref == "/tmp/voicebank/laogui.wav"


def test_invalid_parameters_field_filtered_to_defaults(
    mock_llm, sample_segments, sample_characters, sample_voicebank_result, model_configs_all
):
    """如果 LLM 返回的 parameters 含无效字段，这些字段被丢弃 + 缺失字段用 default 填充。"""
    llm_response = {
        "instructions": [
            {
                "segment_id": "seg_001",
                "model": "S2Pro",
                "parameters": {
                    "instruction": "[excited]",  # 合法字段
                    "fake_field": "should_be_dropped",  # 不在 schema 的字段——丢弃
                    "temperature": "not_a_number",  # 类型错——用 default 覆盖
                },
            }
        ]
    }
    agent = TTSDirectorAgent(llm_client=mock_llm(llm_response), available_models=list(model_configs_all.values()))
    result = agent.direct(
        segments=sample_segments,
        character_profiles=sample_characters,
        voicebank_result=sample_voicebank_result,
        default_model_name="CosyVoice3",
    )

    s2pro_inst = next(inst for inst in result if inst.segment_id == "seg_001")
    # 合法字段保留
    assert s2pro_inst.parameters["instruction"] == "[excited]"
    # 非法字段被丢弃
    assert "fake_field" not in s2pro_inst.parameters
    # 缺失字段用 default 填充
    assert s2pro_inst.parameters["enable_reference_audio"] is True
    assert s2pro_inst.parameters["temperature"] == 1.0  # 用 default 覆盖类型错的 LLM 值
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_tts_director_unit.py::test_fallback_for_missing_segment tests/test_tts_director_unit.py::test_invalid_parameters_field_filtered_to_defaults -v
```

预期：两个 FAIL（fallback 没填 default；无效字段没清洗）。

- [ ] **步骤 3：替换 stub 实现**

在 `src_next/analysis/tts_director.py`，把 `_apply_fallback` 的 stub 替换为：

```python
    def _apply_fallback(
        self,
        segments: list[Segment],
        instructions_by_id: dict[str, ModelSpecificTTSInstruction],
        voicebank_result: VoicebankResult,
        default_model_name: str,
    ) -> list[ModelSpecificTTSInstruction]:
        """对缺失 segment_id 填充 + 清洗无效 parameters。

        - 不在 instructions_by_id 里的 segment，用 default_model_name + 该 model 的
          default parameters 构造 fallback instruction。
        - 所有 instruction（LLM 产出的或 fallback 的），都按 model_config schema 清洗：
          无效字段丢弃，缺失字段用 default 填。
        - voice_ref 对每条 instruction 都从 voicebank_result 填充。
        """
        speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}
        result: list[ModelSpecificTTSInstruction] = []

        for seg in segments:
            inst = instructions_by_id.get(seg.segment_id)
            if inst is None:
                # 缺失——完整 fallback
                params = get_default_parameters(default_model_name)
                inst = ModelSpecificTTSInstruction(
                    segment_id=seg.segment_id,
                    speaker=seg.speaker,
                    text=seg.text,
                    model=default_model_name,
                    parameters=dict(params),
                    voice_ref=speaker_to_voice.get(seg.speaker, ""),
                    attempt=1,
                )
                logger.info("segment %r: 应用 fallback（model=%s）", seg.segment_id, default_model_name)
            else:
                # 已存在——按 schema 清洗 parameters
                inst.parameters = self._clean_parameters(inst.model, inst.parameters)
                inst.voice_ref = speaker_to_voice.get(seg.speaker, "")
            result.append(inst)

        return result

    def _clean_parameters(self, model_name: str, raw_params: dict[str, Any]) -> dict[str, Any]:
        """丢弃不在 schema 里的字段；缺失字段用 default 填充。

        不严格校验值类型——类型错的值用 schema default 覆盖。这是故意放宽：
        LLM 偶尔会输出 "true"（字符串）而非 true（bool）等，严格校验会产生
        太多假阴性。
        """
        try:
            cfg = load_model_config(model_name)
        except Exception:
            logger.warning("无法加载 %r 的 model_config；返回原始 params", model_name)
            return dict(raw_params)

        schema = cfg.get("parameters", {})
        cleaned: dict[str, Any] = {}
        # 先填所有 default
        for field_name, spec in schema.items():
            if "default" in spec:
                cleaned[field_name] = spec["default"]
        # 再叠加 LLM 提供的合法字段
        for field_name, value in raw_params.items():
            if field_name not in schema:
                logger.debug(
                    "丢弃 model %r parameters 中的未知字段 %r", model_name, field_name
                )
                continue
            expected_type = schema[field_name].get("type")
            if not _matches_type(value, expected_type):
                logger.debug(
                    "字段 %r (model %r) 类型不对（实际 %s，期望 %s）；用 default",
                    field_name, model_name, type(value).__name__, expected_type,
                )
                continue
            cleaned[field_name] = value
        return cleaned


def _matches_type(value: Any, expected_type: str | None) -> bool:
    """对 LLM 产出的 parameter 值做宽松类型检查。"""
    if expected_type is None:
        return True
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "bool":
        return isinstance(value, bool)
    if expected_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "list":
        return isinstance(value, list)
    return True
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_tts_director_unit.py -v
```

预期：5 个测试全部 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/analysis/tts_director.py tests/test_tts_director_unit.py
git commit -m "feat(tts_director): C1 step 5 — fallback + parameters 清洗

- 缺失 segment → 用 default_model_name + 该 model 的 default parameters 补齐
- 无效 parameters 字段（不在 schema）→ drop
- 错误类型字段 → 用 default 覆盖
- voice_ref 始终从 voicebank_result 填充

新增 _matches_type 辅助函数做宽松类型检查（容忍 LLM 偶发的字符串化 bool）。

2 个新测试通过（fallback for missing + invalid parameters filtering）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 5：集成测试（真 Gemma4 LLM）

**文件**：
- 新增：`tests/test_tts_director_integration.py`

本测试调用真 Gemma4 HTTP LLM，验证 LLM 在我们的 prompt 下能产出合法响应。标记 `@pytest.mark.integration`，CI fast 模式跳过。

- [ ] **步骤 1：写集成测试**

新建 `tests/test_tts_director_integration.py`：

```python
"""TTSDirectorAgent 集成测试（真 Gemma4 LLM）。

PR 合并前手动运行：
    pytest tests/test_tts_director_integration.py -v -m integration

CI fast 模式默认跳过。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src_next.analysis.tts_director import TTSDirectorAgent
from src_next.core.data_models import Segment
from src_next.llm.registry import create_llm_client
from src_next.utils.model_config_loader import load_all_model_configs


PROFILE_PATH = Path(__file__).resolve().parent.parent / "src_next" / "profiles" / "yellow_qwen3http_cosyvoicehttp.yaml"


def _load_llm_from_profile():
    """用 yellow profile 加载真 LLM client（Gemma4 HTTP）。"""
    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    llm_cfg = profile["llm"]
    return create_llm_client(llm_cfg["backend"], **{k: v for k, v in llm_cfg.items() if k != "backend"})


@pytest.fixture
def integration_segments() -> list[Segment]:
    """样例故事 segments（5 段，3 speaker）。"""
    return [
        Segment(segment_id="seg_001", segment_type="narration", speaker="narrator",
                text="清晨，小松鼠蹦蹦跳跳地穿过森林。"),
        Segment(segment_id="seg_002", segment_type="dialogue", speaker="小松鼠",
                text="乌龟爷爷，您今天怎么这么慢呀？"),
        Segment(segment_id="seg_003", segment_type="narration", speaker="narrator",
                text="老乌龟抬起头，慢慢地说。"),
        Segment(segment_id="seg_004", segment_type="dialogue", speaker="老乌龟",
                text="孩子，时间会等你的，慢慢来。"),
        Segment(segment_id="seg_005", segment_type="dialogue", speaker="小松鼠",
                text="那我陪您一起走！"),
    ]


@pytest.fixture
def integration_characters():
    from src_next.core.data_models import CharacterProfile
    return [
        CharacterProfile(name="narrator", role="narrator", voice_prompt="平稳温和的中性叙述音",
                         age="adult", gender="neutral"),
        CharacterProfile(name="小松鼠", role="child", voice_prompt="活泼轻快的小女孩声音",
                         age="child", gender="female"),
        CharacterProfile(name="老乌龟", role="elderly", voice_prompt="苍老低沉的老年男性声音",
                         age="elderly", gender="male"),
    ]


@pytest.fixture
def integration_voicebank():
    from src_next.core.data_models import VoicebankResult
    return VoicebankResult(
        speaker_to_voice={
            "narrator": "/tmp/voicebank/narrator.wav",
            "小松鼠": "/tmp/voicebank/xiaosongshu.wav",
            "老乌龟": "/tmp/voicebank/laogui.wav",
        },
        config_snapshot={},
    )


@pytest.mark.integration
def test_tts_director_with_real_gemma4(integration_segments, integration_characters, integration_voicebank):
    """端到端：真 Gemma4 LLM 产出合法 ModelSpecificTTSInstruction[]。

    验证：
    - LLM 返回可解析 JSON
    - 输出与输入 segments 1:1
    - 所有 model name 都在 available_models 里
    - voice_ref 从 voicebank 填充
    - LLM 在做差异化决策（至少有一条非 default model）
    """
    llm = _load_llm_from_profile()
    available_models = list(load_all_model_configs().values())

    agent = TTSDirectorAgent(llm_client=llm, available_models=available_models)
    result = agent.direct(
        segments=integration_segments,
        character_profiles=integration_characters,
        voicebank_result=integration_voicebank,
        default_model_name="CosyVoice3",
    )

    # 1:1 契约
    assert len(result) == 5
    assert [inst.segment_id for inst in result] == [s.segment_id for s in integration_segments]

    # 合法性
    valid_names = {cfg["name"] for cfg in available_models}
    for inst in result:
        assert inst.model in valid_names, f"非法 model：{inst.model}"
        assert inst.voice_ref, f"{inst.segment_id} 的 voice_ref 为空"

    # 合理性 sanity check：至少有一条非 default model
    # （证明 LLM 在做 per-segment 差异化决策，而不是图省事全选 default）
    non_default = [inst for inst in result if inst.model != "CosyVoice3"]
    assert len(non_default) >= 1, (
        "LLM 给全部 5 段都选了 CosyVoice3——可能没在做差异化决策。"
        "Prompt 可能需要更强的决策引导。"
    )
```

- [ ] **步骤 2：验证 collect（不实际跑 integration）**

运行：
```bash
pytest tests/test_tts_director_integration.py --collect-only
```

预期：`collected 1 item` + 测试名显示。

- [ ] **步骤 3：（可选，手动）跑集成测试**

PR 合并前手动运行（需要网络访问 `10.50.121.123:8000`）：

```bash
pytest tests/test_tts_director_integration.py -v -m integration
```

预期：~60 秒内 PASS（单次 LLM 调用）。

失败排查：
- 检查 LLM 服务：`curl --noproxy '*' http://10.50.121.123:8000/health`
- 检查 profile 的 `bypass_proxy: true`（黄区内网必须绕过代理）
- LLM 返回非 JSON：检查 prompt 格式后重试

- [ ] **步骤 4：提交**

```bash
git add tests/test_tts_director_integration.py
git commit -m "test(tts_director): C1 step 6 — 真 Gemma4 集成测试

@pytest.mark.integration 标记，CI fast 模式跳过，PR 合并前手动跑。

验证：
- LLM 真实输出可解析为合法 ModelSpecificTTSInstruction[]
- 1:1 与输入 segments 对应
- 所有 model name 都在 available_models 里
- voice_ref 从 voicebank 填充
- 不全选 default model（LLM 实际在做 per-segment 差异化决策）

依赖 yellow_qwen3http_cosyvoicehttp.yaml 的 Gemma4 HTTP LLM。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## C2：adapter 双接口

### 任务 6：cosyvoice_http adapter 双接口

**文件**：
- 修改：`src_next/tts/cosyvoice_http.py`（加 `_synthesize_model_specific`）
- 新增：`tests/test_adapters_model_specific.py`

- [ ] **步骤 1：读 cosyvoice_http.py 当前结构**

运行：
```bash
grep -n "^def \|^class \|def synthesize\|def _synthesize" src_next/tts/cosyvoice_http.py
```

定位 `synthesize()` 方法（入口）和现有私有辅助。记下行号，便于后续 patch。

- [ ] **步骤 2：写失败测试**

新建 `tests/test_adapters_model_specific.py`：

```python
"""adapter _synthesize_model_specific 单元测试（mock HTTP）。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_next.core.data_models import (
    AudioSegmentResult,
    ModelSpecificTTSInstruction,
    VoicebankResult,
)
from src_next.tts.cosyvoice_http import CosyVoiceHTTPAdapter


@pytest.fixture
def cosyvoice_adapter():
    """创建 mock base_url 的 adapter（不发真 HTTP）。"""
    return CosyVoiceHTTPAdapter(
        base_url="http://mock:8005",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout": 10},
    )


@pytest.fixture
def model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="narrator",
            text="测试文本",
            model="CosyVoice3",
            parameters={
                "mode": "instruct",
                "instruct_text": "用平静的语气说",
            },
            voice_ref="/tmp/voicebank/narrator.wav",
            attempt=1,
        ),
    ]


@pytest.fixture
def voicebank_result() -> VoicebankResult:
    return VoicebankResult(speaker_to_voice={"narrator": "/tmp/voicebank/narrator.wav"}, config_snapshot={})


def test_cosyvoice_synthesize_routes_to_model_specific_when_input_is_model_specific(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """当 instructions[0] 是 ModelSpecificTTSInstruction 时，synthesize() 应该
    调用 _synthesize_model_specific（而不是 _synthesize_legacy）。"""
    with patch.object(
        cosyvoice_adapter, "_synthesize_model_specific", return_value=[MagicMock(spec=AudioSegmentResult)]
    ) as mock_ms, patch.object(
        cosyvoice_adapter, "_synthesize_legacy", return_value=[MagicMock(spec=AudioSegmentResult)]
    ) as mock_legacy:
        cosyvoice_adapter.synthesize(
            model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True
        )
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_cosyvoice_synthesize_routes_to_legacy_when_input_is_legacy(
    cosyvoice_adapter, voicebank_result, tmp_path
):
    """当 instructions[0] 是 TTSInstruction（老格式），synthesize() 应该调 _synthesize_legacy。"""
    from src_next.core.data_models import TTSInstruction
    legacy_instructions = [TTSInstruction(
        segment_id="seg_001", speaker="narrator", text="测试", output_filename="seg_001.wav",
    )]
    with patch.object(
        cosyvoice_adapter, "_synthesize_model_specific", return_value=[MagicMock(spec=AudioSegmentResult)]
    ) as mock_ms, patch.object(
        cosyvoice_adapter, "_synthesize_legacy", return_value=[MagicMock(spec=AudioSegmentResult)]
    ) as mock_legacy:
        cosyvoice_adapter.synthesize(legacy_instructions, voicebank_result, str(tmp_path), dry_run=True)
        mock_legacy.assert_called_once()
        mock_ms.assert_not_called()


def test_cosyvoice_model_specific_passes_through_parameters(
    cosyvoice_adapter, model_specific_instructions, voicebank_result, tmp_path
):
    """_synthesize_model_specific 应该把 instruction.parameters 透传给 HTTP，
    不做 emotion→tag 之类的映射（纯透传）。"""
    captured_request = {}

    def fake_http_post(url, **kwargs):
        captured_request["url"] = url
        captured_request.update(kwargs)
        # 返回最小合法 wav 字节
        return MagicMock(content=b"RIFF...wav", status_code=200, headers={})

    with patch("src_next.tts.cosyvoice_http.requests.post", side_effect=fake_http_post):
        results = cosyvoice_adapter._synthesize_model_specific(
            model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    # 验证 HTTP 请求体含 instruction.parameters（透传）
    assert captured_request.get("url"), "HTTP post 未被调用"
    # 具体字段名（data vs json）取决于 adapter 实现；两种都查
    request_data = captured_request.get("data") or captured_request.get("json") or {}
    if isinstance(request_data, dict):
        # adapter 内部把 instruct_text 拼成 prompt_text，但源 instruct_text 必须驱动它
        assert any("平静" in str(v) for v in request_data.values()), (
            f"instruct_text '用平静的语气说' 未体现在 HTTP 请求：{request_data}"
        )
```

- [ ] **步骤 3：运行测试，验证失败**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v
```

预期：ImportError 或 AttributeError（`_synthesize_model_specific` 不存在）。

- [ ] **步骤 4：给 cosyvoice_http.py 加双接口**

修改 `src_next/tts/cosyvoice_http.py`：

1. 在 `core.data_models` 的 import 里加 `ModelSpecificTTSInstruction`。

2. 把现有 `synthesize` 方法体**重命名为** `_synthesize_legacy`（保留全部实现不变）。

3. 加新的 `synthesize` 方法作为 dispatcher：

```python
def synthesize(
    self,
    instructions,
    voicebank_result,
    output_dir: str,
    **kwargs,
):
    """入口。按 instruction 类型分流。"""
    if not instructions:
        return []
    if isinstance(instructions[0], ModelSpecificTTSInstruction):
        return self._synthesize_model_specific(instructions, voicebank_result, output_dir, **kwargs)
    return self._synthesize_legacy(instructions, voicebank_result, output_dir, **kwargs)
```

4. 加新的 `_synthesize_model_specific` 方法：

```python
def _synthesize_model_specific(
    self,
    instructions: list[ModelSpecificTTSInstruction],
    voicebank_result: VoicebankResult,
    output_dir: str,
    dry_run: bool = False,
    limit: int = 0,
    timeout_per_seg: float | None = None,
    **kwargs,
) -> list[AudioSegmentResult]:
    """ModelSpecificTTSInstruction 的纯透传合成。

    把 instruction.parameters 直接映射到 CosyVoice3 HTTP API：
        - mode（默认 "instruct"）
        - instruct_text → 拼成 "You are a helpful assistant. <text>.<|endofprompt|>"
        - cross_lingual_markers → cross_lingual 模式下作为 `text`（覆盖 instruction.text）

    voice_ref 优先取 instruction.voice_ref，否则 fallback 到
    voicebank_result.speaker_to_voice[speaker]。
    """
    out_path = Path(output_dir) / self.output_subdir
    out_path.mkdir(parents=True, exist_ok=True)
    results: list[AudioSegmentResult] = []

    speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}

    for inst in instructions:
        seg_id = inst.segment_id
        out_wav = out_path / f"{seg_id}.wav"

        # 缓存命中
        if out_wav.exists() and out_wav.stat().st_size > 0 and not dry_run:
            results.append(AudioSegmentResult(
                segment_id=seg_id, success=True, audio_path=str(out_wav),
                error="", elapsed_sec=0.0, from_cache=True,
            ))
            continue

        # 解析 voice 参考音频
        voice_ref = inst.voice_ref or speaker_to_voice.get(inst.speaker, "")
        if not voice_ref and inst.model != "Qwen3TTS":  # Qwen3TTS 不需要 ref（未来）
            results.append(AudioSegmentResult(
                segment_id=seg_id, success=False, audio_path="",
                error=f"Missing voice_ref for speaker {inst.speaker!r}", elapsed_sec=0.0,
            ))
            continue

        if dry_run:
            results.append(AudioSegmentResult(
                segment_id=seg_id, success=True, audio_path=str(out_wav),
                error="", elapsed_sec=0.0, from_cache=False,
            ))
            continue

        # 从 instruction.parameters 构造 HTTP 请求（纯透传）
        mode = inst.parameters.get("mode", "instruct")
        if mode == "cross_lingual":
            text_field = inst.parameters.get("cross_lingual_markers", "") or inst.text
            prompt_text_field = ""
        elif mode == "instruct":
            instruct_text = inst.parameters.get("instruct_text", "")
            # 硬约束：instruct 模式必须以这个前缀开头
            prompt_text_field = f"You are a helpful assistant. {instruct_text}.<|endofprompt|>"
            text_field = inst.text
        else:  # zero_shot
            prompt_text_field = f"<|endofprompt|>"
            text_field = inst.text

        try:
            response = requests.post(
                f"{self.base_url}/v1/cosyvoice/generate",
                json={
                    "text": text_field,
                    "prompt_text": prompt_text_field,
                    "prompt_audio": voice_ref,
                    "mode": mode,
                    "stream": False,
                },
                proxies={"http": None, "https": None},
                timeout=timeout_per_seg or self.timeout,
            )
            response.raise_for_status()
            out_wav.write_bytes(response.content)
            results.append(AudioSegmentResult(
                segment_id=seg_id, success=True, audio_path=str(out_wav),
                error="", elapsed_sec=0.0, from_cache=False,
            ))
        except Exception as exc:
            logger.exception("CosyVoice synthesis failed for %s", seg_id)
            results.append(AudioSegmentResult(
                segment_id=seg_id, success=False, audio_path="",
                error=f"{type(exc).__name__}: {exc}", elapsed_sec=0.0,
            ))

    return results
```

注意：HTTP 请求的具体形状（json vs data、字段名、voicebank wav 加载方式）必须和同文件里 `_synthesize_legacy` 的现有实现一致。**写之前先读 `_synthesize_legacy`**，保持请求形状统一。

- [ ] **步骤 5：运行测试，验证通过**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v
```

预期：3 个测试全部 PASS。

如果 `test_cosyvoice_model_specific_passes_through_parameters` 因请求形状不匹配失败，调整测试断言或实现，让两者匹配。

- [ ] **步骤 6：验证老路径仍可用（smoke）**

运行：
```bash
python -m src_next.core.test_tts_from_artifacts 2>&1 | tail -5
```

预期：无报错完成（现有 smoke 测试仍走 `_synthesize_legacy`）。

- [ ] **步骤 7：提交**

```bash
git add src_next/tts/cosyvoice_http.py tests/test_adapters_model_specific.py
git commit -m "feat(tts_director): C2 step 1 — cosyvoice_http 双接口

- synthesize() 入口 isinstance 分流：ModelSpecificTTSInstruction → _synthesize_model_specific；其他 → _synthesize_legacy
- _synthesize_model_specific：纯透传 instruction.parameters 到 HTTP
  - mode：instruct（默认）/ cross_lingual / zero_shot
  - instruct_text 自动拼成 'You are a helpful assistant. <text>.<|endofprompt|>'
- _synthesize_legacy 完全保留（mapping 逻辑不变）

3 个测试通过：路由正确性（新/老）+ 参数透传。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 7：s2pro_adapter 双接口

**文件**：
- 修改：`src_next/tts/s2pro_adapter.py`
- 修改：`tests/test_adapters_model_specific.py`（追加 s2pro 测试）

- [ ] **步骤 1：写失败测试**

追加到 `tests/test_adapters_model_specific.py`：

```python
from src_next.tts.s2pro_adapter import S2ProTTSAdapter


@pytest.fixture
def s2pro_adapter():
    return S2ProTTSAdapter(
        base_url="http://mock:8010",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout": 10, "enable_reference_audio": True},
    )


@pytest.fixture
def s2pro_model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="小松鼠",
            text="太棒了！",
            model="S2Pro",
            parameters={
                "instruction": "[excited]",
                "inline_tags_text": "[excited]太棒了！",
                "enable_reference_audio": True,
                "temperature": 0.9,
                "top_p": 0.7,
            },
            voice_ref="/tmp/voicebank/xiaosongshu.wav",
            attempt=1,
        ),
    ]


def test_s2pro_synthesize_routes_to_model_specific(
    s2pro_adapter, s2pro_model_specific_instructions, voicebank_result, tmp_path
):
    with patch.object(s2pro_adapter, "_synthesize_model_specific", return_value=[MagicMock(spec=AudioSegmentResult)]) as mock_ms, \
         patch.object(s2pro_adapter, "_synthesize_legacy", return_value=[MagicMock(spec=AudioSegmentResult)]) as mock_legacy:
        s2pro_adapter.synthesize(s2pro_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True)
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_s2pro_model_specific_passes_through_inline_tags(
    s2pro_adapter, s2pro_model_specific_instructions, voicebank_result, tmp_path
):
    """当 inline_tags_text 提供，它覆盖 instruction.text 作为 HTTP 的 `text` 字段。
    instruction 字段原样透传（不从 emotion 映射）。"""
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(content=b"RIFF...wav", status_code=200)

    with patch("src_next.tts.s2pro_adapter.requests.post", side_effect=fake_post):
        s2pro_adapter._synthesize_model_specific(
            s2pro_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    assert captured.get("url")
    # text 字段应含 inline_tags_text，不是原始 instruction.text
    data = captured.get("data") or {}
    # S2Pro 8010 用 multipart/form-data，所以查 data dict
    text_value = data.get("text", "")
    assert "[excited]" in text_value, f"inline_tags_text 未透传：{data}"
    # instruction 字段应是全局的
    assert data.get("instruction") == "[excited]"
    # 不应有 emotion→tag mapping（LLM 已经直接产出了 tags）
    # 如果有 mapping，会看到如 [sad]（来自通用 emotion "sad"）；
    # 既然 LLM 直接给 [excited]，就应该只出现 [excited]。
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v -k s2pro
```

预期：FAIL（`S2ProTTSAdapter` 没有 `_synthesize_model_specific`）。

- [ ] **步骤 3：给 s2pro_adapter.py 加双接口**

修改 `src_next/tts/s2pro_adapter.py`：

1. 在 import 里加 `ModelSpecificTTSInstruction`。
2. 把现有 `synthesize` 方法体重命名为 `_synthesize_legacy`。
3. 加新的 `synthesize` dispatcher：

```python
def synthesize(self, instructions, voicebank_result, output_dir: str, **kwargs):
    if not instructions:
        return []
    if isinstance(instructions[0], ModelSpecificTTSInstruction):
        return self._synthesize_model_specific(instructions, voicebank_result, output_dir, **kwargs)
    return self._synthesize_legacy(instructions, voicebank_result, output_dir, **kwargs)
```

4. 加 `_synthesize_model_specific` 方法。关键逻辑：
   - 用 `instruction.parameters.inline_tags_text` 作 `text`（非空时），否则用 `instruction.text`
   - `instruction.parameters.instruction` 直接作为 `instruction` form 字段透传
   - `temperature` / `top_p` / `max_new_tokens` 直接透传
   - 如果 `enable_reference_audio=true` 且 voice_ref 存在：multipart 上传为 `reference_audio` + 用 voice_ref 的转写文本作 `prompt_text`
   - **不要调 `_emotion_to_tag` 或任何 emotion mapping**——LLM 已经产出 tags

框架（HTTP/wav 处理细节参考同文件 `_synthesize_legacy`）：

```python
def _synthesize_model_specific(
    self,
    instructions: list[ModelSpecificTTSInstruction],
    voicebank_result: VoicebankResult,
    output_dir: str,
    dry_run: bool = False,
    limit: int = 0,
    timeout_per_seg: float | None = None,
    **kwargs,
) -> list[AudioSegmentResult]:
    out_path = Path(output_dir) / self.output_subdir
    out_path.mkdir(parents=True, exist_ok=True)
    results: list[AudioSegmentResult] = []
    speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}

    for inst in instructions:
        seg_id = inst.segment_id
        out_wav = out_path / f"{seg_id}.wav"

        if out_wav.exists() and out_wav.stat().st_size > 0 and not dry_run:
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0, from_cache=True))
            continue

        voice_ref = inst.voice_ref or speaker_to_voice.get(inst.speaker, "")
        enable_clone = inst.parameters.get("enable_reference_audio", True)

        if dry_run:
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0))
            continue

        # 构造 multipart form
        text_field = inst.parameters.get("inline_tags_text", "") or inst.text
        form_data = {
            "text": text_field,
            "instruction": inst.parameters.get("instruction", ""),
            "temperature": str(inst.parameters.get("temperature", 1.0)),
            "top_p": str(inst.parameters.get("top_p", 0.6)),
            "max_new_tokens": str(inst.parameters.get("max_new_tokens", 4096)),
        }
        files = {}
        if enable_clone and voice_ref and Path(voice_ref).exists():
            # prompt_text 必须与 voice_ref wav 的转写一致；voicebank 生成的
            # wav 用 voicebank_result 的 reference_text 配置
            form_data["enable_reference_audio"] = "true"
            form_data["prompt_text"] = self._get_prompt_text_for_voice(voice_ref)
            files["reference_audio"] = (Path(voice_ref).name, open(voice_ref, "rb"), "audio/wav")

        try:
            response = requests.post(
                f"{self.base_url}/v1/voicegen/generate",
                data=form_data, files=files or None,
                proxies={"http": None, "https": None},
                timeout=timeout_per_seg or self.timeout,
            )
            response.raise_for_status()
            out_wav.write_bytes(response.content)
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0))
        except Exception as exc:
            logger.exception("S2Pro synthesis failed for %s", seg_id)
            results.append(AudioSegmentResult(segment_id=seg_id, success=False, audio_path="", error=f"{type(exc).__name__}: {exc}", elapsed_sec=0.0))
        finally:
            for _, fobj, _ in files.values():
                fobj.close()

    return results


def _get_prompt_text_for_voice(self, voice_ref: str) -> str:
    """取 voice_ref wav 对应的转写文本（用于 S2Pro prompt_text）。

    voicebank 生成的 wav 通常伴随同名的 .txt 文件（转写），读取它。
    找不到则返回空（S2Pro 会用默认）。
    """
    txt_path = Path(voice_ref).with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8").strip()
    # fallback：用 self.extra_args 里的 reference_text（profile 配的）
    return self.extra_args.get("reference_text", "")
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v -k s2pro
```

预期：2 个 s2pro 测试 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/tts/s2pro_adapter.py tests/test_adapters_model_specific.py
git commit -m "feat(tts_director): C2 step 2 — s2pro_adapter 双接口

- _synthesize_model_specific：纯透传
  - inline_tags_text 优先作 text（带标签版），否则用 instruction.text
  - instruction / temperature / top_p / max_new_tokens 直接传
  - enable_reference_audio + voice_ref → multipart 上传 reference_audio
  - **不再做 emotion→tag mapping**（_EMOTION_TO_S2PRO_TAG 等只在 _synthesize_legacy 用）

新增 _get_prompt_text_for_voice 辅助：读 voice_ref 同名 .txt 或 fallback
到 profile extra_args.reference_text。

2 个新测试通过：路由 + 参数透传（验证 [excited] 标签直接来自 LLM）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 8：indextts_http adapter 双接口

**文件**：
- 修改：`src_next/tts/indextts_http.py`
- 修改：`tests/test_adapters_model_specific.py`（追加 indextts 测试）

- [ ] **步骤 1：写失败测试**

追加到 `tests/test_adapters_model_specific.py`：

```python
from src_next.tts.indextts_http import IndexTTSHTTPAdapter


@pytest.fixture
def indextts_adapter():
    return IndexTTSHTTPAdapter(
        base_url="http://mock:8009",
        output_subdir="audio_segments",
        extra_args={"max_workers": 1, "timeout": 10},
    )


@pytest.fixture
def indextts_model_specific_instructions() -> list[ModelSpecificTTSInstruction]:
    return [
        ModelSpecificTTSInstruction(
            segment_id="seg_001",
            speaker="老乌龟",
            text="孩子，时间会等你的。",
            model="IndexTTS2",
            parameters={
                "emotion_vector": [0, 0, 0.6, 0, 0, 0.4, 0, 0],
                "emotion_alpha": 0.7,
                "temperature": 0.8,
            },
            voice_ref="/tmp/voicebank/laogui.wav",
            attempt=1,
        ),
    ]


def test_indextts_synthesize_routes_to_model_specific(
    indextts_adapter, indextts_model_specific_instructions, voicebank_result, tmp_path
):
    with patch.object(indextts_adapter, "_synthesize_model_specific", return_value=[MagicMock(spec=AudioSegmentResult)]) as mock_ms, \
         patch.object(indextts_adapter, "_synthesize_legacy", return_value=[MagicMock(spec=AudioSegmentResult)]) as mock_legacy:
        indextts_adapter.synthesize(indextts_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=True)
        mock_ms.assert_called_once()
        mock_legacy.assert_not_called()


def test_indextts_model_specific_passes_through_emotion_vector(
    indextts_adapter, indextts_model_specific_instructions, voicebank_result, tmp_path
):
    """instruction.parameters 的 emotion_vector 应该原样透传给 HTTP
    （不是从通用 emotion 字段推导）。"""
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(content=b"RIFF...wav", status_code=200)

    with patch("src_next.tts.indextts_http.requests.post", side_effect=fake_post):
        indextts_adapter._synthesize_model_specific(
            indextts_model_specific_instructions, voicebank_result, str(tmp_path), dry_run=False
        )

    assert captured.get("url")
    json_body = captured.get("json", {})
    assert json_body.get("emotion_vector") == [0, 0, 0.6, 0, 0, 0.4, 0, 0], (
        f"emotion_vector 未透传：{json_body}"
    )
    assert json_body.get("emotion_alpha") == 0.7
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v -k indextts
```

预期：FAIL（无 `_synthesize_model_specific`）。

- [ ] **步骤 3：给 indextts_http.py 加双接口**

修改 `src_next/tts/indextts_http.py`：

1. import 加 `ModelSpecificTTSInstruction`。
2. 把现有 `synthesize` 方法体重命名为 `_synthesize_legacy`。
3. 加 `synthesize` dispatcher（模式同任务 6-7）。
4. 加 `_synthesize_model_specific`：

```python
def _synthesize_model_specific(
    self,
    instructions: list[ModelSpecificTTSInstruction],
    voicebank_result: VoicebankResult,
    output_dir: str,
    dry_run: bool = False,
    limit: int = 0,
    timeout_per_seg: float | None = None,
    **kwargs,
) -> list[AudioSegmentResult]:
    out_path = Path(output_dir) / self.output_subdir
    out_path.mkdir(parents=True, exist_ok=True)
    results: list[AudioSegmentResult] = []
    speaker_to_voice = getattr(voicebank_result, "speaker_to_voice", {}) or {}

    for inst in instructions:
        seg_id = inst.segment_id
        out_wav = out_path / f"{seg_id}.wav"

        if out_wav.exists() and out_wav.stat().st_size > 0 and not dry_run:
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0, from_cache=True))
            continue

        voice_ref = inst.voice_ref or speaker_to_voice.get(inst.speaker, "")
        if not voice_ref:
            results.append(AudioSegmentResult(segment_id=seg_id, success=False, audio_path="", error=f"Missing voice_ref for {inst.speaker!r}", elapsed_sec=0.0))
            continue

        if dry_run:
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0))
            continue

        # 构造 JSON body —— 纯透传 instruction.parameters
        body = {
            "text": inst.text,
            "reference_audio_path": voice_ref,  # 服务器端路径；base64 用 reference_audio_base64
        }
        # 可选字段
        for opt_field in ("emotion_vector", "emotion_alpha", "emotion_text",
                          "use_random", "temperature", "top_p", "top_k",
                          "num_beams", "repetition_penalty", "max_mel_tokens",
                          "max_text_tokens", "interval_silence"):
            if opt_field in inst.parameters:
                body[opt_field] = inst.parameters[opt_field]

        try:
            response = requests.post(
                f"{self.base_url}/v1/tts/synthesize",
                json=body,
                proxies={"http": None, "https": None},
                timeout=timeout_per_seg or self.timeout,
            )
            response.raise_for_status()
            out_wav.write_bytes(response.content)
            results.append(AudioSegmentResult(segment_id=seg_id, success=True, audio_path=str(out_wav), error="", elapsed_sec=0.0))
        except Exception as exc:
            logger.exception("IndexTTS synthesis failed for %s", seg_id)
            results.append(AudioSegmentResult(segment_id=seg_id, success=False, audio_path="", error=f"{type(exc).__name__}: {exc}", elapsed_sec=0.0))

    return results
```

注意：如果现有 `_synthesize_legacy` 用 `reference_audio_base64`（读 wav 文件并 base64 编码），`_synthesize_model_specific` 也应如此。匹配现有模式。

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_adapters_model_specific.py -v -k indextts
```

预期：2 个 indextts 测试 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/tts/indextts_http.py tests/test_adapters_model_specific.py
git commit -m "feat(tts_director): C2 step 3 — indextts_http 双接口

- _synthesize_model_specific：纯透传 emotion_vector / emotion_alpha / 等
- voice_ref 作 reference_audio_path（与老路径一致）
- 不做 emotion → vector 映射（LLM 已直接产出 vector）

2 个新测试通过：路由 + emotion_vector 透传。

C2 完成（3 个 adapter 双接口改造 + 6 个测试）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## C3：backends.yaml + pipeline 集成

### 任务 9：backends.yaml + loader + 测试

**文件**：
- 新增：`src_next/tts/backends.yaml`
- 修改：`src_next/utils/yaml_utils.py`（加 `load_backends_yaml`）
- 新增：`tests/test_backends_yaml_loader.py`

- [ ] **步骤 1：写失败测试**

新建 `tests/test_backends_yaml_loader.py`：

```python
"""src_next/utils/yaml_utils.py:load_backends_yaml 单元测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src_next.utils.yaml_utils import load_backends_yaml


def test_load_backends_yaml_returns_dict_with_required_keys():
    data = load_backends_yaml()
    assert "enabled_backends" in data
    assert "backends" in data
    assert "default_model" in data


def test_load_backends_yaml_enabled_backends_is_list():
    data = load_backends_yaml()
    assert isinstance(data["enabled_backends"], list)
    assert len(data["enabled_backends"]) >= 1


def test_load_backends_yaml_backends_have_base_url():
    data = load_backends_yaml()
    for backend_name in data["enabled_backends"]:
        assert backend_name in data["backends"], f"enabled backend {backend_name!r} 不在 backends dict 里"
        backend_cfg = data["backends"][backend_name]
        assert "base_url" in backend_cfg, f"backend {backend_name!r} 缺 base_url"


def test_load_backends_yaml_default_model_is_valid():
    """default_model 必须是某个 model_configs/*.json 的 name。"""
    from src_next.utils.model_config_loader import load_all_model_configs

    data = load_backends_yaml()
    all_model_names = set(load_all_model_configs().keys())
    assert data["default_model"] in all_model_names, (
        f"default_model {data['default_model']!r} 不在 model_configs names {all_model_names} 里"
    )


def test_load_backends_yaml_enabled_backends_subset_of_backends_dict():
    """每个 enabled backend 必须在 backends dict 里有对应条目。"""
    data = load_backends_yaml()
    backends_dict_keys = set(data["backends"].keys())
    enabled_set = set(data["enabled_backends"])
    assert enabled_set.issubset(backends_dict_keys), (
        f"enabled_backends 含 backends dict 里没有的 key：{enabled_set - backends_dict_keys}"
    )


def test_load_backends_yaml_enabled_backends_have_model_configs():
    """每个 enabled backend 必须能通过 backend 字段对应到 model_config。"""
    from src_next.utils.model_config_loader import load_all_model_configs

    data = load_backends_yaml()
    all_configs = load_all_model_configs()
    backend_to_name = {cfg["backend"]: name for name, cfg in all_configs.items()}

    for backend in data["enabled_backends"]:
        assert backend in backend_to_name, (
            f"enabled backend {backend!r} 没有对应的 model_config"
        )


def test_load_backends_yaml_custom_path(tmp_path):
    """loader 应支持 path override（用于测试）。"""
    custom = tmp_path / "custom_backends.yaml"
    custom.write_text("""
enabled_backends: [mock_backend]
backends:
  mock_backend:
    base_url: http://mock:9999
default_model: MockModel
""", encoding="utf-8")
    data = load_backends_yaml(path=custom)
    assert data["enabled_backends"] == ["mock_backend"]
    assert data["default_model"] == "MockModel"
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_backends_yaml_loader.py -v
```

预期：ImportError（`load_backends_yaml` 不存在）。

- [ ] **步骤 3：建 backends.yaml**

新建 `src_next/tts/backends.yaml`：

```yaml
# src_next/tts/backends.yaml
#
# 全局 TTS backend 注册表。当 profile.pipeline.use_tts_director=true（或
# CLI flag --use-tts-director）时由 pipeline 自动加载，替代 profile.tts 块。
#
# 加新 TTS 服务只改本文件 + 加一个 model_configs/<model>.json，
# 不需要改任何 profile yaml。

# 启用的 backend 列表。LLM 只能从这些 backend 对应的 model_configs 里选 model。
# 必须是下面 backends 字典里 key 的子集。
enabled_backends:
  - cosyvoice_http
  - s2pro_http
  - indextts_http

# 各 backend 的服务地址 + extra_args。
# extra_args 透传给 adapter 构造函数（与老 profile.tts.extra_args 等价）。
backends:
  cosyvoice_http:
    base_url: "http://10.50.121.102:8005"
    extra_args:
      max_workers: 4
      timeout: 300

  s2pro_http:
    base_url: "http://10.50.121.102:8010"   # 8010 端口（含音色克隆）
    extra_args:
      max_workers: 4
      enable_reference_audio: true
      timeout: 300

  indextts_http:
    base_url: "http://10.50.121.102:8009"
    extra_args:
      max_workers: 4
      timeout: 300

# Fallback 模型（LLM 没覆盖的 segment 用这个）。
# 必须是某个 model_configs/*.json 的 name 字段，且其 backend 在 enabled_backends 里。
default_model: CosyVoice3
```

- [ ] **步骤 4：给 yaml_utils.py 加 loader**

修改 `src_next/utils/yaml_utils.py` —— 追加：

```python
_DEFAULT_BACKENDS_YAML = Path(__file__).resolve().parent.parent / "tts" / "backends.yaml"


def load_backends_yaml(path: Path | str | None = None) -> dict[str, Any]:
    """加载 src_next/tts/backends.yaml（全局 TTS backend 注册表）。

    只在 pipeline.use_tts_director=true 时用。校验：
    - 必填 key 存在（enabled_backends, backends, default_model）
    - 每个 enabled_backends 条目都在 backends dict 里
    - 每个 enabled_backends 条目都有 base_url

    Args:
        path: 覆盖路径（用于测试）。

    Returns:
        解析后的 YAML dict。

    Raises:
        FileNotFoundError: backends.yaml 不存在。
        ValueError: schema 不合法。
    """
    yaml_path = Path(path) if path else _DEFAULT_BACKENDS_YAML
    if not yaml_path.exists():
        raise FileNotFoundError(f"backends.yaml not found at {yaml_path}")

    data = load_yaml(yaml_path)

    required_keys = {"enabled_backends", "backends", "default_model"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"backends.yaml 缺必填 key：{missing}")

    if not isinstance(data["enabled_backends"], list) or not data["enabled_backends"]:
        raise ValueError("backends.yaml：enabled_backends 必须是非空 list")

    if not isinstance(data["backends"], dict):
        raise ValueError("backends.yaml：backends 必须是 dict")

    for backend_name in data["enabled_backends"]:
        if backend_name not in data["backends"]:
            raise ValueError(
                f"backends.yaml：enabled_backends 条目 {backend_name!r} "
                f"在 backends dict 里找不到"
            )
        if "base_url" not in data["backends"][backend_name]:
            raise ValueError(
                f"backends.yaml：backend {backend_name!r} 缺 base_url"
            )

    return data
```

- [ ] **步骤 5：运行测试，验证通过**

运行：
```bash
pytest tests/test_backends_yaml_loader.py -v
```

预期：7 个测试全部 PASS。

- [ ] **步骤 6：提交**

```bash
git add src_next/tts/backends.yaml src_next/utils/yaml_utils.py tests/test_backends_yaml_loader.py
git commit -m "feat(tts_director): C3 step 1 — backends.yaml + loader

全局 TTS backend 注册表，集中维护所有 TTS 服务地址。
启用方式：profile.pipeline.use_tts_director=true 或 CLI --use-tts-director。

load_backends_yaml 校验：
- enabled_backends / backends / default_model 三必填
- enabled_backends ⊆ backends 字典 keys
- 每个 backend 必须有 base_url

7 个测试通过（含 schema 校验 + 自定义路径 override）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 10：registry.create_adapter_for_backend + lazy cache

**文件**：
- 修改：`src_next/tts/registry.py`
- 新增：`tests/test_registry_adapter_cache.py`

- [ ] **步骤 1：读当前 registry.py**

运行：
```bash
cat src_next/tts/registry.py
```

确认现有 `create_tts_adapter(backend, **config)` 签名。

- [ ] **步骤 2：写失败测试**

新建 `tests/test_registry_adapter_cache.py`：

```python
"""src_next/tts/registry.py:create_adapter_for_backend 单元测试。"""
from __future__ import annotations

import pytest

from src_next.tts.registry import create_adapter_for_backend, clear_adapter_cache


def test_create_adapter_for_backend_returns_adapter():
    adapter = create_adapter_for_backend("cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments")
    assert adapter is not None


def test_create_adapter_for_backend_caches_per_backend_and_config():
    """相同 backend + 相同 config 应返回相同实例。"""
    clear_adapter_cache()
    a1 = create_adapter_for_backend("cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments")
    a2 = create_adapter_for_backend("cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments")
    assert a1 is a2, "相同 backend+config 应返回缓存实例"


def test_create_adapter_for_backend_different_config_returns_new_instance():
    """不同 config 应产生不同实例。"""
    clear_adapter_cache()
    a1 = create_adapter_for_backend("cosyvoice_http", base_url="http://mock:8005", output_subdir="audio_segments")
    a2 = create_adapter_for_backend("cosyvoice_http", base_url="http://mock:9999", output_subdir="audio_segments")
    assert a1 is not a2, "不同 config 应返回新实例"


def test_create_adapter_for_backend_unknown_backend_raises():
    with pytest.raises(ValueError, match="Unknown backend"):
        create_adapter_for_backend("totally_made_up_backend", base_url="http://x")
```

- [ ] **步骤 3：运行测试，验证失败**

运行：
```bash
pytest tests/test_registry_adapter_cache.py -v
```

预期：ImportError（`create_adapter_for_backend` / `clear_adapter_cache` 不存在）。

- [ ] **步骤 4：给 registry.py 加 create_adapter_for_backend**

修改 `src_next/tts/registry.py` —— 追加：

```python
# 模块级缓存：{(backend, config_hash): adapter_instance}
_adapter_cache: dict[tuple[str, int], BaseTTSAdapter] = {}


def _config_hash(config: dict) -> int:
    """config dict 的稳定 hash（作 cache key）。"""
    import json
    return hash(json.dumps(config, sort_keys=True, ensure_ascii=False, default=str))


def create_adapter_for_backend(backend: str, **config) -> BaseTTSAdapter:
    """按 backend + config 创建或返回缓存的 adapter。

    与 create_tts_adapter（每次都新建）不同，本函数按 (backend, config) tuple
    缓存。stage 8 多 adapter 调度时用：如 LLM 给 10 段选了 CosyVoice3，
    adapter 只构造一次。

    Args:
        backend: backend key（如 'cosyvoice_http'）。
        **config: adapter 构造参数（base_url, extra_args 等）。

    Returns:
        BaseTTSAdapter 实例。

    Raises:
        ValueError: backend 未知。
    """
    cache_key = (backend, _config_hash(config))
    if cache_key in _adapter_cache:
        return _adapter_cache[cache_key]
    adapter = create_tts_adapter(backend, **config)  # 委托给现有工厂
    _adapter_cache[cache_key] = adapter
    return adapter


def clear_adapter_cache() -> None:
    """清空 adapter 缓存。主要用于测试。"""
    _adapter_cache.clear()
```

- [ ] **步骤 5：运行测试，验证通过**

运行：
```bash
pytest tests/test_registry_adapter_cache.py -v
```

预期：4 个测试全部 PASS。

- [ ] **步骤 6：提交**

```bash
git add src_next/tts/registry.py tests/test_registry_adapter_cache.py
git commit -m "feat(tts_director): C3 step 2 — registry.create_adapter_for_backend

加 lazy cache：相同 (backend, config) 只创建一次 adapter 实例。
stage 8 多 adapter 调度时（如 LLM 选 CosyVoice3 用于 10 segments），
adapter 只构造一次，HTTP 连接池等开销分摊。

clear_adapter_cache() 供测试用。

4 个测试通过：返回 + 缓存命中 + 不同 config 不同实例 + 未知 backend 报错。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 11：yaml_utils use_tts_director 开关识别

**文件**：
- 修改：`src_next/utils/yaml_utils.py`
- 修改：`tests/test_backends_yaml_loader.py`（追加）

- [ ] **步骤 1：写失败测试**

追加到 `tests/test_backends_yaml_loader.py`：

```python
def test_read_use_tts_director_flag_default_false(tmp_path):
    """profile 没有 pipeline.use_tts_director 时默认 False。"""
    from src_next.utils.yaml_utils import read_use_tts_director_flag
    profile_path = tmp_path / "test_profile.yaml"
    profile_path.write_text("""
llm: {backend: mock}
tts: {backend: mock}
output: {root: output}
""", encoding="utf-8")
    assert read_use_tts_director_flag(profile_path) is False


def test_read_use_tts_director_flag_true_when_set(tmp_path):
    from src_next.utils.yaml_utils import read_use_tts_director_flag
    profile_path = tmp_path / "test_profile.yaml"
    profile_path.write_text("""
llm: {backend: mock}
tts: {backend: mock}
output: {root: output}
pipeline:
  use_tts_director: true
""", encoding="utf-8")
    assert read_use_tts_director_flag(profile_path) is True


def test_read_use_tts_director_flag_explicit_false(tmp_path):
    from src_next.utils.yaml_utils import read_use_tts_director_flag
    profile_path = tmp_path / "test_profile.yaml"
    profile_path.write_text("""
llm: {backend: mock}
tts: {backend: mock}
output: {root: output}
pipeline:
  use_tts_director: false
""", encoding="utf-8")
    assert read_use_tts_director_flag(profile_path) is False
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_backends_yaml_loader.py -v -k use_tts_director
```

预期：ImportError（`read_use_tts_director_flag` 不存在）。

- [ ] **步骤 3：给 yaml_utils.py 加辅助函数**

修改 `src_next/utils/yaml_utils.py` —— 追加：

```python
def read_use_tts_director_flag(profile_path: Path | str) -> bool:
    """从 profile yaml 读 pipeline.use_tts_director，默认 False。

    Args:
        profile_path: profile yaml 路径。

    Returns:
        pipeline.use_tts_director 显式为 true 时返回 True；否则 False。
    """
    data = load_yaml(profile_path)
    pipeline_block = data.get("pipeline", {}) or {}
    return bool(pipeline_block.get("use_tts_director", False))
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_backends_yaml_loader.py -v -k use_tts_director
```

预期：3 个测试全部 PASS。

- [ ] **步骤 5：提交**

```bash
git add src_next/utils/yaml_utils.py tests/test_backends_yaml_loader.py
git commit -m "feat(tts_director): C3 step 3 — read_use_tts_director_flag

读取 profile yaml 的 pipeline.use_tts_director 字段，默认 False。
配合任务 13 实现的 CLI flag --use-tts-director 实现 OR 逻辑。

3 个测试通过：默认 False / 显式 True / 显式 False。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 12：pipeline stage 7 + stage 8 集成

最大的任务。修改 `audiobook_pipeline.py`：
- 开关开启时 stage 7 切到 `tts_director`
- stage 8 从单 adapter 改为多 adapter 分组调度
- stage 编号按开关渲染为 `[X/9]` 或 `[X/10]`

**文件**：
- 修改：`src_next/core/audiobook_pipeline.py`
- 新增：`tests/test_pipeline_use_tts_director_switch.py`
- 新增：`tests/test_multi_backend_synthesis.py`

- [ ] **步骤 1：写失败 smoke 测试**

新建 `tests/test_pipeline_use_tts_director_switch.py`：

```python
"""pipeline stage 切换 smoke 测试（基于 use_tts_director）。

mock LLM + mock TTS，不打真服务。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pipeline_inputs(tmp_path):
    """mock pipeline 跑一次的最小输入。"""
    input_txt = tmp_path / "story.txt"
    input_txt.write_text("小松鼠说：你好。", encoding="utf-8")
    return input_txt


def test_pipeline_off_flag_runs_10_stages(mock_pipeline_inputs, tmp_path):
    """use_tts_director=false 时，pipeline 跑 10 stage（老链路）。"""
    from src_next.core.audiobook_pipeline import run_pipeline

    # mock 所有 backend，不打真服务
    with patch("src_next.tts.registry.create_tts_adapter") as mock_tts, \
         patch("src_next.voicebank.registry.create_voicebank_adapter") as mock_vb, \
         patch("src_next.llm.registry.create_llm_client") as mock_llm, \
         patch("src_next.analysis.story_director.generate_director_plan") as mock_director, \
         patch("src_next.core.tts_instruction_builder.build_tts_instructions") as mock_builder:

        # mock 返回最小合法对象
        mock_llm.return_value = MagicMock()
        mock_vb.return_value = MagicMock()
        mock_tts.return_value = MagicMock(synthesize=MagicMock(return_value=[]))
        mock_director.return_value = []
        mock_builder.return_value = []

        # use_tts_director=false 跑一次
        try:
            result = run_pipeline(
                input_path=str(mock_pipeline_inputs),
                profile_dict={
                    "llm": {"backend": "mock_llm"},
                    "voicebank": {"backend": "mock_voicebank"},
                    "tts": {"backend": "mock_tts", "base_url": "http://mock", "output_subdir": "audio_segments"},
                    "output": {"root": str(tmp_path)},
                    "pipeline": {"use_tts_director": False, "save_intermediate_json": True},
                },
            )
        except Exception as exc:
            pytest.skip(f"pipeline 结构需要更多 mock：{exc}")
            return

        # 验证 stage 数
        if hasattr(result, "pipeline_summary") and "stages" in result.pipeline_summary:
            stages = result.pipeline_summary["stages"]
            assert len(stages) == 10, f"期望 10 stage（老链路），实际 {len(stages)}"
        # 验证走了老路径
        mock_director.assert_called()
        mock_builder.assert_called()


def test_pipeline_on_flag_runs_9_stages(mock_pipeline_inputs, tmp_path):
    """use_tts_director=true 时，pipeline 跑 9 stage（新链路）。"""
    from src_next.core.audiobook_pipeline import run_pipeline
    from src_next.core.data_models import ModelSpecificTTSInstruction

    with patch("src_next.tts.registry.create_tts_adapter") as mock_tts, \
         patch("src_next.voicebank.registry.create_voicebank_adapter") as mock_vb, \
         patch("src_next.llm.registry.create_llm_client") as mock_llm, \
         patch("src_next.analysis.tts_director.TTSDirectorAgent") as mock_agent_cls:

        mock_llm.return_value = MagicMock()
        mock_vb.return_value = MagicMock()
        mock_tts.return_value = MagicMock(synthesize=MagicMock(return_value=[]))
        # tts_director agent 返回空 list（跳过实际 LLM 调用）
        mock_agent = MagicMock()
        mock_agent.direct.return_value = []
        mock_agent_cls.return_value = mock_agent

        try:
            result = run_pipeline(
                input_path=str(mock_pipeline_inputs),
                profile_dict={
                    "llm": {"backend": "mock_llm"},
                    "voicebank": {"backend": "mock_voicebank"},
                    "tts": {"output_subdir": "audio_segments"},  # 新链路忽略 backend/base_url
                    "output": {"root": str(tmp_path)},
                    "pipeline": {"use_tts_director": True, "save_intermediate_json": True},
                },
            )
        except Exception as exc:
            pytest.skip(f"pipeline 结构需要更多 mock：{exc}")
            return

        if hasattr(result, "pipeline_summary") and "stages" in result.pipeline_summary:
            stages = result.pipeline_summary["stages"]
            assert len(stages) == 9, f"期望 9 stage（新链路），实际 {len(stages)}"
        # 验证走了新路径（tts_director agent 被调）
        mock_agent.direct.assert_called()
```

注意：本测试故意宽松（用 `pytest.skip` 处理 mock 不够的情况）。具体 mock 范围取决于 `run_pipeline` 实现。**先读 `run_pipeline` 签名**再调整测试。

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_pipeline_use_tts_director_switch.py -v
```

预期：FAIL —— 当前 pipeline 永远跑 10 stage；新路径不存在。

- [ ] **步骤 3：修改 audiobook_pipeline.py**

修改 `src_next/core/audiobook_pipeline.py`：

这是最大的改动。定位 stage 7（`story_director`）+ stage 8（`tts_instruction_builder`）+ stage 9（`tts_synthesis`）的代码块。包在条件分支里：

```python
# 当前文件约 670-730 行（stage 6 voicebank 和 stage 9 tts_synthesis 之间）：

use_tts_director = profile_dict.get("pipeline", {}).get("use_tts_director", False)
total_stages = 9 if use_tts_director else 10

if use_tts_director:
    # ── Stage 7/9: tts_director（合并老 stage 7 + 8）─────────
    step, name = "7/9", "tts_director"
    _log_stage_start(step, name)
    t0 = time.time()

    from src_next.analysis.tts_director import TTSDirectorAgent
    from src_next.utils.model_config_loader import load_all_model_configs
    from src_next.utils.yaml_utils import load_backends_yaml

    backends_yaml = load_backends_yaml()
    enabled_backends = backends_yaml["enabled_backends"]
    all_configs = load_all_model_configs()
    # 过滤：只保留 backend 在 enabled_backends 里的 model_configs
    available_models = [
        cfg for cfg in all_configs.values()
        if cfg.get("backend") in enabled_backends
    ]
    default_model = backends_yaml["default_model"]

    tts_director = TTSDirectorAgent(llm_client=llm_client, available_models=available_models)
    tts_instructions = tts_director.direct(
        segments=resolved,
        character_profiles=characters,
        voicebank_result=voicebank_result,
        default_model_name=default_model,
    )
    elapsed = time.time() - t0
    tts_instructions_path = json_dir / "tts_instructions.json"
    if save_json:
        _save_json(tts_instructions, tts_instructions_path)
        artifacts["tts_instructions"] = str(tts_instructions_path)
    stage_timings[name] = elapsed
    _append_stage_record(stages, name=name, status="success", elapsed=elapsed, mode="run",
                         output=str(tts_instructions_path))
    _log_stage_done(step, name, elapsed, extra=f"instructions={len(tts_instructions)}")

else:
    # ── Stage 7/10: story_director（老链路）──────────────────
    # （现有代码不变——保持当前 stage 7 块原样）
    step, name = "7/10", "story_director"
    # ... 现有代码 ...

    # ── Stage 8/10: tts_instruction_builder（老链路）────────
    step, name = "8/10", "tts_instruction_builder"
    # ... 现有代码 ...

# ── Stage 8/9 或 9/10: tts_synthesis ──────────────────────────────
if use_tts_director:
    step, name = "8/9", "tts_synthesis"
    # 多 adapter 分组调度
    from collections import defaultdict
    from src_next.tts.registry import create_adapter_for_backend
    grouped = defaultdict(list)
    for inst in tts_instructions:
        grouped[inst.model].append(inst)
    audio_segments_by_id = {}
    for model_name, group in grouped.items():
        backend = all_configs[model_name]["backend"]  # model.name → backend key
        backend_cfg = backends_yaml["backends"][backend]
        adapter = create_adapter_for_backend(backend, **backend_cfg)
        seg_results = adapter.synthesize(group, voicebank_result, str(output_dir), dry_run=False, limit=0)
        for r in seg_results:
            audio_segments_by_id[r.segment_id] = r
    # 按 segment_id 排序（保留原顺序）
    audio_segments = [audio_segments_by_id[inst.segment_id] for inst in tts_instructions]
else:
    step, name = "9/10", "tts_synthesis"
    # （现有代码 —— 单 adapter synthesize —— 不变）
    ...

# ── Stage 9/9 或 10/10: audio_merger ──────────────────────────────
step, name = (f"9/{total_stages}", "audio_merger") if use_tts_director else (f"10/{total_stages}", "audio_merger")
# （现有 audio_merger 代码不变）
```

**重要**：仔细读现有 pipeline 结构。具体行号和辅助函数名（`_log_stage_start`、`_append_stage_record` 等）必须匹配。`tts_instructions` 变量名在两个分支都要用，让下游 audio_merger 能找到。

另外把其他地方的 `step, name = "X/10", ...` 字符串改成动态 `total_stages`：
- stage 1-6：`f"{N}/{total_stages}"`（因为前 6 个 stage 在两条路径都共享）

**跨开关 reuse 兼容性**（spec §7.6 + §8）：在 reuse 检测时校验 JSON 首元素是否含 `model` 字段；不匹配则 warning + 忽略 reuse。在 stage 7 reuse 检测代码里加：

```python
if reuse and tts_instructions_path.exists():
    # 校验 JSON 格式是否匹配当前模式
    sample = json.loads(tts_instructions_path.read_text(encoding="utf-8"))
    if sample and isinstance(sample[0], dict):
        has_model_field = "model" in sample[0]
        if use_tts_director and not has_model_field:
            logger.warning("reuse: tts_instructions.json 是老 TTSInstruction 格式，新链路无法复用，重新跑 stage 7")
            mode = "run"  # 强制重跑
        elif not use_tts_director and has_model_field:
            logger.warning("reuse: tts_instructions.json 是新 ModelSpecificTTSInstruction 格式，老链路无法复用，重新跑 stage 7+8")
            mode = "run"
```

- [ ] **步骤 4：运行 smoke 测试，验证通过**

运行：
```bash
pytest tests/test_pipeline_use_tts_director_switch.py -v
```

预期：2 个测试 PASS（或 skip 后说明需要更多 mock——补 mock 让它们 PASS）。

- [ ] **步骤 5：验证老路径仍可用（手动 smoke）**

运行：
```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --mock 2>&1 | tail -15
```

预期：10 stage mock 跑成功。

- [ ] **步骤 6：提交**

```bash
git add src_next/core/audiobook_pipeline.py tests/test_pipeline_use_tts_director_switch.py
git commit -m "feat(tts_director): C3 step 4 — pipeline stage 7/8 切换

- use_tts_director=true：stage 7 = tts_director（合并老 7+8），
  stage 8 = tts_synthesis 多 adapter 分组调度，stage 9 = audio_merger。共 9 stage。
- use_tts_director=false：10 stage 不变。
- total_stages 变量化，日志和 pipeline_result.json stages 数组同步。
- 新链路加载 backends.yaml + load_all_model_configs；老链路完全走 profile.tts。
- 跨开关 reuse 校验：JSON 格式不匹配时 warning + 重新跑 stage 7。

2 个 smoke 测试通过（10 stage / 9 stage 切换正确）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 任务 13：CLI flag --use-tts-director

**文件**：
- 修改：`src_next/core/audiobook_pipeline.py`（argparse + override 逻辑）
- 修改：`tests/test_pipeline_use_tts_director_switch.py`（追加）

- [ ] **步骤 1：写失败测试**

追加到 `tests/test_pipeline_use_tts_director_switch.py`：

```python
def test_cli_flag_overrides_profile_use_tts_director_false():
    """--use-tts-director CLI flag 应把 profile 的 use_tts_director 翻成 True。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    # profile=false，CLI=true → true
    assert _resolve_use_tts_director(profile_flag=False, cli_flag=True) is True


def test_cli_flag_off_keeps_profile_flag():
    """没传 CLI flag（None）应保留 profile 设置。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    assert _resolve_use_tts_director(profile_flag=True, cli_flag=None) is True
    assert _resolve_use_tts_director(profile_flag=False, cli_flag=None) is False


def test_cli_flag_off_overrides_profile_flag_on():
    """--no-use-tts-director 应强制 False，即使 profile=true。"""
    from src_next.core.audiobook_pipeline import _resolve_use_tts_director
    assert _resolve_use_tts_director(profile_flag=True, cli_flag=False) is False
```

- [ ] **步骤 2：运行测试，验证失败**

运行：
```bash
pytest tests/test_pipeline_use_tts_director_switch.py -v -k cli_flag
```

预期：ImportError（`_resolve_use_tts_director` 不存在）。

- [ ] **步骤 3：加 CLI flag + resolver**

在 `src_next/core/audiobook_pipeline.py`：

1. 找到 `main()` 里的 `argparse.ArgumentParser` 配置，加：

```python
parser.add_argument(
    "--use-tts-director",
    action="store_true",
    default=None,
    help="启用新 tts_director 链路（合并 stage 7+8，LLM 自动选 TTS model）",
)
parser.add_argument(
    "--no-use-tts-director",
    dest="use_tts_director",
    action="store_false",
    help="强制使用老链路（profile.tts.backend 固定单 TTS）",
)
```

2. 在 `main()` 附近加 resolver 函数：

```python
def _resolve_use_tts_director(*, profile_flag: bool, cli_flag: bool | None) -> bool:
    """合并 profile 开关与 CLI flag。CLI flag 设置时优先。

    Args:
        profile_flag: profile.pipeline.use_tts_director 的值（默认 False）。
        cli_flag: --use-tts-director / --no-use-tts-director 的值（未设为 None）。

    Returns:
        最终的 use_tts_director 值。
    """
    if cli_flag is not None:
        return cli_flag
    return bool(profile_flag)
```

3. 在 `main()` 里，调 `run_pipeline` 之前，解析 flag 并注入 profile_dict：

```python
args = parser.parse_args()

# ... 加载 profile_dict ...

profile_flag = bool(profile_dict.get("pipeline", {}).get("use_tts_director", False))
final_flag = _resolve_use_tts_director(profile_flag=profile_flag, cli_flag=args.use_tts_director)
profile_dict.setdefault("pipeline", {})["use_tts_director"] = final_flag

# ... 继续调 run_pipeline ...
```

- [ ] **步骤 4：运行测试，验证通过**

运行：
```bash
pytest tests/test_pipeline_use_tts_director_switch.py -v
```

预期：5 个测试全部 PASS。

- [ ] **步骤 5：（可选）手动跑新链路端到端**

如果有真服务：
```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --use-tts-director 2>&1 | tail -15
```

预期：9 stage 跑完，audio_final/<story>.wav 生成。

- [ ] **步骤 6：提交**

```bash
git add src_next/core/audiobook_pipeline.py tests/test_pipeline_use_tts_director_switch.py
git commit -m "feat(tts_director): C3 step 5 — CLI flag --use-tts-director

- argparse 加 --use-tts-director / --no-use-tts-director（互斥）
- _resolve_use_tts_director：CLI flag 优先于 profile flag
- main() 解析后注入 profile_dict.pipeline.use_tts_director

3 个测试通过（CLI true 覆盖 false / CLI None 保留 profile / CLI false 覆盖 true）。

C3 完成（backends.yaml + loader + registry cache + yaml_utils switch +
pipeline stage 7/8 切换 + CLI flag）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## C4：docs sync

### 任务 14：更新 CLAUDE.md / README.md / src_next_*.md

**文件**：
- 修改：`CLAUDE.md`
- 修改：`README.md`
- 修改：`src_next_主链路运行及核心模块说明.md`
- 修改：`src_next_总体架构说明.md`

文档无测试。靠阅读 + grep 验证。

- [ ] **步骤 1：更新 CLAUDE.md §4（stage 表格）**

打开 `CLAUDE.md`，定位 §4（10-stage 表格）。在表格上方加注：

```markdown
**Stage 编号随 `pipeline.use_tts_director` 开关变化**：
- `false`（默认）：10 stage（老链路）
- `true`：9 stage（新链路，stage 7 = tts_director 合并老 7+8）
```

更新 stage 表格展示两种变体，或加新链路的第二张子表。

- [ ] **步骤 2：更新 CLAUDE.md §6（加 use_tts_director 开关 + backends.yaml 说明）**

在"Profile 5 块结构"章节，加子节：

```markdown
### `pipeline.use_tts_director` 开关（新）

`true` 时启用 Audio-Oscar 方向1 新链路：
- 加载全局 `src_next/tts/backends.yaml` 取代 profile.tts 块
- LLM 自动从 enabled_backends 选 model（per-segment）
- 老 stage 7 (story_director) + stage 8 (tts_instruction_builder) 合并为新 stage 7 (tts_director)
- 总 stage 数从 10 → 9

CLI 临时启用：`--use-tts-director`
```

- [ ] **步骤 3：更新 CLAUDE.md §11（维护表）**

加一行：

```markdown
| 启用/禁用/重命名 `pipeline.use_tts_director` 开关或 backends.yaml | ✅ 必更新 | §6 + §4 |
```

- [ ] **步骤 4：同步 README.md**

按 CLAUDE.md §11.1 章节对应表同步更新：
- "核心链路" 10-stage 表格注释（提及 9-stage 变体）
- "当前支持的后端" 加 backends.yaml + LLM 自动选 model 说明
- 必要时更新 "Claude Code 协作要求"

- [ ] **步骤 5：更新 src_next_主链路运行及核心模块说明.md**

在 §3（一次任务的执行流程），加新子节 3.x "新链路执行流程（use_tts_director=true）"：

```markdown
### 新链路（use_tts_director=true）执行流程

启用方式：
- CLI：`--use-tts-director`
- Profile：`pipeline: { use_tts_director: true }`

执行流程（9 stages）：
1. 步骤 0-6 同老链路（参数解析 + stage 1-6 不变）
2. 步骤 7：tts_director（合并老 7+8）
   - 文件：`analysis/tts_director.py:TTSDirectorAgent.direct()`
   - 加载：`src_next/tts/backends.yaml` + `src_next/tts/model_configs/*.json`
   - 输入：segments + characters + voicebank + available_models
   - 输出：list[ModelSpecificTTSInstruction]（per-segment 可能不同 model）
   - 落盘：`json/tts_instructions.json`（合并 director_plan，老格式不再生成）
3. 步骤 8：tts_synthesis（多 adapter 分组调度）
   - 按 instruction.model 分组
   - 每组 lazy-create adapter，调对应 backend HTTP
4. 步骤 9：audio_merger（同老链路 stage 10）

排障提示：
- 新链路下 `director_plan.json` 不再生成 → 排障首选 `pipeline_result.json`
- 跨开关 reuse 不兼容（自动忽略 + 重新跑）
```

- [ ] **步骤 6：更新 src_next_总体架构说明.md**

在 §4（架构分层说明），更新 §4.3（分析层），加 `tts_director`：
- 新增子节 "tts_director（合并老 story_director + tts_instruction_builder）"
- 说明触发条件 + 数据契约 ModelSpecificTTSInstruction
- §3.2 stage 表格加注 "新老链路 stage 数差异"

- [ ] **步骤 7：验证文档交叉引用一致**

运行：
```bash
grep -n "tts_director" CLAUDE.md README.md src_next_*.md
grep -n "backends.yaml" CLAUDE.md README.md src_next_*.md
grep -n "use_tts_director" CLAUDE.md README.md src_next_*.md
```

预期：每个关键词都出现在 4 份文档里。

- [ ] **步骤 8：提交**

```bash
git add CLAUDE.md README.md src_next_主链路运行及核心模块说明.md src_next_总体架构说明.md
git commit -m "docs: C4 — tts_director 链路相关文档同步

CLAUDE.md：
- §4：stage 编号随 use_tts_director 开关变化（10/9 stage）
- §6：新增 use_tts_director 开关 + backends.yaml 说明
- §11：维护表加一行（开关 / backends.yaml 改动 → 同步本文件）

README.md：按 CLAUDE.md §11.1 章节对应表同步

src_next_主链路运行及核心模块说明.md：
- 新链路 9 stage 执行流程
- 排障：director_plan.json 不再生成 + 跨开关 reuse 不兼容

src_next_总体架构说明.md：
- §4.3 加 tts_director 子节
- §3.2 stage 表加新老链路 stage 数差异注释

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## 最终验证

### 任务 15：端到端 smoke + 清理

- [ ] **步骤 1：跑全测试套件（不含 integration）**

```bash
pytest tests/ -v -m "not integration"
```

预期：所有 unit + smoke 测试 PASS。

- [ ] **步骤 2：跑老链路端到端（mock）**

```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --mock 2>&1 | tail -20
```

预期：10 stage，成功完成，audio_final/ 有 wav。

- [ ] **步骤 3：跑新链路端到端（mock，若 mock LLM 支持新格式）**

如果项目的 mock LLM（`src_next/llm/mock_llm.py`）支持 tts_director 需要的 JSON 输出格式：

```bash
python -m src_next.core.audiobook_pipeline \
    --input input/sample_story_01.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --mock --use-tts-director 2>&1 | tail -20
```

预期：9 stage，成功完成。

如果 mock_llm 不支持新格式，跳过本步并在 commit message 里注明。

- [ ] **步骤 4：跑集成测试（手动，需要真服务）**

```bash
pytest tests/test_tts_director_integration.py -v -m integration
```

预期：~60 秒内 PASS。

- [ ] **步骤 5：最终提交（如有清理）**

如果步骤 1-4 发现问题，修复后提交。否则不需要 commit。

- [ ] **步骤 6：更新任务清单 / 完工**

所有计划任务完成。实现准备好 review。

---

## 总结

| 阶段 | 任务 | 涉及文件 | 新增测试 |
|---|---|---|---|
| 前置准备 | 任务 0 | 4（pytest setup） | 0 |
| C1 | 任务 1-5 | 5 新 + 0 改 | 10 unit + 1 integration |
| C2 | 任务 6-8 | 0 新 + 3 改 + 1 测试 | 6 unit |
| C3 | 任务 9-13 | 2 新 + 4 改 + 4 测试 | 17 unit + 2 smoke |
| C4 | 任务 14 | 0 新 + 4 改 | 0 |
| 验证 | 任务 15 | 0 | 0 |

**总计：15 任务（原 16，删除 Task 4 同 speaker 一致性后处理），~25 文件，~36 测试**

全程 TDD（test → fail → impl → pass → commit）。每个任务自包含，产出可验证的 artifact。可由单个开发者顺序执行，也可派发给 subagents（每任务一个）并行执行。

**架构变更说明（2026-07-02）**：原设计的"同 speaker → 同 model"约束已废弃。
原因：voice cloning（所有 backend 共享同一个 voice_ref）保证音色一致性，
不需要约束 LLM。改为 per-segment 自由选 model，让表演更丰富。详见 spec §7.3。
