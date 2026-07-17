"""src_next/critic/voicebank_bench — Voicebank Critic 基准测试工具链。

提供 voicebank + voicebank_critic 的基准测试能力：
- prep_characters: 预处理 audiobench_zh 测试集，生成 characters.json
- run_voicebank_bench: 运行 voicebank + critic 基准测试
- test_qwen3omni_vb_critic: Qwen3-Omni 评分引擎最小验证

产物统一存放在 tests/audiobench_zh/ 下的 _prep_characters/ 和 _voicebank_results/。
"""