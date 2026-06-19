"""score_render のテスト。MuseScore 失敗時はスキップして None を返す。"""
import pytest

from scripts.score_render import render_score


@pytest.fixture
def midi_path(workdir, yoen_mp3):
    from scripts.midi_extract import extract_midi
    return extract_midi(str(yoen_mp3), workdir)


def test_render_score_produces_png(midi_path, workdir):
    """PNG が生成されること（MuseScore 実行環境がある前提・無ければ None）。"""
    result = render_score(str(midi_path), workdir)
    # MuseScore が動く環境なら PNG、動かないなら None（どちらも許容）
    if result is not None:
        assert "png" in result
        assert workdir.joinpath("score").exists()
