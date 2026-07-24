"""CLI承認コマンド: _INDEX.md の approved_themes を承認する（SSOT体系化 P3-C Phase1 §4.4）.

人間はファイル直接触らず CLI コマンドのみで承認する契約。
使い方: approve-themes <project> <theme1,theme2,...> [--date YYYY-MM-DD]
       approve-themes <project> -            # 承認解除（空）
"""
import argparse
import sys
from datetime import date as _date
from pathlib import Path

from scripts.obsidian.theme_approval import update_approved_themes


def main() -> None:
    """CLI エントリ: ``approve-themes <project> <themes>`` で承認実行・差分を表示."""
    p = argparse.ArgumentParser(description="_INDEX.md approved_themes 承認(§4.4)")
    p.add_argument("project", help="01_DECISIONS/<project>")
    p.add_argument("themes", help='カンマ区切りテーマ（"-" で承認解除）')
    p.add_argument("--date", default=None, help="YYYY-MM-DD（省略=今日）")
    args = p.parse_args()

    themes = (
        [] if args.themes == "-"
        else [t.strip() for t in args.themes.split(",") if t.strip()]
    )
    today = args.date or _date.today().isoformat()
    index = (
        Path.home()
        / "projects/obsidian-ssot/01_DECISIONS"
        / args.project
        / "_INDEX.md"
    )
    diff = update_approved_themes(index, themes, today)
    print(f"approved: {args.project} themes={themes} ({today})")
    print("--- diff（確認）---")
    print(diff)


if __name__ == "__main__":
    sys.exit(main())
