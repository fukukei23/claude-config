#!/usr/bin/env bash
# git-commit-diff-check.sh — git commit の stage 内容を検査するPreToolUse Hook
# 行数判定: ±10行超=warn(stderr/exit0)・±20行超=block(exit2)・DRY_RUN=1でblock無効・SSOT_AUTO_SYNC=1で除外
# 宣言ベース判定(v3・2026-08-29): paths.json宣言との突合
#   (a) 他🟢タブ活性宣言一致+自タブ宣言外 → block候補
#   (b) 全宣言外+delta>閾値(通常±20/自ID不明時±5) → block候補
#   自タブ宣言内はblockしない(±20超は理由付きwarn)・stale宣言は案内warn
#   PATHS_BLOCK_MODE=shadow(既定・SHADOW_BLOCKログのみ)|enforce(block発動)
#   判定不能時はDEGRADED(通す+緊急警告) — 静かな失敗にしない
# 守備範囲: Claude Code経由commitのみ(--no-verify/worktree/IDE/CIは監査層が担当)
# 8/4型(他タブ48行巻き込み)事故の再発防止・spec §1 + revised_proposal_v3_final.md
set -uo pipefail

# 観測ロガー(F案・spec §1.6) — flock排他・|| true fallback・1MB rotation
# 書込失敗はhook本体に影響させない（doubt-driven #4 fallback）
LOG_FILE="${GIT_COMMIT_DIFF_CHECK_LOG:-$HOME/.claude/state/git-commit-diff-check.log}"
log_append() {
  local entry="$1"
  (
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    flock -w 1 200 2>/dev/null || true
    printf '[%s] %s\n' "$(date '+%F %T')" "$entry" >> "$LOG_FILE" 2>/dev/null || true
    local sz
    sz=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$sz" -gt 1048576 ]; then
      tail -c 524288 "$LOG_FILE" > "${LOG_FILE}.tmp" 2>/dev/null && mv "${LOG_FILE}.tmp" "$LOG_FILE" 2>/dev/null || true
    fi
  ) 200>"${LOG_FILE}.lock" 2>/dev/null || true
}

# block stderr出力（L279③・2026-09-04）: REQUIRED_ACTION を実行可能手順に書き換え
# (1) 自分の意図した大量変更 → paths.json に宣言追加して再commit（宣言内はwarnのみで通過）
# (2) 巻き込み混入 → git restore --staged で除外して再commit
emit_block() {
  local file="$1" delta="$2" hits="${3:-$1}"
  # paths-json-update.py への案内はrepoルート起点の絶対パスにする（2026-09-05修正）。
  # paths-json-update.py の norm() は os.path.abspath をcwd基準で行うため、repo相対の
  # ${file} をそのまま渡すと呼び出し時のcwd(通常$HOME付近)基準で誤ったパスに解決され、
  # 宣言してもblockが解消しない実害があった(Windows Desktop実運用で実測)。
  local abs_file
  abs_file=$(cd "$TARGET_DIR" 2>/dev/null && realpath -m -- "$file" 2>/dev/null)
  [ -z "$abs_file" ] && abs_file="$TARGET_DIR/$file"
  cat >&2 <<EOF
[GIT-COMMIT-DIFF-CHECK]
EXIT_CODE=2
REASON=stage変動が1ファイル±${BLOCK_THRESHOLD}行超を検出: ${file} (max delta=${delta})
MAX_DELTA=${delta}
FILE=${file}
REQUIRED_ACTION=意図した変更なら (1) python3 $HOME/.claude/scripts/session/paths-json-update.py ${SELF_WT4:-<自タブWT4>} '${abs_file}' を実行して宣言追加後に再commit（宣言内はwarnのみで通過） / 巻き込みなら (2) git restore --staged '${file}' で除外して再commit / 一時的に判定を無効化する場合 (3) DRY_RUN=1 git commit -m ... で再実行（インライン指定可・本commitのみblock無効）
---
EOF
}

INPUT=$(cat)

