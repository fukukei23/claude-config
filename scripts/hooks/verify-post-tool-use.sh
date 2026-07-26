#!/bin/bash
# verify-post-tool-use.sh — PostToolUse 検証回避(#7)封じ hook（Phase1・層2）
# spec: docs/superpowers/specs/2026-07-26-LLMサボりバイアス検知-Claude-Code全体組み込み-design.md §3.2(2R改訂)
#
# 仕組み（層2-a廃止・PostToolUse実行のみ）:
# - PostToolUse で Write/Edit/MultiEdit の file_path を取得
# - 拡張子ホワイトリスト(*.py)のみ発火・Markdown/json/yaml 等は早期return
# - Edit 後の変更ファイルに ruff check + pytest(関連テスト・ベストエフォート) 実行
# - 検証失敗時 exit 2 で次操作を block（stderr の JSON を Claude が認識し修正を強制）
# - timeout 時 exit 2 block（exit 0 は soft再発・LLMが timeout を検証スキップ正当化）
# - ファイル単位キャッシュ(mtime+hash)・変更検知時のみ再検証
# - エスケープ: CLAUDE_VERIFY_BYPASS=理由 でログ記録して exit 0
# - 監査ログ: append-only ~/.claude/hook-audit.log
#
# 目標（MiniMaxメタ）: 100%防止でなく「検出+監査+コスト上昇」

set -uo pipefail

cat | python3 -c '
import json, sys, os, subprocess, hashlib, time, shutil, glob

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # パース不能は許可

tool_name = d.get("tool_name", "")
ti = d.get("tool_input", d)
fp = ti.get("file_path", "") or ""

# 対象外 tool
if tool_name not in ("Write", "Edit", "MultiEdit"):
    sys.exit(0)
# 拡張子ホワイトリスト(*.py)
if not fp.endswith(".py"):
    sys.exit(0)
# ファイル存在（PostToolUse なので編集後実体がある想定・なければ許可）
if not os.path.exists(fp):
    sys.exit(0)

CACHE_DIR = os.path.expanduser("~/.claude/verify-cache")
AUDIT_LOG = os.path.expanduser("~/.claude/hook-audit.log")
os.makedirs(CACHE_DIR, exist_ok=True)

def audit(msg):
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass  # 監査ログ失敗で本体を壊さない

# エスケープ（CLI引数/環境変数で理由必須+ログ）
bypass = os.environ.get("CLAUDE_VERIFY_BYPASS", "")
if bypass:
    audit(f"BYPASS fp={fp} reason={bypass[:80]}")
    sys.exit(0)

# キャッシュ（mtime+hash）・変更検知時のみ再検証
try:
    st = os.stat(fp)
    mtime = st.st_mtime
    with open(fp, "rb") as f:
        content = f.read()
    h = hashlib.sha256(content).hexdigest()
    cache_key = hashlib.sha256(fp.encode()).hexdigest()[:16]
    cache_file = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cached = f.read().strip()
        if cached == f"{mtime}:{h}":
            audit(f"CACHE_HIT fp={fp}")
            sys.exit(0)
except Exception:
    pass  # キャッシュ処理失敗は検証続行

# ruff check（必須・軽い）
ruff = shutil.which("ruff") or os.path.expanduser("~/.local/bin/ruff")
errors = []
try:
    rc = subprocess.run([ruff, "check", fp], capture_output=True, text=True, timeout=10)
    if rc.returncode != 0:
        out = (rc.stdout + rc.stderr).strip()
        errors.append(f"ruff check 失敗:\n{out[:800]}")
except subprocess.TimeoutExpired:
    errors.append(f"ruff timeout(10s) fp={fp}")
except Exception as e:
    errors.append(f"ruff 実行エラー: {e}")

# pytest（関連テスト・ベストエフォート）
# 対象ファイルが test_*.py 自体ならそれを実行・foo.py なら同階層 test_foo.py を探す
pytest = shutil.which("pytest")
if pytest and not errors:
    target_dir = os.path.dirname(os.path.abspath(fp))
    base = os.path.basename(fp)
    if base.startswith("test_"):
        test_targets = [fp]
    else:
        mod = base[:-3] if base.endswith(".py") else base
        candidates = glob.glob(os.path.join(target_dir, f"**/test_{mod}.py"), recursive=True)
        test_targets = candidates[:1]  # 関連1件のみ（高速化）
    if test_targets:
        try:
            rc = subprocess.run([pytest, "-q", "--no-header", "--tb=line", "-x"] + test_targets,
                                capture_output=True, text=True, timeout=30, cwd=target_dir)
            if rc.returncode != 0:
                out = (rc.stdout + rc.stderr).strip()
                errors.append(f"pytest 失敗 ({test_targets[0]}):\n{out[:800]}")
        except subprocess.TimeoutExpired:
            errors.append(f"pytest timeout(30s) targets={test_targets}")
        except Exception as e:
            pass  # pytest 実行エラーは ruff 結果で判定（ベストエフォート）

if errors:
    msg = "\n".join(errors)
    audit(f"FAIL fp={fp} errors={msg[:120]}")
    print(json.dumps({
        "decision": "block",
        "reason": f"【Phase1・#7検証回避封じ】コード変更後の検証失敗（verify-post-tool-use.sh）。修正するか、正当な理由があれば CLAUDE_VERIFY_BYPASS=<理由> を設定。\n\n{msg}"
    }, ensure_ascii=False), file=sys.stderr)
    sys.exit(2)

# 成功・キャッシュ更新
try:
    with open(cache_file, "w") as f:
        f.write(f"{mtime}:{h}")
except Exception:
    pass
audit(f"PASS fp={fp}")
sys.exit(0)
'
