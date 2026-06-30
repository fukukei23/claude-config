"""music21→MusicXML→MuseScore で PNG/PDF を生成する。

エラー方針: MuseScore 起動失敗時はスキップし None を返す（features.json は出す）。

music21 の write フォーマット注意:
- fmt='musicxml' : MusicXML テキスト（MuseScore 不要）
- fmt='musicxml.png' / 'musicxml.pdf' : MuseScore 経由で画像化
  （fmt='png'/'pdf' は未サポート。musescoreDirectPNGPath 設定必須）
- PNG 出力は MuseScore の仕様で <stem>-1.png のように連番 suffix が付く。
  write() の戻り値が実際のパスなのでそれを信頼する。
"""
from pathlib import Path

from music21 import converter

from scripts.musescore_setup import configure_musescore


def render_score(midi_path: str, workdir: Path) -> dict | None:
    """MIDI から PNG/PDF を生成する。失敗時は None。

    Args:
        midi_path: 入力 MIDI パス。
        workdir: 出力ディレクトリ。

    Returns:
        workdir 相対パスの {"png": ..., "pdf": ...} または None。
    """
    score_dir = workdir / "score"
    score_dir.mkdir(exist_ok=True)
    try:
        configure_musescore()
        score = converter.parse(midi_path)
        png_abs = score.write(fmt="musicxml.png", fp=str(score_dir / "full"))
        pdf_abs = score.write(fmt="musicxml.pdf", fp=str(score_dir / "full"))
        # workdir 相対パスに正規化（PNG は full-1.png のように連番が付く）
        png_rel = Path(png_abs).relative_to(workdir).as_posix()
        pdf_rel = Path(pdf_abs).relative_to(workdir).as_posix()
        return {"png": png_rel, "pdf": pdf_rel}
    except Exception as exc:  # noqa: BLE001
        print(f"[score_render] 楽譜生成スキップ: {exc}")
        return None
