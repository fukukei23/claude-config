#!/usr/bin/env python3
"""Daily Triage: 複数ソースからタスク候補を収集→Claude判定→today-tasks.md生成。

収集ロジック（collect_*）はパスを引数で受け取り pytest で TDD。
Claude判定は claude --print の外部APIのため手動検証（--collect-only/--no-llm で検証可能）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

# handoff ファイル名形式（YYYY-MM-DD_HHMM.md）。
# handoff_prompt.md のような非日付の固定名ファイルを「最新」誤認して拾わないためのフィルタ。
_HANDOFF_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}\.md$")

# バックログタスク行末の日付（M/D）。年は today 基準で推定。
# 「（5/19完了）」「（6/26）」等の最初の M/D を拾う。
_TASK_DATE_RE = re.compile(r"（\s*(\d{1,2})/(\d{1,2})")

# stale 判定閾値（日）。超えると ⚠stale マークで実装AIの空振りを防ぐ。
STALE_DAYS = 30
_STALE_PREFIX = "⚠stale "


def parse_task_date(text: str, today: date | None = None) -> date | None:
    """タスク本文行末の (M/D...) から日付を抽出。年は today 基準で推定。

    バックログの日付表記「（5/19完了）」「（6/26）」等の最初の M/D を拾う。
    M/D が today の月日より未来なら前年扱い（年跨ぎの古いタスク）。
    日付無し・パース失敗は None（stale 判定不可＝マーク付けず）。

    Args:
        text: タスク本文（"- [ ]" 除去後）。
        today: 基準日（None なら date.today()・テストで注入）。

    Returns:
        抽出した date。無ければ None。
    """
    m = _TASK_DATE_RE.search(text)
    if not m:
        return None
    today = today or date.today()
    month, day = int(m.group(1)), int(m.group(2))
    try:
        candidate = date(today.year, month, day)
    except ValueError:  # 不正月日（13/40等）
        return None
    if candidate > today:
        candidate = date(today.year - 1, month, day)
    return candidate


def collect_backlog(path: Path, today: date | None = None) -> list[str]:
    """バックログからP0/P1未完了タスク([ ])を抽出。P2・完了済みセクションは除外。

    30日(STALE_DAYS)超のタスクには ⚠stale マークを付与し、LLM判定で優先度を
    下げる根拠とする（古い前提のタスクで実装AIが空振りするのを防止）。

    Args:
        path: バックログ.md のパス
        today: stale 判定の基準日（None なら date.today()・テストで注入）。

    Returns:
        タスク本文のリスト（"- [ ]" マーカー除去済み・stale なら prefix付与）
    """
    if not path.exists():
        return []
    today = today or date.today()
    tasks: list[str] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## P0:") or line.startswith("## P1:"):
            section = line
        elif line.startswith("## P2:") or line.startswith("## 完了済み"):
            section = ""
        elif line.startswith("- [ ]") and section:
            body = line[5:].strip()  # "- [ ]" (5文字) を除去
            task_date = parse_task_date(body, today=today)
            if task_date is not None and (today - task_date).days > STALE_DAYS:
                body = _STALE_PREFIX + body
            tasks.append(body)
    return tasks


def collect_active_green(path: Path) -> list[str]:
    """active-sessions.md の 🟢進行中タスク表の行を抽出。

    単一表化（2026-07-02〜）に対応した実装。旧 "## 🟢" セクション方式と
    単一表 "## セッション状態" 状態列方式の両方に対応（後方互換）。

    単一表形式では、ヘッダー行から「状態」列のインデックスを動的に特定し
    （列順序変更耐性）、その列の値が 🟢 の行のみを抽出する。

    Args:
        path: active-sessions.md のパス

    Returns:
        テーブル行（"|" 始まり）のリスト
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")

    # 新形式: 単一表（## セッション状態 セクション内、状態列が 🟢 の行）
    new_format_rows = _collect_single_table_green(text)
    if new_format_rows:
        return new_format_rows

    # 新形式で該当なし → 旧形式にフォールバック（後方互換）
    return _collect_legacy_green(text)


def _is_table_row(line: str) -> bool:
    """テーブル行（"| ... |" で空白以外で開始）か判定"""
    return line.startswith("| ") and not line.startswith("|---") and not line.startswith("|- ")


def _is_header_row(line: str) -> bool:
    """テーブルヘッダー行か判定（カラム名を含む）"""
    lowered = line.lower()
    return any(h in lowered for h in (
        "| セッション", "| タスク", "| 環境", "| 開始", "| 状態",
        "| 触る共通ファイル", "| 方針",
    ))


