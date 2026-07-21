"""CLI承認コマンド: pending meaning を本hash化(固定)する（SSOT体系化 P1 Task 3）.

人間はファイル直接触らず CLI コマンドのみで承認する契約（spec R1/R7）。
approve_manifest() は pending_approval フラグ操作のみを行い、
meaning_hash は初回生成時（Task 2 build_manifest_entry）に既に固定済み。
"""
import argparse
import json
import sys
from pathlib import Path

from scripts.obsidian.dir_manifests import validate_manifest


def approve_manifest(manifest_path: Path, dir_path: str) -> None:
    """指定 dir の pending_approval を False にする（meaning_hash は不変）.

    Args:
        manifest_path: ``.dir-manifest.json`` の絶対パス。
        dir_path: 承認するディレクトリパス文字列。

    Raises:
        SystemExit: 対象 dir が存在しない・既に承認済(pending_approval=True 无)時。
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for d in data["directories"]:
        if d["path"] == dir_path and d.get("pending_approval"):
            d["pending_approval"] = False
            break
    else:
        sys.exit(f"pending entry not found: {dir_path}")
    validate_manifest(data)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    """CLI エントリ: ``approve-meaning <project> <dir>`` で承認実行."""
    p = argparse.ArgumentParser(
        description="manifest meaning 承認(仮hash→本hash固定)",
    )
    p.add_argument("project", help="01_DECISIONS/<project>")
    p.add_argument("dir", help="承認するdir path")
    args = p.parse_args()
    manifest = (
        Path.home()
        / "projects/obsidian-ssot/01_DECISIONS"
        / args.project
        / ".dir-manifest.json"
    )
    approve_manifest(manifest, args.dir)
    print(f"approved: {args.project}/{args.dir}")


if __name__ == "__main__":
    main()
