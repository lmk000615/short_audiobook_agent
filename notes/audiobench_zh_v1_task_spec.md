# Task: 构建 Audiobench zh v1 中文短篇故事测试集（30 条）

> 本文件是一份 TASK_SPEC，由 `/claude-instruction-builder` 生成。
> 使用方式：把本文件完整内容复制粘贴给一个新的 Claude Code 会话即可执行。

---

## 1. Background

`short_audiobook_agent` 的 `src_next/` 链路目前缺乏统一的中文测试集来回归测试文本分段、说话人识别、角色档案、导演指令合成、音效规划等能力。现有 `input/` 目录只有 5 篇样例（小红帽、桂花雨、将相和、不懂就要问、sample_story_01/02），无法覆盖"说话人后置 / 句内情绪转折 / TTS 前端复杂文本 / 音效触发"等边角场景。

需要构建一份 **Audiobench zh v1**：30 条精心设计的中文短篇故事（150–500 字/条），按 8 类配比，**专门用于压测有声书生成链路**——不是普通故事，而是带"埋点"的 adversarial 样例。

存储采用 **`tests/audiobench_zh/cases/<id>.txt` + `<id>.meta.yaml`** 双文件模式，元数据深度选 **中等**（含 test_purpose / expected_challenges / expected_speaker_count / recommended_profile / expected_difficulty），音效事件采用 **自然语言埋点**（不写 inline 标记）。

## 2. Goal

交付一个位于 `tests/audiobench_zh/` 的完整测试集：

- 30 条 `.txt`（纯故事正文，150–500 字/条）
- 30 条同名 `.meta.yaml`（含 8 个固定字段）
- 1 份 `index.yaml`（30 条索引：id / category / test_purpose）
- 1 份 `README.md`（说明配比、用法、字段定义）

交付后系统状态：可以用 `python -m src_next.core.audiobook_pipeline --input tests/audiobench_zh/cases/<id>.txt --profile <yaml>` 单条跑测；可以用 `pytest tests/audiobench_zh/test_integrity.py` 校验测试集自身完整性。

## 3. Non-goals

- **不**实现 benchmark runner（自动跑 30 条 + 算分）。仅交付数据，runner 是 v2。
- **不**生成 ground truth（expected_speakers[] / expected_emotion_segments[] / expected_sfx_events[]）。这些是 v2 工作。
- **不**修改任何 `src_next/` 业务代码、`src/` 旧代码、`requirements.txt`、profile yaml。
- **不**调用真实 LLM / TTS 服务跑通 30 条（成本高，留给执行方按需跑）。
- **不**新建 loader.py / dataset 类。仅 txt + yaml + 索引。
- **不**翻译为英文版（zh v1 限定）。
- **不**写 inline 标记（如 `[SFX:knock]`）——音效靠自然语言埋点。

## 4. Relevant Files

- `tests/audiobench_zh/` —— **新建目录**，全部产物落在这里。
- `input/sample_story_01.txt` —— 参考现有样例的写作风格（中文短篇、儿童故事口吻）。
- `input/桂花雨.txt` / `input/将相和.txt` —— 参考多角色叙事与对白穿插的中文写法。
- `src_next/core/segment_builder.py` —— 理解 segment 如何切分，才能写出"故意刁难"的样例（不修改，只读）。
- `src_next/analysis/quote_classifier.py` —— 理解引号分类逻辑，才能写"speaker 归属困难"类（不修改，只读）。
- `src_next/analysis/character_analyzer.py` —— 理解角色档案如何提取，才能写"长文本记忆"类（不修改，只读）。
- `src_next/analysis/story_director.py` / `src_next/analysis/tts_director.py` —— 理解导演指令生成的输入，才能写"句内情绪转折" / "强情绪对白"类（不修改，只读）。
- `CLAUDE.md` §10 验证清单 —— 验收命令格式参考（不修改）。

## 5. Required Reading Order

