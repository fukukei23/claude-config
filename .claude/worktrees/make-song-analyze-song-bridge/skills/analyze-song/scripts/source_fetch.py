"""音源取得: YouTube URL は yt-dlp、ローカルパスはコピー。

エラー方針: yt-dlp の一時的失敗は2回まで自動リトライ。動画削除/非公開は即停止。
"""
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

YT_RETRY = 2
OUTPUT_NAME = "audio.mp3"


def _ytdlp_download(url: str, outtmpl: str) -> int:
    """yt-dlp で URL を MP3 抽出する（テストでモック可能な関数として分離）。

    Args:
        url: YouTube 動画 URL。
        outtmpl: 出力テンプレートパス（拡張子なし）。

    Returns:
        yt-dlp の終了コード。
    """
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.download([url])


def fetch_source(source: str, workdir: Path) -> Path:
    """音源を取得し workdir/audio.mp3 を返す。

    Args:
        source: YouTube URL またはローカル MP3 パス。
        workdir: 作業ディレクトリ。

    Returns:
        workdir/audio.mp3 のパス。

    Raises:
        FileNotFoundError: ローカルパスが存在しない、または yt-dlp がリトライ上限で失敗。
    """
    out_path = workdir / OUTPUT_NAME
    parsed = urlparse(source)

    if parsed.scheme in ("http", "https"):
        outtmpl = str(workdir / "audio")
        last_err = None
        for attempt in range(YT_RETRY + 1):
            try:
                code = _ytdlp_download(source, outtmpl)
                if code == 0 and out_path.exists():
                    return out_path
                last_err = f"yt-dlp exit code {code}"
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                time.sleep(2)
        raise FileNotFoundError(f"yt-dlp 取得失敗({YT_RETRY+1}回): {last_err}")

    # ローカルパス
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"音源が見つかりません: {source}")
    shutil.copy2(src, out_path)
    return out_path
