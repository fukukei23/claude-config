"""実DB全体の preprocess サニティテスト（フラット表記・サイレント除外検出）。"""
import json
from pathlib import Path

import pytest

from scripts import preprocess

_REAL_DB = Path("/home/yn4416/projects/obsidian-ssot/reference/名曲DB")


@pytest.mark.skipif(not _REAL_DB.exists(), reason="実DB不在")
def test_real_db_no_song_silently_dropped():
    """30曲すべて preprocess 成功（None 返却なし=サイレント除外なし）。"""
    feat_paths = sorted(_REAL_DB.glob("*/features.json"))
    assert len(feat_paths) >= 30, f"DB曲数不足: {len(feat_paths)}"
    dropped = []
    for p in feat_paths:
        feat = json.loads(p.read_text(encoding="utf-8"))
        if preprocess.preprocess(feat) is None:
            dropped.append(p.parent.name)
    assert dropped == [], f"サイレント除外された曲: {dropped}"


@pytest.mark.skipif(not _REAL_DB.exists(), reason="実DB不在")
def test_real_db_range_valid_sane():
    """range_valid=True の曲は high>=low かつ (high-low)<=48。"""
    for p in sorted(_REAL_DB.glob("*/features.json")):
        feat = json.loads(p.read_text(encoding="utf-8"))
        v = preprocess.preprocess(feat)
        if v is None:
            continue
        if v["range_valid"]:
            assert v["range_high_midi"] >= v["range_low_midi"], f"{p.parent.name}: high<low"
            assert v["range_high_midi"] - v["range_low_midi"] <= 48, f"{p.parent.name}: >48 semitones"
