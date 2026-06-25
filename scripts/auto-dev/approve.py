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

from daily_triage import validate_repo

STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
TODAY_TASKS = Path("/home/yn4416/.claude/state/today-tasks.md")
RUN_SCRIPT = Path("/home/yn4416/.claude/scripts/auto-dev/run-task.sh")

LINE_RE = re.compile(
    r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*[—-]\s*(.+?)"
    r"(?:（想定コスト:\s*([SML])）)?"
    r"\s*(?:（(repo:\s*.+?|手動)）)?\s*$"
)


def parse_today_tasks(text: str) -> list[dict]:
    """today-tasks.md から 'N. **<タスク>** — <理由>（コスト）（marker）' を抽出。

    marker は 'repo: <name>' または '手動'。無ければ repo=None・manual=False。

    Args:
        text: today-tasks.md の全文。

    Returns:
        [{n, title, reason, cost, repo, manual}, ...]。
        repo は名前 or None。cost は無ければ None。manual は bool。
    """
    tasks: list[dict] = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        n, title, reason, cost, marker = m.groups()
        repo: str | None = None
        manual = False
        if marker:
            if marker.startswith("repo:"):
                repo = marker[len("repo:"):].strip()
            elif marker.strip() == "手動":
                manual = True
        tasks.append({
            "n": int(n),
            "title": title.strip(),
            "reason": reason.strip(),
            "cost": cost,
            "repo": repo,
            "manual": manual,
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


def select_queueable(
    tasks: list[dict], projects_dir: Path | None = None
) -> tuple[list[dict], list[dict]]:
    """タスクリストを (自動実行可能, 手動除外) に振り分け。

    manual=True または repo実在チェック不可（validate_repo が None）は除外。
    queueable 側には解決済み 'repo_path'（絶対パス）を付与。

    Args:
        tasks: parse_today_tasks() の結果。
        projects_dir: validate_repo の親ディレクトリ（None ならデフォルト ~/projects）。

    Returns:
        (queueable, excluded)。queueable 各要素は元フィールド + 'repo_path'。
    """
    validate_kwargs = {} if projects_dir is None else {"projects_dir": projects_dir}
    queueable: list[dict] = []
    excluded: list[dict] = []
    for t in tasks:
        if t.get("manual"):
            excluded.append(t)
            continue
        repo_path = validate_repo(t.get("repo") or "", **validate_kwargs)
        if repo_path is None:
            excluded.append(t)
            continue
        queueable.append({**t, "repo_path": repo_path})
    return queueable, excluded


def load_or_init_state() -> dict:
    """state.json を読むか空テンプレを返す。"""
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {
        "active": True,
        "pending": [],
        "current": None,
        "completed": [],
        "blocked": [],
    }


def main() -> int:
    """対話的に候補を選択→state.json 登録→最初のタスクを起動（多repo対応）。"""
    if not TODAY_TASKS.exists():
        print(f"❌ {TODAY_TASKS} がありません。先に daily-triage.sh を実行してください。")
        return 1

    tasks = parse_today_tasks(TODAY_TASKS.read_text(encoding="utf-8"))
    if not tasks:
        print("候補がありません。")
        return 0

    print("=== 今日のタスク候補 ===")
    for t in tasks:
        cost = f" [{t['cost']}]" if t["cost"] else ""
        marker = f" (repo: {t['repo']})" if t["repo"] else (" (手動)" if t["manual"] else "")
        print(f"  {t['n']}. {t['title']}{cost}{marker} — {t['reason']}")
    print("\n承認する番号をカンマ区切りで入力（例: 1 または 1,2,3）")
    print("⚠️ 大量一括は非推奨（ch12① agentic trap）。今日やる分だけ。")
    print("ℹ️ （手動）タスクは選んでも自動実行対象外として除外されます。")

    raw = input("> ").strip()
    nums = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    if not nums:
        print("未選択・中止します。")
        return 0

    selected = [t for t in tasks if t["n"] in nums]
    queueable, excluded = select_queueable(selected)

    for t in excluded:
        print(f"⚠️ 自動実行対象外・人間対応: {t['title']}")

    state = load_or_init_state()
    state["pending"] = [build_task_entry(t, t["repo_path"]) for t in queueable]
    state["active"] = True
    state["running"] = False
    first_task = state["pending"].pop(0) if state["pending"] else None
    state["current"] = first_task
    state["completed"] = []
    state["blocked"] = []
    state["project"] = "multi"
    state.pop("repo_path", None)  # top-level repo_path 廃止（多repoでは無意味）
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ キュー登録: {[t['title'] for t in queueable]}")

    if not queueable:
        print("ℹ️ 自動実行可能なタスクがありません（全て手動）。起動せず終了。")
        return 0

    if first_task:
        subprocess.Popen(
            ["setsid", "bash", str(RUN_SCRIPT), first_task["title"]],
            cwd=first_task["repo"],
            start_new_session=True,
        )
        print(f"🚀 最初のタスク起動: {first_task['title']} (repo: {first_task['repo']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