# tool_name 抽出（純bash・コロンの前後空白を許容: Windows Desktop版実入力は空白+tool_inputネスト形・08-22実測）
tool_name=$(printf '%s' "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/^"tool_name"[[:space:]]*:[[:space:]]*"//;s/"$//')

if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

# command 抽出（python3のjson decodeで正しくアンエスケープ・2026-09-05修正）
# 旧実装はsedで"command":"..."の生文字列を抜き出すのみで、JSON側の \n エスケープを
# 実際の改行にデコードしていなかった。ヒアドキュメント形式(wsl bash -s <<EOF\n...\nEOF)
# のコマンドはJSON化時に改行が \n (バックスラッシュ+n の2文字)のまま残り、
# 直前が単語文字(例: pipefail\ngit の n)だと後続の \bgit の単語境界(\b)が
# 「n と g の間」に成立しなくなり cwd/-C 解析(_cd_path/_gc_path)が空振りして
# hookのcwd(=無関係なrepo)にfallbackする実害が出た(Windows Desktop実運用で実測)。
cmd=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)
ti = d.get('tool_input')
c = ti.get('command') if isinstance(ti, dict) else None
if c is None:
    c = d.get('command', '')
sys.stdout.write(c if isinstance(c, str) else '')
" 2>/dev/null)

# git commit 以外は対象外（cwd対応: git -C <path> commit 形式も検出・L260①）
if ! echo "$cmd" | grep -qE 'git([[:space:]]+-C[[:space:]]+("[^"]*"|[^ ;&|]+))*[[:space:]]+commit([[:space:]]|$)'; then
  exit 0
fi

# auto-sync経路除外（層1のauto-sync誤block防止・spec §4.2）
if [[ "${SSOT_AUTO_SYNC:-}" == "1" ]]; then
  exit 0
fi

