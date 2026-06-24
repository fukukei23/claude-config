#!/usr/bin/env python3
"""approve.py — Daily Triage 候補を人間が承認し state.json キューに登録・起動。

today-tasks.md を番号表示→選択→state.json の pending に本文ベースで登録→
最初のタスクで run-task.sh を起動（以降 Stop hook 連鎖）。

ch9「人間の判断を仰ぐボックス」。大量一括承認は禁止（ch12① agentic trap 対策）。
"""
import json
import re
import subprocess
from pathlib import Path

STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
TODAY_TASKS = Path("/home/yn4416/.claude/state/today-tasks.md")
RUN_SCRIPT = Path("/home/yn4416/.claude/scripts/auto-dev/run-task.sh")

LINE_RE = re.compile(
    r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*[—-]\s*(.+?)(?:（想定コスト:\s*([SML])）)?\s*$"
)


def parse_today_tasks(text: str) -> list[dict]:
    """today-tasks.md から 'N. **<タスク>** — <理由>（コスト）' を抽出。

    Args:
        text: today-tasks.md の全文。

    Returns:
        [{n, title, reason, cost}, ...]。cost は無ければ None。
    """
    tasks: list[dict] = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        n, title, reason, cost = m.groups()
        tasks.append({
            "n": int(n),
            "title": title.strip(),
            "reason": reason.strip(),
            "cost": cost,
        })
    return tasks


def build_task_entry(task: dict, repo: str) -> dict:
    """選択タスクから state.json の pending 要素を生成。

    Args:
        task: parse_today_tasks の要素。
        repo: 実行先リポジトリの絶対パス。

    Returns:
        {title, prompt, repo, issue}。issue は本文由来なので None。
    """
    return {
        "title": task["title"],
        "prompt": f"{task['title']} を実装してください。理由/背景: {task['reason']}",
        "repo": repo,
        "issue": None,
    }
