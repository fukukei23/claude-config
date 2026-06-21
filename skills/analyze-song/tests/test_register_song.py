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


def test_register_one_end_to_end(tmp_path: Path, monkeypatch):
    """run_pipeline をモックし、登録フルフローを検証。"""
    ssot_db = tmp_path / "ssot" / "名曲DB"
    local_raw = tmp_path / "raw"
    index_file = ssot_db / "_index.yaml"

    def fake_pipeline(source, workdir, title="(unknown)"):
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "features.json").write_text(
            json.dumps({"meta": {"title": title, "phase": "1b"}}), encoding="utf-8"
        )
        (workdir / "source.mp3").write_bytes(b"FAKE")
        return {"meta": {"title": title}}

    monkeypatch.setattr(register_song.analyze_song, "run_pipeline", fake_pipeline)

    meta = {
        "title": "テスト曲", "artist": "誰か", "genre": "JPOP",
        "commercial_rank": "million", "era": "1990s",
        "selection_reason": "代表例", "source_type": "youtube",
        "source_url": "https://youtu.be/xxx",
        "analyzed_at": "2026-06-21", "analyze_phase": "1b",
    }
    entry = register_song.register_one(
        "JPOP-001", "https://youtu.be/xxx", meta,
        ssot_db=ssot_db, local_raw=local_raw, index_file=index_file,
    )

    # features.json が SSOT に置かれた
    assert (ssot_db / "JPOP-001" / "features.json").exists()
    # _index.yaml にエントリ追記された
    from scripts import db_index
    index = db_index.load_index(index_file)
    assert any(s["id"] == "JPOP-001" for s in index["songs"])
    # 戻り値に features_path が含まれる
    assert entry["features_path"] == "JPOP-001/features.json"


def test_register_one_never_leaks_media_to_ssot(tmp_path: Path, monkeypatch):
    """register_one フルフロー後、SSOT 配下に mp3/png/wav が無いこと。"""
    ssot_db = tmp_path / "ssot" / "名曲DB"
    local_raw = tmp_path / "raw"
    index_file = ssot_db / "_index.yaml"

    def fake_pipeline(source, workdir, title="(unknown)"):
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "features.json").write_text(
            json.dumps({"meta": {"title": title}}), encoding="utf-8"
        )
        (workdir / "source.mp3").write_bytes(b"FAKE")
        (workdir / "stems").mkdir()
        (workdir / "stems" / "drums.wav").write_bytes(b"FAKE")
        (workdir / "score").mkdir()
        (workdir / "score" / "full.png").write_bytes(b"FAKE")

    monkeypatch.setattr(register_song.analyze_song, "run_pipeline", fake_pipeline)
    meta = {
        "title": "x", "artist": "", "genre": "JPOP",
        "commercial_rank": "million", "era": "1990s",
        "selection_reason": "", "source_type": "youtube",
        "source_url": "", "analyzed_at": "2026-06-21", "analyze_phase": "1b",
    }
    register_song.register_one(
        "JPOP-001", "https://youtu.be/x", meta,
        ssot_db=ssot_db, local_raw=local_raw, index_file=index_file,
    )

    media_exts = (".mp3", ".wav", ".png")
    leaked = [str(p) for p in ssot_db.rglob("*")
              if p.is_file() and p.suffix.lower() in media_exts]
    assert not leaked, f"著作物が SSOT に漏洩: {leaked}"
