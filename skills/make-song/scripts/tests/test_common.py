"""kanji_to_hiragana 共通変換ロジックのテスト."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from kanji_to_hiragana import kanji_to_hiragana


def test_loads_theme_map_sangoku():
    result = kanji_to_hiragana("曹仁", theme="sangoku")
    assert result == "そうじん"


def test_loads_theme_map_cyber_wa():
    result = kanji_to_hiragana("般若", theme="cyber-wa")
    assert result == "はんにゃ"


def test_ha_wa_particle():
    result = kanji_to_hiragana("曹仁は樊城を守る", theme="sangoku")
    assert "そうじん" in result and "はんじょう" in result and "わ" in result


def test_basic_kanji_fukutsu():
    result = kanji_to_hiragana("不屈", theme="sangoku")
    assert "ふくつ" in result
