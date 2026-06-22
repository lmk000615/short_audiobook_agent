"""src_next/voicebank/qwen_voicegenerator.py

Qwen VoiceGenerator / VoiceDesign 通用 voicebank adapter（v2，已接入 subprocess）。

**通用** 的意思是：本 adapter 不区分蓝区和服务器。两者的路径差异全部
通过构造参数传入（由 profiles/blue_*.yaml 和 profiles/server_*.yaml 分别提供）。

字段含义：
    generator_root      voicegenerator 项目根目录（Windows 路径风格）
    script_path         具体运行脚本，可以是绝对路径，也可以是相对 generator_root 的相对路径
    model_path          模型权重路径（可选，voicedesign 用 --model-dir 传）
    preset_path         preset.json 路径（可选；当前 voicedesign 脚本不消费，仅记录快照）
    python_executable   Python 解释器；可以是 str 或 list[str]。
                        list 形式用于 wrapper 调用，例如 ["wsl", "/mnt/f/.../bin/python"]。
    output_subdir       在 output_dir 下创建的子目录名（默认 voicebank）
    extra_args          其他 CLI 参数。常见字段：
                        - language (默认 Chinese)
                        - device (默认 cuda:0)
                        - reference_text (voicedesign 用的固定参考文本)
                        - timeout_per_char (单字符 subprocess 超时秒数，默认 300)

v2 行为：
    prepare_voicebank 对每个 character 执行一次 subprocess 调用，参数映射：
        --text       <- extra_args.reference_text（默认 "你好，欢迎使用语音设计功能，..."）
        --instruct   <- character.voice_prompt（缺失时根据 gender/age_style 兜底）
        --output     <- <voicebank_dir>/<character.name>.wav
        --model-dir  <- config.model_path（若有）
        --language   <- extra_args.language（默认 Chinese）
        --device     <- extra_args.device（默认 cuda:0）

    每个 character 的 stdout/stderr 落到 <voicebank_dir>/<name>.log，便于排错。
    部分失败不阻塞其他 character；失败列表写到 <voicebank_dir>/errors.log。
    全部成功 → VoicebankResult.success=True；任何失败 → success=False。

路径风格：
    配置中所有路径用 Windows 风格（F:/...）。当 python_executable 检测到 wsl
    时，adapter 自动把传给 subprocess 的路径转成 /mnt/f/... 形式。
    蓝区 venv 是 WSL 创建的（pyvenv.cfg 里 executable=/usr/bin/python3），
    所以必须通过 wsl 调用，路径也必须转换。

本文件中不写死任何 F:/... / /data3/... / M:/... / C:/... 路径。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from src_next.core.data_models import CharacterProfile, VoicebankResult

from .base import BaseVoicebankAdapter, VoicebankError


_DEFAULT_OUTPUT_SUBDIR = "voicebank"
_DEFAULT_REFERENCE_TEXT = "你好，欢迎使用语音设计功能，这是一个测试句子。"
_DEFAULT_LANGUAGE = "Chinese"
_DEFAULT_DEVICE = "cuda:0"
_DEFAULT_TIMEOUT_PER_CHAR = 300  # 秒；加载 1.7B 模型 + 生成一句话，留够余量


class QwenVoiceGeneratorAdapter(BaseVoicebankAdapter):
    """通用 Qwen VoiceGenerator adapter（蓝区/服务器共用）。"""

    def __init__(
        self,
        *,
        generator_root: str,
        script_path: str,
        model_path: str | None = None,
        preset_path: str | None = None,
        python_executable: str | list[str] | None = None,
        output_subdir: str = _DEFAULT_OUTPUT_SUBDIR,
        extra_args: dict[str, Any] | None = None,
    ) -> None:
        self.generator_root = (generator_root or "").strip()
        self.script_path = (script_path or "").strip()
        self.model_path = (model_path or "").strip() or None
        self.preset_path = (preset_path or "").strip() or None

        # python_executable 接受 str 或 list[str]
        if isinstance(python_executable, (list, tuple)):
            self.python_executable: list[str] = [str(p).strip() for p in python_executable if str(p).strip()]
        else:
            py = (str(python_executable) if python_executable else "").strip()
            self.python_executable = [py] if py else []

        self.output_subdir = (output_subdir or _DEFAULT_OUTPUT_SUBDIR).strip() or _DEFAULT_OUTPUT_SUBDIR
        self.extra_args: dict[str, Any] = dict(extra_args) if extra_args else {}

    # ── BaseVoicebankAdapter 实现 ───────────────────────────────────

    def prepare_voicebank(
        self,
        characters: list[CharacterProfile],
        output_dir: str,
        *,
        dry_run: bool = False,
        timeout_per_char: int | None = None,
        **kwargs: Any,
    ) -> VoicebankResult:
        self._validate_config()

        voicebank_dir = Path(output_dir).expanduser() / self.output_subdir
        voicebank_dir.mkdir(parents=True, exist_ok=True)

        char_entries = [self._character_to_entry(c) for c in characters]

        # 写 input JSON 和 config snapshot，便于事后排错和审计
        config_snapshot = {
            "generator_root": self.generator_root,
            "script_path": self.script_path,
            "model_path": self.model_path,
            "preset_path": self.preset_path,
            "python_executable": self.python_executable,
            "output_subdir": self.output_subdir,
            "extra_args": self.extra_args,
        }
        input_payload = {
            "version": 2,
            "backend": "qwen_voicegenerator",
            "characters": char_entries,
            "config": config_snapshot,
            "output_dir": str(voicebank_dir),
        }
        (voicebank_dir / "voicegenerator_input.json").write_text(
            json.dumps(input_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (voicebank_dir / "adapter_config.json").write_text(
            json.dumps(config_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if dry_run:
            # dry_run：和 v1 一致，明确 success=False，不真实调用模型
            speaker_to_voice = {
                entry["name"]: str(voicebank_dir / f"{entry['name']}.wav")
                for entry in char_entries
            }
            return VoicebankResult(
                speaker_to_voice=speaker_to_voice,
                voicebank_dir=str(voicebank_dir),
                backend="qwen_voicegenerator",
                success=False,
            )

        # v2：真实 subprocess 调用，每 character 一次
        timeout = timeout_per_char or int(
            self.extra_args.get("timeout_per_char", _DEFAULT_TIMEOUT_PER_CHAR)
        )

        speaker_to_voice: dict[str, str] = {}
        errors: list[str] = []

        for char in characters:
            voice_path = voicebank_dir / f"{char.name}.wav"

            # 简单缓存：已存在的 wav 不重复生成
            if voice_path.exists():
                speaker_to_voice[char.name] = str(voice_path)
                continue

            cmd = self._build_command_for_character(char, voice_path)
            log_path = voicebank_dir / f"{char.name}.log"

            try:
                with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
                    logf.write("=== INVOCATION ===\n")
                    logf.write(" ".join(cmd) + "\n")
                    logf.write("=== OUTPUT ===\n")
                    logf.flush()
                    completed = subprocess.run(
                        cmd,
                        stdout=logf,
                        stderr=subprocess.STDOUT,
                        timeout=timeout,
                        check=True,
                    )
                speaker_to_voice[char.name] = str(voice_path)
            except subprocess.CalledProcessError as err:
                errors.append(
                    f"{char.name}: subprocess exit={err.returncode}, see {log_path.name}"
                )
            except subprocess.TimeoutExpired:
                errors.append(
                    f"{char.name}: timeout after {timeout}s, see {log_path.name}"
                )
            except FileNotFoundError as err:
                errors.append(
                    f"{char.name}: executable not found: {err}. "
                    "Check python_executable in profile."
                )
            except Exception as err:  # noqa: BLE001
                errors.append(
                    f"{char.name}: {type(err).__name__}: {err}"
                )

        if errors:
            (voicebank_dir / "errors.log").write_text(
                "\n".join(errors) + "\n",
                encoding="utf-8",
            )

        return VoicebankResult(
            speaker_to_voice=speaker_to_voice,
            voicebank_dir=str(voicebank_dir),
            backend="qwen_voicegenerator",
            success=(not errors),
        )

    # ── 内部工具 ────────────────────────────────────────────────────

    def _validate_config(self) -> None:
        if not self.generator_root:
            raise VoicebankError(
                "QwenVoiceGeneratorAdapter 缺少 generator_root。"
                "请在 profile 中配置 voicebank.generator_root。"
            )
        if not self.script_path:
            raise VoicebankError(
                "QwenVoiceGeneratorAdapter 缺少 script_path。"
                "请在 profile 中配置 voicebank.script_path。"
            )

    @staticmethod
    def _character_to_entry(c: CharacterProfile) -> dict[str, Any]:
        return {
            "name": c.name,
            "role_type": c.role_type,
            "gender": c.gender,
            "age_style": c.age_style,
            "personality": c.personality,
            "voice_prompt": c.voice_prompt,
            "confidence": c.confidence,
        }

    def _resolve_script_path(self) -> str:
        """script_path 可以是绝对路径，也可以是相对 generator_root 的相对路径。

        返回 Windows 风格路径（不管最终是否走 WSL，原始路径解析在 Windows 侧做）。
        """
        script = Path(self.script_path)
        if script.is_absolute():
            return str(script)
        return str(Path(self.generator_root) / script)

    def _is_wsl_invocation(self) -> bool:
        """检测 python_executable 是否是 wsl 包装调用。"""
        if not self.python_executable:
            return False
        first = self.python_executable[0].lower()
        # 兼容 wsl / wsl.exe
        return first == "wsl" or first.endswith("wsl.exe") or first.endswith("\\wsl")

    def _to_subprocess_path(self, p: str | Path) -> str:
        """把 Windows 路径转成 subprocess 能理解的路径。

        如果 python_executable 走 wsl，把 F:\\... 转 /mnt/f/...；否则原样返回。
        相对路径不转换。
        """
        s = str(p).replace("\\", "/")
        if not self._is_wsl_invocation():
            return s
        # 绝对路径判断：第二字符是冒号（F:、C: ...）
        if len(s) >= 2 and s[1] == ":":
            drive = s[0].lower()
            rest = s[2:].lstrip("/")
            return f"/mnt/{drive}/{rest}"
        return s

    def _default_instruct(self, char: CharacterProfile) -> str:
        """character.voice_prompt 缺失时的兜底 instruct。"""
        gender = char.gender or "中性"
        age = char.age_style or "成年"
        if char.role_type == "narrator":
            return f"用平稳客观的{age}{gender}说书人嗓音说"
        return f"用{age}{gender}的嗓音说"

    def _build_command_for_character(
        self,
        char: CharacterProfile,
        voice_path: Path,
    ) -> list[str]:
        """构建单个角色的 subprocess 命令（v2 真实执行）。"""
        py_parts = self._python_command_parts()
        script = self._to_subprocess_path(self._resolve_script_path())

        cmd: list[str] = list(py_parts) + [script]
        cmd += ["--text", str(self.extra_args.get("reference_text", _DEFAULT_REFERENCE_TEXT))]
        cmd += ["--instruct", char.voice_prompt or self._default_instruct(char)]
        cmd += ["--output", self._to_subprocess_path(voice_path)]

        if self.model_path:
            cmd += ["--model-dir", self._to_subprocess_path(self.model_path)]

        # 显式挑出 voicedesign 脚本支持的 CLI 参数
        language = str(self.extra_args.get("language", _DEFAULT_LANGUAGE))
        device = str(self.extra_args.get("device", _DEFAULT_DEVICE))
        cmd += ["--language", language]
        cmd += ["--device", device]

        # src_next 的 run_voicedesign_srcnext.py 支持 --attn-implementation
        # 默认走 sdpa（不依赖 flash-attn 包）
        attn_impl = str(self.extra_args.get("attn_implementation", "sdpa"))
        cmd += ["--attn-implementation", attn_impl]

        return cmd

    def _python_command_parts(self) -> list[str]:
        """python_executable 的统一出口：始终返回 list[str]。"""
        if self.python_executable:
            return list(self.python_executable)
        return [sys.executable]
