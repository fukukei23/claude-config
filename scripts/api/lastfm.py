#!/usr/bin/env python3
"""Last.fm API経由でYouTube楽曲のメタデータを取得し、統一JSONで返す.

Usage:
    lastfm.py --youtube <URL> [--track <曲名>] [--artist <アーティスト>]

スキル（CC）は summary のみを受領し、full_data はキャッシュを参照する。
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import (  # noqa: E402
    make_error_result,
    make_success_result,
    run_api,
)

LASTFM_ENDPOINT = "https://ws.audioscrobbler.com/2.0/"
OEMBED_ENDPOINT = "https://www.youtube.com/oembed"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Last.fm メタデータ取得")
    parser.add_argument("--youtube", required=True, help="解析対象のYouTube URL")
    parser.add_argument(
        "--track", default=None, help="曲名（track.search誤認時の手動指定）"
    )
    parser.add_argument(
        "--artist", default=None, help="アーティスト（同上）"
    )
    return parser.parse_args(argv)


def parse_search_response(
    search_json: dict,
) -> tuple[str | None, str | None]:
    """track.search レスポンスから上位1件の (track, artist) を抽出する.

    Returns:
        (track_name, artist_name)・一致なしは (None, None)
    """
    matches = search_json.get("results", {}).get("trackmatches", {})
    tracks = matches.get("track", [])
    if not tracks:
        return None, None
    top = tracks[0] if isinstance(tracks, list) else tracks
    return top.get("name"), top.get("artist")


def parse_top_tags(tags_json: dict, limit: int = 5) -> list[str]:
    """artist.getTopTags レスポンスから上位 limit 件のタグ名を抽出する.

    Returns:
        タグ名のリスト（件数不足はその分だけ）・なしは空リスト
    """
    tags = tags_json.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    return [t.get("name", "") for t in tags[:limit] if t.get("name")]


def parse_similar_artists(similar_json: dict, limit: int = 5) -> list[str]:
    """artist.getSimilar レスポンスから上位 limit 件のアーティスト名を抽出する.

    Returns:
        アーティスト名のリスト・なしは空リスト
    """
    artists = similar_json.get("similarartists", {}).get("artist", [])
    if isinstance(artists, dict):
        artists = [artists]
    return [a.get("name", "") for a in artists[:limit] if a.get("name")]


def fetch_youtube_title(youtube_url: str) -> str:
    """oEmbed API でYouTube動画タイトルを取得する（APIキー不要）."""
    params = {"url": youtube_url, "format": "json"}
    url = f"{OEMBED_ENDPOINT}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    title = data.get("title", "")
    if not title.strip():
        raise RuntimeError(f"empty title from oEmbed: {youtube_url}")
    return title


def _lastfm_get(params: dict, api_key: str) -> dict:
    """Last.fm API にGETリクエストを送り、JSONを返す."""
    query_params = {**params, "api_key": api_key, "format": "json"}
    url = f"{LASTFM_ENDPOINT}?{urllib.parse.urlencode(query_params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_track(
    query: str, api_key: str
) -> tuple[str | None, str | None]:
    """track.search でクエリから上位1件の (track, artist) を特定する."""
    resp = _lastfm_get({"method": "track.search", "track": query}, api_key)
    return parse_search_response(resp)


def fetch_metadata(track: str, artist: str, api_key: str) -> dict:
    """track/artist のメタデータ（getInfo/getSimilar/getTopTags）を取得する."""
    return {
        "track": _lastfm_get(
            {"method": "track.getInfo", "track": track, "artist": artist},
            api_key,
        ),
        "artist": _lastfm_get(
            {"method": "artist.getInfo", "artist": artist}, api_key
        ),
        "similar": _lastfm_get(
            {"method": "artist.getSimilar", "artist": artist}, api_key
        ),
        "tags": _lastfm_get(
            {"method": "artist.getTopTags", "artist": artist}, api_key
        ),
    }


def _cache_key_for(youtube_url: str) -> str:
    """YouTube URLからキャッシュキーを生成する."""
    return "lastfm_" + hashlib.md5(youtube_url.encode("utf-8")).hexdigest()[:12]


def _summarize(meta: dict, cache_key: str) -> dict:
    """メタデータを構造化summaryにしてキャッシュ保存する.

    summaryは Gemini プロンプト注入用（ジャンル=タグ・類似アーティスト中心）。
    """
    track_info = meta.get("track", {}).get("track", {})
    artist_info = meta.get("artist", {}).get("artist", {})
    track_name = track_info.get("name", "")
    artist_name = artist_info.get(
        "name", ""
    ) or track_info.get("artist", {}).get("name", "")
    tags = parse_top_tags(meta.get("tags", {}), limit=5)
    similar = parse_similar_artists(meta.get("similar", {}), limit=5)

    summary = (
        f"曲名: {track_name} / "
        f"アーティスト: {artist_name} / "
        f"ジャンル・タグ: {', '.join(tags)} / "
        f"類似アーティスト: {', '.join(similar)}"
    )
    return make_success_result(
        summary=summary,
        full_data={
            "track": track_name,
            "artist": artist_name,
            "tags": tags,
            "similar": similar,
            "raw": meta,
        },
        cache_key=cache_key,
    )


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。JSON結果を標準出力に出す."""
    args = parse_args(argv)
    api_key = os.environ.get("LASTFM_API_KEY", "")
    if not api_key:
        result = make_error_result("LASTFM_API_KEY not set in environment")
        print(json.dumps(result, ensure_ascii=False))
        return 1

    cache_key = _cache_key_for(args.youtube)

    def call_fn() -> dict:
        if args.track and args.artist:
            track, artist = args.track, args.artist
        else:
            title = fetch_youtube_title(args.youtube)
            track, artist = search_track(title, api_key)
            if not track or not artist:
                raise RuntimeError(
                    f"track.search で曲名/アーティストを特定できませんでした"
                    f"（title={title}）"
                )
        return fetch_metadata(track, artist, api_key)

    result = run_api(call_fn, _summarize, cache_key=cache_key)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
