"""GitHub Trending を週次スクレイピングし、新規AI関連リポジトリ候補を
pending-ai-repos.json に保存する。評価・導入判定は会話型（人間+Claude）。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

GITHUB_LINK_RE = re.compile(r"\(https://github\.com/([\w.-]+/[\w.-]+)\)")


def extract_evaluated_repos(markdown_text: str) -> set[str]:
    """評価テーブルのMarkdownリンクURLから owner/repo の集合を抽出する。"""
    return set(GITHUB_LINK_RE.findall(markdown_text))
