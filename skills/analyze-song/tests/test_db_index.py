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
