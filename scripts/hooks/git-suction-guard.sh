#!/bin/bash
# git-suction-guard.sh — サブディレクトリでのgit initが上位リポジトリに吸着する前に確認を要求
#
# 背景（2026-09-04 meeting-pipeline事故未遂）: .gitが無いサブディレクトリでgitコマンドを
# 実行すると、gitは上位リポジトリに静かに吸着する。git initが吸着状態で実行されると、
# 上位リポジトリ（例: /home/yn4416のホームrepo）内にネストした新規リポジトリが生まれ、
# 巻き込み・履歴汚染の原因になる。層1ルール頼みは「git add巻き込み」2回事故で不十分と
# 実証済みのため機械的確認層を追加（spec: 2026-09-04_git吸着対策hookと知識保存層ガイド分離）。
#
# 仕組み:
# - PreToolUse hook（matcher Bash）で git init を検知
# - 対象ディレクトリ（-C 引数 > cd 複合のcd先 > hookのcwd）に.gitが無く、上位に.gitが
#   存在する場合 → permissionDecision: ask（ふくけい確認必須・LLMが自己判断で続行不可）
# - 対象ディレクトリ自身に.gitがある（再init）・上位に.gitが無い・--bare は通過
# - git init以外（status/add等）は対象外（ホームrepo配下の日常作業での誤爆防止）
#
# 出力: exit 0 常時 + 吸着検知時のみ permissionDecision ask のJSON（warn-naming-rules.sh 同構成）

set -euo pipefail

INPUT=$(cat)

echo "$INPUT" | python3 -c '
import json, os, re, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # パース不能は許可（他hookに任せる）

ti = d.get("tool_input", d)
cmd = (ti.get("command", "") or "")
cwd = (d.get("cwd", "") or os.getcwd())

# git init を含むコマンドか（複合コマンド内も対象）
# `git init` / `git -C path init` / `cd x && git init` の3形式を網羅
if not re.search(r"(?:^|[;&|]\s*)\s*git\b[^\n;&|]*\binit\b", cmd):
    sys.exit(0)

# --bare は吸着被害なし（独立したリポジトリとして生成される）ので対象外
if "--bare" in cmd:
    sys.exit(0)

# 対象ディレクトリの決定（優先順: -C 引数 > cd 先 > cwd）
target = None
m = re.search(r"\bgit\s+(?:-\S+\s+)*-C\s+(\"[^\"]+\"|\S+)", cmd)
if m:
    target = m.group(1).strip("\"")
else:
    m = re.search(r"\bcd\s+(\"[^\"]+\"|\S+)", cmd)
    if m:
        target = m.group(1).strip("\"")
if target:
    target = os.path.normpath(os.path.join(cwd, target) if not os.path.isabs(target) else target)
else:
    target = cwd

# Windows Desktop版のパス区切り正規化（2026-08-30 既存hookと同対応）
target = target.replace("\\\\", "/")

# 対象ディレクトリ自身に.gitがあれば吸着ではない（再init・正当）
if os.path.isdir(os.path.join(target, ".git")):
    sys.exit(0)

# 上位へ遡って.gitを探す（吸着検知）
probe = os.path.dirname(target.rstrip("/")) or "/"
adsorbed_toplevel = None
while True:
    if os.path.isdir(os.path.join(probe, ".git")):
        adsorbed_toplevel = probe
        break
    parent = os.path.dirname(probe)
    if parent == probe or probe == "/":
        break
    probe = parent

if not adsorbed_toplevel:
    sys.exit(0)

msg = (
    "[git-suction-guard] 吸着検知: " + target + " には .git が無く、上位リポジトリ "
    + adsorbed_toplevel + " に吸着します。このまま git init すると上位リポジトリ内に"
    "ネストした新規リポジトリが生まれ、巻き込み・履歴汚染の原因になります。"
    "先に git rev-parse --show-toplevel で吸着先を確認するか、別の保存先を検討してください。"
    "（誤検知の場合はふくけい確認の上続行可・2026-09-04 spec）"
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": msg
    }
}, ensure_ascii=False))

# 発火ログ（頻度計測・review改訂案「推定値を自動計測」対応）
try:
    logdir = os.path.expanduser("~/.claude/logs")
    os.makedirs(logdir, exist_ok=True)
    with open(os.path.join(logdir, "git-suction-guard.log"), "a") as f:
        f.write("ask\t%s\t%s\n" % (target, adsorbed_toplevel))
except Exception:
    pass  # ログ失敗でhook自体は止めない

sys.exit(0)
'
