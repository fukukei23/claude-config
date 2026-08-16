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
import sys
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


def collect_wants(path: Path) -> list[str]:
    """バックログ.mdの🎯要望(Why)セクションから W1〜W4 を抽出。

    セクション検出は collect_backlog と同じ行頭パターン方式。要望行(^- W[0-9]:)を
    本文付きで返す。LLM contextでタスク選択の軸として使用（行末の←Wx逆参照と照合）。
    """
    if not path.exists():
        return []
    wants: list[str] = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 🎯 要望"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and re.match(r"^- W[0-9]:", line):
            wants.append(line)
    return wants


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


def build_context(backlog: list[str], green: list[str], handoff: str | None, wants: list[str] | None = None, stale_section: str = "") -> str:
    """収集データを Claude判定用プロンプトに組み立てる。

    Args:
        backlog: collect_backlog() の結果
        green: collect_active_green() の結果
        handoff: collect_handoff_latest() の結果（None 可）
        wants: collect_wants() の結果（None 可・🎯要望層・タスク選択の軸）
        stale_section: format_stale_section() の結果（None or 空 → 出力しない）

    Returns:
        セクション（要望/バックログ/🟢進行中/stale/handoff）のテキスト
    """
    lines: list[str] = []
    if wants:
        lines.append("## 🎯要望（Why）— タスク選択の軸")
        lines.extend(wants)
        lines.append("")
    if stale_section:
        lines.append(stale_section)
    lines.append("## バックログ（P0/P1未完了）")
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
OUTWARD_REPLY_LOG = SSOT / "00_SYSTEM" / "参考資料" / "外向き返信実績" / "log.md"


def format_outward_reply_section(log_path: Path) -> str:
    """外向き返信ログの件数・結果未入力数を表示セクション化（spec 2026-08-16）。

    Args:
        log_path: log.md のパス（存在しない → 空文字で出力しない）

    Returns:
        セクション文字列（未入力率>40%で分析停止ガード行つき・ログ無しは ""）
    """
    if not log_path.exists():
        return ""
    rows = [ln for ln in log_path.read_text(encoding="utf-8").splitlines()
            if ln.startswith("| 2") and "|" in ln[1:]]
    if not rows:
        return ""
    total = len(rows)
    pending = sum(1 for r in rows if r.rstrip().endswith("未定 |") or r.rstrip().endswith("未定|"))
    lines = [f"## 📮外向き返信ログ: {total}件（結果未入力{pending}件）"]
    if pending / total > 0.4:
        lines.append("- ⚠️ 結果未入力率>40% — 分析提案停止（データ品質ガード・spec）")
    return "\n".join(lines)


def monthly_review_hint(today: date, state_dir: Path) -> str:
    """月次集計の提案ヒント（月1回・1〜7日のみ・spec 2026-08-16）。

    Args:
        today: 基準日（テストで注入）
        state_dir: doneフラグ置き場（~/.claude/state）

    Returns:
        ヒント文字列（提案時はdoneフラグを作成・条件外は ""）
    """
    if today.day > 7:
        return ""
    flag = state_dir / f"outward-reply-monthly-{today.strftime('%Y-%m')}.done"
    if flag.exists():
        return ""
    state_dir.mkdir(parents=True, exist_ok=True)
    flag.write_text("done", encoding="utf-8")
    return ("- 💡月次集計候補: outward-replyログの月次分析を本セッションで提案"
            "（類型別頻度・修正率・結果相関・データヘルシ度・改善提案は上位3件まで）")


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

# LLM応答の構造検証（D'案・2026-07-14）。
# 文字数下限は空応答の、必須ヘッダ/箇条書きは中身が壊れた応答の検知用。
MIN_BODY_CHARS = 100
REQUIRED_HEADER = "## 今日のタスク候補"
_GENERATED_AT_RE = re.compile(r"<!-- generated_at: (\d{4}-\d{2}-\d{2})T")
_NUMBERED_LIST_RE = re.compile(r"(?m)^\d+\.\s")


