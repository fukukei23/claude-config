#!/usr/bin/env python3
"""librosa.pyin でメロディ音高(F0)を抽出し、サビ上がり・音域適合を判定する.

セクション別音域コンター（[L1]楽曲制作基礎 §G）を客観検証。
「サビが曲で一番高い」「同じメロディを繰り返していないか」を数値＋視覚で判定。

人間の耳でなく音響DSPで「ドレミのどの音が出てるか」を自動抽出する。
セクション分割は構造タイムスタンプ未知のため時間比率（Verse=前半40% /
Chorus=後半40%）で簡易推定。

オプション:
  --plot  ピッチロールPNGを出力（音高×時間・セクション色分け・楽譜代替）
  --midi  MIDIファイルを出力（F0→MIDI note・MuseScore等で五線譜表示）

Usage:
    melody-judge.py --audio <path> [<path> ...] [--plot] [--midi] [--outdir <dir>]
"""
import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import make_success_result  # noqa: E402

MALE_HIT_LOW = 60   # C4
MALE_HIT_HIGH = 79  # G4


def _judge(rise: float | None, chorus_midi: float | None) -> str:
    """上がり具合と音域適合から判定テキストを返す."""
    parts = []
    if rise is None:
        parts.append("サビ判定: データ不足")
    elif rise >= 2:
        parts.append(f"サビ上がり◎(+{rise:.1f}半音)")
    elif rise >= 0:
        parts.append(f"サビやや上がり△(+{rise:.1f}半音)")
    else:
        parts.append(f"サビ下がり✗({rise:.1f}半音)")

    if chorus_midi is not None and MALE_HIT_LOW <= chorus_midi <= MALE_HIT_HIGH:
        parts.append("男性売れ線音域(C4-G4)◎")
    elif chorus_midi is not None:
        parts.append(f"音域外(Chorus={chorus_midi:.0f}/C4-G4=60-79)")
    return " / ".join(parts)


def _plot_pitchroll(name: str, f0, voiced, times, out_png: Path) -> str:
    """ピッチロール（音高×時間）をPNG出力する。セクション色分けで反復を視覚判定."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    midi = librosa.hz_to_midi(f0)
    fig, ax = plt.subplots(figsize=(14, 4))
    n = len(f0)
    # セクション帯
    t_v_end = times[int(n * 0.4)] if n else 0
    t_c_start = times[int(n * 0.6)] if n else 0
    ax.axvspan(times[0], t_v_end, alpha=0.12, color="royalblue", label="Verse(前半)")
    ax.axvspan(t_c_start, times[-1], alpha=0.12, color="crimson", label="Chorus(後半)")
    # 有声音高
    vmask = voiced & ~np.isnan(midi)
    ax.scatter(times[vmask], midi[vmask], s=3, c="black")
    ax.set_ylabel("MIDI note (音高)")
    ax.set_xlabel("time (秒)")
    ax.set_title(f"{name} — ピッチロール（音の動き＝楽譜代替）")
    ax.set_ylim(30, 85)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    return str(out_png)


def _to_midi(name: str, f0, voiced, out_mid: Path) -> str:
    """F0をMIDI note列に変換しMIDIファイル出力（MuseScore等で五線譜表示可能）."""
    import numpy as np
    from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

    midi_raw = librosa.hz_to_midi(f0)
    tick = 120  # フレームあたりのtick（分解能1920/tick相当・概略）
    notes: list[tuple[int, int]] = []
    prev = None
    dur = 0
    for i in range(len(f0)):
        if voiced[i] and not np.isnan(midi_raw[i]):
            n = int(round(midi_raw[i]))
            if n == prev:
                dur += tick
            else:
                if prev is not None:
                    notes.append((prev, dur))
                prev = n
                dur = tick
        else:
            if prev is not None:
                notes.append((prev, dur))
                prev = None
                dur = 0
    if prev is not None:
        notes.append((prev, dur))

    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(85)))
    for note, length in notes:
        track.append(Message("note_on", note=note, velocity=80, time=0))
        track.append(Message("note_off", note=note, velocity=80, time=max(length, 30)))
    mid.save(out_mid)
    return str(out_mid)


def _analyze_one(path: Path, do_plot: bool, do_midi: bool, outdir: Path) -> dict:
    """1曲のF0を抽出しセクション別音域・可視化・MIDIを出力する."""
    import numpy as np
    global librosa
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = 512
    f0, voiced, _ = librosa.pyin(y, fmin=80, fmax=600, sr=sr)
    midi = librosa.hz_to_midi(f0)
    times = librosa.times_like(f0, sr=sr, hop_length=hop)

    n = len(midi)
    verse_mask = voiced & (np.arange(n) < n * 0.4)
    chorus_mask = voiced & (np.arange(n) >= n * 0.6)
    verse_m = midi[verse_mask]
    chorus_m = midi[chorus_mask]

    vm = float(np.mean(verse_m)) if verse_m.size else None
    cm = float(np.mean(chorus_m)) if chorus_m.size else None
    rise = (cm - vm) if (vm is not None and cm is not None) else None

    valid = midi[voiced]
    result = {
        "file": path.name,
        "overall_min_note": librosa.midi_to_note(float(np.min(valid))) if valid.size else None,
        "overall_max_note": librosa.midi_to_note(float(np.max(valid))) if valid.size else None,
        "verse_mean_note": librosa.midi_to_note(vm) if vm else None,
        "chorus_mean_note": librosa.midi_to_note(cm) if cm else None,
        "verse_mean_midi": round(vm, 1) if vm else None,
        "chorus_mean_midi": round(cm, 1) if cm else None,
        "rise_semitones": round(rise, 1) if rise is not None else None,
        "chorus_in_male_hitrange": bool(MALE_HIT_LOW <= cm <= MALE_HIT_HIGH) if cm else False,
        "verdict": _judge(
            round(rise, 1) if rise is not None else None,
            round(cm, 1) if cm else None,
        ),
    }

    stem = path.stem
    if do_plot:
        png = outdir / f"{stem}_pitchroll.png"
        result["pitchroll_png"] = _plot_pitchroll(path.name, f0, voiced, times, png)
    if do_midi:
        mid = outdir / f"{stem}.mid"
        result["midi"] = _to_midi(path.name, f0, voiced, mid)
    return result


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。判定結果JSONを出力（オプションでPNG/MIDI生成）."""
    parser = argparse.ArgumentParser(description="メロディ音域・サビ上がり判定＋楽譜代替可視化")
    parser.add_argument("--audio", nargs="+", required=True)
    parser.add_argument("--plot", action="store_true", help="ピッチロールPNG出力")
    parser.add_argument("--midi", action="store_true", help="MIDI出力（五線譜用）")
    parser.add_argument("--outdir", default=".", help="PNG/MIDI出力ディレクトリ")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    results = []
    for a in args.audio:
        p = Path(a)
        if not p.exists():
            results.append({"file": p.name, "error": "not found"})
            continue
        try:
            results.append(_analyze_one(p, args.plot, args.midi, outdir))
        except Exception as exc:  # noqa: BLE001
            results.append({"file": p.name, "error": f"{type(exc).__name__}: {exc}"})

    out = make_success_result(
        summary=json.dumps(results, ensure_ascii=False, indent=2),
        full_data={"results": results},
        cache_key=None,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
