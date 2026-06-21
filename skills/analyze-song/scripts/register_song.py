"""名曲DB への登録パイプライン。

run_pipeline() をローカル(raw)で実行し、features.json のみを SSOT へコピー。
音源MP3・楽譜PNG・stems は workdir（ローカル）に残置し SSOT に置かない。
"""
import shutil
from datetime import date
from pathlib import Path

from scripts import analyze_song, db_index


def split_to_db(workdir: Path, song_id: str, ssot_db: Path) -> Path:
    """workdir 内の features.json を SSOT へコピーする。

    音源MP3・楽譜PNG・stems は workdir（ローカル）に残置し SSOT に置かない。

    Args:
        workdir: run_pipeline の出力ディレクトリ（ローカル raw 側）。
        song_id: 曲ID。
        ssot_db: SSOT の DB ルート（reference/名曲DB/）。

    Returns:
        コピー先の features.json パス。
    """
    src = Path(workdir) / "features.json"
    dest_dir = Path(ssot_db) / song_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "features.json"
    shutil.copy2(src, dest)
    return dest


def register_one(
    song_id: str,
    source: str,
    meta: dict,
    ssot_db: Path,
    local_raw: Path,
    index_file: Path,
) -> dict:
    """1曲を解析し DB へ登録する（run_pipeline → 配置分離 → _index 更新）。

    Args:
        song_id: 曲ID（<GENRE>-<3桁>）。
        source: YouTube URL またはローカル MP3 パス。
        meta: DB固有メタ（title/artist/genre/commercial_rank/era/
              selection_reason/source_type/source_url/analyzed_at/analyze_phase）。
        ssot_db: SSOT の DB ルート。
        local_raw: ローカル raw ルート（音源/PNG/stems を置く）。
        index_file: _index.yaml のパス。

    Returns:
        _index.yaml に追記されたエントリ辞書。
    """
    ssot_db = Path(ssot_db)
    local_raw = Path(local_raw)
    index_file = Path(index_file)

    workdir = local_raw / song_id
    analyze_song.run_pipeline(source, workdir, title=meta["title"])
    split_to_db(workdir, song_id, ssot_db)

    meta = {**meta, "features_path": f"{song_id}/features.json"}
    if index_file.exists():
        index = db_index.load_index(index_file)
    else:
        index = {
            "version": db_index.SCHEMA_VERSION,
            "updated": date.today().isoformat(),
            "songs": [],
        }
    db_index.add_entry(index, song_id, meta)
    index["updated"] = date.today().isoformat()
    db_index.save_index(index_file, index)

    return {"id": song_id, "status": "registered", **meta}
