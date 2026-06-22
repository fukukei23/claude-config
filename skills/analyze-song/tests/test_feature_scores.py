"""feature_scores の単体テスト。"""
import math

from scripts import feature_scores as fs


def _vec(bpm=120.0, key_pc=0, scale="major", prog=None,
         low=48, high=84, range_valid=True):
    return {
        "bpm": bpm, "bpm_confidence": 0.9,
        "key_pc": key_pc, "scale": scale, "key_confidence": 0.8,
        "progression": prog or ["i", "iv", "v"],
        "range_low_midi": low, "range_high_midi": high,
        "range_valid": range_valid,
    }


def test_score_bpm_exact():
    assert fs.score_bpm(_vec(bpm=120.0), _vec(bpm=120.0)) == 1.0


def test_score_bpm_sigma8():
    s8 = fs.score_bpm(_vec(bpm=120.0), _vec(bpm=128.0))   # Δ=8
    s12 = fs.score_bpm(_vec(bpm=120.0), _vec(bpm=132.0))  # Δ=12
    assert abs(s8 - math.exp(-0.5)) < 1e-9   # ≈0.607
    assert abs(s12 - math.exp(-(144/128))) < 1e-9  # ≈0.325


def test_score_bpm_octave_halving():
    # 86 vs 172（倍）→ Δ/2=86 を採用 → 高スコア
    s = fs.score_bpm(_vec(bpm=86.0), _vec(bpm=172.0))
    assert s > 0.9


def test_score_bpm_missing_returns_none():
    q = _vec(bpm=120.0)
    d = _vec(bpm=120.0)
    d["bpm"] = None
    assert fs.score_bpm(q, d) is None


def test_score_key_perfect():
    assert fs.score_key(_vec(key_pc=0, scale="major"),
                        _vec(key_pc=0, scale="major")) == 1.0


def test_score_key_perfect_fifth():
    # C vs G は五度圏で1歩 → 1 - 1/6 ≈ 0.833
    s = fs.score_key(_vec(key_pc=0), _vec(key_pc=7))
    assert abs(s - (1 - 1/6)) < 1e-9


def test_score_key_tritone_zero():
    # C vs F# は三全音(6歩) → 0.0
    s = fs.score_key(_vec(key_pc=0), _vec(key_pc=6))
    assert s == 0.0


def test_score_key_scale_mismatch():
    # Cmaj vs Cmin: pc 同じ(1.0) × scale不一致ペナルティ0.5
    s = fs.score_key(_vec(key_pc=0, scale="major"),
                     _vec(key_pc=0, scale="minor"))
    assert abs(s - 0.5) < 1e-9


def test_score_key_relative_no_penalty():
    # Cmaj vs Amin: 相対調(min3rd=3半音) → 完全一致扱い 1.0
    s = fs.score_key(_vec(key_pc=0, scale="major"),
                     _vec(key_pc=9, scale="minor"))
    assert abs(s - 1.0) < 1e-9


def test_score_key_missing_returns_none():
    q = _vec(key_pc=0)
    d = _vec(key_pc=0)
    d["key_pc"] = None
    assert fs.score_key(q, d) is None