1. 先读 `CLAUDE.md` §3 §4 —— 明确 10 stage 主链路在每个 stage 做什么，决定测试样例"埋点"放在哪一层。
2. 读 `input/sample_story_01.txt` + 任一 `input/小红帽.txt` —— 校准中文叙事风格，避免样例过于书面化。
3. 读 `src_next/core/segment_builder.py` —— 理解一个 segment 只有一个 speaker 的结构保证，避免写出"无解"样例。
4. 读 `src_next/analysis/quote_classifier.py` —— 理解引号分类何时困难，针对 speaker_attribution_hard 类设计陷阱。
5. 读 `src_next/analysis/story_director.py` 中的 DirectorInstruction 11 字段 —— 句内情绪转折 / 强情绪对白类要把这 11 字段都覆盖到。
6. 跑一遍 `python -m src_next.core.audiobook_pipeline --input input/sample_story_01.txt --mock` 看产物结构，了解 meta.yaml 中 recommended_profile 该填什么。

## 6. Implementation Plan

> 强制要求：每一步动手**生成样例文件之前**，必须先复述"本步要生成哪几条、各自的测试目的、埋点是什么"，等用户确认后再写入文件。

### Step 0: 准备工作

- **Understand**：读 §5 列出的文件，特别是 segment_builder 的切分规则。
- **Plan**：复述对 8 个类别的理解 + 给出 ID 命名规则（见下方）+ 给出 meta.yaml 完整 schema 草案，请用户确认。
- **Modify**：创建空目录 `tests/audiobench_zh/` 和 `tests/audiobench_zh/cases/`。
- **Verify**：`ls tests/audiobench_zh/` 应能看到 `cases/` 子目录。

**ID 命名规则**（每类前缀 + 两位序号，便于按文件名排序）：

| 类别 | 前缀 | 数量 | ID 范围 |
|---|---|---|---|
| 基础儿童故事 | `basic_children_` | 4 | `basic_children_01` ~ `04` |
| 多角色连续对白 | `multi_role_dialog_` | 4 | `multi_role_dialog_01` ~ `04` |
| speaker 归属困难 | `speaker_hard_` | 4 | `speaker_hard_01` ~ `04` |
| 句内情绪转折 | `emotion_shift_` | 4 | `emotion_shift_01` ~ `04` |
| 强情绪对白 | `strong_emotion_` | 4 | `strong_emotion_01` ~ `04` |
| 长文本记忆 | `long_memory_` | 3 | `long_memory_01` ~ `03` |
| TTS 前端复杂文本 | `tts_frontend_` | 3 | `tts_frontend_01` ~ `03` |
| 段内/段间音效触发 | `sfx_trigger_` | 4 | `sfx_trigger_01` ~ `04` |

**meta.yaml schema（每条样例必填 8 字段）**：

```yaml
id: basic_children_01
category: basic_children
test_purpose: "一句话说明本条要压测的能力点。"
expected_speaker_count: 3              # 整数，含旁白
expected_challenges:                   # 列表，2-5 条
  - "陷阱 1（一句话）"
  - "陷阱 2（一句话）"
recommended_profile: yellow_qwen3http_cosyvoicehttp.yaml
expected_difficulty: 2                 # 1-5
char_count: 280                        # 实际字数，必须 150-500
tags:                                  # 自由标签
  - "儿童故事"
  - "省略主语"
```

### Step 1: 基础儿童故事（4 条）

- **Understand**：这一类是 baseline，要求"看似简单但暗藏 1-2 个非平凡点"，作为链路最基础回归用例。
- **Plan**：复述 4 条的故事大纲、各自埋点（如：引号嵌套 / 说话人后置 / 旁白中插入拟声词），请用户确认后再写。
- **Modify**：写入 `cases/basic_children_01.txt` ~ `04.txt` 和对应 `.meta.yaml`。
- **Verify**：
  - 每条 `wc -m cases/basic_children_0*.txt` 字数在 150-500
  - 每条 `.meta.yaml` 含 8 字段
  - 任挑 1 条喂给 `python -m src_next.core.audiobook_pipeline --input tests/audiobench_zh/cases/basic_children_01.txt --mock`，应能跑出 segments_raw.json 不报错

