#!/usr/bin/env python3
"""frontmatter_lint.py — MOC/Index frontmatter 許可リスト検証（spec §6.2・変更4）

許可リスト方式: 許可キー以外の frontmatter キーを commit ブロック。
可変情報（created_at/updated_at/last_sync/cache_hit 等）の MOC 静的書込を防止。

usage: frontmatter_lint.py <repo_root> <file>...
"""
import re
import sys
from pathlib import Path

import yaml

ALLOWED_CONFIG = Path(__file__).parent / "frontmatter_allowed_keys.yaml"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str):
    """frontmatter（---囲みYAML）を解析。なしは None。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}


def load_allowed() -> dict:
    """許可リスト設定を読み込む。"""
    return yaml.safe_load(ALLOWED_CONFIG.read_text(encoding="utf-8"))


def get_allowed_keys(file_path: Path, repo_root: Path, allowed: dict):
    """ファイルの許可キー。対象外は None。"""
    try:
        rel = str(file_path.relative_to(repo_root))
    except ValueError:
        rel = str(file_path)
    moc = allowed.get("moc", {})
    for f in moc.get("files", []):
        if rel.endswith(f):
            return moc.get("allowed_keys", [])
    index = allowed.get("index", {})
    if re.search(index.get("pattern", ""), rel):
        return index.get("allowed_keys", [])
    return None


def lint_file(file_path: Path, repo_root: Path, allowed: dict) -> list:
    """1ファイル検証。違反メッセージリスト（空=合格）。"""
    allowed_keys = get_allowed_keys(file_path, repo_root, allowed)
    if allowed_keys is None:
        return []  # 対象外スキップ
    text = file_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        return []  # frontmatter なし=空=許可
    return [
        f"{file_path}: 禁止キー '{key}'（許可: {allowed_keys}）"
        for key in fm
        if key not in allowed_keys
    ]


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: frontmatter_lint.py <repo_root> <file>...", file=sys.stderr)
        return 2
    repo_root = Path(sys.argv[1]).resolve()
    allowed = load_allowed()
    all_violations = []
    for f in sys.argv[2:]:
        all_violations.extend(lint_file(Path(f), repo_root, allowed))
    if all_violations:
        for v in all_violations:
            print(f"❌ {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
