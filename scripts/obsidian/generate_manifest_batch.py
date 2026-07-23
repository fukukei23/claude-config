"""SSOT体系化 P3-B: 複数プロジェクトへ frontmatter + manifest を一括生成するCLI.

Usage:
    python3 -m scripts.obsidian.generate_manifest_batch \\
        --ssot-root ~/projects/obsidian-ssot \\
        --projects career,infra,_shared \\
        --date 2026-07-24 [--dry-run]

各プロジェクトで generate_manifest_for_project を呼ぶ。
1件失敗しても skip継続（失敗耐性・spec R2）。dry-run は実ファイル変更なし。
"""
import argparse
import sys
from pathlib import Path

from scripts.obsidian.dir_manifests import generate_manifest_for_project

EXTERNAL_REPO_PROJECTS = {
    "ai-ceo-advisor", "atelier-kyo-manager", "claude-code-guide", "claude-config",
    "contextforge", "demo-site-sales", "dev-textbook", "mnp_manager",
    "openclaw-stack", "orchestrix", "python-reading-guide", "ssh-guide",
    "ssot-guide", "tech-glossary", "x-automation", "zenn",
}


def _resolve_repo_path(project: str) -> Path | None:
    """プロジェクト名 → 外部リポパス（無ければNone=SSOT内のみ）."""
    if project in EXTERNAL_REPO_PROJECTS:
        return Path.home() / "projects" / project
    return None


def main() -> int:
    """CLI エントリ: プロジェクト群へ manifest 一括生成."""
    p = argparse.ArgumentParser(description="P3-B manifest一括生成CLI")
    p.add_argument("--ssot-root", required=True, help="obsidian-ssot ルート")
    p.add_argument("--projects", required=True, help="カンマ区切りプロジェクト名")
    p.add_argument("--date", required=True, help="YYYY-MM-DD (last_verified)")
    p.add_argument("--status", default="active", help="frontmatter status既定値")
    p.add_argument("--dry-run", action="store_true", help="変更なし・計画表示のみ")
    args = p.parse_args()

    ssot = Path(args.ssot_root).expanduser()
    projects = [x.strip() for x in args.projects.split(",") if x.strip()]
    print(
        f"[p3b-batch] 対象 {len(projects)}件 / date={args.date} "
        f"/ dry-run={args.dry_run}"
    )

    ok, fail = 0, 0
    for proj in projects:
        repo_path = _resolve_repo_path(proj)
        if args.dry_run:
            kind = "外部リポ" if repo_path else "SSOT内"
            print(f"  [DRY] {proj} ({kind}) → 生成予定")
            ok += 1
            continue
        try:
            result = generate_manifest_for_project(
                ssot_root=ssot, project=proj, repo_path=repo_path,
                date=args.date, status=args.status,
            )
            print(
                f"  OK {proj}: fm={result['frontmatter_changed']} "
                f"created={result['manifest_created']} "
                f"pending={result['pending_count']}"
            )
            ok += 1
        except Exception as e:  # noqa: BLE001 - skip継続(spec R2)
            print(f"  FAIL {proj}: {type(e).__name__}: {e}")
            fail += 1
    print(f"[p3b-batch] 完了: ok={ok} fail={fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
