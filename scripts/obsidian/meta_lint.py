#!/usr/bin/env python3
"""meta_lint.py — lint設定自体のメタ検証（spec §6.2・変更8）

許可リスト設定（frontmatter_allowed_keys.yaml）が正しい構造か検証。
lint 本体の劣化（設定ミス・壊れた正規表現）を防止。
"""
import re
from pathlib import Path
import yaml

CONFIG = Path(__file__).parent / "frontmatter_allowed_keys.yaml"


def validate_allowed_config() -> list:
    """設定の整合性検証。エラーリスト（空=合格）。"""
    errors = []
    if not CONFIG.exists():
        return [f"設定ファイル不在: {CONFIG}"]
    d = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for section in ("moc", "index"):
        if section not in d:
            errors.append(f"セクション欠落: {section}")
            continue
        if not isinstance(d[section].get("allowed_keys"), list):
            errors.append(f"{section}.allowed_keys が list でない")
    if not isinstance(d.get("moc", {}).get("files"), list):
        errors.append("moc.files が list でない")
    pattern = d.get("index", {}).get("pattern", "")
    try:
        re.compile(pattern)
    except re.error as e:
        errors.append(f"index.pattern が無効な正規表現: {e}")
    return errors


if __name__ == "__main__":
    errs = validate_allowed_config()
    if errs:
        for e in errs:
            print(f"❌ {e}")
        raise SystemExit(1)
    print("✅ lint設定 正常")
