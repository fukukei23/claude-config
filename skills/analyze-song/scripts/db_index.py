"""名曲DB の _index.yaml 読み書きを担う。"""
from pathlib import Path

import yaml

SCHEMA_VERSION = 1


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
