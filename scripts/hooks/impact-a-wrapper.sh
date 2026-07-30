#!/bin/bash
# impact-a-wrapper.sh — multi-llm-review impactモード 層a
# spec: docs/superpowers/specs/2026-07-30-multi-llm-review-impact-mode-design.md
# 並存先: verify-post-tool-use.sh (同PostToolUse matcher)
#
# 責務:
#  - PostToolUse で Edit/Write/MultiEdit のファイル変更後に git diff 取得
#  - 拡張子ホワイトリスト対象のみ解析
#  - データファイル読込 → 検知 → additionalContext 注入 (3択)
#  - 検知失敗は silent skip + 検知失敗カウンタ記録（G1/M17反映）
#  - 静的危険操作カタログ一致時は layer-b 起動推奨メッセージ追加

set -uo pipefail

HOOKS_DIR="$HOME/.claude/scripts/hooks"
FAIL_COUNTER="$HOME/.claude/state/impact-a-fail-count"
mkdir -p "$(dirname "$FAIL_COUNTER")"
[ -f "$FAIL_COUNTER" ] || echo "0" > "$FAIL_COUNTER"

# stdin から JSON 取得
INPUT=$(cat)

# Python 層a 検出ロジック呼び出し
OUTPUT=$(echo "$INPUT" | python3 -c '
import json, sys, os, subprocess, re
from pathlib import Path

HOOKS_DIR = Path.home() / ".claude" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

try:
    from impact_a.detector import detect_from_state, build_injection_text, load_config
    from impact_a.parser import parse_antipatterns_md, parse_dangerous_ops_yaml
except Exception:
    fc = Path(os.path.expanduser("~/.claude/state/impact-a-fail-count"))
    fc.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(fc, "a") as f: f.write("import_error\n")
    except Exception: pass
    sys.exit(0)

try:
    data = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

tool_name = data.get("tool_name", "")
ti = data.get("tool_input", {})
fp = ti.get("file_path", "") or ""

if tool_name not in ("Edit", "Write", "MultiEdit"):
    sys.exit(0)
if not fp:
    sys.exit(0)

cfg = load_config()
exts = tuple(cfg["edit_extensions"])
if not fp.endswith(exts):
    sys.exit(0)

try:
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "HEAD", "--", fp],
        capture_output=True, text=True, timeout=10,
    ).stdout
    if not diff:
        diff = subprocess.run(
            ["git", "diff", "--unified=0", "--", fp],
            capture_output=True, text=True, timeout=10,
        ).stdout
    # フォールバック: git diff が空（未追跡/別リポ）→ tool_input の new_string から
    # 簡易 unified diff を合成し、`parse_unified_zero_diff` が "+追加行" として読める形にする。
    if not diff:
        new_str = ti.get("new_string", "") or ""
        if new_str:
            diff = (
                f"diff --git a/{fp} b/{fp}\n"
                f"--- a/{fp}\n"
                f"+++ b/{fp}\n"
                + "\n".join(f"+{line}" for line in new_str.splitlines())
                + "\n"
            )
except Exception:
    Path(os.path.expanduser("~/.claude/state/impact-a-fail-count")).write_text(
        str(int(Path(os.path.expanduser("~/.claude/state/impact-a-fail-count")).read_text().strip() or "0") + 1)
    )
    sys.exit(0)

try:
    aps_text = cfg["global_antipatterns_path"].read_text()
    ops_text = cfg["dangerous_ops_path"].read_text()
except Exception:
    fc = Path(os.path.expanduser("~/.claude/state/impact-a-fail-count"))
    try:
        cur = int(fc.read_text().strip() or "0")
        fc.write_text(str(cur + 1))
    except Exception: pass
    sys.exit(0)

try:
    antipatterns = parse_antipatterns_md(aps_text)
    dangerous_ops = parse_dangerous_ops_yaml(ops_text)
except Exception:
    fc = Path(os.path.expanduser("~/.claude/state/impact-a-fail-count"))
    try:
        cur = int(fc.read_text().strip() or "0")
        fc.write_text(str(cur + 1))
    except Exception: pass
    sys.exit(0)

result = detect_from_state(diff, antipatterns, dangerous_ops)
injection = build_injection_text(result) if result.get("matched") else ""

if result.get("dangerous_op_match"):
    injection += " | [限定自動発動候補] layer-b (impact-mode) 手動起動を強く推奨"

if injection:
    print(injection)

sys.exit(0)
' 2>/dev/null)

if [ -n "$OUTPUT" ]; then
    echo "$OUTPUT"
fi
exit 0