def _collect_legacy_green(text: str) -> list[str]:
    """旧形式 "## 🟢" セクションのテーブル行を抽出（後方互換）。

    2026-07-02 単一表化前のアクティブセッション定義。
    新形式で該当が無い場合のみフォールバック実行。
    """
    rows: list[str] = []
    in_green = False
    for line in text.splitlines():
        if line.startswith("## 🟢"):
            in_green = True
            continue
        if in_green and line.startswith("## "):
            break
        if in_green and _is_table_row(line) and not _is_header_row(line):
            rows.append(line)
    return rows


def _collect_single_table_green(text: str) -> list[str]:
    """単一表形式の active-sessions.md から 🟢 行を抽出。

    "## セッション状態" セクション内のテーブルから、「状態」列の値が 🟢 の行を返す。
    列インデックスはヘッダー行から動的に取得（列順変更耐性・Geminiレビュー指摘反映）。
    """
    rows: list[str] = []
    in_section = False
    status_col_index = -1
    for line in text.splitlines():
        # セッション状態セクションの検出
        if line.startswith("## セッション状態"):
            in_section = True
            status_col_index = -1
            continue
        # 別セクションで終了
        if in_section and line.startswith("## ") and not line.startswith("## セッション状態"):
            in_section = False
            continue
        if not in_section:
            continue
        # ヘッダー行: 「状態」列のインデックスを動的に特定
        if _is_header_row(line):
            header_cells = [c.strip() for c in line.split("|") if c.strip()]
            if "状態" in header_cells:
                status_col_index = header_cells.index("状態")
            continue
        # テーブル行の判定（ヘッダー・区切り行は除外）
        if not _is_table_row(line):
            continue
        # 状態列が特定できていない場合はスキップ
        if status_col_index == -1:
            continue
        # 状態列の値が 🟢 か判定
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) > status_col_index and cells[status_col_index] == "🟢":
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
    files = sorted(
        [p for p in handoff_dir.glob("*.md") if _HANDOFF_DATE_RE.match(p.name)],
        key=lambda p: p.name,
        reverse=True,
    )
    if not files:
        return None
    return files[0].read_text(encoding="utf-8")


def collect_repo_names(repo_index: Path) -> list[str]:
    """repo-index.yaml からリポジトリ名一覧を抽出（LLMのrepo選択制約用）。

    Args:
        repo_index: repo-index.yaml のパス。

    Returns:
        リポジトリ名のリスト。ファイル無ければ空。
    """
    if not repo_index.exists():
        return []
    names: list[str] = []
    for line in repo_index.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            names.append(stripped[len("- name:"):].strip())
    return names


def collect_issues() -> list[str]:
    """fetch_issues.run() で auto-loop ラベル Issue を取得し候補文字列化。

    fetch_issues インポート失敗・0件時は空リスト（Daily Triage を止めない）。

    Returns:
        Issue 候補のリスト（today-tasks.md 混入用）。
    """
    try:
        import fetch_issues
        tasks = fetch_issues.run()
    except Exception:
        return []
    return [f"{t['title']}（repo: {Path(t['repo']).name}・Issue #{t['issue']}）" for t in tasks]


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
PROJECTS_DIR = Path("/home/yn4416/projects")


def validate_repo(repo_name: str, projects_dir: Path = PROJECTS_DIR) -> str | None:
    """repo名→実在チェック。実在するディレクトリなら絶対パス、非実在/空は None。

    Args:
        repo_name: リポジトリ名（~/projects/ 配下のディレクトリ名）。
        projects_dir: 親ディレクトリ（デフォルト ~/projects・テストで注入）。

    Returns:
        実在すれば絶対パス・非実在/空なら None。
    """
    if not repo_name:
        return None
    path = projects_dir / repo_name
    return str(path) if path.is_dir() else None


def _resolve_claude_bin() -> str:
    """claude CLI のパスを解決。fnmハードコード優先、なければPATHから探す。

    fnmのバージョン固有パスは既存(start.sh等)と一貫させるため優先。
    バージョンアップでパスが消えた場合はPATH上のclaudeにフォールバック。
    """
    hardcoded = "/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"
    if Path(hardcoded).exists():
        return hardcoded
    found = shutil.which("claude")
    if found:
        return found
    raise RuntimeError("claude CLI が見つかりません（fnmパス・PATHいずれにもなし）")


