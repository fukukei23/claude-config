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

import state_store
import tdd_gate
from daily_triage import validate_repo

STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
TODAY_TASKS = Path("/home/yn4416/.claude/state/today-tasks.md")
RUN_SCRIPT = Path("/home/yn4416/.claude/scripts/auto-dev/run-task.sh")

LINE_RE = re.compile(
    r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*[—-]\s*(.+?)"
    r"(?:（想定コスト:\s*([SML])）)?"
    r"\s*(?:（(repo:\s*.+?|手動)）)?\s*$"
)

# today-tasks.md 先頭の生成タイムスタンプ（並行再生成対策・Phase3.1課題2）。
_GENERATED_AT_RE = re.compile(r"<!--\s*generated_at:\s*([^\s>]+)\s*-->")


def parse_generated_at(text: str) -> str | None:
    """today-tasks.md 先頭の generated_at メタデータから ISO時刻文字列を抽出。

    別セッションで daily-triage.sh が再実行され today-tasks.md が書き換わると
    この時刻が進む。人間が承認時に「自分が閲覧した候補か」を照合する根拠。

    Args:
        text: today-tasks.md の全文。

    Returns:
        ISO時刻文字列（例: 2026-06-28T12:34:56）。無ければ None。
    """
    m = _GENERATED_AT_RE.search(text[:512])  # 先頭付近のみ走査
    return m.group(1) if m else None


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


def prompt_test_policy(title: str, _input=input) -> dict | None:
    """対話的にテスト方針を入力させる（F層・欄空白=起票block）。

    選択肢: 1=テスト追加必要 / 2=既存テストで網羅 / 3=該当なし（理由20字以上）。
    無効・空白は1回再問し、それでも無効なら None（該当タスク起票除外）。

    Args:
        title: タスク名（プロンプト表示用）。
        _input: 入力関数（テスト差し替え用・デフォルト input）。

    Returns:
        {"choice": 1|2|3, "reason": str} または None（起票除外）。
    """
    for _ in range(2):
        raw = _input(
            f"テスト方針 [{title}] "
            "1=テスト追加 / 2=既存で網羅 / 3=該当なし(理由20字以上): "
        ).strip()
        policy = tdd_gate.parse_test_policy(raw)
        if policy:
            return policy
        print("⚠️ 無効・空白は起票不可（1/2/3 のいずれか・3は理由20字以上）")
    return None


def build_task_entry(task: dict, repo: str) -> dict:
    """選択タスクから state.json の pending 要素を生成。

    Args:
        task: parse_today_tasks の要素（test_policy キー込み・F層）。
        repo: 実行先リポジトリの絶対パス。

    Returns:
        {title, prompt, repo, issue, test_policy}。issue は本文由来なので None。
    """
    policy = task.get("test_policy") or {}
    policy_text = f"{policy.get('choice', '')} {policy.get('reason', '')}".strip()
    prompt = (
        f"{task['title']} を実装してください。理由/背景: {task['reason']}"
    )
    if policy_text:
        prompt += f"\nテスト方針(起票時宣言・計画と実装に引き継ぐこと): {policy_text}"
    return {
        "title": task["title"],
        "prompt": prompt,
        "repo": repo,
        "issue": None,
        "test_policy": policy,
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

    raw = TODAY_TASKS.read_text(encoding="utf-8")
    tasks = parse_today_tasks(raw)
    if not tasks:
        print("候補がありません。")
        return 0

    generated_at = parse_generated_at(raw)
    if generated_at:
        print(f"=== 今日のタスク候補（生成: {generated_at}）===")
    else:
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

    # F層: テスト方針入力（欄空白・無効は起票block・D″案第一段階）
    with_policy: list[dict] = []
    for t in queueable:
        policy = prompt_test_policy(t["title"])
        if policy is None:
            print(f"⚠️ テスト方針未宣言・起票除外: {t['title']}")
            excluded.append(t)
        else:
            with_policy.append({**t, "test_policy": policy})
    queueable = with_policy

    for t in excluded:
        print(f"⚠️ 自動実行対象外・人間対応: {t['title']}")

    first_task_box = {"task": None}

    def _init_state(s: dict) -> None:
        """state を approve 用に再構築（atomic+flock 内）。"""
        s["pending"] = [build_task_entry(t, t["repo_path"]) for t in queueable]
        s["active"] = True
        s["mode"] = "manual"  # approve.py は manual entry point・auto残留防止(I1)
        s["running"] = False
        if s["pending"]:
            first = s["pending"].pop(0)
            first["started"] = False  # run-task 起動前
            s["current"] = first
            first_task_box["task"] = first
        else:
            s["current"] = None
        s["completed"] = []
        s["blocked"] = []
        s["project"] = "multi"
        s.pop("repo_path", None)  # top-level repo_path 廃止（多repoでは無意味）

    state_store.update(STATE, _init_state)
    first_task = first_task_box["task"]
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
