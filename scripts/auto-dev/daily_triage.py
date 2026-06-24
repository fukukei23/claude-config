#!/usr/bin/env python3
"""Daily Triage: 複数ソースからタスク候補を収集→Claude判定→today-tasks.md生成。

収集ロジック（collect_*）はパスを引数で受け取り pytest で TDD。
Claude判定は claude --print の外部APIのため手動検証（--collect-only/--no-llm で検証可能）。
"""
from pathlib import Path


def collect_backlog(path: Path) -> list[str]:
    """バックログからP0/P1未完了タスク([ ])を抽出。P2・完了済みセクションは除外。

    Args:
        path: バックログ.md のパス

    Returns:
        タスク本文のリスト（"- [ ]" マーカー除去済み）
    """
    if not path.exists():
        return []
    tasks: list[str] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## P0:") or line.startswith("## P1:"):
            section = line
        elif line.startswith("## P2:") or line.startswith("## 完了済み"):
            section = ""
        elif line.startswith("- [ ]") and section:
            tasks.append(line[5:].strip())  # "- [ ]" (5文字) を除去
    return tasks


def collect_active_green(path: Path) -> list[str]:
    """active-sessions.md の 🟢進行中タスク表の行を抽出。

    ヘッダー行（| タスク）・区切り行（|---）・別セクションは除外。
    セクションは "## 🟢" で開始し次の "## " で終了。

    Args:
        path: active-sessions.md のパス

    Returns:
        テーブル行（"|" 始まり）のリスト
    """
    if not path.exists():
        return []
    rows: list[str] = []
    in_green = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 🟢"):
            in_green = True
            continue
        if in_green and line.startswith("## "):
            break
        if in_green and line.startswith("| ") and not line.startswith("| タスク") and not line.startswith("|-"):
            rows.append(line)
    return rows
