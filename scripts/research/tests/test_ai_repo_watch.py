"""ai_repo_watch のユニットテスト"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_repo_watch import (
    extract_evaluated_repos,
    parse_trending_html,
    filter_new_repos,
    save_pending_repos,
    load_pending_repos,
)  # noqa: E402

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


def test_save_then_load_pending_repos_roundtrip(tmp_path):
    """新規分をJSONに保存し、同じ内容を読み込める。"""
    path = tmp_path / "pending-ai-repos.json"
    new_repos = [
        {"name": "owner/repo", "url": "https://github.com/owner/repo",
         "description": "desc", "stars_today": 10},
    ]

    save_pending_repos(path, new_repos, fetched_date="2026-06-26")
    result = load_pending_repos(path)

    assert len(result) == 1
    assert result[0]["name"] == "owner/repo"
    assert result[0]["fetched_date"] == "2026-06-26"


def test_save_pending_repos_appends_without_duplicates(tmp_path):
    """既存pendingに同じnameがあれば追加しない（再実行の重複防止）。"""
    path = tmp_path / "pending-ai-repos.json"
    first = [{"name": "owner/repo", "url": "u", "description": "d", "stars_today": 1}]
    save_pending_repos(path, first, fetched_date="2026-06-26")
    save_pending_repos(path, first, fetched_date="2026-07-03")

    result = load_pending_repos(path)
    assert len(result) == 1


def test_load_pending_repos_missing_file_returns_empty_list(tmp_path):
    """ファイルが存在しない場合は空リストを返す。"""
    assert load_pending_repos(tmp_path / "missing.json") == []
