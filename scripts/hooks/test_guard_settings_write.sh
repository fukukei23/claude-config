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
check("layer2_disguise_bash", core.layer2_long("Bash(curl -d sk_live_4eC39HqLyjWDarjtT1zdp7dc1yX8u5abcdef TARGET)"), False)  # spec L77: Bash( 含む→層2除外(正規allow誤検知抑制)・既知限界: Bash(偽装のTOKENは層1-4未検知・要別対応(Pre/運用)
check("layer2_all_lower", core.layer2_long("a"*40), False)  # 文字種1種のみ

# === 層3: キー名+${ENV}厳密判定 ===
check("layer3_token_plain", core.layer3_keyname("api_token", "sk-abc123"), True)
check("layer3_envvar_ok", core.layer3_keyname("API_KEY", "${OPENAI_API_KEY}"), False)
check("layer3_envvar_disguise", core.layer3_keyname("token", "${sk-12345abcdef}"), True)  # ${}装いは実値扱い
check("layer3_envvar_default", core.layer3_keyname("secret", "${AWS_KEY:-fallback}"), True)  # :-デフォルト値は実値
check("layer3_nonsecret_key", core.layer3_keyname("comment", "sk-abc123"), False)  # キー名非secret→層3対象外(層4で捕獲)
check("layer3_empty_val", core.layer3_keyname("api_key", ""), False)

# === 層4: 値ブロードスキャン（再帰・キー名無関係）===
check("layer4_keyname_disguise", core.scan_value_for_token("comment", "sk-abc123DEFghi456jkl789mno012pqr345stu678"), True)  # commentキーにTOKEN→層1で捕獲
check("layer4_clean", core.scan_value_for_token("description", "ユーザー設定ファイル"), False)
check("layer4_nested_dict", core.scan_object({"a": {"b": "ghp_" + "x"*36}}), True)
check("layer4_array_split", core.scan_object({"parts": ["sk-", "abc123", "DEF"]}), False)  # 分割状態: 'sk-'単独はlen<10で層1非hit(既知限界・spec短TOKEN境界)
check("layer4_long_random", core.scan_object({"note": "xJ3kP9mQ2nR8vT1wY5aZ4bC6"}), False)  # 24字<32→層2非hit

print(f"\n{'='*40}\npassed: {passed} / failed: {failed}")
sys.exit(1 if failed else 0)
PYEOF
