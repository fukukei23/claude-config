"""sangokuテーマ固有名詞マップのテスト."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from kanji_to_hiragana import kanji_to_hiragana


def test_sangoku_generals():
    for name in ["曹仁", "関羽", "曹操", "諸葛亮", "呂布"]:
        result = kanji_to_hiragana(name, theme="sangoku")
        assert result, f"{name}の読みが空"


def test_sangoku_kanji_split_prevention():
    assert kanji_to_hiragana("関羽", theme="sangoku") == "かんう"
