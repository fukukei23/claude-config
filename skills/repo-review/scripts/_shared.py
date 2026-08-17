"""repo-review スクリプト群の共通定数・ヘルパー（単一ソース・2026-08-18 critical 2-2対応）。

DEFAULT_EXCLUDE / CODE_EXT を更新する時は必ず本ファイルのみを編集すること。
スクリプト個別に定義すると repo_metrics(19項目) と split_tests(旧12項目) の不統一が
再発し test:src 比が偽数値化する（2026-08-17 設計レビュー critical・両LLM一致指摘）。
"""
from __future__ import annotations

import os

# ディレクトリ除外の既定リスト（repo_metrics / split_tests / js_metrics 共通）
DEFAULT_EXCLUDE = {
    ".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target",
    "__pycache__", ".next", "coverage", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "htmlcov", ".gradio", "mutants", "site-packages", ".terraform",
}

# 計測対象拡張子（言語ラベル付き・repo_metrics の言語別LOCで使用）
CODE_EXT = {
    ".py": "Python", ".js": "JS", ".ts": "TS", ".tsx": "TS", ".jsx": "JS",
    ".gs": "GAS", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".java": "Java",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
    ".md": "Markdown", ".html": "HTML", ".css": "CSS", ".yml": "YAML", ".yaml": "YAML",
}

# test:src 比の対象外拡張子（ドキュメント・マークアップ・設定形式はテスト対象コードでないため）。
# ※ レビュー3-3の「.html 追加」は意図的に不採用: HTML はテスト可能なロジックコードでなく
#   比の分母を膨らませるだけ（zenn 実測: source 1283→2013 になり回帰期待値も崩れる・2026-08-18）
RATIO_EXCLUDED_EXT = {".md", ".html", ".css", ".yml", ".yaml"}

# Phase 1-2 の機械検出で除外候補に上げるキーワード（SKILL.md と対応）
EXCLUDE_HINT_KEYWORDS = ("plugin", "cache", "marketplace", "example", "sample",
                         "fixture", "third_party", "external")


def prune_dirnames(dirnames: list[str], dirpath: str, root: str,
                   extra_exclude: set[str]) -> None:
    """os.walk の dirnames を除外フィルタで in-place 更新する。

    ベース名一致（従来）に加え、パス指定（例: backend/plugins）を
    relpath の子セグメント完全一致で落とす（レビュー3-2: ベース名一致だと
    パス指定が空振りし指定配下が計測に混入する問題の修正）。
    """
    rel = os.path.relpath(dirpath, root)
    parts = [] if rel == "." else rel.replace(os.sep, "/").split("/")
    kept = []
    for d in dirnames:
        if d in DEFAULT_EXCLUDE or d in extra_exclude:
            continue
        child = "/".join(parts + [d])
        if any("/" in e and (child == e or child.startswith(e + "/"))
               for e in extra_exclude):
            continue
        kept.append(d)
    dirnames[:] = kept
