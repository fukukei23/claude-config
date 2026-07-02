"""kanji_to_hiragana.py のテスト."""
from kanji_to_hiragana import kanji_to_hiragana, PROPER_NOUNS


def test_proper_nouns_include_key_generals():
    """三国志主要武将が固有名詞マップに含まれること."""
    for name in ["曹仁", "樊城", "関羽", "于禁", "庞徳", "徐晃", "曹操", "諸葛亮", "呂布"]:
        assert name in PROPER_NOUNS, f"{name} が固有名詞マップに不在"


def test_proper_noun_not_split():
    """固有名詞が形態素分割されず正しい読みになること."""
    result = kanji_to_hiragana("関羽")
    assert result == "かんう", f"関羽の読みが不正: {result}"


def test_basic_kanji_reading():
    """基本漢字の読みが正しいこと（不屈=ふくつ・曹仁v5教訓）."""
    result = kanji_to_hiragana("不屈")
    assert "ふくつ" in result, f"不屈の読みが不正: {result}"


def test_mixed_sentence():
    """固有名詞+一般語の混文が正しく変換されること."""
    result = kanji_to_hiragana("曹仁は樊城を守る")
    assert "そうじん" in result
    assert "はんじょう" in result
