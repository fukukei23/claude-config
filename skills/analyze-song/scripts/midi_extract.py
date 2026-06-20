"""basic_pitch で vocals/accompaniment ステムからMIDIを生成する（Phase1b）。

Phase1a では生ミックスをそのまま食わせていたが、Phase1b では source_separate で
切り出した vocals/other ステムをそれぞれ MIDI 化する。これでメロディ系特徴量は
ボーカル、コード系特徴量は伴奏に基づくクリーンな入力になる。

設計補正2: predict_and_save は閾値引数を持たないため basic_pitch デフォルト閾値
(onset=0.5/frame=0.3/min_note_length=127.7ms) を採用。ノイズ除去は features.py の
music21 側で行う。
"""
import glob
import shutil
from pathlib import Path

from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import predict_and_save


def _stem_to_midi(stem_wav: Path, workdir: Path, out_name: str) -> Path:
    """1ステムWAV を basic_pitch で MIDI 化し workdir/<out_name>.mid を返す。

    basic_pitch は <stem>.mid という名前で出力するため、一時ディレクトリで生成後
    目的名へリネームする。
    """
    tmp = workdir / f".pitch_{out_name}"
    tmp.mkdir(exist_ok=True)
    predict_and_save(
        [str(stem_wav)],
        str(tmp),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
    )
    candidates = glob.glob(str(tmp / "*.mid"))
    if not candidates:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"basic_pitch が {stem_wav} の MIDI を生成しませんでした")
    target = workdir / f"{out_name}.mid"
    Path(candidates[0]).replace(target)
    shutil.rmtree(tmp, ignore_errors=True)
    return target


def extract_midi(stems: dict, workdir: Path) -> dict:
    """vocals/other ステムから vocals.mid/accompaniment.mid を生成する。

    Args:
        stems: source_separate の戻り値 {"drums","bass","other","vocals": Path}。
        workdir: 出力ディレクトリ。

    Returns:
        {"vocals": Path(vocals.mid), "accompaniment": Path(accompaniment.mid)}
    """
    return {
        "vocals": _stem_to_midi(stems["vocals"], workdir, "vocals"),
        "accompaniment": _stem_to_midi(stems["other"], workdir, "accompaniment"),
    }
