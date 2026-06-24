#!/usr/bin/env python3
"""Daily Triage: 複数ソースからタスク候補を収集→Claude判定→today-tasks.md生成。

収集ロジック（collect_*）はパスを引数で受け取り pytest で TDD。
Claude判定は claude --print の外部APIのため手動検証（--collect-only/--no-llm で検証可能）。
"""
import argparse
import subprocess
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


def collect_handoff_latest(handoff_dir: Path) -> str | None:
    """handoff/ から最新1件（ファイル名降順）の全文を返す。

    ファイル名は YYYY-MM-DD_HHMM.md 形式で、文字列降順が最新。
    次タスク・未解決の解釈は Claude判定に委ねる（全文をそのまま渡す）。

    Args:
        handoff_dir: handoff ディレクトリのパス

    Returns:
        最新handoffの全文。ファイルが無ければ None。
    """
    if not handoff_dir.exists():
        return None
    files = sorted(handoff_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    if not files:
        return None
    return files[0].read_text(encoding="utf-8")


def build_context(backlog: list[str], green: list[str], handoff: str | None) -> str:
    """収集データを Claude判定用プロンプトに組み立てる。

    Args:
        backlog: collect_backlog() の結果
        green: collect_active_green() の結果
        handoff: collect_handoff_latest() の結果（None 可）

    Returns:
        3セクション（バックログ/🟢進行中/handoff）のテキスト
    """
    lines: list[str] = ["## バックログ（P0/P1未完了）"]
    if backlog:
        lines.extend(f"- {t}" for t in backlog)
    else:
        lines.append("（なし）")
    lines.append("")
    lines.append("## 🟢進行中タスク（他セッション占有・参考）")
    if green:
        lines.extend(green)
    else:
        lines.append("（なし）")
    lines.append("")
    lines.append("## 最新handoff")
    lines.append(handoff if handoff else "（なし）")
    return "\n".join(lines)


SSOT = Path("/home/yn4416/projects/obsidian-ssot")
STATE_DIR = Path("/home/yn4416/.claude/state")
TODAY_TASKS = STATE_DIR / "today-tasks.md"
CLAUDE_BIN = "/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"

JUDGE_PROMPT = """あなたは Daily Triage エージェント。以下の収集データから「今日取り組むべきタスク候補」を優先度順に最大5つ選び、指定フォーマットで出力せよ。

# 判定基準
- 緊急度・依存関係・コスト・リスクを総合的に判定
- 🟢進行中タスクは他セッションが対応中なら候補から除外
- バックログP0を最優先。handoffの「次のタスク」を次点
- 公務員で日中作業不可→夜1セッションで完結する粒度を優先

# 出力フォーマット（厳守・Markdown）
## 今日のタスク候補 ({date})

1. **<タスク>** — <理由>（想定コスト: <S/M/L>）
2. **<タスク>** — <理由>（想定コスト: <S/M/L>）

---
※ 人間の承認後に実行。

# 収集データ
{context}
"""


def judge_with_claude(context: str, date_str: str) -> str:
    """claude --print で優先度判定し today-tasks.md 形式の本文を返す。

    外部APIのため手動検証（pytest 対象外）。
    """
    prompt = JUDGE_PROMPT.format(context=context, date=date_str)
    result = subprocess.run(
        [CLAUDE_BIN, "--print", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude --print 失敗 (rc={result.returncode}): {result.stderr}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Triage — タスク候補生成")
    parser.add_argument(
        "--collect-only", action="store_true",
        help="収集データのみstdoutへ（Claude判定スキップ・検証用）",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="収集データをそのまま today-tasks.md へ（LLM不使用・検証用）",
    )
    parser.add_argument("--output", type=Path, default=TODAY_TASKS, help="出力先")
    args = parser.parse_args()

    backlog = collect_backlog(SSOT / "00_SYSTEM" / "バックログ.md")
    green = collect_active_green(SSOT / "00_SYSTEM" / "active-sessions.md")
    handoff = collect_handoff_latest(SSOT / "00_SYSTEM" / "handoff")
    context = build_context(backlog, green, handoff)

    if args.collect_only:
        print(context)
        return 0

    from datetime import date
    date_str = date.today().isoformat()
    body = context if args.no_llm else judge_with_claude(context, date_str)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")
    print(f"✅ today-tasks.md 生成: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
