#!/bin/bash
# diary-write-guard.sh — 日記・SSOT追記専用ファイルへのstale全体上書きを防ぐPreToolUse hook
#
# 背景（2026-09-05 02:15日記巻き込み事故・過去同型5件）: 並行セッションが直前Read無しで
# Writeツールにより日記を全体上書きし、別セッションのcommitで誤commitされた。
# 文章ルール（ssot-record SKILL.md 3-3「既存ファイルには末尾追記」）は破られた実績があるため
# 機械ゲートで防御する（設計: 00_SYSTEM/マルチLLMレビュー/2026-09-05_日記巻き込み再発防止G案/・
# 2ラウンド3機レビュー51件統合のG″案）。
#
# ゲート構成（G″）:
#   硬ゲート(deny): 追記専用リスト（diary-write-guard-list.conf glob）の既存ファイルへのWrite
#     - bypass: marker（TTL・既定300s）+ 同一パス×同一セッション 1回目のみ許可(bypass_1st)・2回目はdeny
#     - 新規作成は当日日付(10_DAILY/YYYY-MM-DD.md の当日)のみ許可・symlink/hardlinkは拒否
#   Edit: replace_all=true / 空old_string → deny・old_string 3行超 → ask・通常追記は許可
#   柔ゲート(ask): 日記以外の既存.mdへのWriteで (行数比率30%超減 AND 絶対10行超減) OR Byte長30%未満
#   Bash層ゲート(ask): SSOT内.mdへのリダイレクト上書きパターン（> / tee / sed -i）→ ask
#     ※文字列解析のため回避可能 = 第1.5防線・最終防線はcommit層（期限付き後続）
#   軽量Read追跡: Read時のmtimeを記録し、Write/Edit時にmtime不一致 → ask（stale検知の軽量版）
#
# 動作モード（DIARY_GUARD_MODE・既定=shadow）:
#   shadow  — 判定をすべて決定ログに記録するが block/ask は出さない（導入期1週間の誤検知観察用）
#   enforce — deny/ask を permissionDecision JSON として出力
#
# 出力: exit 0 常時（パース不能・対象外パスは無判断で即通過・決定ログに出ない）
# 判定ログ: ~/.claude/state/diary-write-guard/decisions.jsonl（沈黙検知の一次情報）

set -uo pipefail

INPUT=$(cat)

DIARY_GUARD_INPUT="$INPUT" python3 << 'PYEOF'
import json, os, re, sys, time, fnmatch

try:
    d = json.loads(os.environ.get("DIARY_GUARD_INPUT", "{}"))
except Exception:
    sys.exit(0)  # パース不能は許可（他hookに任せる）

tool = d.get("tool_name", "")
if tool not in ("Write", "Edit", "Bash", "Read"):
    sys.exit(0)
ti = d.get("tool_input", d)
if not isinstance(ti, dict):
    sys.exit(0)
session = (d.get("session_id", "") or "unknown")

SSOT_ROOT = os.path.normpath(os.environ.get("DIARY_GUARD_SSOT_ROOT", "/home/yn4416/projects/obsidian-ssot"))
STATE_DIR = os.path.expanduser(os.environ.get("DIARY_GUARD_STATE", "~/.claude/state/diary-write-guard"))
LIST_FILE = os.path.expanduser(os.environ.get("DIARY_GUARD_LIST", "~/.claude/scripts/hooks/diary-write-guard-list.conf"))
MODE = os.environ.get("DIARY_GUARD_MODE", "shadow")
TTL = int(os.environ.get("DIARY_GUARD_TTL", "300"))

def norm(p):
    """パス正規化（Windows版表記差対応・2026-08-30 既存hookと同対応）"""
    p = (p or "").replace("\\\\", "/")
    if p.startswith("//wsl.localhost/Ubuntu"):
        p = p[len("//wsl.localhost/Ubuntu"):]
    if p.startswith("~"):
        p = os.path.expanduser(p)
    return os.path.normpath(p)

def under_ssot(fp):
    try:
        return os.path.commonpath([fp, SSOT_ROOT]) == SSOT_ROOT
    except Exception:
        return False

def append_line(fname, obj):
    """決定・追跡ログ追記（ログ失敗でhook自体は止めない）"""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, fname), "a") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass

def emit(decision, reason, path=""):
    """決定ログ記録→shadowなら黙って終了・enforceならdeny/askをJSON出力"""
    append_line("decisions.jsonl", {"ts": time.time(), "tool": tool, "path": path, "decision": decision, "reason": reason.split(":")[0], "mode": MODE})
    if MODE == "enforce" and decision in ("deny", "ask"):
        msg = "[diary-write-guard] %s: %s（設計: マルチLLMレビュー2026-09-05 G″案・誤検知時はふくけい確認の上調整）" % (decision, reason)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": msg
            }
        }, ensure_ascii=False))
    sys.exit(0)

def in_append_list(rel):
    try:
        with open(LIST_FILE) as f:
            pats = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except Exception:
        pats = ["10_DAILY/*.md"]  # 設定欠落時は日記のみに縮退（fail-safe側）
    return any(fnmatch.fnmatch(rel, p) for p in pats)

def bypass_active():
    p = os.path.join(STATE_DIR, "bypass-active")
    try:
        return (time.time() - os.path.getmtime(p)) < TTL
    except Exception:
        return False

