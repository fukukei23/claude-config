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


def score_key(q: dict, db: dict, relative: bool = True) -> float | None:
    """キー軸スコア（五度圏距離 + scale ペナルティ）。

    完全5度=半音7つで1歩進む五度圏上の最短距離を測る。
    scale 不一致は 0.5 ペナルティ。ただし相対調（min3rd差・major/minor逆）
    は構成音同一のため完全一致扱い(1.0)とする（relative=True の既定）。

    Args:
        q: query の正規化ベクトル。
        db: DB曲の正規化ベクトル。
        relative: 相対調を完全一致扱いするか（既定 True）。

    Returns:
        [0,1] スコア。いずれかの key_pc 欠損時は None。
    """
    pq, pd = q.get("key_pc"), db.get("key_pc")
    if pq is None or pd is None:
        return None
    # 五度圏座標（pc × 7 mod 12）
    fq, fd = (pq * 7) % 12, (pd * 7) % 12
    d = abs(fq - fd)
    d_pc = min(d, 12 - d)  # ∈ [0, 6]
    s_pc = 1.0 - d_pc / 6.0

    sq, sd = q.get("scale", ""), db.get("scale", "")
    if sq == sd:
        return s_pc
    # 相対調判定: 半音距離が3（min3rd）かつ scale が異なる → 構成音同一
    chroma = abs(pq - pd)
    chroma = min(chroma, 12 - chroma)
    if relative and chroma == 3:
        return 1.0  # 相対調: 完全一致扱い
    return s_pc * 0.5


def _ngrams(seq: list, n: int) -> set:
    """シーケンスから n-gram の集合を生成する。"""
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    """Jaccard 係数 |A∩B| / |A∪B|。両方空なら 0.0。"""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def score_chord(q: dict, db: dict) -> float | None:
    """コード進行軸スコア（2-gram/3-gram Jaccard の加重平均）。

    Args:
        q: query の正規化ベクトル。
        db: DB曲の正規化ベクトル。

    Returns:
        [0,1] スコア。いずれかの progression が空の場合は None（軸無効化）。
    """
    pq, pd = q.get("progression") or [], db.get("progression") or []
    if not pq or not pd:
        return None
    j2 = _jaccard(_ngrams(pq, 2), _ngrams(pd, 2))
    j3 = _jaccard(_ngrams(pq, 3), _ngrams(pd, 3))
    return 0.4 * j2 + 0.6 * j3
