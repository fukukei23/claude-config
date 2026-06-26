"""ai_repo_watch のユニットテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_repo_watch import extract_evaluated_repos  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def test_extract_evaluated_repos_returns_owner_repo_set():
    """評価テーブルのMarkdownリンクURLから owner/repo の集合を抽出する。"""
    text = (FIX / "evaluated_table_sample.md").read_text(encoding="utf-8")
    result = extract_evaluated_repos(text)

    assert result == {
        "DeusData/codebase-memory-mcp",
        "addyosmani/agent-skills",
        "LMCache/LMCache",
    }


def test_extract_evaluated_repos_empty_text_returns_empty_set():
    """テーブルがない場合は空集合を返す。"""
    assert extract_evaluated_repos("# 何もないドキュメント") == set()
