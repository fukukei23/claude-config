"""aiwatch.models のユニットテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch.models import (  # noqa: E402
    RepoStats,
    EvaluatedRepo,
    EnvProfile,
    LifecycleState,
)


def test_repo_stats_growth_rate():
    r = RepoStats(
        name="a/b",
        url="https://github.com/a/b",
        description="d",
        stars_today=100,
        stars_total=1000,
        growth_rate=0.1,
        tag="初見",
    )
    assert r.growth_rate == 0.1
    assert r.name == "a/b"


def test_evaluated_repo_eval_method_field():
    repo = RepoStats("a/b", "url", "d", 100, 1000, 0.1, "初見")
    e = EvaluatedRepo(repo=repo, fit_star=3, eval_text="おすすめ", eval_method="rule_fallback")
    assert e.eval_method == "rule_fallback"
    assert e.fit_star == 3


def test_lifecycle_state_unique_values():
    states = {LifecycleState.PENDING, LifecycleState.ARCHIVED, LifecycleState.DECLINED, LifecycleState.EVALUATED}
    assert len(states) == 4
    assert LifecycleState.PENDING.value == "pending"


def test_env_profile_fields():
    p = EnvProfile(
        mcp_active=["brave-search"],
        mcp_disabled=["context7"],
        projects=["NexusCore"],
        skill_categories=["review"],
        past_decisions=["MCPは4個に絞る"],
        fetched_at="2026-08-11",
    )
    assert p.mcp_active == ["brave-search"]
    assert len(p.past_decisions) == 1