CLAUDE_BIN = _resolve_claude_bin()

JUDGE_PROMPT = """あなたは Daily Triage エージェント。以下の収集データから「今日取り組むべきタスク候補」を優先度順に最大5つ選び、指定フォーマットで出力せよ。

# 判定基準
- 緊急度・依存関係・コスト・リスクを総合的に判定
- 🟢進行中タスクは他セッションが対応中なら候補から除外
- バックログP0を最優先。handoffの「次のタスク」を次点
- 公務員で日中作業不可→夜1セッションで完結する粒度を優先
- 各タスクの対象リポジトリを repo_list から選び (repo: <name>) で付与
- コード作業でない（応募・学習・手動運用・リポジトリ外）は (手動) を付与
- 「⚠stale」マーク付きタスクは30日以上更新のない旧タスク。前提が古い可能性があるため、候補に入れる場合は理由を明記し優先度を下げること

# repo_list（この中から選ぶ・該当無しは (手動)）
{repo_list}

# 出力フォーマット（厳守・Markdown）
## 今日のタスク候補 ({date})

1. **<タスク>** — <理由>（想定コスト: <S/M/L>）（repo: <name>） または （手動）
2. **<タスク>** — <理由>（想定コスト: <S/M/L>）（repo: <name>） または （手動）

---
※ 人間の承認後に実行。

# 収集データ
{context}
"""


def judge_with_claude(context: str, date_str: str, repo_list: list[str]) -> str:
    """claude --print で優先度判定し today-tasks.md 形式の本文を返す。

    外部APIのため手動検証（pytest 対象外）。
    """
    prompt = JUDGE_PROMPT.format(
        context=context, date=date_str, repo_list=", ".join(repo_list)
    )
    result = subprocess.run(
        [CLAUDE_BIN, "--print", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude --print 失敗 (rc={result.returncode}): {result.stderr}")
    return result.stdout.strip()


DISCORD_WEBHOOK_ENV = "DISCORD_CLAUDE_WEBHOOK"
DISCORD_MAX_CHARS = 2000


def send_discord(content: str, webhook_url: str, max_chars: int = DISCORD_MAX_CHARS) -> bool:
    """Discord webhook にメッセージを送信する。

    2000文字（Discord上限）超は切り詰めて送信。外部通信のため pytest では
    urllib.request.urlopen を monkeypatch して検証。

    Args:
        content: 送信するメッセージ本文。
        webhook_url: Discord webhook URL。
        max_chars: メッセージ文字数上限（Discord仕様で2000）。

    Returns:
        送信成功なら True、失敗・例外時は False。
    """
    import urllib.request
    payload = json.dumps({"content": content[:max_chars]}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "ClaudeCode-DailyTriage/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


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
    parser.add_argument(
        "--notify-discord", action="store_true",
        help="today-tasks.md 生成後、Discord webhook に候補を通知",
    )
    args = parser.parse_args()

    backlog = collect_backlog(SSOT / "00_SYSTEM" / "バックログ.md")
    green = collect_active_green(SSOT / "00_SYSTEM" / "active-sessions.md")
    handoff = collect_handoff_latest(SSOT / "00_SYSTEM" / "handoff")
    repo_list = collect_repo_names(SSOT / "00_SYSTEM" / "repo-index.yaml")
    context = build_context(backlog, green, handoff)
    issues = collect_issues()
    if issues:
        context = context + "\n\n## OSS Issue 候補（auto-loop ラベル）\n" + "\n".join(f"- {i}" for i in issues)

    if args.collect_only:
        print(context)
        return 0

    date_str = date.today().isoformat()
    body = context if args.no_llm else judge_with_claude(context, date_str, repo_list)

    # 並行再生成対策: 生成タイムスタンプを埋め込み、approve.py で人間が承認時に
    # 「自分が閲覧した候補か」を照合できるようにする（別セッションで再生成されると時刻が進む）
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    body = f"<!-- generated_at: {generated_at} -->\n{body}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")
    print(f"✅ today-tasks.md 生成: {args.output}（生成時刻: {generated_at}）")

    if args.notify_discord:
        webhook_url = os.environ.get(DISCORD_WEBHOOK_ENV, "")
        if not webhook_url:
            print(f"⚠️ {DISCORD_WEBHOOK_ENV} 未設定・Discord通知スキップ")
        elif send_discord(body, webhook_url):
            print(f"✅ Discord通知送信完了")
        else:
            print(f"⚠️ Discord通知失敗（webhook送信エラー）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
