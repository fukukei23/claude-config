"""kanji_to_hiragana.py のテスト（サイバー和モダン用語）."""
from kanji_to_hiragana import kanji_to_hiragana, PROPER_NOUNS


def test_proper_nouns_include_key_terms():
    """サイバー和モダン主要用語が固有名詞マップに含まれること."""
    for name in ["般若", "般若の面", "蓮華", "三味線", "琵琶", "尺八", "太鼓", "提灯", "線香", "読経", "原点廻帰", "電子参拝", "百鬼夜行"]:
        assert name in PROPER_NOUNS, f"{name} が固有名詞マップに不在"


def test_proper_noun_not_split():
    """固有名詞が形態素分割されず正しい読みになること（般若=はんにゃ・分割誤読防止）."""
    result = kanji_to_hiragana("般若")
    assert result == "はんにゃ", f"般若の読みが不正: {result}"


def test_basic_kanji_reading():
    """基本漢字の読みが正しいこと（宴=うたげ）."""
    result = kanji_to_hiragana("宴")
    assert "うたげ" in result, f"宴の読みが不正: {result}"


def test_mixed_sentence():
    """固有名詞+一般語の混文が正しく変換されること."""
    result = kanji_to_hiragana("般若の面が三味線を弾く")
    assert "はんにゃ" in result
    assert "しゃみせん" in result
