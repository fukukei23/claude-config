"""Demucs htdemucs で音源を4ステム(drums/bass/other/vocals)に分離する。

Phase1b の核心: 生ミックスをそのまま basic_pitch に食わせるとゴミMIDIになるため、
先に音源分離して vocals/accompaniment/drums を切り出す。

demucs 4.0.1 API: load_track → apply_model → save_audio（htdemucs は 44100Hz）。
"""
from pathlib import Path

import soundfile as sf
import torch

from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.separate import load_track

STEMS = ("drums", "bass", "other", "vocals")


def separate_source(audio_path: str, workdir: Path) -> dict:
    """音源を4ステムWAVに分離し workdir/stems/<stem>.wav を返す。

    Args:
        audio_path: 入力音源パス（MP3/WAV 等）。
        workdir: 出力ディレクトリ。

    Returns:
        {"drums": Path, "bass": Path, "other": Path, "vocals": Path}
        （各値は workdir/stems/<stem>.wav のパス）
    """
    stems_dir = Path(workdir) / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    model = get_model("htdemucs")
    model.cpu()
    sr = model.samplerate

    wav = load_track(audio_path, model.audio_channels, sr)
    # demucs 標準の正規化: 振幅を単位分散に揃え、出力で元に戻す
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    estimates = apply_model(
        model, wav[None], device="cpu", split=True, overlap=0.25, progress=False
    )[0]
    estimates = estimates * ref.std() + ref.mean()

    result = {}
    for estimate, name in zip(estimates, model.sources):
        out = stems_dir / f"{name}.wav"
        # torchaudio 2.11 は保存に torchcodec を要求するため soundfile で直接保存
        sf.write(str(out), estimate.cpu().numpy().T, sr)
        result[name] = out
    return result
