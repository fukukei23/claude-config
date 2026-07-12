#!/usr/bin/env python3
"""
メロディ品質3軸チェッカーのテスト（Phase 1: 軸A音節密度 + 軸B中高音 + 軸C抑揚幅）

TDD先行: 失敗事例v1-v6と成功基準を明文化。
"""

import sys
from pathlib import Path

# スクリプトをimport
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_song_quality import (  # noqa: E402
    calc_mid_high_score,  # 軸B
    calc_pitch_range_score,  # 軸C
    SECTION_WEIGHTS,
    classify_section,
    MID_HIGH_THRESHOLD,
    PITCH_RANGE_THRESHOLD,
)


# ========================================
# 軸B: 中高音使用率スコア
# ========================================

def test_軸B_失敗例_低音ウィスパー偏り_低スコア():
    """v2歌詞のような低音ウィスパー・モノトーン前提の言葉を多く含む歌詞は低スコア"""
    # 「囁く」「伏せる」「眠る」型 = ウィスパー語彙
    whisper_lines = [
        "囁くようにそっと窓を伏せて",
        "眠る街角 影が揺れる",
        "そっと息を殺して夜が更ける",
    ]
    score = calc_mid_high_score("Verse 1", whisper_lines)
    assert score < 50, f"ウィスパー偏りVerseは50未満であるべき、実際: {score}"


def test_軸B_成功例_中高音dominant_高スコア():
    """v5サ BiaLyricsのような力強い中高音言葉を多く含むサビは高スコア"""
    chorus_lines = [
        "祭礼前夜 胸を張れ",
        "朝日が出るまで 足踏み鳴らせ",
        "名もない連帯を信じて",
        "漏れそうな火種を抱いて行け",
    ]
    score = calc_mid_high_score("Chorus", chorus_lines)
    assert score >= 50, f"力強いサビは50以上であるべき、実際: {score}"


def test_軸B_セクション重み付け_サビがVerseより高評価():
    """同じ歌詞でも、サビとして評価される方がスコアが高い"""
    lines = [
        "胸を張れ 声を揃え",
        "足踏み鳴らせ 火種を抱いて",
    ]
    chorus_score = calc_mid_high_score("Chorus", lines)
    verse_score = calc_mid_high_score("Verse 1", lines)
    assert chorus_score > verse_score, (
        f"サビ({chorus_score}) > Verse({verse_score}) であるべき"
    )


def test_軸B_破裂音行カウント():
    """破裂音（パ・バ・タ・ダ行）を含む行は加点される"""
    with_plosive = ["胸を張れ パッと跳ねろ"]
    without_plosive = ["そっと 静かに 眠れ"]
    score_with = calc_mid_high_score("Chorus", with_plosive)
    score_without = calc_mid_high_score("Chorus", without_plosive)
    assert score_with > score_without, (
        f"破裂音ありが{score_with} > なし{score_without} であるべき"
    )


def test_軸B_空行_ゼロスコア():
    """空歌詞は0点（÷0回避）"""
    assert calc_mid_high_score("Chorus", []) == 0.0
    assert calc_mid_high_score("Verse 1", [""]) == 0.0


def test_軸B_Intro_Break_重み低():
    """Intro/Breakはそもそも中高音を要求されないため重みが低い"""
    weight_intro = SECTION_WEIGHTS.get("Intro", 1.0)
    weight_chorus = SECTION_WEIGHTS.get("Chorus", 1.0)
    weight_break = SECTION_WEIGHTS.get("Break", 1.0)
    assert weight_chorus > weight_intro, "Chorus > Intro"
    assert weight_intro == weight_break, "IntroとBreakは同じ重み"
    assert weight_chorus >= weight_intro * 2, "ChorusはIntroの2倍以上の重み"


# ========================================
# 軸C: 抑揚幅スコア
# ========================================

def test_軸C_失敗例_平板メロ_低スコア():
    """全行が同じ音節数・同じ強母音の繰り返し = 平板メロ"""
    flat_lines = [
        "あああああ いいいいい",
        "ううううう えええええ",
        "おおおおお あああああ",
    ]
    score = calc_pitch_range_score("Verse 1", flat_lines)
    assert score < 50, f"平板メロは50未満であるべき、実際: {score}"


def test_軸C_成功例_音節数ばらつき_高スコア():
    """行の音節数がばらついている = メロディに抑揚がある"""
    varied_lines = [
        "胸を張れ",
        "朝日が出るまで 足踏み鳴らせ",
        "信じて",
        "漏れそうな火種を抱いて行け",
    ]
    score = calc_pitch_range_score("Verse 1", varied_lines)
    assert score >= 50, f"ばらつきVerseは50以上であるべき、実際: {score}"


def test_軸C_強母音交替頻度():
    """強母音（あいうえお）が行内に**複数**含まれる方が音程跳躍を促す

    行内に複数強母音がある = その行内で音程が動く = 抑揚幅が大きい
    """
    varied_vowel = ["あいうえお", "かきくけこ", "さしすせそ"]
    flat_vowel = ["ああああ", "いいいい", "うううう"]
    score_varied = calc_pitch_range_score("Chorus", varied_vowel)
    score_flat = calc_pitch_range_score("Chorus", flat_vowel)
    assert score_varied > score_flat, (
        f"母音多様ありが{score_varied} > なし{score_flat}"
    )


def test_軸C_空行_ゼロスコア():
    """空歌詞は0点"""
    assert calc_pitch_range_score("Verse 1", []) == 0.0


def test_軸C_セクション重み():
    """サビ/Big Chorusは抑揚幅が要求されるため重みが高い"""
    weight_sabi = SECTION_WEIGHTS.get("Big Chorus", 1.0)
    weight_verse = SECTION_WEIGHTS.get("Verse 1", 1.0)
    assert weight_sabi > weight_verse, "Big Chorus > Verse"


# ========================================
# 統合: classify_section
# ========================================

def test_classify_セクション判定():
    """セクション名を3カテゴリ（sabi/verse/low）に分類"""
    assert classify_section("Chorus") == "sabi"
    assert classify_section("Big Chorus") == "sabi"
    assert classify_section("Verse 1") == "verse"
    assert classify_section("Verse 2") == "verse"
    assert classify_section("Intro") == "low"
    assert classify_section("Break") == "low"


# ========================================
# 閾値定数
# ========================================

def test_閾値定数の妥当性():
    """MID_HIGH_THRESHOLDとPITCH_RANGE_THRESHOLDが妥当な範囲"""
    assert 0 < MID_HIGH_THRESHOLD <= 100
    assert 0 < PITCH_RANGE_THRESHOLD <= 100
