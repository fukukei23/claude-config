#!/bin/bash
# guard-config-secrets.sh — 設定ファイルコピーへの生値シークレット混入をブロック
# 監査⑩根本対策（2026-07-06）。enforce-ssot-record.sh と同構成。
#
# 仕組み:
# - PreToolUse hook で Write/Edit/MultiEdit の file_path を検査
# - file_path が 01_DECISIONS/claude-code/設定ファイル/ 配下の時、新しく書き込む内容を検査
# - シークレット系キー名(api_key/auth_token/secret 等)に ${ENV} 参照以外の実値があれば exit 2
# - 古い内容(old_string)は検査しない（sanitize作業で新内容に${}を入れるのは通す）
# - 常にブロック（フラグ迂回なし・設定ファイルコピーに生値の正当ケースなし）
#
# 2026-07-06 背景: 01_DECISIONS/claude-code/設定ファイル/settings.json コピーにAUTH_TOKEN等が
# 生値でpushされ続けていた（監査⑩）。CLAUDE.md頼みは弱い→機械的防止層。

set -euo pipefail

INPUT=$(cat)

# python で file_path 抽出 + 生値検査を一括処理（日本語パス対策）
echo "$INPUT" | python3 -c '
import json, sys, re

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # パース不能は許可（他hookに任せる）

ti = d.get("tool_input", d)
fp = (ti.get("file_path", "") or "").replace("\\", "/")  # Windows Desktop版のパス区切り正規化(2026-08-30)

# 対象外は許可
if "01_DECISIONS/claude-code/設定ファイル/" not in fp:
    sys.exit(0)

# 新しく書き込む内容を収集（old_stringは含めない）
parts = []
if "content" in ti:
    parts.append(ti["content"])
if "new_string" in ti:
    parts.append(ti["new_string"])
for e in ti.get("edits", []):
    if "new_string" in e:
        parts.append(e["new_string"])
content = "\n".join(parts)

# シークレット系キーの値を検査
# - 値が空は許可（未設定）
# - 値が ${ENV_VAR} 完全一致のみ許可（ENV参照）
# - ${ENV}sk-abc 等の部分混入・生値はブロック
pat = re.compile(
    r"\"([A-Za-z0-9_-]*(?:api[_-]?key|[_-]?token|secret|password)[A-Za-z0-9_-]*)\"\s*:\s*\"([^\"]*)\"",
    re.IGNORECASE,
)
blocked = None
for m in pat.finditer(content):
    val = m.group(2)
    if val and not re.fullmatch(r"\$\{[^}]+\}", val):
        blocked = m
        break
if blocked:
    print(json.dumps({
        "decision": "block",
        "reason": f"設定ファイルコピーへの生値シークレット混入を検出（監査⑩根本対策・guard-config-secrets.sh）。キー「{blocked.group(1)}」の値が ${{ENV}} 参照ではありません。値を ${{ENV_VAR}} 形式にsanitizeしてください。"
    }, ensure_ascii=False), file=sys.stderr)
    sys.exit(2)

sys.exit(0)
'
