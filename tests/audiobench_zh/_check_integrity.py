"""Audiobench zh v1 完整性校验脚本。

校验内容：
1. cases/ 目录下 .txt 与 .meta.yaml 一一配对
2. 每条 .txt 字数在 150-500 之间
3. 每条 .meta.yaml 含 9 个必填字段
4. meta.yaml 的 id 与文件名一致
5. meta.yaml 的 category 在 8 类白名单中
6. meta.yaml 的 char_count 与实际字数一致
7. 8 类配比正确（总数 30）

依赖：
- 优先使用 PyYAML（推荐）
- PyYAML 不可用时降级到内置简化解析（仅支持本测试集使用的 yaml 子集）

用法：
    python tests/audiobench_zh/_check_integrity.py

退出码：
- 0: ALL_PASS
- 1: 有错误
"""

import os
import re
import sys

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases')

EXPECTED_CATEGORIES = {
    'basic_children': 4,
    'multi_role_dialog': 4,
    'speaker_hard': 4,
    'emotion_shift': 4,
    'strong_emotion': 4,
    'long_memory': 3,
    'tts_frontend': 3,
    'sfx_trigger': 4,
}

REQUIRED_FIELDS = (
    'id',
    'category',
    'test_purpose',
    'expected_speaker_count',
    'expected_challenges',
    'recommended_profile',
    'expected_difficulty',
    'char_count',
    'tags',
)


def parse_yaml(text):
    """优先用 PyYAML；不可用则降级到简化解析。"""
    try:
        import yaml
        return yaml.safe_load(text), 'pyyaml'
    except ImportError:
        return _parse_yaml_simple(text), 'simple'


def _parse_yaml_simple(text):
    """简化 yaml 解析，仅支持本测试集使用的结构。

    支持：
    - key: value（标量，自动去引号）
    - key: 后跟 list（- item 形式）
    - # 注释行跳过
    - 数字字段转 int
    不支持：嵌套 dict、多行字符串、anchor/alias。
    """
    result = {}
    current_list_key = None
    current_list = []

    def flush():
        nonlocal current_list_key, current_list
        if current_list_key is not None:
            result[current_list_key] = list(current_list)
            current_list_key = None
            current_list = []

    for raw in text.split('\n'):
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith('#'):
            continue

        # 列表项: ^  - "..."
        m = re.match(r'^\s+-\s+(.+?)\s*$', line)
        if m and current_list_key is not None:
            val = m.group(1)
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            current_list.append(val)
            continue

        # key: value
        m = re.match(r'^([a-z_]+):\s*(.*)$', line)
        if m:
            flush()
            key, value = m.group(1), m.group(2).strip()
            if value == '':
                current_list_key = key
                current_list = []
            else:
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                result[key] = value
    flush()
    return result


def coerce_int(d, key):
    """把字段转成 int（如果是字符串）。"""
    if key in d and isinstance(d[key], str):
        try:
            d[key] = int(d[key])
        except ValueError:
            pass


def check():
    if not os.path.isdir(CASES_DIR):
        print(f'ERROR: {CASES_DIR} 不存在', file=sys.stderr)
        sys.exit(2)

    errors = []
    counts = {k: 0 for k in EXPECTED_CATEGORIES}
    all_ids = []

    files = os.listdir(CASES_DIR)
    txt_files = sorted(f for f in files if f.endswith('.txt') and not f.startswith('_'))
    yaml_files = sorted(f for f in files if f.endswith('.meta.yaml'))

    # 选一个 yaml 看 PyYAML 是否可用
    sample_yaml = ''
    if yaml_files:
        with open(os.path.join(CASES_DIR, yaml_files[0]), encoding='utf-8') as fh:
            sample_yaml = fh.read()
    _, parser_used = parse_yaml(sample_yaml) if sample_yaml else ({}, 'pyyaml')

    for tf in txt_files:
        cid = tf[:-4]
        all_ids.append(cid)

        # 1. 字数
        txt_path = os.path.join(CASES_DIR, tf)
        with open(txt_path, encoding='utf-8') as fh:
            text = fh.read()
        text_no_nl = text.replace('\n', '').replace('\r', '')
        n = len(text_no_nl)
        if not (150 <= n <= 500):
            errors.append(f'{tf}: 字数 {n} 越界（150-500）')

        # 2. 配对
        yf = cid + '.meta.yaml'
        if yf not in yaml_files:
            errors.append(f'{tf}: 缺配对 {yf}')
            continue
        yaml_path = os.path.join(CASES_DIR, yf)
        with open(yaml_path, encoding='utf-8') as fh:
            yaml_text = fh.read()
        meta, _ = parse_yaml(yaml_text)

        # 3. 字段齐全
        miss = [f for f in REQUIRED_FIELDS if f not in meta]
        if miss:
            errors.append(f'{yf}: 缺字段 {miss}')
            continue

        # 4. id 与文件名一致
        if meta['id'] != cid:
            errors.append(f'{yf}: id={meta["id"]!r} 与文件名 {cid!r} 不一致')

        # 5. category 合法
        cat = meta['category']
        if cat not in EXPECTED_CATEGORIES:
            errors.append(f'{yf}: category={cat!r} 不在 8 类白名单')
        else:
            counts[cat] += 1

        # 6. char_count 与实际一致
        coerce_int(meta, 'char_count')
        if str(meta.get('char_count')) != str(n):
            errors.append(f'{yf}: char_count={meta.get("char_count")} 实际={n}')

    # 7. 配比正确
    for cat, expected in EXPECTED_CATEGORIES.items():
        if counts[cat] != expected:
            errors.append(f'配比错: {cat} 实际 {counts[cat]} / 期望 {expected}')

    total = sum(counts.values())
    if total != 30:
        errors.append(f'总数 {total} 不等于 30')

    # 也检查 yaml 是否有 txt 配对（反方向）
    txt_set = {f[:-4] for f in txt_files}
    for yf in yaml_files:
        cid = yf[: -len('.meta.yaml')]
        if cid not in txt_set:
            errors.append(f'{yf}: 无对应 txt')

    # 输出
    print('=' * 60)
    print('Audiobench zh v1 完整性校验')
    print(f'cases 目录: {CASES_DIR}')
    print(f'yaml 解析器: {parser_used}')
    print('=' * 60)
    print()
    print('配比:')
    for cat in EXPECTED_CATEGORIES:
        mark = 'OK' if counts[cat] == EXPECTED_CATEGORIES[cat] else 'X'
        print(f'  [{mark}] {cat}: {counts[cat]} / {EXPECTED_CATEGORIES[cat]}')
    print(f'  TOTAL: {total} / 30')
    print()

    if errors:
        print(f'FAIL（{len(errors)} 个错误）:')
        for e in errors:
            print(f'  - {e}')
        sys.exit(1)

    print('ALL_PASS')
    print()
    print(f'共 {len(all_ids)} 条样例 ID（按字母序）:')
    for cid in sorted(all_ids):
        print(f'  - {cid}')


if __name__ == '__main__':
    check()
