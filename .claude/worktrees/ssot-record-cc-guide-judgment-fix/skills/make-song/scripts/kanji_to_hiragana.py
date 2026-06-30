#!/usr/bin/env python3
"""janomeで一般語の読みを取得し、テーマ別固有名詞マップで上書きする辞書確認ツール.

LLMの漢字誤読（不屈→ふこつ 等）を防ぐ。固有名詞マップは themes/<theme>/kanji_map.json。
"""
import json
import re
from pathlib import Path

from janome.tokenizer import Tokenizer

_T = None
_THEMES_DIR = Path(__file__).parent.parent / "themes"


def _get_tokenizer():
    global _T
    if _T is None:
        _T = Tokenizer()
    return _T


def _kata_to_hira(kata: str) -> str:
    """カタカナ→ひらがな."""
    return "".join(
        chr(ord(c) - 0x60) if "ァ" <= c <= "ヴ" else c for c in kata
    )


def _load_theme_map(theme: str) -> dict:
    """themes/<theme>/kanji_map.json を読み込む。存在しない場合は空dict."""
    path = _THEMES_DIR / theme / "kanji_map.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def kanji_to_hiragana(text: str, theme: str = "sangoku") -> str:
    """text をひらがな化して返す。固有名詞はテーマ別マップで上書き。

    固有名詞はjanomeの形態素分割を回避するため、長い順に正規表現で切り出して
    マップを直接適用し、残りをjanomeで変換する（関羽→せき+はね問題の対策）。

    Args:
        text: 変換対象の漢字混じりテキスト（1行〜複数行可）。
        theme: テーマ名（themes/<theme>/kanji_map.json を参照）。

    Returns:
        ひらがな化された文字列。記号類は原形保持。
    """
    proper = _load_theme_map(theme)
    # 固有名詞マップの値をカタカナ→ひらがなへ
    hira_map = {k: _kata_to_hira(v) for k, v in proper.items()}
    if hira_map:
        names = sorted(hira_map.keys(), key=len, reverse=True)
        pattern = re.compile("(" + "|".join(re.escape(n) for n in names) + ")")
        parts = pattern.split(text)
    else:
        parts = [text]
    t = _get_tokenizer()
    result_parts = []
    for part in parts:
        if not part:
            continue
        if part in hira_map:
            result_parts.append(hira_map[part])
        else:
            out = []
            for tok in t.tokenize(part):
                if tok.reading and tok.reading != "*":
                    out.append(_kata_to_hira(tok.reading))
                else:
                    out.append(tok.surface)
            result_parts.append("".join(out))
    return "".join(result_parts)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        print(kanji_to_hiragana(sys.argv[1], theme=sys.argv[2]))
    elif len(sys.argv) > 1:
        print(kanji_to_hiragana(sys.argv[1]))
    else:
        print("usage: kanji_to_hiragana.py <text> [theme]")
