#!/usr/bin/env python3
"""GitHub Issue → state.json pending 自動積込エンジン。

gh CLI で auto-loop ラベル付き Issue を取得し、state.json の pending に供給する。
manual モード（Daily Triage から候補混入）・auto モード（next_issue.py が枯渇補充）
の両方から呼ばれる。
"""
import json
import subprocess
import sys
from pathlib import Path

STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
CONFIG = Path("/home/yn4416/.claude/scripts/auto-dev/auto-loop-config.yaml")


def ensure_state_fields(state: dict) -> dict:
    """state.json に新規フィールドのデフォルトを保証（破壊的 setdefault）。

    Args:
        state: state.json の内容。

    Returns:
        mode/max_tasks_per_session/session_task_count が保証された state。
    """
    state.setdefault("mode", "manual")
    state.setdefault("max_tasks_per_session", 3)
    state.setdefault("session_task_count", 0)
    return state


def format_issue(issue: dict, repo_path: str) -> dict:
    """gh の Issue JSON を pending 形式に変換。

    Args:
        issue: gh が出力する {number, title, body}。
        repo_path: リポジトリの絶対パス（per-task・next_issue.py 互換）。

    Returns:
        {title, prompt, repo, issue} の pending エントリ。
    """
    number = issue.get("number")
    title = issue.get("title", f"Issue #{number}")
    body = issue.get("body") or ""
    prompt = f"以下のGitHub Issueを実装せよ。\n\n# {title}\n\n{body}"
    return {"title": title, "prompt": prompt, "repo": repo_path, "issue": number}


def fetch_from_repo(repo_path: str, label: str) -> list[dict]:
    """1リポジトリの auto-loop Issue を取得（pending 形式リスト）。

    gh CLI 失敗時は空リスト（例外なし・呼出元で安全停止）。

    Args:
        repo_path: リポジトリ絶対パス（cwd=repo_path で gh を起動）。
        label: 取得対象ラベル名。

    Returns:
        pending 形式の Issue リスト。失敗時は []。
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--label", label, "--state", "open",
             "--json", "number,title,body", "--limit", "30"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return [format_issue(i, repo_path) for i in issues]


def filter_duplicates(new_tasks: list[dict], state: dict) -> list[dict]:
    """既存 pending/current/completed/blocked の issue 番号と重複するものを除外。

    Args:
        new_tasks: fetch_from_repo で取得した pending 形式リスト。
        state: 現在の state.json。

    Returns:
        重複を除外した新しいタスクリスト。
    """
    existing_numbers = set()
    for entry in state.get("pending", []):
        if isinstance(entry, dict) and entry.get("issue") is not None:
            existing_numbers.add(entry["issue"])
    cur = state.get("current")
    if isinstance(cur, dict) and cur.get("issue") is not None:
        existing_numbers.add(cur["issue"])
    for entry in state.get("completed", []) + state.get("blocked", []):
        if isinstance(entry, dict) and entry.get("issue") is not None:
            existing_numbers.add(entry["issue"])
    return [t for t in new_tasks if t.get("issue") not in existing_numbers]


def load_config(path: Path) -> dict:
    """auto-loop-config.yaml を読む（PyYAML）。無ければ空 dict。

    Args:
        path: 設定ファイルパス。

    Returns:
        設定 dict。repos/label/max_tasks_per_session を含む。
    """
    if not path.exists():
        return {"repos": [], "label": "auto-loop", "max_tasks_per_session": 3}
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run() -> list[dict]:
    """config の全 repo から Issue を取得し重複除外して返す。

    Returns:
        pending に積込可能な新規タスクリスト。
    """
    config = load_config(CONFIG)
    label = config.get("label", "auto-loop")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    state = ensure_state_fields(state)
    new_tasks: list[dict] = []
    for repo in config.get("repos", []):
        repo_path = repo.get("path")
        if repo_path:
            new_tasks.extend(fetch_from_repo(repo_path, label))
    return filter_duplicates(new_tasks, state)


def main() -> int:
    """取得した Issue を state.json の pending に追記し、件数をログ出力。"""
    new_tasks = run()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    state = ensure_state_fields(state)
    state.setdefault("pending", [])
    added = filter_duplicates(new_tasks, state)
    state["pending"].extend(added)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ fetch_issues: {len(added)}件 追加（取得{len(new_tasks)}件・重複除外済）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
