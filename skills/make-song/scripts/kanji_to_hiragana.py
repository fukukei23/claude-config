#!/usr/bin/env python3
"""漢字歌詞 → 正しいひらがな歌詞 変換スクリプト.

janomeで一般語の読みを取得し、サイバー和モダン用語の固有名詞は手動マップで上書き。
LLMの漢字誤読（般若→はんにゃ 等）を防ぐための辞書確認ツール。
"""
import re

from janome.tokenizer import Tokenizer

# サイバー和モダン固有名詞の手動マップ（janomeデフォルト辞書にない・正しい日本語読み・カタカナ値）
PROPER_NOUNS = {
    # 作品名
    "原点廻帰": "ゲンテンカイキ",
    "電子参拝": "デンシサンパイ",
    "百鬼夜行": "ヒャッキヤギョウ",
    # 仏教・寺院
    "般若": "ハンニャ",
    "般若の面": "ハンニャノメン",
    "蓮華": "レンゲ",
    "読経": "ドキョウ",
    "線香": "センコウ",
    "香炉": "コウロ",
    "参道": "サンドウ",
    "御朱印": "ゴシュイン",
    "本堂": "ホンドウ",
    "障子": "ショウジ",
    "提灯": "チョウチン",
    # 和楽器
    "三味線": "シャミセン",
    "琵琶": "ビワ",
    "尺八": "シャクハチ",
    "太鼓": "タイコ",
    # 美術・様式
    "水墨画": "スイボクガ",
    "浮世絵": "ウキヨエ",
    "陰音階": "インオンカイ",
    "都節": "ミヤコブシ",
    "都節音階": "ミヤコブシオンカイ",
    # キャラ・事物
    "鬼": "オニ",
    "群衆": "グンシュウ",
}


def kata_to_hira(kata: str) -> str:
    """カタカナ→ひらがな."""
    out = []
    for c in kata:
        if "ァ" <= c <= "ヴ":
            out.append(chr(ord(c) - 0x60))
        else:
            out.append(c)
    return "".join(out)


def get_reading(text: str, tokenizer: Tokenizer) -> tuple:
    """text の各形態素の(表面, ひらがな読み)を返す。読めない語は要確認フラグ."""
    result = []
    unknown = []
    for tk in tokenizer.tokenize(text):
        s = tk.surface
        if not s.strip():
            result.append((s, s))
            continue
        if s in PROPER_NOUNS:
            result.append((s, kata_to_hira(PROPER_NOUNS[s])))
        elif tk.reading and tk.reading != "*":
            result.append((s, kata_to_hira(tk.reading)))
        else:
            # 読めない語（記号・未知語）
            result.append((s, s))
            if tk.part_of_speech.split(",")[0] not in ("記号",):
                unknown.append(s)
    return result, unknown


def kanji_to_hiragana(text: str, tokenizer=None) -> str:
    """text をひらがな化して返す。固有名詞はPROPER_NOUNSで上書き。

    固有名詞はjanomeの形態素分割を回避するため、正規表現で先に切り出して
    PROPER_NOUNSを直接適用し、残りをjanomeで変換する（関羽→せき+はね問題の対策）。

    Args:
        text: 変換対象の漢字混じりテキスト（1行〜複数行可）。
        tokenizer: 再利用するjanome Tokenizer（省略時は内部生成）。

    Returns:
        ひらがな化された文字列。構造タグ[...]・括弧(...)等の記号は原形保持。
    """
    if tokenizer is None:
        tokenizer = Tokenizer()
    # 固有名詞（長い順）で分割
    names = sorted(PROPER_NOUNS.keys(), key=len, reverse=True)
    pattern = re.compile("(" + "|".join(re.escape(n) for n in names) + ")")
    parts = pattern.split(text)
    result_parts = []
    for part in parts:
        if not part:
            continue
        if part in PROPER_NOUNS:
            result_parts.append(kata_to_hira(PROPER_NOUNS[part]))
        else:
            readings, _ = get_reading(part, tokenizer)
            result_parts.append("".join(r for _, r in readings))
    return "".join(result_parts)


def convert_lyrics(lyrics: str) -> None:
    """構造タグ[...]や括弧(...)を保持しつつ、各行をひらがな化して表示（CLI用途）."""
    t = Tokenizer()
    print("=" * 60)
    print("【ひらがな版】（AI入力用）")
    print("=" * 60)
    all_unknown = []
    hira_lines = []
    kanji_lines = []
    for line in lyrics.split("\n"):
        stripped = line.strip()
        # 構造タグ [Verse 1] 等はそのまま
        if stripped.startswith("[") and stripped.endswith("]"):
            hira_lines.append(line)
            kanji_lines.append(line)
            continue
        if not stripped:
            hira_lines.append(line)
            kanji_lines.append(line)
            continue
        readings, unknown = get_reading(line, t)
        all_unknown.extend(unknown)
        hira = "".join(r for _, r in readings)
        hira_lines.append(hira)
        kanji_lines.append(line)
    print("\n".join(hira_lines))
    print()
    print("=" * 60)
    print("【漢字版】（意味確認用）")
    print("=" * 60)
    print("\n".join(kanji_lines))
    print()
    print("=" * 60)
    print("【読めなかった語（要手動確認）】")
    print("=" * 60)
    if all_unknown:
        for w in all_unknown:
            print(f"  ⚠️ {w}")
    else:
        print("  なし（全語の読み取得成功）")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # ファイルパス指定: そのファイルの歌詞をひらがな化
        with open(sys.argv[1], encoding="utf-8") as f:
            convert_lyrics(f.read())
    else:
        # サンプル: 曹仁樊城v8のIntro/Verse1抜粋
        LYRICS_SAMPLE = """[Intro]
樊城の 嵐…
(いざ！)

[Verse 1]
秋の 雨雲 空を 暗くら
関羽の 軍が 迫る (迫る！)
"""
        convert_lyrics(LYRICS_SAMPLE)
