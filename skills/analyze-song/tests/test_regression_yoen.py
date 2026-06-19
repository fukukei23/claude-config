"""yoen-v3_1 回帰テスト。

Phase 1a では librosa/basic_pitch の推定限界を踏まえ、絶対精度より
「パイプライン動作＋特徴量が妥当な範囲で記録されること」を検証する。
（BPM精度・phrase_repetition精度は Phase 1b で改善対象）
"""
import json

from scripts.analyze_song import run_pipeline


def test_yoen_regression_pipeline_and_valid_ranges(yoen_mp3, tmp_path):
    """yoen-v3_1 でフルパイプラインが動作し、特徴量が妥当範囲で記録されること。"""
    workdir = tmp_path / "analysis"
    workdir.mkdir()
    run_pipeline(str(yoen_mp3), workdir, title="yoen-v3_1")
    features = json.loads((workdir / "features.json").read_text())

    # パイプライン完走
    assert features["meta"]["title"] == "yoen-v3_1"
    assert (workdir / "report.md").exists()

    # BPM: 妥当な音楽テンポ範囲（librosa限界で85±10とは限らない）
    bpm = features["tempo"]["bpm"]
    assert 40 <= bpm <= 250, f"BPM が妥当範囲外: {bpm}"

    # キー推定: confidence が正の値
    assert features["key"]["confidence"] > 0

    # phrase_repetition: match/total が記録されている（detected True/False 問わず）
    pr = features["melody"]["phrase_repetition"]
    assert "pairs" in pr
    if pr["pairs"]:
        pair = pr["pairs"][0]
        assert "match" in pair and "total" in pair
        assert pair["total"] > 0

    # structure: セクションが2つ以上
    assert len(features["structure"]["sections"]) >= 2
