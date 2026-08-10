"""lifecycle — ライフサイクル状態機械 + 在庫シミュレーション。

状態: pending → archived(4週非表示) / declined(人間却下) / evaluated(人間採用)
declined は180日経過+再トレンドで再考Issue(自動適用しない)。
"""
from datetime import date, timedelta

RECONSIDER_DAYS = 180  # declined 再考期間
ARCHIVE_AFTER_WEEKS = 4  # 4週連続でTrending外→archived


def transition(weeks_seen: int, last_trending_week_offset: int) -> str:
    """現在状態から次状態を判定。

    weeks_seen: 連続観測週数
    last_trending_week_offset: 最後にTrendingしたのが何週前か(0=今週)
    戻り値: "pending"|"archived"
    """
    if last_trending_week_offset >= ARCHIVE_AFTER_WEEKS:
        return "archived"
    return "pending"


def should_reconsider_declined(declined_at: str, today: str, days: int = RECONSIDER_DAYS) -> bool:
    """declined が再考期間を過ぎているか(再トレンド前提でIssue起票判定)。"""
    try:
        age = date.fromisoformat(today) - date.fromisoformat(declined_at)
        return age >= timedelta(days=days)
    except ValueError:
        return False


def dependency_requeue(declined_reason: str, covered_target_archived: bool) -> bool:
    """依存ルール: 'covered by X' で X が archived なら再評価キューに戻す。"""
    if "covered by" in declined_reason.lower() and covered_target_archived:
        return True
    return False


def simulate_inventory(
    weekly_inflow: int, archive_after_weeks: int, weeks: int
) -> int:
    """流入/退場シミュレーションで steady-state 在庫数を推定。

    各リポは archive_after_weeks 週後に退場すると仮定。
    """
    if weekly_inflow <= 0 or archive_after_weeks <= 0:
        return 0
    # steady-state: inflow × archive_weeks(全リポが均等に観測期間を持つ)
    return weekly_inflow * archive_after_weeks


def convergence_check(
    weekly_inflow: int, archive_after_weeks: int, threshold: int = 200
) -> tuple[bool, int]:
    """lifecycle が在庫を threshold 以下に収束させるか検証。

    戻り値: (収束するか, 推定steady-state在庫)
    """
    steady = simulate_inventory(weekly_inflow, archive_after_weeks, weeks=20)
    return steady <= threshold, steady


def suggest_dynamic_threshold(weekly_inflow: int, current_inventory: int) -> int:
    """在庫量に応じた動的archive週を提案(在庫>200で5週・<100で3週・デフォルト4週)。"""
    if current_inventory > 200:
        return 5
    if current_inventory < 100:
        return 3
    return ARCHIVE_AFTER_WEEKS
