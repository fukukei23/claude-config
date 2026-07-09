#!/usr/bin/env python3
"""
check-command-safety.py
PreToolUse フック: Bash / Read ツールの危険パターンを事前ブロック
  - ブロック時: {"decision": "block", "reason": "..."} を stdout へ出力
  - 許可時   : 何も出力せず exit 0
  - エラー時 : 常に exit 0（フック自体でセッションを止めない）
"""

import sys
import json
import re


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": f"[security-guard] {reason}"}))
    sys.exit(0)


# 機密ファイルパスのパターン
SECRET_FILE_RE = re.compile(
    r'(?:\.secrets\.env'
    r'|settings\.json'
    r'|settings\.local\.json'
    r'|claude_desktop_config\.json'
    r'|\.bash_history'
    r'|\.env(?![a-zA-Z]))'  # .env は .env.example 等を除外
)


def check_bash(cmd: str) -> None:
    """Bash ツールのコマンド文字列を検査する"""

    # --- 1. トレース系（常にブロック）---
    if re.search(r'(?:^|[\s;|&])(bash|sh)\s+-\S*x', cmd):
        block("bash/sh -x 禁止 — 全変数値がトレース出力に露出します")
    if re.search(r'(?:^|[\s;|&])set\s+(?:-x|-o\s+xtrace)', cmd):
        block("set -x / set -o xtrace 禁止 — 機密値が露出します")
    if re.search(r'(?:^|[\s;|&])(strace|ltrace)\s', cmd):
        block("strace / ltrace 禁止 — プロセスの全出力が記録されます")

    # コマンドをチャンク分割して各部を検査
    chunks = re.split(r'[;&|]+', cmd)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # --- 2. 機密ファイルの直接表示 ---
        if re.search(r'(?:^|\s)(cat|head|tail|less|more|nano|vi|vim)\s', chunk):
            if SECRET_FILE_RE.search(chunk):
                block(
                    "機密ファイルの直接表示禁止 — "
                    "構造確認は grep -E '^[A-Z_]+=' <file> | sed 's/=.*/=<REDACTED>/' を使ってください"
                )

        # --- 2b. jq による機密ファイルの全ダンプ ---
        if re.search(r'(?:^|\s)jq\b', chunk):
            if SECRET_FILE_RE.search(chunk):
                # セーフパターン: 機密を含まない特定フィールドのみ（ホワイトリスト）
                safe_fields = r'\.(?:statusLine|model|fallbackModel|smallModel|apiBaseUrl|permissions|theme|preferredNotifChannel)'
                if not re.search(safe_fields, chunk):
                    block(
                        "jq による機密ファイルの全/広域ダンプ禁止 — "
                        "APIキーが露出します。特定フィールドのみ: jq '.statusLine' 等"
                    )

        # --- 3. cat -A / -v / -E（特殊文字表示）---
        if re.search(r'(?:^|\s)cat\s+-[A-Za-z]*[AvE]', chunk):
            block("cat -A/-v/-E 禁止 — 機密値が特殊文字形式で露出します（今回のインシデント事例）")

        # --- 4. 機密ファイルへの grep（sed マスクなし）---
        if re.search(r'(?:^|\s)grep\b', chunk) and SECRET_FILE_RE.search(chunk):
            # grep -c（行数）/ grep -l（ファイル名）は値を表示しないので許可
            if not re.search(r'grep\s+[^|]*-[A-Za-z]*[cl]\b', chunk):
                # パイプ後に sed による値マスクがあれば許可（シングル・ダブル・引用符なし全対応）
                if not re.search(r"""sed\s+['""]?s/""", cmd):
                    block(
                        "機密ファイルへの grep には値マスクが必要: "
                        "grep ... | sed 's/=.*/=<REDACTED>/'"
                    )

        # --- 5. 環境変数の全ダンプ ---
        if re.search(r'^(env|printenv)\s*$', chunk):
            block("env / printenv 引数なし禁止 — 全 API キーが露出します。特定変数のみ: echo \"$VAR\"")
        if re.search(r'^declare\s+-p\s*$', chunk):
            block("declare -p 引数なし禁止 — 全変数値が露出します")
        if re.search(r'^set\s*$', chunk):
            block("set 引数なし禁止 — シェル変数が全て表示されます")

        # --- 6. /proc/*/environ（プロセス環境変数ダンプ）---
        if re.search(r'/proc/\S+/environ', chunk):
            block("/proc/*/environ へのアクセス禁止 — 他プロセスの機密値が露出します")

        # --- 7. ps による環境変数付きプロセス表示 ---
        if re.search(r'(?:^|\s)ps\s+\S*(?:eww|auxe|axe)\b', chunk):
            block("ps eww / ps auxe 禁止 — 全プロセスの環境変数が表示されます")


def check_read(file_path: str) -> None:
    """Read ツールのファイルパスを検査する"""
    sensitive = re.compile(
        r'settings\.json'
        r'|settings\.local\.json'
        r'|claude_desktop_config\.json'
        r'|\.secrets\.env'
        r'|\.bash_history'
    )
    if sensitive.search(file_path):
        block(
            f"Read ツールによる機密ファイル読み取り禁止: {file_path.split('/')[-1]} — "
            "確認は jq '.field'（単一フィールドのみ・ホワイトリスト）。"
            "編集は python 構造操作で: json.load→該当箇所変更→json.dump(indent=2) "
            "（値非接触・フォーマット保持・バックアップ推奨）"
        )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if tool_name == "Bash":
        cmd = data.get("tool_input", {}).get("command", "")
        if cmd:
            check_bash(cmd)

    elif tool_name == "Read":
        file_path = data.get("tool_input", {}).get("file_path", "")
        if file_path:
            check_read(file_path)

    sys.exit(0)


if __name__ == "__main__":
    main()
