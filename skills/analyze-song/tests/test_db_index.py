"""db_index の単体テスト。"""
from pathlib import Path

from scripts import db_index


def test_load_index_returns_dict_with_songs(tmp_path: Path):
    index_file = tmp_path / "_index.yaml"
    index_file.write_text(
        "version: 1\nupdated: 2026-06-21\nsongs: []\n", encoding="utf-8"
    )
    index = db_index.load_index(index_file)
    assert index["version"] == 1
    assert index["songs"] == []


def test_save_index_writes_yaml(tmp_path: Path):
    index_file = tmp_path / "_index.yaml"
    index = {"version": 1, "updated": "2026-06-21", "songs": []}
    db_index.save_index(index_file, index)
    loaded = db_index.load_index(index_file)
    assert loaded == index


import pytest


@pytest.mark.parametrize("song_id,ok", [
    ("JPOP-001", True),
    ("HIPHOP-010", True),
    ("WAFU-099", True),
    ("jpop-001", False),   # 小文字不可
    ("JPOP-1", False),     # 桁不足
    ("JAZZ-001", False),   # 未定義ジャンル
    ("JPOP-0001", False),  # 桁超過
])
def test_validate_id(song_id: str, ok: bool):
    assert db_index.validate_id(song_id) is ok


def test_add_entry_appends_new_song(tmp_path: Path):
    index = {"version": 1, "updated": "2026-06-21", "songs": []}
    meta = {
        "title": "テスト曲", "artist": "誰か", "genre": "JPOP",
        "commercial_rank": "million", "era": "1990s",
        "selection_reason": "代表例", "source_type": "youtube",
        "source_url": "https://youtu.be/xxx",
        "features_path": "JPOP-001/features.json",
        "analyzed_at": "2026-06-21", "analyze_phase": "1b",
    }
    db_index.add_entry(index, "JPOP-001", meta)
    assert len(index["songs"]) == 1
    assert index["songs"][0]["id"] == "JPOP-001"
    assert index["songs"][0]["status"] == "registered"


def test_add_entry_is_idempotent(tmp_path: Path):
    """同ID再登録は重複エントリを作らず上書きする。"""
    index = {"version": 1, "updated": "2026-06-21", "songs": []}
    meta = {"title": "前", "artist": "", "genre": "JPOP",
            "commercial_rank": "million", "era": "1990s",
            "selection_reason": "", "source_type": "youtube",
            "source_url": "", "features_path": "JPOP-001/features.json",
            "analyzed_at": "2026-06-21", "analyze_phase": "1b"}
    db_index.add_entry(index, "JPOP-001", meta)
    meta["title"] = "後"
    db_index.add_entry(index, "JPOP-001", meta)
    assert len(index["songs"]) == 1
    assert index["songs"][0]["title"] == "後"


def test_add_entry_rejects_invalid_id(tmp_path: Path):
    index = {"version": 1, "updated": "2026-06-21", "songs": []}
    meta = {"title": "x", "genre": "JPOP", "commercial_rank": "million",
            "era": "1990s", "selection_reason": "", "source_type": "youtube",
            "source_url": "", "features_path": "x/features.json",
            "analyzed_at": "2026-06-21", "analyze_phase": "1b", "artist": ""}
    with pytest.raises(ValueError):
        db_index.add_entry(index, "JPOP-1", meta)  # 桁不足


def _write_candidates(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_update_candidate_status_sets_registered(tmp_path: Path):
    """該当曲の status を pending→registered にし、他曲は変更しない。"""
    f = _write_candidates(
        tmp_path / "_candidates.yaml",
        "version: 1\n"
        "updated: 2026-06-21\n"
        "candidates:\n"
        "  - id: JPOP-001\n"
        "    title: Lemon\n"
        "    status: pending\n"
        "  - id: JPOP-002\n"
        "    title: ドライフラワー\n"
        "    status: pending\n",
    )
    found = db_index.update_candidate_status(f, "JPOP-001")
    assert found is True
    data = db_index.load_index(f)
    statuses = {c["id"]: c["status"] for c in data["candidates"]}
    assert statuses["JPOP-001"] == "registered"
    assert statuses["JPOP-002"] == "pending"


def test_update_candidate_status_preserves_comments(tmp_path: Path):
    """冒頭コメント・行内コメントを保持したまま status を更新する。"""
    f = _write_candidates(
        tmp_path / "_candidates.yaml",
        "version: 1\n"
        "updated: 2026-06-21\n"
        "# 選定基準: 商業指標\n"
        "candidates:\n"
        "  # JPOP枠\n"
        "  - id: JPOP-001\n"
        "    status: pending\n",
    )
    db_index.update_candidate_status(f, "JPOP-001")
    content = f.read_text(encoding="utf-8")
    assert "# 選定基準" in content
    assert "# JPOP枠" in content
    assert "registered" in content


def test_update_candidate_status_unknown_id_returns_false(tmp_path: Path):
    """候補に無い id は False を返し、ファイル(updated含)を変更しない。"""
    f = _write_candidates(
        tmp_path / "_candidates.yaml",
        "version: 1\n"
        "updated: 2026-06-21\n"
        "candidates:\n"
        "  - id: JPOP-001\n"
        "    status: pending\n",
    )
    found = db_index.update_candidate_status(f, "UNKNOWN-999")
    assert found is False
    data = db_index.load_index(f)
    assert str(data["updated"]) == "2026-06-21"
    assert data["candidates"][0]["status"] == "pending"
