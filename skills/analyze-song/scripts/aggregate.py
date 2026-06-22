"""照合スコアの集計（加重平均・k-NN・重心）を担う。"""
from pathlib import Path

import yaml


def load_weights(path: Path) -> dict:
    """weights.yaml を読み込む。

    Args:
        path: weights.yaml のパス。

    Returns:
        weights 辞書（weights/k/low_confidence_range_max を含む）。

    Raises:
        ValueError: 重み合計が 1.0 でない場合。
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    total = sum(data["weights"].values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"重み合計が1.0でない: {total}")
    return data
