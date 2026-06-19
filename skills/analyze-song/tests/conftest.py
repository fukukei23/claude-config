"""analyze-song テスト共通 fixture。"""
from pathlib import Path

import pytest

# テスト正解音源（85BPM・Aメロ/サビ 12音中10音一致が既知）
YOEN_V3_1 = Path(
    "/home/yn4416/projects/make-song-guide/songs/yoen-night/"
    "20260619_130406_yoen-v3_1.mp3"
)


@pytest.fixture
def yoen_mp3() -> Path:
    """yoen-v3_1 の MP3 パス。"""
    assert YOEN_V3_1.exists(), f"テスト音源が見つかりません: {YOEN_V3_1}"
    return YOEN_V3_1


@pytest.fixture
def workdir(tmp_path) -> Path:
    """1曲分の作業ディレクトリ（analysis/ 相当）。"""
    d = tmp_path / "analysis"
    d.mkdir()
    return d