def bypass_count(fp):
    """TTL内の同一パス×同一セッションのbypass使用回数"""
    p = os.path.join(STATE_DIR, "bypass.jsonl")
    n = 0
    try:
        now = time.time()
        for l in open(p):
            try:
                e = json.loads(l)
            except Exception:
                continue
            if e.get("path") == fp and e.get("session") == session and (now - e.get("ts", 0)) < TTL:
                n += 1
    except Exception:
        pass
    return n

def is_stale(fp):
    """軽量Read追跡: 同一セッションのRead記録mtimeが現在と不一致 → stale"""
    p = os.path.join(STATE_DIR, "reads.jsonl")
    try:
        cur = os.stat(fp).st_mtime
        now = time.time()
        for l in open(p):
            try:
                e = json.loads(l)
            except Exception:
                continue
            if e.get("session") == session and e.get("path") == fp and (now - e.get("ts", 0)) < 3600:
                if abs(e.get("mtime", cur) - cur) > 0.001:
                    return True
    except Exception:
        pass
    return False

def handle_read():
    fp = norm(ti.get("file_path", ""))
    if fp.endswith(".md") and under_ssot(fp) and os.path.isfile(fp):
        try:
            append_line("reads.jsonl", {"ts": time.time(), "session": session, "path": fp, "mtime": os.stat(fp).st_mtime})
        except Exception:
            pass
    sys.exit(0)

def handle_write():
    fp = norm(ti.get("file_path", ""))
    if not fp.endswith(".md") or not under_ssot(fp):
        sys.exit(0)  # 対象外は即通過（決定ログにも出さない=早期return）
    rel = os.path.relpath(fp, SSOT_ROOT)
    exists = os.path.isfile(fp)
    if not in_append_list(rel):
        if not exists:
            sys.exit(0)  # 非対象の新規作成は自由
        if is_stale(fp):
            emit("ask", "stale_ask: Read後に他者が更新（mtime不一致）・再Readを推奨", fp)
        try:
            old = open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            old = ""
        new = ti.get("content", "") or ""
        ol, nl = len(old.splitlines()), len(new.splitlines())
        shrink_ratio = nl < ol * 0.7 and (ol - nl) > 10
        shrink_bytes = len(new.encode("utf-8", "replace")) < len(old.encode("utf-8", "replace")) * 0.3
        if (ol > 0 and (shrink_ratio or shrink_bytes)):
            emit("ask", "soft_ask: 既存.mdの大幅削減(比率30%%超減×10行超 or Byte30%%未満)・全面上書き疑い", fp)
        emit("pass", "soft_pass", fp)
    # 以下: 追記専用リスト対象
    if not exists:
        expected = "10_DAILY/" + time.strftime("%Y-%m-%d") + ".md"
        is_special = os.path.islink(fp) or (os.path.exists(fp) and os.stat(fp).st_nlink > 1)
        if rel == expected and not is_special:
            emit("pass", "new_today_ok", fp)
        emit("deny", "append_only_new_not_today: 新規作成は当日日付のみ・symlink/hardlink不可", fp)
    if bypass_active():
        if bypass_count(fp) == 0:
            append_line("bypass.jsonl", {"ts": time.time(), "session": session, "path": fp})
            emit("bypass_1st", "bypass_1st: 同一パス×同一セッションの1回目のみ許可・2回目はdeny", fp)
        emit("deny", "bypass_exhausted: bypassは同一パス×同一セッションで1回まで", fp)
    emit("deny", "append_only_overwrite: 追記専用ファイルへの全体上書きはdeny・Read後にEditで追記可", fp)

def handle_edit():
    fp = norm(ti.get("file_path", ""))
    if not fp.endswith(".md") or not under_ssot(fp):
        sys.exit(0)
    if not os.path.isfile(fp):
        sys.exit(0)
    rel = os.path.relpath(fp, SSOT_ROOT)
    if in_append_list(rel):
        if ti.get("replace_all") is True:
            emit("deny", "edit_replace_all: 追記専用ファイルでのreplace_allはdeny", fp)
        if not (ti.get("old_string", "") or "").strip():
            emit("deny", "edit_empty_old: 空old_stringは全体上書りと同等のためdeny", fp)
        if len((ti.get("old_string", "") or "").splitlines()) > 3:
            emit("ask", "edit_long_old: old_string 3行超は改変疑い・追記は短いアンカーで", fp)
        if is_stale(fp):
            emit("ask", "stale_ask: Read後に他者が更新（mtime不一致）・再Readを推奨", fp)
        emit("pass", "edit_append_ok", fp)
    if is_stale(fp):
        emit("ask", "stale_ask: Read後に他者が更新（mtime不一致）・再Readを推奨", fp)
    emit("pass", "edit_pass", fp)

def handle_bash():
    cmd = ti.get("command", "") or ""
    pats = [
        r"(?<!>)>\s*([^\s;&|\"']+\.md)",      # > file.md（>> は除外）
        r"\btee\s+(?!-a)([^\s;&|\"']+\.md)",   # tee file.md（tee -a は追記で除外）
        r"\bsed\b[^\n;&|]*-i[^\n;&|]*\s+([^\s;&|\"']+\.md)",  # sed -i file.md
    ]
    for pat in pats:
        for m in re.finditer(pat, cmd):
            fp = norm(m.group(1))
            if fp.endswith(".md") and under_ssot(fp):
                # 文字列解析のため回避可能 = 第1.5防線・最終防線はcommit層
                emit("ask", "bash_overwrite: SSOT内.mdへのリダイレクト上書きパターン検知", fp)

if tool == "Read":
    handle_read()
elif tool == "Write":
    handle_write()
elif tool == "Edit":
    handle_edit()
elif tool == "Bash":
    handle_bash()
sys.exit(0)
PYEOF
