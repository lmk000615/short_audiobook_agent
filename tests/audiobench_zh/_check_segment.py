"""L2 验证：直接调 segment_builder，看每条样例的切分结果。

不依赖 PyYAML / 不调 LLM，纯结构检查。
"""
import os
import sys

sys.path.insert(0, r'M:\Users\l30083418\Documents\short_audiobook_agent')

from src_next.core.segment_builder import build_segments
from src_next.core.data_models import StoryInput

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases')

# 抽查代表性的几条
SPOT_CHECK = [
    'basic_children_01',  # 引号嵌套
    'basic_children_03',  # 拟声词引号
    'speaker_hard_02',    # 引号嵌套（外 "" + 内 「」）
    'speaker_hard_04',    # 心理 vs 对白
    'sfx_trigger_01',     # 音效触发
]

print('=' * 70)
print('L2 验证: segment_builder 切分结果')
print('=' * 70)

for cid in SPOT_CHECK:
    txt_path = os.path.join(CASES_DIR, cid + '.txt')
    if not os.path.exists(txt_path):
        continue
    with open(txt_path, encoding='utf-8') as fh:
        text = fh.read()
    segs = build_segments(StoryInput(story_name=cid, text=text))
    print(f'\n--- {cid} ({len(text)} chars → {len(segs)} segments) ---')
    for s in segs:
        type_tag = f'[{s.segment_type:9s}]'
        speaker_tag = f'spk={s.speaker:8s}'
        text_preview = s.text[:60] + ('...' if len(s.text) > 60 else '')
        print(f'  {s.segment_id} {type_tag} {speaker_tag} raw={s.raw_index} | {text_preview}')

# 全部 30 条快速过一遍：每条切出几个 segment / 几个 dialogue
print('\n' + '=' * 70)
print('全部 30 条 segment 统计')
print('=' * 70)
print(f'{"id":<28} {"segs":>5} {"narr":>5} {"dial":>5} {"inner":>6}')
all_txt = sorted(f for f in os.listdir(CASES_DIR) if f.endswith('.txt') and not f.startswith('_'))
total_segs = 0
total_dial = 0
for tf in all_txt:
    cid = tf[:-4]
    with open(os.path.join(CASES_DIR, tf), encoding='utf-8') as fh:
        text = fh.read()
    segs = build_segments(StoryInput(story_name=cid, text=text))
    narr = sum(1 for s in segs if s.segment_type == 'narration')
    dial = sum(1 for s in segs if s.segment_type == 'dialogue')
    inner = sum(1 for s in segs if s.segment_type == 'inner_thought')
    total_segs += len(segs)
    total_dial += dial
    print(f'  {cid:<28} {len(segs):>5} {narr:>5} {dial:>5} {inner:>6}')

print(f'\n总计: {len(all_txt)} 条样例 → {total_segs} segments (其中 {total_dial} dialogue)')
