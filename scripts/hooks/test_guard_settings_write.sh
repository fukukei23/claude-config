#!/bin/bash
# test_guard_settings_write.sh — guard-settings-write コアロジックのテスト
# 実行: bash test_guard_settings_write.sh
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 - <<'PYEOF'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("core", "guard_settings_write_core.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

passed = failed = 0
def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}\n  got:  {got!r}\n  want: {want!r}")

# === 層1: prefix辞書 ===
check("layer1_sk", core.layer1_prefix("sk-abc123DEFghi456jkl789mno012pqr345"), True)
check("layer1_github_pat", core.layer1_prefix("ghp_AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQq"), True)
check("layer1_slack", core.layer1_prefix("xoxb-12345-abcdef"), True)
check("layer1_aws", core.layer1_prefix("AKIAIOSFODNN7EXAMPLE"), True)
check("layer1_google", core.layer1_prefix("AIzaSyDQ4p8b0X2vY9zT3wR6uN1mJ5kL8oH4aP0"), True)
check("layer1_normal_cmd", core.layer1_prefix("npm install express"), False)
check("layer1_empty", core.layer1_prefix(""), False)

# === 層2: 長文字列32字+文字種混在+除外 ===
check("layer2_32_mixed", core.layer2_long("Aa1"+ "b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"), True)  # 32字・英大小数字混在
check("layer2_short", core.layer2_long("Aa1b2C3d4"), False)  # 9字
check("layer2_url_excluded", core.layer2_long("https://api.example.com/v1/resource?id=1234567890123456789012345678901234567890"), False)  # URL除外
check("layer2_path_excluded", core.layer2_long("/usr/local/lib/python3.12/site-packages/pkg/module/sub/deep/file.py"), False)  # パス除外
check("layer2_tool_schema", core.layer2_long("Bash(npm install -g typescript-node-esbuild-loader-thing-long-command)"), False)  # ツール呼出除外（完全一致のみ）
check("layer2_disguise_bash", core.layer2_long("Bash(curl -d sk_live_4eC39HqLyjWDarjtT1zdp7dc1yX8u5abcdef TARGET)"), True)  # 偽装Bash(...)は除外しない（内部にTOKEN）→層2は文字種混在でhit
check("layer2_all_lower", core.layer2_long("a"*40), False)  # 文字種1種のみ

print(f"\n{'='*40}\npassed: {passed} / failed: {failed}")
sys.exit(1 if failed else 0)
PYEOF