### Step 2: 多角色连续对白（4 条）

- **Understand**：≥3 个角色、连续 3+ 轮对白、说话人必须靠上下文判断（部分省略"他说/道"）。
- **Plan**：每条复述出场角色、对白轮数、谁的台词不写明说话人，确认后写。
- **Modify**：写入 `cases/multi_role_dialog_01.txt` ~ `04.txt` + meta。
- **Verify**：同 Step 1 三项 + 额外检查"每条至少出现 3 个不同说话人"。

### Step 3: speaker 归属困难（4 条）

- **Understand**：故意刁难 quote_classifier。陷阱可包括：
  - 说话人后置（"……"他低头说。）
  - 倒装（李明笑了笑：……）
  - 引号嵌套（"他说'你好'的时候）
  - 长段旁白后突然出现一台词无主语
  - 同一引号内两人交替
- **Plan**：每条复述埋的陷阱类型 + 期望 quote_classifier 大概率会错的点。
- **Modify**：写入 `cases/speaker_hard_01.txt` ~ `04.txt` + meta。
- **Verify**：每条 meta.yaml 的 expected_challenges 至少列出 2 个 trap。

### Step 4: 句内情绪转折（4 条）

- **Understand**：**单段单引号内**情绪明显切换（开心→难过 / 愤怒→委屈 / 害怕→坚定）。压测 director 的 emotion 字段稳定性。
- **Plan**：每条复述情绪路径 A→B、转折触发词。
- **Modify**：写入 `cases/emotion_shift_01.txt` ~ `04.txt` + meta。
- **Verify**：每条至少 1 句对白含明确情绪转折（人工肉眼）。

### Step 5: 强情绪对白（4 条）

- **Understand**：**整段单一强情绪**（暴怒/大哭/惊恐/狂喜）。压测 emotion_intensity + volume + pace 三字段。
- **Plan**：每条选定主情绪 + 标点策略（"！！！" "……" 等）。
- **Modify**：写入 `cases/strong_emotion_01.txt` ~ `04.txt` + meta。
- **Verify**：每条至少出现 2 处情绪标点（！、……、？！）。

### Step 6: 长文本记忆（3 条）

- **Understand**：**字数逼近上限**（450-500），同一角色在 3+ 段中保持性格/语气一致。压测 character_analyzer 的角色档案稳定性。
- **Plan**：每条选定主角 + 设定一致性策略（口癖、用词偏好、态度），分段不少于 4 段。
- **Modify**：写入 `cases/long_memory_01.txt` ~ `03.txt` + meta。
- **Verify**：每条 `wc -m` ≥ 400；分段（双换行分段）≥ 4。

### Step 7: TTS 前端复杂文本（3 条）

- **Understand**：埋入多音字（行/还/重/朝）、数字（"7 月 15 日 8 点 30 分"）、英文缩写（"AI"/"CPU"/"APP"）、单位（"3 公斤"/"100 米"）、特殊符号（%、@、~）。压测 TTS 前端 g2p / 数字读法。
- **Plan**：每条列出埋的 5+ 个前端难点。
- **Modify**：写入 `cases/tts_frontend_01.txt` ~ `03.txt` + meta。
- **Verify**：每条至少出现 5 个前端难点（人工核对）。

### Step 8: 段内/段间音效触发（4 条）

- **Understand**：**自然语言**埋入声音事件（不写 inline 标记）：敲门、脚步、风声、雨声、树叶响、杯子落地、门被推开、动物叫等。压测音效规划能力（v1 链路未必有，留给未来 stage）。
- **Plan**：每条列出 3-5 个埋入的声音事件、对应触发词。
- **Modify**：写入 `cases/sfx_trigger_01.txt` ~ `04.txt` + meta（meta 的 expected_challenges 字段列出埋的声音事件）。
- **Verify**：每条至少出现 3 个声音事件描述（人工核对）。

### Step 9: 索引与说明文档

