"""名曲DB の _index.yaml 読み書きを担う。"""
import re
from pathlib import Path

import yaml

SCHEMA_VERSION = 1

_GENRES = ("JPOP", "ROCK", "HIPHOP", "WAFU", "WORLD")
_ID_PATTERN = re.compile(rf"^({'|'.join(_GENRES)})-\d{{3}}$")

_REQUIRED_META_KEYS = (
    "title", "artist", "genre", "commercial_rank", "era",
    "selection_reason", "source_type", "source_url",
    "features_path", "analyzed_at", "analyze_phase",
)


def load_index(path: Path) -> dict:
    """_index.yaml を読み込む。

    Args:
        path: _index.yaml のパス。

    Returns:
        index 辞書（version/updated/songs を含む）。
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def save_index(path: Path, index: dict) -> None:
    """index 辞書を _index.yaml に書き出す。

    Args:
        path: _index.yaml のパス。
        index: index 辞書。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(index, f, allow_unicode=True, sort_keys=False)


def validate_id(song_id: str) -> bool:
    """曲ID が <GENRE>-<3桁> 規約に合うか。

    Args:
        song_id: 検査する曲ID。

    Returns:
        正しければ True。
    """
    return bool(_ID_PATTERN.match(song_id))


def add_entry(index: dict, song_id: str, meta: dict) -> None:
    """index の songs にエントリを追加（同IDは上書き・冪等）。

    Args:
        index: load_index で読んだ辞書（破壊的に更新）。
        song_id: 曲ID。
        meta: DB固有メタ（_REQUIRED_META_KEYS を全て含むこと）。

    Raises:
        ValueError: 曲ID が不正、または必須メタキー不足。
    """
    if not validate_id(song_id):
        raise ValueError(f"invalid song_id: {song_id}")
    missing = [k for k in _REQUIRED_META_KEYS if k not in meta]
    if missing:
        raise ValueError(f"missing meta keys: {missing}")

    entry = {"id": song_id, "status": "registered", **meta}
    songs = index.setdefault("songs", [])
    for i, s in enumerate(songs):
        if s.get("id") == song_id:
            songs[i] = entry
            return
    songs.append(entry)
