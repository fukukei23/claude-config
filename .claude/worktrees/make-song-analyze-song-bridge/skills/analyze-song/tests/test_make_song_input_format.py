"""make-song連携フォーマット（build_make_song_input 出力）の構造固定テスト。

対象コード(match_report.build_make_song_input)は既存・未変更。
出力構造の改変を検知する回帰テスト。JSON Schema は消費側(make-song)未実装のため作らない(YAGNI)。
"""
import json
from pathlib import Path

import pytest
import yaml

from scripts import match_report, match_song

_REAL_DB = Path("/home/yn4416/projects/obsidian-ssot/reference/名曲DB")
_LEMON = _REAL_DB / "JPOP-001" / "features.json"


def _build_msi():
    """Lemon を query に make_song_input を構築（match_song.main と同一呼び出し）。"""
    rep = match_song.match(_LEMON, _REAL_DB)
    idx = yaml.safe_load((_REAL_DB / "_index.yaml").read_text(encoding="utf-8"))
    db_meta = {s["id"]: s for s in idx["songs"]}
    query_features = json.loads(_LEMON.read_text(encoding="utf-8"))
    return match_report.build_make_song_input(rep, db_meta, query_features, "JPOP-001")


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_required_keys_and_schema_version() -> None:
    """必須キー全て存在・schema_version==1。"""
    msi = _build_msi()
    required = {
        "schema_version", "query", "reference_songs",
        "centroid", "recommended", "genre_distribution", "notes",
    }
    assert required <= set(msi.keys()), f"欠損キー: {required - set(msi.keys())}"
    assert msi["schema_version"] == 1


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_reference_songs_ranked_and_self_excluded() -> None:
    """reference_songs は rank 昇順・query_id(JPOP-001) は除外済み。"""
    msi = _build_msi()
    refs = msi["reference_songs"]
    assert len(refs) > 0
    # rank は 1 から昇順
    ranks = [r["rank"] for r in refs]
    assert ranks == sorted(ranks), f"rank 順序不正: {ranks}"
    assert ranks[0] == 1
    # 自己参照なし
    assert all(r["id"] != "JPOP-001" for r in refs), "query 自身が参照に含まれる"
    # 各 entry 必須キー
    for r in refs:
        assert {"rank", "id", "total"} <= set(r.keys()), f"entry 欠損: {r}"


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_genre_distribution_matches_references() -> None:
    """genre_distribution が reference_songs の手元集計と一致（二重計算矛盾の検知）。"""
    msi = _build_msi()
    manual: dict = {}
    for r in msi["reference_songs"]:
        g = r.get("genre")
        if g:
            manual[g] = manual.get(g, 0) + 1
    assert msi["genre_distribution"] == manual, (
        f"genre_distribution 不一致: engine={msi['genre_distribution']} manual={manual}"
    )


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_query_has_id_and_centroid_fields() -> None:
    """query に id 含む・centroid に avg_bpm/mode_key_pc キー存在。"""
    msi = _build_msi()
    assert msi["query"].get("id") == "JPOP-001"
    assert "avg_bpm" in msi["centroid"]
    assert "mode_key_pc" in msi["centroid"]
