"""名曲DB への登録パイプライン。

run_pipeline() をローカル(raw)で実行し、features.json のみを SSOT へコピー。
音源MP3・楽譜PNG・stems は workdir（ローカル）に残置し SSOT に置かない。
"""
import shutil
from pathlib import Path


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
