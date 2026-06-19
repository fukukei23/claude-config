#!/usr/bin/env python3
"""librosa.pyin でメロディ音高(F0)を抽出し、サビ上がり・音域適合を判定する.

セクション別音域コンター（[L1]楽曲制作基礎 §G）を客観検証。
「サビが曲で一番高い」を数値判定。MiniMax 生成曲の選別支援。

人間の耳でなく音響DSPで「ドレミのどの音が出てるか」を自動抽出する。
セクション分割は構造タイムスタンプ未知のため時間比率（Verse=前半40% /
Chorus=後半40%）で簡易推定。

Usage:
    melody-judge.py --audio <path> [<path> ...]
"""
import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import make_success_result  # noqa: E402

# 男性ボーカル売れ線サビ音域（[L1]楽曲制作基礎 §G: C4-G4）
MALE_HIT_LOW = 60   # C4 (MIDI)
MALE_HIT_HIGH = 79  # G4 (MIDI)


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


def _analyze_one(path: Path) -> dict:
    """1曲のF0を抽出しセクション別音域を算出する."""
    import numpy as np
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    f0, voiced, _ = librosa.pyin(y, fmin=80, fmax=600, sr=sr)
    midi = librosa.hz_to_midi(f0)

    n = len(midi)
    verse_mask = voiced & (np.arange(n) < n * 0.4)
    chorus_mask = voiced & (np.arange(n) >= n * 0.6)
    verse_m = midi[verse_mask]
    chorus_m = midi[chorus_mask]

    vm = float(np.mean(verse_m)) if verse_m.size else None
    cm = float(np.mean(chorus_m)) if chorus_m.size else None
    rise = (cm - vm) if (vm is not None and cm is not None) else None

    valid = midi[voiced]
    return {
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


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。各曲の判定結果JSONを出力する."""
    parser = argparse.ArgumentParser(description="メロディ音域・サビ上がり判定")
    parser.add_argument(
        "--audio", nargs="+", required=True,
        help="判定対象の音声ファイル（複数可）",
    )
    args = parser.parse_args(argv)

    results = []
    for a in args.audio:
        p = Path(a)
        if not p.exists():
            results.append({"file": p.name, "error": "not found"})
            continue
        try:
            results.append(_analyze_one(p))
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
