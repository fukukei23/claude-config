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
    """対話的に候補を選択→state.json 登録→最初のタスクを起動。"""
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
        print(f"  {t['n']}. {t['title']}{cost} — {t['reason']}")
    print("\n承認する番号をカンマ区切りで入力（例: 1 または 1,2）")
    print("⚠️ 大量一括は非推奨（ch12① agentic trap）。今日やる分だけ。")

    raw = input("> ").strip()
    nums = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    if not nums:
        print("未選択・中止します。")
        return 0

    repo = input("実行先リポジトリパス (例: /home/yn4416/projects/<repo>): ").strip()
    if not repo:
        print("リポジトリ未指定・中止。")
        return 1

    selected = [t for t in tasks if t["n"] in nums]
    state = load_or_init_state()
    state["pending"] = [build_task_entry(t, repo) for t in selected]
    state["active"] = True
    state["running"] = False
    state["current"] = None
    state["completed"] = []
    state["blocked"] = []
    state["project"] = Path(repo).name
    state["repo_path"] = repo
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ キュー登録: {[t['title'] for t in selected]}")

    first = state["pending"][0]
    subprocess.Popen(
        ["setsid", "bash", str(RUN_SCRIPT), first["title"]],
        cwd=repo,
        start_new_session=True,
    )
    print(f"🚀 最初のタスク起動: {first['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