- **Understand**：把 30 条整合成可查询的索引 + 给后人看的说明文档。
- **Plan**：复述 index.yaml schema（id/category/test_purpose/char_count/difficulty）和 README.md 章节。
- **Modify**：
  - 写 `tests/audiobench_zh/index.yaml`，列出 30 条
  - 写 `tests/audiobench_zh/README.md`，含：分类说明 / 配比表 / 字段定义 / 单条跑测命令 / mock 跑测命令
- **Verify**：`yaml.safe_load(open('tests/audiobench_zh/index.yaml'))` 不报错；README.md 渲染正常。

### Step 10: 完整性校验脚本（一次性自检，不留 CI）

- **Understand**：写一个临时校验脚本，确认全部 30 条满足硬约束。
- **Plan**：在 `tests/audiobench_zh/_check_integrity.py` 写：遍历 cases/，校验 txt+yaml 配对、字数 150-500、8 字段齐全、id 与文件名一致、配比正确。
- **Modify**：写入脚本并运行。
- **Verify**：`python tests/audiobench_zh/_check_integrity.py` 输出 `ALL_PASS` 且打印 30 条 id。脚本本身**不**作为 pytest fixture，是 v1 的一次性工具（用户可在 v2 决定是否保留）。

### Step 11: 同步 CLAUDE.md / README.md（按需）

- **Understand**：本任务**新增了测试集目录**，按 CLAUDE.md §11 维护规则，需要同步文档。
- **Plan**：
  - 在 `CLAUDE.md` §10 验证清单末尾加一行："6. Audiobench zh 测试集完整性：`python tests/audiobench_zh/_check_integrity.py`"
  - 在 `CLAUDE.md` §2 仓库结构表加一行：`tests/audiobench_zh/  ← 中文测试集（30 条 adversarial 样例）`
  - 同步 README.md 对应章节（按 §11.1）
- **Modify**：编辑 CLAUDE.md + README.md（仅文档，不改正文）。
- **Verify**：`git diff CLAUDE.md README.md` 只动了对应章节。

## 7. Modification Boundaries

**可以改**：
- `tests/audiobench_zh/`（新建目录及全部内容）
- `CLAUDE.md`（仅 §2 表格 + §10 验证清单，新增条目）
- `README.md`（仅对应章节同步）

**不能改**：
- `src_next/**`（任何业务代码）
- `src/**`（旧链路）
- `input/**`（现有样例）
- `config/**` / `profiles/**`
- `requirements.txt` / `pyproject.toml`
- 任何 `.github/` workflow
- `run.py`

**禁止行为**：
- 不调用真实 LLM/TTS 服务（30 条全跑成本高）。
- 不使用 `--no-verify` 跳过 git hooks。
- 不创建 `loader.py` / `dataset.py` 等"看起来将来会有用"的文件——v1 只要数据，不要代码。
- 不在样例文本里写 inline 标签（`[SFX:...]` 等）。
- 不在 meta.yaml 写未在 §6 Step 0 schema 里定义的字段。

## 8. Verification

**每步即时验证**（每个 Step 完成后跑）：
```bash
ls tests/audiobench_zh/cases/ | wc -l        # 文件总数（应有 step_n*2 个）
python -c "import yaml; yaml.safe_load(open('tests/audiobench_zh/cases/<id>.meta.yaml'))"
```

**整体最终验证**（Step 10 跑完后）：

1. **配比正确**：
```bash
python tests/audiobench_zh/_check_integrity.py
# 期望输出（节选）：
# basic_children: 4
# multi_role_dialog: 4
# speaker_hard: 4
# emotion_shift: 4
# strong_emotion: 4
# long_memory: 3
# tts_frontend: 3
# sfx_trigger: 4
# TOTAL: 30
# ALL_PASS
```

2. **mock pipeline 跑通**（随机抽 3 条，不依赖真实服务）：
```bash
for id in basic_children_01 speaker_hard_01 sfx_trigger_01; do
    python -m src_next.core.audiobook_pipeline \
        --input tests/audiobench_zh/cases/${id}.txt \
        --mock \
        --output-root output-src-next/audiobench_smoke
done
# 期望：每条都生成 audio_final/<id>.wav，pipeline_result.json 中 stop_stage = 10/9 不报错
```

