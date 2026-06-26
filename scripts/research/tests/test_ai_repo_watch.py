"""ai_repo_watch のユニットテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_repo_watch import extract_evaluated_repos, parse_trending_html, filter_new_repos  # noqa: E402

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


def test_parse_trending_html_extracts_repo_entries():
    """Trending HTMLから name/url/description/stars_todayを抽出する。"""
    html = (FIX / "trending_sample.html").read_text(encoding="utf-8")
    result = parse_trending_html(html)

    assert len(result) == 2
    assert result[0]["name"] == "owner-a/repo-a"
    assert result[0]["url"] == "https://github.com/owner-a/repo-a"
    assert result[0]["description"] == "説明テキストA"
    assert result[0]["stars_today"] == 123
    assert result[1]["stars_today"] == 45


def test_filter_new_repos_excludes_already_evaluated():
    """既評価済み(owner/repo)に含まれるものは除外する。"""
    trending = [
        {"name": "DeusData/codebase-memory-mcp", "url": "https://github.com/DeusData/codebase-memory-mcp"},
        {"name": "new-owner/new-repo", "url": "https://github.com/new-owner/new-repo"},
    ]
    evaluated = {"DeusData/codebase-memory-mcp"}

    result = filter_new_repos(trending, evaluated)

    assert len(result) == 1
    assert result[0]["name"] == "new-owner/new-repo"
