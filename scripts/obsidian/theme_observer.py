"""SSOT体系化 承認スキーマ自動化 Phase2 最小観測(A‴′): 新規ファイル観測機構.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md §7.1
01_DECISIONSへの新規ファイル追加時だけ dry-run 自動発火 → 新規テーマ候補を通知/ログ。
承認は人が ``--apply`` で行う(Phase1半自動維持)・本モジュールは分類しない(観測専任)。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__all__ = ["detect_new_decision_files", "run_observation", "log_observation"]


def detect_new_decision_files(diff_output: str) -> list[tuple[str, str]]:
    """git diff --name-only --diff-filter=A の出力から新規 01_DECISIONS ファイルを抽出.

    Args:
        diff_output: git diff の出力(1行1ファイルパス)。

    Returns:
        ``[(project, filename), ...]``。``_INDEX.md`` は除外。
        パス形式: ``01_DECISIONS/<project>/<filename>.md``。
    """
    results: list[tuple[str, str]] = []
    for raw in diff_output.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        parts = line.split("/")
        # 01_DECISIONS/<project>/<file>.md (最低3セグメント)
        if len(parts) < 3 or parts[0] != "01_DECISIONS":
            continue
        filename = parts[-1]
        if not filename.endswith(".md") or filename == "_INDEX.md":
            continue
        project = parts[1]
        results.append((project, filename))
    return results


def run_observation(
    project: str,
    trigger_file: str,
    ssot_root: Path | str | None = None,
    classify_fn: Callable[..., dict] | None = None,
    load_approved_fn: Callable[..., list[str]] | None = None,
) -> dict:
    """新規ファイル(trigger_file)単体を分類 → 新規テーマ候補抽出.

    A‴′は「新規ファイル追加時だけ dry-run 発火」が目的。PJ全ファイル分類
    (run_dry_run)は大PJでGemini大量呼出→timeoutするため、trigger_file 1件のみ
    分類する(軽量・Gemini 1回呼出)。採用率集計は Phase0 の別用途。

    Args:
        project: ``01_DECISIONS/<project>`` のプロジェクト名。
        trigger_file: 新規追加ファイル名(``01_DECISIONS/<project>/`` 配下)。
        ssot_root: SSOT ルート(省略時は ``~/projects/obsidian-ssot``)。
        classify_fn: 1ファイル分類関数(依存注入・テスト用。デフォルト ``_classify_file_themes``)。
        load_approved_fn: approved_themes 読込関数(依存注入・テスト用)。

    Returns:
        ``{"project", "trigger_file", "new_themes", "matched", "confidence",
        "needs_review", "timestamp"}``。
    """
    if classify_fn is None:
        from scripts.obsidian.theme_classifier import _classify_file_themes as classify_fn
    if load_approved_fn is None:
        from scripts.obsidian.theme_classifier import _load_approved_themes as load_approved_fn

    if ssot_root is None:
        ssot_root = Path.home() / "projects/obsidian-ssot"
    proj_dir = Path(ssot_root) / "01_DECISIONS" / project
    approved = load_approved_fn(proj_dir / "_INDEX.md")
    result = classify_fn(proj_dir / trigger_file, approved)
    return {
        "project": project,
        "trigger_file": trigger_file,
        "new_themes": result.get("new", []),
        "matched": result.get("matched", []),
        "confidence": result.get("confidence", 0.0),
        "needs_review": result.get("needs_review", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def log_observation(log_path: Path | str, entry: dict) -> None:
    """観測ログ(JSON Lines)に1エントリ追記.

    Args:
        log_path: ログファイルパス(親ディレクトリは自動作成)。
        entry: 記録するdict(run_observation の戻り値等)。
    """
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
