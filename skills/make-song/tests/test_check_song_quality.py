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
    check_syllable_density,  # 軸A
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


# ========================================
# 統合: 3軸チェッカー動作確認
# ========================================

SAMPLE_LYRICS = """# サンプル歌詞

### [Intro] 8小節

```
灯がともる　提灯
まだ誰も来てない　風に鳴る
```

### [Verse 1] 16小節

```
町会の倉庫　骨を組む音
汗のにじんだ手拭い　順に回す
去年の自分より　少しは力が要る
揃わない足音に　夜が応える
```

### [Chorus]

```
祭礼前夜　胸を張れ
朝日が出るまで　足踏み鳴らせ
名もない連帯を信じて
漏れそうな火種を抱いて行け
```
"""


def test_3軸統合_セクション毎に軸B_C_スコアが入っている(tmp_path=None):
    """3軸チェッカーを実行すると各セクションにmid_high_scoreとpitch_range_scoreが入る"""
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(SAMPLE_LYRICS)
        path = Path(f.name)

    results = check_syllable_density(path, bpm=98)
    path.unlink()

    assert "Chorus" in results, "Chorus セクションが抽出されるべき"
    chorus = results["Chorus"]
    assert "mid_high_score" in chorus, "Chorusに軸Bスコアが必要"
    assert "pitch_range_score" in chorus, "Chorusに軸Cスコアが必要"
    assert "axes" in chorus, "Chorusに3軸判定が必要"
    assert "overall" in chorus, "Chorusに総合判定が必要"


def test_3軸統合_祭礼前夜Chorusが安全判定():
    """祭礼前夜のChorus（中高音言葉豊富）は総合✅になる"""
    import tempfile

    chorus_only = """# テスト

### [Chorus]

```
祭礼前夜　胸を張れ
朝日が出るまで　足踏み鳴らせ
名もない連帯を信じて
漏れそうな火種を抱いて行け
```
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(chorus_only)
        path = Path(f.name)

    results = check_syllable_density(path, bpm=98)
    path.unlink()

    assert "Chorus" in results
    chorus = results["Chorus"]
    assert chorus["mid_high_score"] >= MID_HIGH_THRESHOLD, (
        f"祭礼前夜Chorusの軸BスコアはMID_HIGH_THRESHOLD以上であるべき: {chorus['mid_high_score']}"
    )
    assert chorus["overall"] == "✅ 安全", (
        f"祭礼前夜Chorusは総合✅であるべき、実際: {chorus['overall']}"
    )


def test_3軸統合_低音ウィスパーVerseが警告域():
    """低音ウィスパー語彙が支配的なVerseは軸B❌で総合警告"""
    import tempfile

    whisper_verse = """# テスト

### [Verse 1] 16小節

```
囁くようにそっと窓を伏せて
眠る街角 影が揺れる
そっと息を殺して夜が更ける
静かな夜に ただ眠る
```
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(whisper_verse)
        path = Path(f.name)

    results = check_syllable_density(path, bpm=98)
    path.unlink()

    assert "Verse 1" in results
    verse = results["Verse 1"]
    assert verse["mid_high_score"] < MID_HIGH_THRESHOLD, (
        f"ウィスパーVerseの軸BはMID_HIGH_THRESHOLD未満であるべき: {verse['mid_high_score']}"
    )
    assert "❌" in verse["overall"] or "⚠️" in verse["overall"], (
        f"ウィスパーVerseは総合❌または⚠️であるべき、実際: {verse['overall']}"
    )


def test_3軸統合_祭礼前夜実歌詞ファイル():
    """実際の祭礼前夜歌詞.mdで3軸チェックが動作する"""
    lyrics_path = Path("/home/yn4416/projects/cyber-wa-modern/songs/原点廻帰/祭礼前夜/歌詞.md")
    if not lyrics_path.exists():
        import pytest
        pytest.skip("祭礼前夜歌詞.mdが存在しない")
    results = check_syllable_density(lyrics_path, bpm=98)
    assert len(results) > 0, "歌詞からセクションが抽出されるべき"
    # 全セクションに軸B/Cスコアが入っている
    for section_name, data in results.items():
        assert "mid_high_score" in data, f"{section_name}に軸Bスコアが必要"
        assert "pitch_range_score" in data, f"{section_name}に軸Cスコアが必要"
        assert "axes" in data, f"{section_name}に3軸判定が必要"


# ========================================
# 軸B/C 融合評価: 実測+文字列統合
# ========================================

def test_軸B_実測版_統合_融合評価が動作する():
    """wavファイルが存在する場合、融合評価（実測50% + 文字列50%）が動作する"""
    from check_song_quality import calc_mid_high_score_fused
    chorus_path = Path(__file__).parent / "fixtures" / "祭礼前夜_chorus.wav"
    if not chorus_path.exists():
        import pytest
        pytest.skip(f"テストフィクスチャ未生成: {chorus_path}")
    lines = [
        "祭礼前夜 胸を張れ",
        "朝日が出るまで 足踏み鳴らせ",
        "名もない連帯を信じて",
        "漏れそうな火種を抱いて行け",
    ]
    fused_score = calc_mid_high_score_fused(
        section_name="Chorus",
        lines=lines,
        audio_path=chorus_path,
    )
    assert 0.0 <= fused_score <= 100.0, f"融合スコアは0-100が期待: {fused_score}"
    assert isinstance(fused_score, float)


def test_軸B_実測版_統合_wav無しでも動作する():
    """wavファイルが存在しない場合、文字列評価のみ実行"""
    from check_song_quality import calc_mid_high_score_fused
    lines = ["胸を張れ", "足踏み鳴らせ"]
    fused_score = calc_mid_high_score_fused(
        section_name="Chorus",
        lines=lines,
        audio_path=None,
    )
    string_only = calc_mid_high_score("Chorus", lines)
    assert abs(fused_score - string_only) < 0.001, (
        f"wav無しなら文字列と同等: fused={fused_score}, string={string_only}"
    )
