"""source_separate の単体テスト（Demucs 4ステム分離）。

※ 実分離を伴うため重い（CPU で数分）。pytest 実行時は -m slow 等で分離推奨。
"""
from pathlib import Path

from scripts.source_separate import STEMS, separate_source


def test_separate_source_four_stems(yoen_mp3: Path, tmp_path: Path):
    """yoen-v3_1 を4ステムに分離し、全ステムWAVが生成されること。"""
    result = separate_source(str(yoen_mp3), tmp_path)

    assert set(result.keys()) == set(STEMS)
    for stem in STEMS:
        wav = result[stem]
        assert isinstance(wav, Path)
        assert wav.exists(), f"{stem}.wav 未生成"
        assert wav.stat().st_size > 0, f"{stem}.wav が空"
