"""cyber-waテーマ固有名詞マップのテスト."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from kanji_to_hiragana import kanji_to_hiragana


def test_cyber_wa_terms():
    for name in ["般若", "蓮華", "三味線", "琵琶", "尺八"]:
        result = kanji_to_hiragana(name, theme="cyber-wa")
        assert result, f"{name}の読みが空"


def test_cyber_wa_hannya_split_prevention():
    assert kanji_to_hiragana("般若", theme="cyber-wa") == "はんにゃ"
