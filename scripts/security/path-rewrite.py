#!/usr/bin/env python3
"""
path-rewrite.py
PreToolUse フック（Windows Desktop版settings.jsonにのみ登録）。
Bashツールのコマンド文字列内の既知WSLホームパスプレフィックスを
UNCパスへ書き換える。$HOME環境変数やOS設定は一切変更しない。

  - 置換発生時: hookSpecificOutput.updatedInput.command を stdout へ出力
  - 置換なし  : 何も出力せず exit 0
  - エラー時  : 常に exit 0（フック自体でセッションを止めない）

詳細: docs/superpowers/specs/2026-06-30-windows-desktop-wsl-path-bridge-design.md
"""

import json
import re
import sys

WSL_UNC_ROOT = "//wsl.localhost/Ubuntu/home/yn4416"

# 既知の固定プレフィックスのみを対象とするホワイトリスト。
# 汎用的な `~/` 全般を対象にすると echo ~ 等のホーム展開を壊すため、
# 共有ファイルで実際に使われている2系統の表記だけに絞る。
PREFIX_MAP: dict[str, str] = {
    "~/projects/": f"{WSL_UNC_ROOT}/projects/",
    "~/.claude/": f"{WSL_UNC_ROOT}/.claude/",
    "/home/yn4416/projects/": f"{WSL_UNC_ROOT}/projects/",
    "/home/yn4416/.claude/": f"{WSL_UNC_ROOT}/.claude/",
}

# 置換後の文字列が別プレフィックスに再マッチして二重置換されるのを防ぐため、
# 全プレフィックスを1つの正規表現にまとめ、一度の左から右へのパスで置換する。
_PREFIX_RE = re.compile(
    "|".join(re.escape(prefix) for prefix in PREFIX_MAP)
)


def rewrite_command(command: str) -> str | None:
    """既知プレフィックスを置換したコマンド文字列を返す。変更がなければNoneを返す。"""
    rewritten = _PREFIX_RE.sub(lambda m: PREFIX_MAP[m.group(0)], command)
    return rewritten if rewritten != command else None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    updated = rewrite_command(command)
    if updated is not None:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": updated},
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
