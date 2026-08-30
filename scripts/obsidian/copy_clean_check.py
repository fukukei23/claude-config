#!/usr/bin/env python3
"""コピペ前整形チェック: 文字数実測+マークダウン残骸の2階層検知。

使い方:
    python3 copy_clean_check.py <profile> <field> <textfile>
    python3 copy_clean_check.py coconala サービス内容 /tmp/copy_clean_target.txt

終了コード: 0=合格 / 1=文字数超過またはエラー扱い残骸あり / 2=profile・欄名不明
標準ライブラリのみ（依存ゼロ・MiniMax#7指摘対応）。
"""
import json
import re
import sys
from pathlib import Path

PROFILES_PATH = Path.home() / ".claude/scripts/obsidian/copy_clean_profiles.json"

# エラー扱い: ココナラ等プレーンテキスト欄で確実に不自然な記法（必ず除去）
ERR_PATTERNS: list[tuple[str, str]] = [
    ("太字**", r"\*\*"),
    ("斜体__", r"__"),
    ("コードフェンス```", r"```"),
    ("リンク[](", r"\]\("),
    ("HTMLタグ", r"<[a-zA-Z/][^>]*>"),
]
# 警告扱い: プレーンテキストでも自然に現れうる（自動修正せず報告のみ・Gemini#2）
WARN_PATTERNS: list[tuple[str, str]] = [
    ("行頭見出し#", r"^#{1,6}\s"),
    ("行頭引用>", r"^>\s"),
    ("箇条書き-", r"^\s*[-*]\s"),
    ("番号付き1.", r"^\s*\d+\.\s"),
]


def load_profiles() -> dict:
    """プロファイルJSONを読み込む。"""
    with open(PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    """エントリポイント。終了コードは0/1/2。"""
    if len(sys.argv) != 4:
        print("使い方: copy_clean_check.py <profile> <field> <textfile>")
        return 2
    profile_name, field_name, text_path = sys.argv[1], sys.argv[2], sys.argv[3]
    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict) or profile_name.startswith("_"):
        print(f"[FAIL] プロファイル不明: {profile_name}（未登録欄の沈黙通過禁止・MiniMax#3）")
        return 2
    spec = profile.get(field_name)
    if not isinstance(spec, dict):
        print(f"[FAIL] 欄不明: {profile_name}/{field_name} → 停止して編集画面の表示値を確認すること")
        return 2

    text = Path(text_path).read_text(encoding="utf-8")
    count = len(text)
    upper = spec.get("max")
    lower = spec.get("min", 0)

    print(f"欄: {profile_name}/{field_name}（{spec.get('label', '')}）")
    print(f"実測文字数: {count} / 上限 {upper} / 下限 {lower}")
    over = count > upper or count < lower
    print(f"文字数判定: {'[FAIL] 上限・下限外' if over else '[OK] 範囲内'}")

    err_hits: list[str] = []
    for label, pattern in ERR_PATTERNS:
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line):
                err_hits.append(f"{label} L{i}: {line[:60]}")
    warn_hits: list[str] = []
    for label, pattern in WARN_PATTERNS:
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line):
                warn_hits.append(f"{label} L{i}: {line[:60]}")

    if err_hits:
        print(f"エラー扱い残骸: {len(err_hits)}件（必ず除去）")
        for h in err_hits[:10]:
            print(f"  {h}")
    else:
        print("エラー扱い残骸: 0件（**・__・```・[](・HTMLタグ）")
    if warn_hits:
        print(f"警告扱い: {len(warn_hits)}件（自動修正しない・目視で確認）")
        for h in warn_hits[:5]:
            print(f"  {h}")
    else:
        print("警告扱い: 0件")

    if over or err_hits:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
