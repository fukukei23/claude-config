#!/usr/bin/env python3
"""Last.fm API経由でYouTube楽曲のメタデータを取得し、統一JSONで返す.

Usage:
    lastfm.py --youtube <URL> [--track <曲名>] [--artist <アーティスト>]

スキル（CC）は summary のみを受領し、full_data はキャッシュを参照する。
"""
import argparse
import sys
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

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


def main(argv: list[str] | None = None) -> int:
    """エントリポイント（スケルトン・DEBUG出力のみ）."""
    args = parse_args(argv)
    print(
        f"[DEBUG] youtube={args.youtube} "
        f"track={args.track} artist={args.artist}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
