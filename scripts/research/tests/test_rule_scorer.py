"""aiwatch.rule_scorer のユニットテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch.models import EnvProfile, RepoStats  # noqa: E402
from aiwatch.rule_scorer import score_repo, score_repos  # noqa: E402

PROFILE = EnvProfile(
    mcp_active=["brave-search", "glm", "minimax"],
    mcp_disabled=["context7"],
    projects=["NexusCore"],
    skill_categories=["review"],
    past_decisions=[],
    fetched_at="2026-08-11",
)


def _repo(desc: str, today=100, total=1000, tag="初見") -> RepoStats:
    return RepoStats("a/b", "url", desc, today, total, 0.1, tag)


def test_ai_keyword_match_increases_star():
    r = _repo("An MCP server for code review and RAG")
    e = score_repo(r, PROFILE)
    assert e.fit_star >= 3
    assert e.eval_method == "rule_fallback"


def test_non_ai_low_star_with_penalty():
    r = _repo("A jailbreak tool for iOS devices")
    e = score_repo(r, PROFILE)
    assert e.fit_star <= 2


def test_high_total_stars_adds_point():
    r = _repo("some generic tool", today=10, total=20000)
    e = score_repo(r, PROFILE)
    assert e.fit_star >= 2  # 累計★1万超で+1


def test_buzz_today_adds_point():
    r = _repo("tool", today=600, total=5000)
    e = score_repo(r, PROFILE)
    assert e.fit_star >= 2  # today500超で+1


def test_teijyo_adds_point():
    r = _repo("tool", tag="定着")
    e = score_repo(r, PROFILE)
    assert e.fit_star >= 2  # 定着で+1


def test_star_ceiling_at_5():
    r = _repo("MCP agent CLI for RAG workflow review", today=800, total=50000, tag="定着")
    e = score_repo(r, PROFILE)
    assert e.fit_star == 5


def test_star_floor_at_1():
    r = _repo("xyz random")  # ヒット皆無・ベース1
    e = score_repo(r, PROFILE)
    assert e.fit_star >= 1


def test_score_repos_list():
    repos = [_repo("mcp tool"), _repo("jailbreak ios")]
    results = score_repos(repos, PROFILE)
    assert len(results) == 2
    assert all(r.eval_method == "rule_fallback" for r in results)
