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
