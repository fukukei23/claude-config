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


def weighted_total(scores: dict, weights: dict) -> float | None:
    """各軸スコアを固定重みで加重平均する（無効軸は比例再配分）。

    Args:
        scores: 軸名→スコア(float) または None の辞書。
        weights: 軸名→重み の辞書。

    Returns:
        [0,1] 総合類似度。有効軸が0個なら None。
    """
    valid = {a: s for a, s in scores.items() if s is not None}
    total_w = sum(weights[a] for a in valid)
    if total_w == 0:
        return None
    return sum(weights[a] * s for a, s in valid.items()) / total_w
