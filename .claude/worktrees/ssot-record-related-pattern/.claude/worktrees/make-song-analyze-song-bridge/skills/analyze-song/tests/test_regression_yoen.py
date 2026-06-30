"""yoen-v3_1 回帰テスト（Phase1b: Demucs音源分離パイプライン）。

実曲検証で drums stem 方式が機能すること（Stayin' Alive 104→103.36）を確認済み。
yoen-v3_1 は AI生成音源で drums onset が特殊（BPM推定が112の外れ値）だが、
パイプライン全体が動作し特徴量が妥当範囲で記録されることを検証する。
"""
import json

from scripts.analyze_song import run_pipeline


def test_yoen_regression_pipeline_and_valid_ranges(yoen_mp3, tmp_path):
    """yoen-v3_1 で Phase1b フルパイプラインが動作し、特徴量が妥当範囲で記録されること。"""
    workdir = tmp_path / "analysis"
    workdir.mkdir()
    run_pipeline(str(yoen_mp3), workdir, title="yoen-v3_1")
    features = json.loads((workdir / "features.json").read_text())

    # パイプライン完走・Phase1b
    assert features["meta"]["title"] == "yoen-v3_1"
    assert features["meta"]["phase"] == "1b"
    assert (workdir / "report.md").exists()

    # source_separate ステップが log に記録されている
    steps = {entry["step"] for entry in features["_log"]}
    assert "source_separate" in steps

    # BPM: 妥当な音楽テンポ範囲（yoenはAI音源の外れ値で112・絶対精度は別途）
    bpm = features["tempo"]["bpm"]
    assert 40 <= bpm <= 250, f"BPM が妥当範囲外: {bpm}"

    # キー推定: confidence が正の値
    assert features["key"]["confidence"] > 0

    # コード進行: ローマ数字表記が得られる（Phase1b改善）
    prog = features["chords"]["progression"]
    assert isinstance(prog, list) and len(prog) > 0

    # phrase_repetition: match/total が記録されている
    pr = features["melody"]["phrase_repetition"]
    assert "pairs" in pr
    if pr["pairs"]:
        pair = pr["pairs"][0]
        assert "match" in pair and "total" in pair
        assert pair["total"] > 0

    # structure: 音源duration_sec基準でセクションが2つ以上
    assert len(features["structure"]["sections"]) >= 2