# cwd対応（バックログL260①・2026-08-29）: コマンド文字列から対象repoを解決
# "cd <path> && git commit" / "git -C <path> commit" 形式でhookのcwd≠対象repoでも
# staged diff を正しく見る。近似: 最後のcd→その後のgit -C を優先（シェル完全再現は非目標）
# 限制: クォート付き空白パス("my repo")は非対応・解決失敗時は従来どおりcwdで検査
resolve_path() {
  # $1=パス文字列($2=基準dir) → ~展開+相対解決 → stdout
  local p="$1" base="$2"
  if [[ "$p" == "~" || "$p" == "~/"* ]]; then
    printf '%s\n' "$HOME${p#\~}"
  elif [[ "$p" == /* ]]; then
    printf '%s\n' "$p"
  else
    printf '%s\n' "$base/${p#./}"
  fi
}
TARGET_DIR="$PWD"
_cd_path=$(printf '%s' "$cmd" | grep -oE '\bcd[[:space:]]+("[^"]*"|[^ ;&|]+)' | tail -1 | sed -E 's/^cd[[:space:]]+//; s/^"//; s/"$//')
if [ -n "$_cd_path" ]; then
  TARGET_DIR=$(resolve_path "$_cd_path" "$PWD")
fi
_gc_path=$(printf '%s' "$cmd" | grep -oE '\bgit[[:space:]]+-C[[:space:]]+("[^"]*"|[^ ;&|]+)' | tail -1 | sed -E 's/^git[[:space:]]+-C[[:space:]]+//; s/^"//; s/"$//')
if [ -n "$_gc_path" ]; then
  TARGET_DIR=$(resolve_path "$_gc_path" "$TARGET_DIR")
fi
unset _cd_path _gc_path

# staged diff の行数取得（core.quotepath=false: 非ASCIIファイル名の8進エスケープを無効化。
# 既定(true)だと日本語ファイル名が "\346\227..." 形式で出力され、paths.json宣言の生UTF-8
# 文字列と一致せず宣言判定が常に外れる不具合があった・2026-09-05実測）
numstat=$(git -c core.quotepath=false -C "$TARGET_DIR" diff --cached --numstat 2>/dev/null)
if [ -z "$numstat" ]; then
  exit 0  # staged empty or not a git repo
fi

# pathspec限定（L279②・2026-09-04）: "git commit ... -- <paths>" 形式は指定パスのみ判定対象。
# それ以外のstaged（他セッションの作業）は本commitに乗らないため判定外。
# 近似: 最初の "commit" 以降の最後の " -- " 以降をpathspecとみなす・; & | で打ち切り。
# 限制: 空白含みパス非対応・メッセージ内 "--" 誤検出時は一致stagedゼロ→全体判定にfallback（偽陰性ガード）
_pathspec_str=""
_rest="${cmd#*commit}"
case "$_rest" in
  *" -- "*) _pathspec_str="${_rest##* -- }" ;;
esac
if [ -n "$_pathspec_str" ]; then
  _pathspec_str="${_pathspec_str%%[;&|]*}"
  _filtered=$(git -c core.quotepath=false -C "$TARGET_DIR" diff --cached --numstat -- ${_pathspec_str} 2>/dev/null)
  [ -n "$_filtered" ] && numstat="$_filtered"
fi
unset _pathspec_str _rest _filtered

# per-file status map（L279①・2026-09-04）: A=新規は意図的追加としてblock対象から除外
# リネーム(R)は旧path側をキーにする（numstat/engine の旧側正規化と整合）
declare -A FILE_STATUS=()
while IFS=$'\t' read -r _st _p1 _p2; do
  [ -n "$_p1" ] && FILE_STATUS["$_p1"]="${_st:0:1}"
done < <(git -c core.quotepath=false -C "$TARGET_DIR" diff --cached --name-status 2>/dev/null)

# max delta 計算（insertions/deletions の大きい方）
max_delta=0
max_file=""
while IFS=$'\t' read -r ins del file; do
  # バイナリ等の "-" は除外
  [[ "$ins" == "-" || "$del" == "-" ]] && continue
  delta=$(( ins > del ? ins : del ))
  if [ "$delta" -gt "$max_delta" ]; then
    max_delta=$delta
    max_file=$file
  fi
done <<< "$numstat"

# max_file の status 判定（A=新規/M=修正/R=リネーム・doubt-driven #7 正規/非正規タグ基盤）
file_status="?"
if [ -n "$max_file" ]; then
  ns_line=$(git -c core.quotepath=false -C "$TARGET_DIR" diff --cached --name-status -- "$max_file" 2>/dev/null | head -1 | cut -f1)
  [ -n "$ns_line" ] && file_status="${ns_line:0:1}"
fi

WARN_THRESHOLD=10
BLOCK_THRESHOLD=20
# dry-run mode: block無効化（Phase 0運用・spec §3）
if [[ "${DRY_RUN:-}" == "1" ]]; then
  BLOCK_THRESHOLD=999999
fi
# コマンド文字列内のインライン DRY_RUN=1 も受理（L279①・2026-09-04）:
# hookはCCの別processで起動されるため "DRY_RUN=1 git commit" のインラインenvは
# hook本体のenvに届かない（2026-09-01実測）。案内された脱出経路を実行可能にするため
# コマンド文字列側から検出して同等に扱う。
if printf '%s' "$cmd" | grep -qE '(^|[[:space:];&|])DRY_RUN=1([[:space:]]|$)'; then
  BLOCK_THRESHOLD=999999
fi

# 注: ±20超のblock発動は宣言エンジン（下記）の分類後に実施（L279①③・2026-09-04）。
# 自タブ宣言内(SELF)・新規追加(A)・stale宣言はblock対象外。エンジン故障時(DEGRADED)は
# 分類不能のため max_file ベースのfallback block で保護を維持（A除外は適用）。
if [ "$max_delta" -gt "$WARN_THRESHOLD" ]; then
  cat >&2 <<EOF
[GIT-COMMIT-DIFF-CHECK]
EXIT_CODE=0
REASON=stage変動が1ファイル±${WARN_THRESHOLD}行超を検出: ${max_file} (max delta=${max_delta})・確認推奨
MAX_DELTA=${max_delta}
FILE=${max_file}
REQUIRED_ACTION=git diff --cached --stat で内容確認推奨（block無・commit継続）
---
EOF
  log_append "WARN delta=${max_delta} file=${max_file} status=${file_status} exit=0"
fi

# === 宣言ベース判定（v3・revised_proposal_v3_final.md） ===
PATHS_BLOCK_MODE="${PATHS_BLOCK_MODE:-shadow}"

# 自タブID（WT_SESSION優先→CLAUDE_CODE_SESSION_ID・resume-sessionと同一フォールバック式）
SELF_WT="${WT_SESSION:-unknown}"
SELF_ID="${SELF_WT}"
[ "$SELF_ID" = "unknown" ] && SELF_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
SELF_WT4=""
if [ "$SELF_ID" != "unknown" ]; then
  SELF_WT4="${SELF_ID:0:4}"
  # heartbeat自己修復touch（hookが動いた=自タブ活性の自己証明・登録漏れSPOF対策）
  HB_DIR="${HEARTBEAT_DIR:-$HOME/.claude/state/heartbeat}"
  ( mkdir -p "$HB_DIR" 2>/dev/null && : > "$HB_DIR/$SELF_WT4" 2>/dev/null ) || true
fi

# ID衝突検知（同一WT4で🟢行が複数=衝突疑い・ボードが一次情報源）
ID_COLLISION=0
BOARD_FILE="${PATHS_BOARD_FILE:-$HOME/projects/obsidian-ssot/00_SYSTEM/active-sessions.md}"
if [ -n "$SELF_WT4" ] && [ -f "$BOARD_FILE" ]; then
  _n=$(grep -c "^| $SELF_WT4 |.*🟢" "$BOARD_FILE" 2>/dev/null || echo 0)
  [ "${_n:-0}" -ge 2 ] && ID_COLLISION=1
fi

# 宣言エンジン（python3・1回呼出）: paths.json parse+活性判定+突合
# 入力: 環境変数NUMSTAT_DATAに"ins\tdel\tpath"行・argvに(self_wt4, target_dir)
#        ※heredocがpython3のstdinを占有するためstagedデータはenv経由(R/Dは旧path・numstatの"old => new"から旧側抽出)
# 出力: "ENGINE_STATUS=OK|JSON_ERROR|NO_ID" + 分類行 "SELF|OTHER_ACTIVE|OTHER_STALE|UNDECL\tdelta\tpath"
engine_out=$(NUMSTAT_DATA="$numstat" python3 - "$SELF_WT4" "$TARGET_DIR" 2>/dev/null <<'PYEOF'
import json, os, sys, time, re

self_wt4 = sys.argv[1] if len(sys.argv) > 1 else ""
target_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
paths_json = os.environ.get("PATHS_JSON_FILE") or os.path.join(
    os.path.expanduser("~"), ".claude", "state", "active-sessions-paths.json")
hb_dir = os.environ.get("HEARTBEAT_DIR") or os.path.join(
    os.path.expanduser("~"), ".claude", "state", "heartbeat")
STALE_SEC = 12 * 3600

def norm(p):
    return os.path.realpath(os.path.abspath(os.path.expanduser(p)))

# staged行 → (delta, old_path) 抽出（renameの"{a => b}"/"a => b"は旧側）
rows = []
for line in os.environ.get("NUMSTAT_DATA", "").splitlines():
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 3:
        continue
    ins, dele, path = parts[0], parts[1], parts[2]
    if ins == "-" or dele == "-":
        continue
    try:
        delta = max(int(ins), int(dele))
    except ValueError:
        continue
    if "=>" in path:
        old = path.split("=>")[0]
        old = old.replace("{", "").replace("}", "").strip()
        path = old
    rows.append((delta, path))

repo_root = norm(target_dir)

# repoルートはgitから正確に取る(fallback: target_dir)
import subprocess
try:
    repo_root = norm(subprocess.run(
        ["git", "-C", target_dir, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=5).stdout.strip())
except Exception:
    repo_root = norm(target_dir)

if not self_wt4:
    print("ENGINE_STATUS=NO_ID")
    for d, p in rows:
        print(f"UNDECL\t{d}\t{p}")
    sys.exit(0)

try:
    with open(paths_json) as f:
        data = json.load(f)
    entries = data.get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("entries not dict")
except Exception:
    print("ENGINE_STATUS=JSON_ERROR")
    for d, p in rows:
        print(f"UNDECL\t{d}\t{p}")
    sys.exit(0)

now = time.time()

def is_active(tab):
    hb = os.path.join(hb_dir, tab)
    try:
        return (now - os.path.getmtime(hb)) < STALE_SEC
    except OSError:
        return False

def matches(declared, abspath):
    """完全一致 or 宣言dir配下（repoルート/全域宣言はdir展開しない・広域宣言ガード）"""
    d = norm(declared)
    if d in ("/", os.path.expanduser("~")) or d == repo_root:
        return d == abspath
    if d == abspath:
        return True
    return abspath.startswith(d.rstrip(os.sep) + os.sep)

other_active, other_stale, self_set = set(), set(), set()
for tab, plist in entries.items():
    if not isinstance(plist, list):
        continue
    if tab == self_wt4:
        for p in plist:
            if isinstance(p, str):
                self_set.add(norm(p))
    elif is_active(tab):
        for p in plist:
            if isinstance(p, str):
                other_active.add(norm(p))
    else:
        for p in plist:
            if isinstance(p, str):
                other_stale.add(norm(p))

print("ENGINE_STATUS=OK")
for d, p in rows:
    ab = norm(os.path.join(repo_root, p))
    if any(matches(x, ab) for x in self_set):
        print(f"SELF\t{d}\t{p}")
    elif any(matches(x, ab) for x in other_active):
        print(f"OTHER_ACTIVE\t{d}\t{p}")
    elif any(matches(x, ab) for x in other_stale):
        print(f"OTHER_STALE\t{d}\t{p}")
    else:
        print(f"UNDECL\t{d}\t{p}")
PYEOF
)
engine_rc=$?

# DEGRADED判定: python3失敗/JSON_ERROR → 従来ヒューリスティックで既にwarn済みなので
# 緊急警告+カウンタのみ（通す=DEGRADED・v3でfail-closed撤回）
engine_status=$(printf '%s\n' "$engine_out" | grep -o 'ENGINE_STATUS=[A-Z_]*' | head -1 | cut -d= -f2)
[ -z "$engine_status" ] && engine_status="ENGINE_FAIL"

if [ "$engine_status" = "JSON_ERROR" ] || [ "$engine_status" = "ENGINE_FAIL" ]; then
  _today=$(date '+%F')
  _deg_count=$(grep -c "\[${_today}.*DEGRADED" "$LOG_FILE" 2>/dev/null || echo 0)
  # 分類不能でも ±20超(M)の保護だけは維持する（L279①・エンジン故障をblock迂回に使わせない）
  if [ "$file_status" != "A" ] && [ "$max_delta" -gt "$BLOCK_THRESHOLD" ]; then
    emit_block "$max_file" "$max_delta"
    log_append "BLOCK delta=${max_delta} file=${max_file} status=${file_status} exit=2 engine=${engine_status}"
    exit 2
  fi
  echo "[PATHS-BLOCK DEGRADED] 宣言判定エンジンが${engine_status}のため判定不能・commitは通します(要注意)" >&2
  log_append "DEGRADED engine=${engine_status} count=$(( ${_deg_count:-0} + 1 ))"
  if [ "${_deg_count:-0}" -ge 10 ]; then
    echo "[PATHS-BLOCK DEGRADED] 本日${_deg_count}回超の判定不能。paths.json/python3環境を点検してください" >&2
  fi
  exit 0
fi

# 分類集計
block_a=""  # 他タブ活性宣言一致+自タブ宣言外
block_b=""  # 全宣言外+delta>閾値
self_big="" # 自タブ宣言内+delta>20(理由付きwarn)
stale_hit=""
B_THRESHOLD=20
[ "$engine_status" = "NO_ID" ] && B_THRESHOLD=5
[ "$ID_COLLISION" -eq 1 ] && B_THRESHOLD=5

while IFS=$'\t' read -r cls delta path; do
  [ -z "$cls" ] && continue
  case "$cls" in
    OTHER_ACTIVE) block_a="$block_a$path " ;;
    OTHER_STALE)  stale_hit="$stale_hit$path " ;;
    SELF)         [ "$delta" -gt 20 ] && self_big="$self_big$path(${delta}) " ;;
    UNDECL)       [ "$delta" -gt "$B_THRESHOLD" ] && block_b="$block_b$path(${delta}) " ;;
  esac
done <<< "$(printf '%s\n' "$engine_out" | grep -v 'ENGINE_STATUS')"

# shadow/enforce 共通のshadowログ記録
[ -n "$block_a" ] && log_append "SHADOW_BLOCK type=a files=${block_a% } self=${SELF_WT4:-unknown} mode=$PATHS_BLOCK_MODE collision=$ID_COLLISION"
[ -n "$block_b" ] && log_append "SHADOW_BLOCK type=b thresh=$B_THRESHOLD files=${block_b% } self=${SELF_WT4:-unknown} mode=$PATHS_BLOCK_MODE collision=$ID_COLLISION"
[ -n "$stale_hit" ] && log_append "SHADOW_BLOCK_STALE files=${stale_hit% } self=${SELF_WT4:-unknown}"

# legacy block（L279①③・2026-09-04）: 宣言分類後に判定。
# block対象 = 未宣言(UNDECL) or 他タブ活性(OTHER_ACTIVE) かつ 修正系(status≠A) かつ delta>±20。
# 自タブ宣言内(SELF)とstale宣言は warnのみで通過（宣言追加が実行可能な脱出経路として機能する）。
legacy_block_hits=""
while IFS=$'\t' read -r cls delta path; do
  [ -z "$cls" ] && continue
  case "$cls" in
    UNDECL|OTHER_ACTIVE)
      if [ "${FILE_STATUS[$path]:-?}" != "A" ] && [ "$delta" -gt "$BLOCK_THRESHOLD" ]; then
        legacy_block_hits="$legacy_block_hits$path(${delta}) "
      fi
      ;;
  esac
done <<< "$(printf '%s\n' "$engine_out" | grep -v 'ENGINE_STATUS')"

if [ -n "$legacy_block_hits" ]; then
  _lb_first=${legacy_block_hits%% *}
  _lb_file=${_lb_first%%(*}
  _lb_delta=${_lb_first##*\(}; _lb_delta=${_lb_delta%\)}
  emit_block "$_lb_file" "$_lb_delta" "${legacy_block_hits% }"
  log_append "BLOCK delta=${_lb_delta} files=${legacy_block_hits% } self=${SELF_WT4:-unknown} exit=2"
  unset _lb_first _lb_file _lb_delta
  exit 2
fi

# 自タブ宣言内の過大diff(理由付きwarn・git add .型大量混入の見える化)
if [ -n "$self_big" ]; then
  echo "[GIT-COMMIT-DIFF-CHECK] WARN: 自タブ宣言内の過大diff: ${self_big% }・意図した変更か確認推奨" >&2
fi

# stale宣言の案内warn
if [ -n "$stale_hit" ]; then
  echo "[GIT-COMMIT-DIFF-CHECK] WARN(stale): ${stale_hit% } はstale宣言(12h無活動)タブの宣言 path・占有タブの確認または🟢行✅化後に再commit推奨" >&2
fi

# ID衝突疑いの常時警告
if [ "$ID_COLLISION" -eq 1 ]; then
  echo "[GIT-COMMIT-DIFF-CHECK] WARN: 自タブID(${SELF_WT4})に衝突疑い(ボードに同ID🟢複数)・閾値を±5に安全側倒し" >&2
  log_append "ID_COLLISION self=${SELF_WT4}"
fi

# block発動(enforce時のみ・shadowはログのみ)
if [ "$PATHS_BLOCK_MODE" = "enforce" ]; then
  if [ -n "$block_a" ] || [ -n "$block_b" ]; then
    cat >&2 <<EOF
[GIT-COMMIT-DIFF-CHECK]
EXIT_CODE=2
REASON=PATHS_BLOCK: 宣言ベースblock候補を検出
BLOCK_REASON=他タブ活性宣言との衝突 or 未宣言+delta>${B_THRESHOLD}
FILES_A=${block_a:-なし}
FILES_B=${block_b:-なし}
SELF_ID=${SELF_WT4:-unknown} MODE=$PATHS_BLOCK_MODE COLLISION=$ID_COLLISION
REQUIRED_ACTION=(1) paths.jsonの自タブ宣言に該当pathを追加して再commit (2) 占有タブの作業完了なら🟢行を✅化 (3) それ以外は git restore --staged <file> で除外
---
EOF
    log_append "BLOCK paths type=a[${block_a:-}]b[${block_b:-}] self=${SELF_WT4:-unknown} exit=2"
    exit 2
  fi
fi

# git commit -a 系の巻込み注意(1行)
if printf '%s' "$cmd" | grep -qE 'git[[:space:]]+(-C[[:space:]]+("[^"]*"|[^ ;&|]+))*[[:space:]]+commit[[:space:]]+(-[a-zA-Z]*a[a-zA-Z]*|--all)'; then
  echo "[GIT-COMMIT-DIFF-CHECK] note: -a/--all 使用時は追跡ファイル全変更がstageに乗ります・巻込み注意" >&2
fi

exit 0
