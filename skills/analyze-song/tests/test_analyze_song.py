"""analyze_song CLI の結合テスト（1曲フルパイプライン）。"""
import json

from scripts.analyze_song import run_pipeline


def test_run_pipeline_full(yoen_mp3, tmp_path):
    """yoen-v3_1 で features.json + report.md が生成されること。"""
    workdir = tmp_path / "analysis"
    workdir.mkdir()
    run_pipeline(str(yoen_mp3), workdir, title="yoen-v3_1")

    features = json.loads((workdir / "features.json").read_text())
    assert features["meta"]["title"] == "yoen-v3_1"
    assert features["meta"]["phase"] == "1a"
    assert "tempo" in features
    assert "key" in features
    assert "chords" in features
    assert (workdir / "report.md").exists()
    # 楽譜は環境依存で None の可能性があるため、features.json のみ必須
