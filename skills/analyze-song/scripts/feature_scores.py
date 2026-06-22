"""query vs DB曲の各軸類似度スコア（[0,1]）を計算する。"""
import math

# BPM ガウシアンの標準偏差
_BPM_SIGMA = 8.0


def score_bpm(q: dict, db: dict) -> float | None:
    """BPM 軸スコア（ガウシアン変換・オクターブ誤判定救済付き）。

    Args:
        q: query の正規化ベクトル。
        db: DB曲の正規化ベクトル。

    Returns:
        [0,1] スコア。いずれかの bpm 欠損時は None。
    """
    bq, bd = q.get("bpm"), db.get("bpm")
    if bq is None or bd is None:
        return None
    # オクターブ誤判定（倍/半分）を救済:
    # query を倍/半分した場合との最小差を採用
    delta_eff = min(
        abs(bq - bd),
        abs(bq * 2 - bd),
        abs(bq / 2 - bd),
    )
    return math.exp(-(delta_eff ** 2) / (2 * _BPM_SIGMA ** 2))
