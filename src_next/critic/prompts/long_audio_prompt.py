"""长音频综合听感评分 prompt。

迁移自 test_long_audio.py:50,52-74。与 critic_prompt.py 的 5 维 prompt 互补：
- critic_prompt.py：针对单段 TTS（1-30s），5 维 0-10 + 修复建议，配合 tts_repair 闭环
- 本文件：针对整段长音频（~2 分钟 audio_final/*.wav），4 维 0-10 + A/B/C/D，
  关注"整体听感"而非"单段可修复性"

4 维（emotion_expressiveness / rhythm / naturalness / clarity）针对有声书最终
听感评判定制，强调情绪是否舒服自然（不是"强不强"）、整体连贯性、吐字清晰度。
"""
from __future__ import annotations


LONG_AUDIO_SYSTEM_PROMPT = "Return only valid minified JSON. No markdown. No extra text."


LONG_AUDIO_EVAL_PROMPT = """
任务：评价下面这段音频的综合听感质量。这是一段有声书/TTS/旁白/角色对白的长音频片段。

评分维度：
1. emotion_expressiveness：情绪是否自然、匹配、适度、舒服。情绪过平要扣分；情绪过强、浮夸、用力过猛、戏剧腔、听感尴尬也要明显扣分。
2. rhythm：语速、停顿、断句、连贯性、是否容易听懂。
3. naturalness：发音是否自然、像真人说话、无明显TTS合成感或机械感；语气衔接是否流畅。
4. clarity：人声是否清晰、吐字是否清楚、有无含混或失真、背景噪声是否干扰。

等级区间：
A=7.5-10，B=5.0-7.4，C=2.5-4.9，D=0-2.4。只输出 score，grade 由程序计算。

强制规则：
- 如果情绪略夸张或略用力，emotion_expressiveness 最高 7.4。
- 如果情绪明显浮夸、用力过猛、不够克制、戏剧腔明显，emotion_expressiveness 最高 4.9。
- 如果情绪刺耳、尴尬、严重不匹配，emotion_expressiveness 最高 2.4。
- reason 必须说明扣分原因；problems 只能写实际听到的问题，没有问题写空数组 []。
- main_problems 必须汇总最影响整体听感的 1-3 个问题，不能写"无明显问题"除非所有维度都大于等于 8.0。
- suggestions 必须和 main_problems 对应，给出 1-3 条可执行优化建议。

输出要求：只输出合法 JSON，不要 markdown，不要解释。字段固定如下：
{"scores":{"emotion_expressiveness":{"score":0,"reason":"30字内","problems":["12字内"]},"rhythm":{"score":0,"reason":"30字内","problems":["12字内"]},"naturalness":{"score":0,"reason":"30字内","problems":["12字内"]},"clarity":{"score":0,"reason":"30字内","problems":["12字内"]}},"main_problems":["16字内"],"suggestions":["16字内"]}
""".strip()
