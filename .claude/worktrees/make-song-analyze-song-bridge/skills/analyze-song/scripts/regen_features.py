"""features.py 正規化後、全30曲の features.json を MIDI中間ファイルから一括再生成する。

音源から Demucs + MIDI 抽出をやり直さず、残存 MIDI（~/Music/名曲DB_raw/<ID>/）から
analyze_features() のみを再実行して features.json を上書きする。
旧 features.json の meta/tempo/score/_log は analyze_features が返さないため保持し、
key/chords/melody/vocals/structure/(instrumentation) のみ更新する。

Usage:
    cd ~/projects/claude-config/skills/analyze-song
    ~/projects/claude-config/.venv/bin/python -m scripts.regen_features            # 全曲
    ~/projects/claude-config/.venv/bin/python -m scripts.regen_features JPOP-002   # 1曲のみ
"""
import json
import sys
from pathlib import Path

from scripts.features import analyze_features

RAW_ROOT = Path.home() / "Music/名曲DB_raw"
SSOT_DB = Path("/home/yn4416/projects/obsidian-ssot/reference/名曲DB")
STEM_PARTS = ("drums", "bass", "vocals", "other")


def regen_one(song_id: str) -> dict:
    """1曲の features.json を MIDI から再生成し、raw 側 + SSOT 側に上書き保存する。

    Args:
        song_id: 曲ID（例: "JPOP-002"）。

    Returns:
        再生成後の features dict。
    """
    work = RAW_ROOT / song_id
    if not (work / "vocals.mid").exists():
        raise FileNotFoundError(f"MIDI not found: {work}")

    old = json.loads((work / "features.json").read_text(encoding="utf-8"))
    duration_sec = float(old["structure"]["sections"][-1]["end"])
    stems_paths = {
        p: str(work / "stems" / f"{p}.wav")
        for p in STEM_PARTS
        if (work / "stems" / f"{p}.wav").exists()
    }

    result = analyze_features(
        vocals_mid=str(work / "vocals.mid"),
        accomp_mid=str(work / "accompaniment.mid"),
        duration_sec=duration_sec,
        stems_paths=stems_paths or None,
    )
    # meta/tempo/score/_log は保持（analyze_features が返さない）。features 部分のみ更新。
    old.update(result)
    payload = json.dumps(old, ensure_ascii=False, indent=2)
    (work / "features.json").write_text(payload, encoding="utf-8")
    ssot_dest = SSOT_DB / song_id / "features.json"
    if ssot_dest.parent.exists():
        ssot_dest.write_text(payload, encoding="utf-8")
    return old


def main(argv: list[str]) -> int:
    ids = argv[1:]
    if not ids:
        ids = sorted(p.name for p in RAW_ROOT.iterdir() if (p / "vocals.mid").exists())
    print(f"=== {len(ids)} 曲を再生成 ===")
    for sid in ids:
        feat = regen_one(sid)
        print(f"  {sid}: unique_progressions={feat['chords']['unique_progressions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
