"""名曲DB への登録パイプライン。

run_pipeline() をローカル(raw)で実行し、features.json のみを SSOT へコピー。
音源MP3・楽譜PNG・stems は workdir（ローカル）に残置し SSOT に置かない。
"""
import argparse
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
    candidates_file: Path | None = None,
) -> dict:
    """1曲を解析し DB へ登録する（run_pipeline → 配置分離 → _index 更新・候補status更新）。

    Args:
        song_id: 曲ID（<GENRE>-<3桁>）。
        source: YouTube URL またはローカル MP3 パス。
        meta: DB固有メタ（title/artist/genre/commercial_rank/era/
              selection_reason/source_type/source_url/analyzed_at/analyze_phase）。
        ssot_db: SSOT の DB ルート。
        local_raw: ローカル raw ルート（音源/PNG/stems を置く）。
        index_file: _index.yaml のパス。
        candidates_file: _candidates.yaml のパス（省略可・指定時は該当曲の
            status を pending→registered に更新・コメント保持）。

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

    if candidates_file is not None:
        db_index.update_candidate_status(candidates_file, song_id)

    return {"id": song_id, "status": "registered", **meta}


DEFAULT_SSOT_DB = Path.home() / "projects/obsidian-ssot/reference/名曲DB"
DEFAULT_LOCAL_RAW = Path.home() / "Music/名曲DB_raw"


def main() -> None:
    """CLI エントリ: 名曲1曲を DB へ登録する。"""
    parser = argparse.ArgumentParser(
        description="名曲を analyze-song で解析し DB へ登録する"
    )
    parser.add_argument("song_id", help="曲ID (例: JPOP-001)")
    parser.add_argument("source", help="YouTube URL or ローカル MP3 パス")
    parser.add_argument("--title", required=True)
    parser.add_argument("--artist", required=True)
    parser.add_argument("--genre", required=True,
                        choices=["JPOP", "ROCK", "HIPHOP", "WAFU", "WORLD"])
    parser.add_argument("--commercial-rank", required=True,
                        choices=["million", "oricon1", "billboard_top10", "long_seller"])
    parser.add_argument("--era", required=True,
                        choices=["1970s", "1980s", "1990s", "2000s", "2010s", "2020s"])
    parser.add_argument("--selection-reason", required=True)
    parser.add_argument("--ssot-db", default=str(DEFAULT_SSOT_DB))
    parser.add_argument("--local-raw", default=str(DEFAULT_LOCAL_RAW))
    args = parser.parse_args()

    meta = {
        "title": args.title,
        "artist": args.artist,
        "genre": args.genre,
        "commercial_rank": args.commercial_rank,
        "era": args.era,
        "selection_reason": args.selection_reason,
        "source_type": "youtube" if args.source.startswith("http") else "local",
        "source_url": args.source if args.source.startswith("http") else "",
        "analyzed_at": date.today().isoformat(),
        "analyze_phase": "1b",
    }
    candidates_path = Path(args.ssot_db) / "_candidates.yaml"
    entry = register_one(
        args.song_id, args.source, meta,
        ssot_db=Path(args.ssot_db), local_raw=Path(args.local_raw),
        index_file=Path(args.ssot_db) / "_index.yaml",
        candidates_file=candidates_path if candidates_path.exists() else None,
    )
    print(f"registered: {entry['id']} -> {entry['features_path']}")


if __name__ == "__main__":
    main()
