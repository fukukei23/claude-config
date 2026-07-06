"""drift_detector の単体テスト

ルールベース + KPI 数値評価で review_summary と objective のズレを検知するロジックのテスト。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from drift_detector import DriftResult, detect_drift  # noqa: E402


def test_detect_drift_no_kpi_no_drift_keywords():
    """KPI 無し・drift キーワード無し → drifted=False"""
    result = detect_drift(
        review_summary="validate_email が RFC 5321 準拠になった",
        objective="validate_email を RFC 5321 準拠にする",
        kpi=None,
    )
    assert isinstance(result, DriftResult)
    assert result.drifted is False


def test_detect_drift_kpi_met():
    """KPI が数値で達成されている → drifted=False"""
    result = detect_drift(
        review_summary="テストカバレッジ 96% 達成",
        objective="validate_email のテストカバレッジを 95% 以上にする",
        kpi={"value": 95.0, "unit": "%", "direction": "gte"},
    )
    assert result.drifted is False
    assert result.kpi_value == 96.0


def test_detect_drift_kpi_unmet():
    """KPI が数値で未達 → drifted=True"""
    result = detect_drift(
        review_summary="テストカバレッジ 80% 達成",
        objective="validate_email のテストカバレッジを 95% 以上にする",
        kpi={"value": 95.0, "unit": "%", "direction": "gte"},
    )
    assert result.drifted is True
    assert "KPI" in result.reason


def test_detect_drift_objective_keywords_missing():
    """objective のキーワードが review に全く含まれない → drifted=True"""
    result = detect_drift(
        review_summary="README にタイポ修正",
        objective="validate_email を RFC 5321 準拠にする",
        kpi=None,
    )
    assert result.drifted is True
    assert "objective" in result.reason or "キーワード" in result.reason


def test_detect_drift_kpi_lte_exceeded():
    """direction=lte で KPI を超過 → drifted=True"""
    result = detect_drift(
        review_summary="レスポンス 250ms",
        objective="API レスポンスを 200ms 以下にする",
        kpi={"value": 200.0, "unit": "ms", "direction": "lte"},
    )
    assert result.drifted is True


def test_detect_drift_kpi_lte_met():
    """direction=lte で KPI 以内 → drifted=False"""
    result = detect_drift(
        review_summary="レスポンス 150ms",
        objective="API レスポンスを 200ms 以下にする",
        kpi={"value": 200.0, "unit": "ms", "direction": "lte"},
    )
    assert result.drifted is False