def validate_judge_output(body: str, min_chars: int = MIN_BODY_CHARS) -> str:
    """LLM判定結果の構造検証。無効なら RuntimeError。

    rc=0 でも空/壊れた応答を返す claude --print の事故（2026-07-13）を検知する。
    文字数下限（空検知）＋必須ヘッダ・数字箇条書き（中身の形検知）の3層。

    Args:
        body: judge_with_claude の生応答。
        min_chars: 最小文字数（デフォルト100・正常時は2457バイト）。

    Returns:
        検証OKなら body をそのまま返す。

    Raises:
        RuntimeError: 空/短すぎる・必須ヘッダ不在・箇条書き不在。
    """
    stripped = body.strip()
    if len(stripped) < min_chars:
        raise RuntimeError(f"LLM応答が短すぎます ({len(stripped)}文字 < 下限{min_chars})")
    if REQUIRED_HEADER not in stripped:
        raise RuntimeError(f"LLM応答に必須ヘッダ不在: '{REQUIRED_HEADER}'")
    if not _NUMBERED_LIST_RE.search(stripped):
        raise RuntimeError("LLM応答に数字箇条書き不在")
    return body


def is_generated_today(path: Path, today_str: str) -> bool:
    """today-tasks.md が当日日付で既に生成済みか（当日重複実行防止・D'案核心）。

    flock は「秒差の同時実行」しか防げず「分差の再実行」は防げない（17分差事故）。
    generated_at タイムスタンプが当日と一致すれば「今日分は生成済み」と判定し skip する。

    Args:
        path: today-tasks.md のパス。
        today_str: 当日日付（YYYY-MM-DD）。

    Returns:
        当日生成済みなら True・未生成/別日/ファイル不在/旧形式なら False。
    """
    if not path.exists():
        return False
    match = _GENERATED_AT_RE.search(path.read_text(encoding="utf-8"))
    return bool(match and match.group(1) == today_str)


