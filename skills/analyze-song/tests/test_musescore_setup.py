"""musescore_setup のテスト。"""
from scripts.musescore_setup import configure_musescore

MUSESCORE = "/home/yn4416/tools/MuseScore-Studio-4.7.3.AppImage"


def test_configure_musescore_sets_musicxml_path():
    """設定後に music21 の musicxmlPath が AppImage を指すこと。"""
    from music21 import environment

    configure_musescore()
    assert str(environment.UserSettings()["musicxmlPath"]) == MUSESCORE


def test_configure_musescore_returns_path():
    """設定関数は設定したパスを返すこと。"""
    path = configure_musescore()
    assert path == MUSESCORE
