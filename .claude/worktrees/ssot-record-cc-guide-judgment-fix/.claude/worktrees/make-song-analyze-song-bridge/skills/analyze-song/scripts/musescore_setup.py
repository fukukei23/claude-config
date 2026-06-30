"""music21 に MuseScore AppImage のパスを設定する共通ユーティリティ。

Phase 1a では固定パス（~/tools/ の AppImage）を使う。
"""
from music21 import environment

MUSESCORE_PATH = "/home/yn4416/tools/MuseScore-Studio-4.7.3.AppImage"


def configure_musescore() -> str:
    """music21 に MuseScore AppImage を設定し、パスを返す。

    music21 は用途別に2つの設定キーを持つため両方を設定する:
    - musicxmlPath: MusicXML 読み書き（score.write(fmt='musicxml')）
    - musescoreDirectPNGPath: PNG/PDF 出力（score.write(fmt='musicxml.png')）

    Returns:
        設定した MuseScore AppImage のパス文字列。
    """
    us = environment.UserSettings()
    us["musicxmlPath"] = MUSESCORE_PATH
    us["musescoreDirectPNGPath"] = MUSESCORE_PATH
    return MUSESCORE_PATH
