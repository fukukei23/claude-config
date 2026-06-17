"""lastfm.py の単体テスト（parse系純粋関数）"""
from scripts.api.lastfm import (
    parse_search_response,
    parse_similar_artists,
    parse_top_tags,
)


def test_parse_search_response_returns_top_track():
    """track.search の上位1件から (track, artist) を抽出する"""
    resp = {
        "results": {
            "trackmatches": {
                "track": [
                    {"name": "Bohemian Rhapsody", "artist": "Queen", "url": "..."},
                    {"name": "Other", "artist": "X"},
                ]
            }
        }
    }
    track, artist = parse_search_response(resp)
    assert track == "Bohemian Rhapsody"
    assert artist == "Queen"


def test_parse_search_response_empty_returns_none():
    """一致なしの場合は (None, None) を返す"""
    resp = {"results": {"trackmatches": {"track": []}}}
    track, artist = parse_search_response(resp)
    assert track is None
    assert artist is None


def test_parse_search_response_single_dict():
    """track がリストでなく単一 dict の場合も処理する"""
    resp = {
        "results": {
            "trackmatches": {
                "track": {"name": "Solo", "artist": "Artist"}
            }
        }
    }
    track, artist = parse_search_response(resp)
    assert track == "Solo"
    assert artist == "Artist"


def test_parse_top_tags_returns_top5_names():
    """artist.getTopTags から上位5件のタグ名を抽出する"""
    resp = {
        "toptags": {
            "tag": [
                {"name": "rock", "count": 100},
                {"name": "classic rock", "count": 90},
                {"name": "70s", "count": 80},
                {"name": "Queen", "count": 70},
                {"name": "british", "count": 60},
                {"name": "6th", "count": 50},
            ]
        }
    }
    tags = parse_top_tags(resp, limit=5)
    assert tags == ["rock", "classic rock", "70s", "Queen", "british"]


def test_parse_top_tags_empty():
    """タグなしの場合は空リスト"""
    resp = {"toptags": {"tag": []}}
    assert parse_top_tags(resp) == []


def test_parse_top_tags_single_dict():
    """tag がリストでなく単一 dict の場合も処理する"""
    resp = {"toptags": {"tag": {"name": "rock", "count": 100}}}
    assert parse_top_tags(resp) == ["rock"]


def test_parse_similar_artists_returns_top5_names():
    """artist.getSimilar から上位5件のアーティスト名を抽出する"""
    resp = {
        "similarartists": {
            "artist": [
                {"name": "Freddie Mercury", "match": "1"},
                {"name": "David Bowie", "match": "0.9"},
                {"name": "The Beatles", "match": "0.8"},
                {"name": "Led Zeppelin", "match": "0.7"},
                {"name": "Pink Floyd", "match": "0.6"},
                {"name": "6th Artist", "match": "0.5"},
            ]
        }
    }
    similar = parse_similar_artists(resp, limit=5)
    assert similar == [
        "Freddie Mercury",
        "David Bowie",
        "The Beatles",
        "Led Zeppelin",
        "Pink Floyd",
    ]


def test_parse_similar_artists_empty():
    """類似なしの場合は空リスト"""
    resp = {"similarartists": {"artist": []}}
    assert parse_similar_artists(resp) == []


def test_parse_similar_artists_single_dict():
    """artist がリストでなく単一 dict の場合も処理する"""
    resp = {"similarartists": {"artist": {"name": "Freddie Mercury"}}}
    assert parse_similar_artists(resp) == ["Freddie Mercury"]
