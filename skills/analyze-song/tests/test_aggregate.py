"""aggregate の単体テスト。"""
from pathlib import Path

from scripts import aggregate


def test_load_weights_returns_normalized(tmp_path: Path):
    wf = tmp_path / "weights.yaml"
    wf.write_text(
        "weights:\n  bpm: 0.35\n  key: 0.25\n  chord: 0.25\n  range: 0.15\n"
        "k: 5\nlow_confidence_range_max: 48\n",
        encoding="utf-8",
    )
    data = aggregate.load_weights(wf)
    assert data["weights"]["bpm"] == 0.35
    assert data["k"] == 5
    assert data["low_confidence_range_max"] == 48


def test_load_weights_rejects_unnormalized(tmp_path: Path):
    import pytest

    wf = tmp_path / "weights.yaml"
    wf.write_text("weights:\n  bpm: 0.5\n  key: 0.2\nk: 5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        aggregate.load_weights(wf)


def test_weighted_total_all_axes():
    weights = {"bpm": 0.35, "key": 0.25, "chord": 0.25, "range": 0.15}
    scores = {"bpm": 1.0, "key": 1.0, "chord": 1.0, "range": 1.0}
    assert abs(aggregate.weighted_total(scores, weights) - 1.0) < 1e-9


def test_weighted_total_redistribution():
    # range 無効(None) → 残3軸で再配分
    weights = {"bpm": 0.35, "key": 0.25, "chord": 0.25, "range": 0.15}
    scores = {"bpm": 1.0, "key": 1.0, "chord": 1.0, "range": None}
    # 残重み合計 0.85 → 1.0/0.85 倍されて合計1.0維持
    assert abs(aggregate.weighted_total(scores, weights) - 1.0) < 1e-9


def test_weighted_total_mixed_values():
    weights = {"bpm": 0.35, "key": 0.25, "chord": 0.25, "range": 0.15}
    scores = {"bpm": 0.8, "key": 0.6, "chord": None, "range": None}
    # 残 bpm+key=0.6 → (0.35*0.8+0.25*0.6)/0.6
    expected = (0.35 * 0.8 + 0.25 * 0.6) / 0.6
    assert abs(aggregate.weighted_total(scores, weights) - expected) < 1e-9


def test_weighted_total_all_none_returns_none():
    weights = {"bpm": 0.35, "key": 0.25}
    scores = {"bpm": None, "key": None}
    assert aggregate.weighted_total(scores, weights) is None