3. **字数硬约束**：
```bash
python -c "
import os
for f in sorted(os.listdir('tests/audiobench_zh/cases')):
    if f.endswith('.txt'):
        n = len(open(f'tests/audiobench_zh/cases/{f}', encoding='utf-8').read())
        assert 150 <= n <= 500, f'{f}: {n} out of range'
print('CHAR_COUNT_OK')
"
```

4. **yaml 字段完整性**：
```bash
python -c "
import os, yaml
required = {'id','category','test_purpose','expected_speaker_count','expected_challenges','recommended_profile','expected_difficulty','char_count','tags'}
for f in sorted(os.listdir('tests/audiobench_zh/cases')):
    if f.endswith('.yaml'):
        d = yaml.safe_load(open(f'tests/audiobench_zh/cases/{f}', encoding='utf-8'))
        miss = required - set(d.keys())
        assert not miss, f'{f} missing: {miss}'
print('YAML_FIELDS_OK')
"
```

**人工抽检**（必须做，不能跳）：
- 至少 5 条随机 txt 肉眼通读，确认"不是平铺直叙"，确实有埋点。
- 全部 8 类各抽 1 条 meta.yaml 检查 test_purpose 写得是否具体（不能是"测试 TTS"这种空话）。

## 9. Failure Handling

- **`yaml.safe_load` 报错**：先看具体行号，**不要**重写整个文件，定位是引号 / 缩进 / 中文标点混入。yaml 文件必须用 ASCII 标点（`:` 而非 `：`）。
- **`wc -m` 字数超 500**：**不要**为了凑字数硬拆段，先看故事是否有冗余旁白可删；删不动则调整结尾收束。
- **mock pipeline 报错**（如 segment_builder 异常）：**先分类**——
  - **代码问题**（链路 bug）→ 不要修链路，把 case 留作已知问题，记在 README.md 的 Known issues。
  - **样例问题**（如全角空格 / 异常标点）→ 修样例。
  - **配置问题**（output-root 路径）→ 检查 CLI 参数。
- **某类样例写作时发现"凑不出 4 条不同陷阱"**：停下汇报，不要硬塞。某些类别可能 3 条已穷尽陷阱，可以建议调整配比。
- **批量写文件卡住**（如 30 条一次性写不完）：**不要**写半成品 yaml（缺字段），每条完整写完再写下一条。卡住超过 3 条就停下汇报当前进度。
- **CLAUDE.md / README.md 同步时发现其他过期内容**：**不要**顺手修——本次任务范围窄，过期内容另开 issue。仅同步本任务直接相关的章节。

## 10. Final Report Format

完成后汇报必须包含：

1. **修改清单**（逐文件）：
   - 新增：`tests/audiobench_zh/cases/*.txt` × 30
   - 新增：`tests/audiobench_zh/cases/*.meta.yaml` × 30
   - 新增：`tests/audiobench_zh/index.yaml`
   - 新增：`tests/audiobench_zh/README.md`
   - 新增：`tests/audiobench_zh/_check_integrity.py`
   - 修改：`CLAUDE.md`（§2 表格 + §10 验证清单）
   - 修改：`README.md`（对应章节）

2. **每个文件为什么这样写**（30 条 txt 至少按类别给共性动机，meta.yaml 给 schema 决策理由）。

3. **验证证据**：
   - 跑了哪几条命令（逐条列出实际命令）
   - 每条命令的实际输出摘要（PASS/FAIL + 关键数字）
   - mock pipeline 抽测结果（哪 3 条 / 各自的 stop_stage / 是否生成 wav）

4. **配比验证**：8 类的实际数量 + 总数 30。

5. **遗留问题与后续建议**：
   - 哪些样例可能在真实 profile 下报错
   - v2 是否需要补 ground truth
   - 是否需要写 loader.py / benchmark runner
