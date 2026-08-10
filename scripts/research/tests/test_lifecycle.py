"""aiwatch.lifecycle のユニットテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch.lifecycle import (  # noqa: E402
    convergence_check,
    dependency_requeue,
    should_reconsider_declined,
    simulate_inventory,
    suggest_dynamic_threshold,
    transition,
)


def test_4week_absent_archives():
    assert transition(weeks_seen=1, last_trending_week_offset=4) == "archived"
    assert transition(weeks_seen=5, last_trending_week_offset=4) == "archived"


def test_recent_trending_stays_pending():
    assert transition(weeks_seen=1, last_trending_week_offset=0) == "pending"
    assert transition(weeks_seen=3, last_trending_week_offset=2) == "pending"


def test_declined_reconsider_after_180d():
    assert should_reconsider_declined("2026-01-01", "2026-08-11") is True
    assert should_reconsider_declined("2026-08-01", "2026-08-11") is False


def test_declined_reconsider_invalid_date():
    assert should_reconsider_declined("invalid", "2026-08-11") is False


def test_dependency_requeue_when_covered_target_archived():
    assert dependency_requeue("covered by context7", True) is True
    assert dependency_requeue("covered by context7", False) is False
    assert dependency_requeue("not relevant", True) is False


def test_simulate_inventory_steady_state():
    # 15件/週 × 4週 = 60件に収束
    assert simulate_inventory(15, 4, 20) == 60
    assert simulate_inventory(0, 4, 20) == 0


def test_convergence_check_under_threshold():
    ok, steady = convergence_check(weekly_inflow=15, archive_after_weeks=4, threshold=200)
    assert ok is True
    assert steady == 60


def test_convergence_check_overflow():
    # 50件/週 × 4週 = 200 = 境界 → threshold=200 でOK
    ok, steady = convergence_check(weekly_inflow=50, archive_after_weeks=4, threshold=200)
    assert steady == 200


def test_suggest_dynamic_threshold():
    assert suggest_dynamic_threshold(15, 250) == 5  # 在庫多い→長め
    assert suggest_dynamic_threshold(15, 50) == 3  # 在庫少ない→短め
    assert suggest_dynamic_threshold(15, 150) == 4  # デフォルト
