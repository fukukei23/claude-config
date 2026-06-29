"""照合スコアの集計（加重平均・k-NN・重心）を担う。"""
from collections import Counter
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


def rank(results: list, k: int) -> list:
    """総合類似度降順で上位 k 件を返す（None は除外・k は有効曲数に縮退）。

    Args:
        results: (song_id, total) のリスト（total は float または None）。
        k: 上位何件か。

    Returns:
        (song_id, total) のリスト（降順・最大 k 件）。
    """
    valid = [(sid, t) for sid, t in results if t is not None]
    valid.sort(key=lambda x: x[1], reverse=True)
    return valid[:k]


def centroid(top: list, normalized_db: dict) -> dict:
    """上位k件の高信頼度軸（BPM/key）で重心（代表値）を算出する。

    Args:
        top: rank() の戻り値（(song_id, total) リスト）。
        normalized_db: song_id→正規化ベクトル の辞書。

    Returns:
        avg_bpm / mode_key_pc（いずれもデータ不足時は None）。
    """
    bpms = [normalized_db[sid]["bpm"] for sid, _ in top
            if normalized_db[sid].get("bpm") is not None]
    keys = [normalized_db[sid]["key_pc"] for sid, _ in top
            if normalized_db[sid].get("key_pc") is not None]
    avg_bpm = sum(bpms) / len(bpms) if bpms else None
    mode_key = Counter(keys).most_common(1)[0][0] if keys else None
    return {"avg_bpm": avg_bpm, "mode_key_pc": mode_key}
