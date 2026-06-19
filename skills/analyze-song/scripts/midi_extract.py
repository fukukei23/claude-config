"""basic_pitch で MP3→MIDI 変換する。

設計補正2: predict_and_save は閾値引数を持たないため、basic_pitch デフォルト閾値
(onset=0.5/frame=0.3/min_note_length=127.7ms) を採用。ノイズ除去は features.py の
music21 側で行う。
"""
import glob
from pathlib import Path

from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import predict_and_save

OUTPUT_NAME = "raw.mid"


def extract_midi(audio_path: str, workdir: Path) -> Path:
    """音源から MIDI を生成し workdir/raw.mid を返す。

    basic_pitch は <音源stem>.mid という名前で出力するため、生成後に raw.mid へリネームする。

    Args:
        audio_path: 入力音源パス。
        workdir: 出力ディレクトリ。

    Returns:
        workdir/raw.mid のパス。
    """
    predict_and_save(
        [audio_path],
        str(workdir),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
    )
    # basic_pitch は <stem>.mid を生成。それを raw.mid に統一。
    candidates = glob.glob(str(workdir / "*.mid"))
    if not candidates:
        raise RuntimeError("basic_pitch が MIDI を生成しませんでした")
    generated = Path(candidates[0])
    target = workdir / OUTPUT_NAME
    if generated != target:
        generated.rename(target)
    return target
