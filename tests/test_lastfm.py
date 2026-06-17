"""lastfm.py の単体テスト（parse系純粋関数）"""
from scripts.api.lastfm import parse_search_response


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
