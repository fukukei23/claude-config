"""register_song の単体テスト。"""
import json
from pathlib import Path

from scripts import register_song


def _seed_workdir(workdir: Path) -> Path:
    """run_pipeline が出力した体で workdir にダミーファイルを置く。"""
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "features.json").write_text(
        json.dumps({"meta": {"title": "テスト"}}), encoding="utf-8"
    )
    (workdir / "source.mp3").write_bytes(b"FAKE_MP3")          # 著作物
    (workdir / "score").mkdir()
    (workdir / "score" / "full.png").write_bytes(b"FAKE_PNG")   # 二次的著作物
    return workdir / "features.json"


def test_split_to_db_copies_features_to_ssot(tmp_path: Path):
    workdir = tmp_path / "raw" / "JPOP-001"
    _seed_workdir(workdir)
    ssot_db = tmp_path / "ssot" / "名曲DB"
    dest = register_song.split_to_db(
        workdir, "JPOP-001", ssot_db
    )
    # features.json が SSOT にコピーされている
    assert dest == ssot_db / "JPOP-001" / "features.json"
    assert dest.exists()
    assert json.loads(dest.read_text(encoding="utf-8"))["meta"]["title"] == "テスト"


def test_split_to_db_leaves_audio_and_png_in_local(tmp_path: Path):
    """音源MP3・楽譜PNG は SSOT 配下に存在してはならない（著作権安全）。"""
    workdir = tmp_path / "raw" / "JPOP-001"
    _seed_workdir(workdir)
    ssot_db = tmp_path / "ssot" / "名曲DB"
    register_song.split_to_db(workdir, "JPOP-001", ssot_db)
    # SSOT 配下を走査・mp3/png が一つも無いことを検証
    ssot_files = [p.name for p in ssot_db.rglob("*") if p.is_file()]
    assert not any(f.endswith(".mp3") for f in ssot_files), "mp3 が SSOT に漏洩"
    assert not any(f.endswith(".png") for f in ssot_files), "png が SSOT に漏洩"
    # ローカル側には残っている
    assert (workdir / "source.mp3").exists()
    assert (workdir / "score" / "full.png").exists()
