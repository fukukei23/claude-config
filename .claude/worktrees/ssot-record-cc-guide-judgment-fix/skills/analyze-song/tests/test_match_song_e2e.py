"""match_song の E2E テスト（実名曲DB使用）。"""
from pathlib import Path

import pytest

from scripts import match_song

# 実DB（30曲）・配置分離: features.json のみ・音源不要
_REAL_DB = Path("/home/yn4416/projects/obsidian-ssot/reference/名曲DB")
_LEMON = _REAL_DB / "JPOP-001" / "features.json"


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_e2e_self_reproduction_lemon():
    """Lemon を query に → DB 内の Lemon 自身が rank1。"""
    rep = match_song.match(_LEMON, _REAL_DB)
    assert rep["score"]["top"][0][0] == "JPOP-001"
    assert rep["score"]["top"][0][1] > 0.99


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_e2e_top5_all_valid_scores():
    """上位5件すべてにスコアが付く（フォールバック未発動）。"""
    rep = match_song.match(_LEMON, _REAL_DB)
    assert len(rep["score"]["top"]) == 5
    for _, total in rep["score"]["top"]:
        assert total is not None
        assert 0.0 <= total <= 1.0


@pytest.mark.skipif(not _LEMON.exists(), reason="実DB(Lemon)不在")
def test_e2e_report_markdown_render():
    """レポートが Markdown として描画できる。"""
    rep = match_song.match(_LEMON, _REAL_DB)
    from scripts import match_report
    md = match_report.render_markdown(rep, {"title": "Lemon(self)"})
    assert "# 名曲照合レポート" in md
    assert "類似名曲ランキング" in md