JUDGE_PROMPT = """あなたは Daily Triage エージェント。以下の収集データから「今日取り組むべきタスク候補」を優先度順に最大5つ選び、指定フォーマットで出力せよ。

# 判定基準
- 緊急度・依存関係・コスト・リスクを総合的に判定
- 🟢進行中タスクは他セッションが対応中なら候補から除外
- バックログP0を最優先。handoffの「次のタスク」を次点
- タスク行末の ←W1 等の逆参照と上記🎯要望(W1〜W4)を照合し、動機に合致するタスク・複数の要望に効くタスクを優先
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
    return validate_judge_output(result.stdout)


DISCORD_WEBHOOK_ENV = "DISCORD_CLAUDE_WEBHOOK"
DISCORD_MAX_CHARS = 2000


# ============== L98 stale🟢検知 ==============
HEARTBEAT_DEFAULT_THRESHOLD = 12
LONG_RUN_DEFAULT_THRESHOLD = 72
DEFAULT_STALE_CHECK_SCRIPT = Path.home() / ".claude" / "scripts" / "obsidian" / "check-stale-sessions.sh"


def detect_stale_green(
    active_sessions: Path,
    heartbeat_dir: Path,
    handoff_dir: Path,
    *,
    threshold: int = HEARTBEAT_DEFAULT_THRESHOLD,
    long_threshold: int = LONG_RUN_DEFAULT_THRESHOLD,
    script_path: Path | None = DEFAULT_STALE_CHECK_SCRIPT,
) -> str:
    """check-stale-sessions.sh を呼び出し、結果JSON配列を返す。

    シェルスクリプト不在/失敗時は空配列を返す（fail-safe：Daily Triageを止めない）。

    Args:
        active_sessions: active-sessions.md のパス
        heartbeat_dir: WT4別 heartbeat ディレクトリ
        handoff_dir: handoff ディレクトリ
        threshold: デフォルト閾値（時間）
        long_threshold: [長時間]行の閾値（時間）
        script_path: check-stale-sessions.sh のパス（既定値あり）

    Returns:
        JSON配列文字列（例: '[{"id": "df70", ...}]'）
    """
    if script_path is None or not script_path.exists():
        return "[]"
    ssot_root = active_sessions.parent.parent  # 00_SYSTEM の親 = SSOT root
    try:
        result = subprocess.run(
            [
                "bash", str(script_path),
                "--json",
                "--threshold", str(threshold),
                "--long-threshold", str(long_threshold),
                "--ssot-path", str(ssot_root),
                "--heartbeat-dir", str(heartbeat_dir),
                "--handoff-dir", str(handoff_dir),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode not in (0, 1):  # 0=stale無し, 1=stale有り=正常
            return "[]"
        return result.stdout.strip() or "[]"
    except Exception:
        return "[]"


def format_stale_section(stale: list[dict]) -> str:
    """stale🟢候補を Markdown セクション文字列に整形。

    空リスト → 空文字列（セクション自体出さない）。
    """
    if not stale:
        return ""
    lines = ["", "## ⚠停滞🟢確認（人間が✅化してください）", ""]
    for r in stale:
        age = r.get("age_hours")
        age_str = f"{age}h" if age is not None else "不明(証跡無)"
        long_marker = " [長時間]" if r.get("is_long_run") else ""
        threshold_h = r.get("threshold_hours", HEARTBEAT_DEFAULT_THRESHOLD)
        reason = r.get("reason", "unknown")
        sid = r.get("id", "?")
        session_name = r.get("session", "")
        lines.append(f"- **{sid}**{long_marker} | 経過: {age_str} | 閾値: {threshold_h}h | 理由: {reason}")
        lines.append(f"  - タスク: {session_name}")
    lines.append("")
    lines.append("※ 上記🟢行が古い=セッション死亡の可能性大。`active-sessions.md` を確認して✅化してください。")
    lines.append("")
    return "\n".join(lines)


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
    if len(content) > max_chars:
        content = content[: max_chars - 30] + "\n…(Discord文字数上限で省略)"
    payload = json.dumps({"content": content}).encode("utf-8")
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
    wants = collect_wants(SSOT / "00_SYSTEM" / "バックログ.md")
    repo_list = collect_repo_names(SSOT / "00_SYSTEM" / "repo-index.yaml")
    # L98 stale🟢検知: build_context に渡す前に JSON 取得
    stale_json = detect_stale_green(
        SSOT / "00_SYSTEM" / "active-sessions.md",
        Path.home() / ".claude" / "state" / "heartbeat",
        SSOT / "00_SYSTEM" / "handoff",
    )
    stale_list = json.loads(stale_json) if stale_json else []
    context = build_context(backlog, green, handoff, wants, stale_section=format_stale_section(stale_list))
    issues = collect_issues()
    if issues:
        context = context + "\n\n## OSS Issue 候補（auto-loop ラベル）\n" + "\n".join(f"- {i}" for i in issues)

    if args.collect_only:
        print(context)
        return 0

    date_str = date.today().isoformat()

    # 当日重複実行防止（D'案核心・2026-07-14）: 当日分が既に生成済みなら skip。
    # flock は「秒差の同時実行」しか防げず「分差の再実行」は防げない（17分差事故）。
    # --no-llm（検証モード）では強制再生成を許可する。
    if not args.no_llm and is_generated_today(args.output, date_str):
        print(f"⏭️ 当日分の today-tasks.md 生成済み ({args.output})。スキップします。")
        return 0

    try:
        body = context if args.no_llm else judge_with_claude(context, date_str, repo_list)
    except RuntimeError as e:
        # LLM判定失敗時のフォールバック: 収集生データで代用＋失敗原因を可視化（空通知防止）。
        # catch範囲はLLM判定のみ（ファイル書込/Discord失敗ではフォールバックしない）。
        err = str(e)
        print(f"⚠️ LLM判定失敗・フォールバック（収集生データで代用）: {err}", file=sys.stderr)
        body = f"<!-- ⚠LLM判定失敗・収集生データで代用 -->\n<!-- 原因: {err} -->\n{context}"

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
