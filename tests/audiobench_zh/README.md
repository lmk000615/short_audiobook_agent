# Audiobench zh v1

> 中文短篇故事测试集，用于压测 `src_next/` 有声书生成链路。
> 不是普通故事，而是带"埋点"的 adversarial 样例。

## 是什么

30 条精心设计的中文短篇故事（150–500 字/条），按 8 类配比，**专门用于压测**：

- 文本分段（segment_builder）
- 说话人识别（quote_classifier / story_resolver）
- 角色档案一致性（character_analyzer）
- 导演指令合成（story_director / tts_director）
- 音效规划（未来 stage）

每条样例的"测试目的"和"埋点陷阱"写在同名 `.meta.yaml` 里。

## 配比表

| 类别 | 数量 | 主要压测能力点 |
|---|---|---|
| `basic_children` | 4 | 基础回归：引号嵌套 / 说话人后置 / 拟声词引号陷阱 / 省略说话人 |
| `multi_role_dialog` | 4 | 多角色连续对白，部分轮次省略说话人 |
| `speaker_hard` | 4 | 说话人归属困难：倒装 / 引号嵌套 / 长旁白孤对白 / 心理 vs 对白 |
| `emotion_shift` | 4 | 句内情绪转折（A→B 明显切换） |
| `strong_emotion` | 4 | 强情绪对白（暴怒/大哭/惊恐/狂喜） |
| `long_memory` | 3 | 长文本（450+ 字）角色一致性 |
| `tts_frontend` | 3 | TTS 前端复杂文本（多音字/数字/缩写/邮箱 URL） |
| `sfx_trigger` | 4 | 段内/段间音效触发（自然语言埋声音事件） |
| **总计** | **30** | |

## 目录结构

```
tests/audiobench_zh/
├── cases/
│   ├── basic_children_01.txt        # 故事正文
│   ├── basic_children_01.meta.yaml  # 元数据
│   ├── ...
│   └── sfx_trigger_04.meta.yaml
├── index.yaml                        # 30 条索引
├── README.md                         # 本文件
└── _check_integrity.py               # 完整性校验脚本
```

## 字段定义（meta.yaml）

每条 `.meta.yaml` 含 9 个字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 与文件名一致，如 `basic_children_01` |
| `category` | str | 8 类之一 |
| `test_purpose` | str | 一句话说明本条要压测的能力点 |
| `expected_speaker_count` | int | 期望 speaker 数（含旁白） |
| `expected_challenges` | list[str] | 埋点陷阱清单（2-6 条） |
| `recommended_profile` | str | 推荐 profile yaml |
| `expected_difficulty` | int | 1-5，5 = 最难 |
| `char_count` | int | 实际字数（不含换行） |
| `tags` | list[str] | 自由标签 |

## 引号字符合规性

所有样例**只使用以下引号字符**（与 `src_next/core/segment_builder.py` 切分逻辑一致）：

- 智能双引号：`""`
- 直角引号：`「」`
- 书名号：`《》`（不被切分）
- ASCII 单引号：`'`（保留在文本中，不被切分）

**不使用 ASCII 双引号 `"`** 作为对白定界。

## 单条跑测命令

### 离线 mock 跑测（不依赖服务）

```bash
python -m src_next.core.audiobook_pipeline \
    --input tests/audiobench_zh/cases/basic_children_01.txt \
    --mock
```

### 真实 profile 跑测（黄区才能跑）

```bash
python -m src_next.core.audiobook_pipeline \
    --input tests/audiobench_zh/cases/speaker_hard_02.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml
```

### 新链路（use_tts_director）

```bash
python -m src_next.core.audiobook_pipeline \
    --input tests/audiobench_zh/cases/long_memory_03.txt \
    --profile src_next/profiles/yellow_qwen3http_cosyvoicehttp.yaml \
    --use-tts-director
```

## 完整性校验

```bash
python tests/audiobench_zh/_check_integrity.py
```

期望输出 `ALL_PASS` + 8 类计数 + 总数 30。

## 验证层级

| 层级 | 验证手段 | 蓝区/黄区 |
|---|---|---|
| L1 字面 | 字数 150-500 / yaml 字段齐全 / 引号合规 | 蓝区 |
| L2 切分 | 直接调 segment_builder，看 narration/dialogue 结构 | 蓝区 |
| L3 mock 端到端 | mock pipeline 跑通，但 quote_classifier 走 fallback | 蓝区（需 PyYAML） |
| L4 真实 profile | LLM/TTS 真实响应，验证埋点效果 | **黄区** |

## 已知问题

- **当前蓝区环境缺 PyYAML**，L3/L4 验证需在黄区跑。
- **v1 不含 ground truth**（expected_speakers / expected_emotion_segments / expected_sfx_events），无法自动算分。这是 v2 工作。
- **v1 不含 benchmark runner**（自动跑 30 条 + 算分 + 出报告）。这是 v2 工作。

## v2 路线（未实现）

1. benchmark runner：读 `index.yaml` → 按 category 跑 → 写报告
2. ground truth：人工标注 expected_speakers / emotions / sfx_events
3. LLM-as-judge：用 expected_challenges 当检查清单，自动判分
4. 跨 backend 对比：同一样例用不同 profile 跑，对比 TTS 输出质量

## 维护

- 新增样例：在 `cases/` 加 `<id>.txt` + `<id>.meta.yaml`，更新 `index.yaml`
- 删除样例：从 `cases/` 删文件，更新 `index.yaml`
- 改 schema：所有 30 条 meta.yaml 必须同步更新
