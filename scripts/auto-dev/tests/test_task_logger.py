"""task_logger の単体テスト。

task-log.md を生成する write_task_log のテスト。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from task_logger import write_task_log  # noqa: E402


def test_write_task_log_minimal(tmp_path: Path):
    """最小ケース: 目的・計画・レビュー結果のみ。"""
    review = {"critical": [], "high": ["x"], "med": [], "low": []}
    drift = {"drifted": False, "reason": "ok"}

    log_path = write_task_log(
        task_id="test-task-001",
        task_dir=tmp_path,
        objective="validate_email を RFC 5321 準拠にする",
        kpi=None,
        plan_summary="validate_email を更新",
        review_result=review,
        drift_result=drift,
        verdict="SUCCESS",
    )

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "# 📖 test-task-001" in content
    assert "SUCCESS" in content
    assert "RFC 5321" in content


def test_write_task_log_with_drift(tmp_path: Path):
    """drifted=True の場合、ズレ検知履歴セクションが含まれる。"""
    review = {"critical": [], "high": [], "med": [], "low": []}
    drift = {"drifted": True, "reason": "objective のキーワードが review に含まれない"}

    log_path = write_task_log(
        task_id="test-task-002",
        task_dir=tmp_path,
        objective="validate_email を RFC 5321 準拠にする",
        kpi=None,
        plan_summary="plan",
        review_result=review,
        drift_result=drift,
        verdict="SUCCESS",
    )

    content = log_path.read_text(encoding="utf-8")
    assert "ズレ検知履歴" in content
    assert "objective のキーワード" in content


def test_write_task_log_with_kpi(tmp_path: Path):
    """KPI ありの場合、dict 形式で JSON 出力。"""
    review = {"critical": [], "high": [], "med": [], "low": []}
    drift = {"drifted": False, "reason": "KPI達成", "kpi_value": 96.0}
    kpi = {"value": 95.0, "unit": "%", "direction": "gte"}

    log_path = write_task_log(
        task_id="test-task-003",
        task_dir=tmp_path,
        objective="validate_email のテストカバレッジを 95% 以上にする",
        kpi=kpi,
        plan_summary="plan",
        review_result=review,
        drift_result=drift,
        verdict="SUCCESS",
    )

    content = log_path.read_text(encoding="utf-8")
    assert '"value": 95.0' in content
    assert '"direction": "gte"' in content


def test_write_task_log_creates_directory(tmp_path: Path):
    """task_dir が存在しなくても作成される。"""
    nested_dir = tmp_path / "nested" / "task"
    review = {"critical": [], "high": [], "med": [], "low": []}
    drift = {"drifted": False, "reason": "ok"}

    log_path = write_task_log(
        task_id="test-task-004",
        task_dir=nested_dir,
        objective="test",
        kpi=None,
        plan_summary="plan",
        review_result=review,
        drift_result=drift,
        verdict="SUCCESS",
    )

    assert log_path.exists()
    assert nested_dir.is_dir()
