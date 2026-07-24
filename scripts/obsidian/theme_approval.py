"""SSOT体系化 P3-C Phase1: _INDEX.md frontmatter の approved_themes 管理 + 承認ログ.

spec §4.4: LLMがテーマ候補生成→ユーザー承認→approved_themes frontmatter記録 + 承認行(日付・内容)。
承認フィードバックとして変更差分(diff)を返し、LLM誤記録をユーザーが検出できる経路を担保する
（「触らず」≠「確認せず」）。
"""
from __future__ import annotations

import difflib
from pathlib import Path

from scripts.obsidian.dir_manifests import _parse_frontmatter

_MANAGED_KEYS = ("project", "status", "last_verified")
_APPROVAL_LOG_HEADER = "## テーマ承認ログ"


def update_approved_themes(index_path: Path, themes: list[str], date: str) -> str:
    """_INDEX.md の approved_themes を更新し承認ログ行を追記、差分文字列を返す.

    Args:
        index_path: ``_INDEX.md`` の絶対パス。
        themes: 承認するテーマ名リスト（空リスト=承認解除で ``[]``）。
        date: ``YYYY-MM-DD`` 形式の承認日。

    Returns:
        変更差分の unified diff 文字列（ユーザー確認用・§4.4 承認フィードバック）。
    """
    original = index_path.read_text(encoding="utf-8")
    fm, fm_block, body = _parse_frontmatter(original)
    updates = {
        "project": fm.get("project", index_path.parent.name),
        "status": fm.get("status", "active"),
        "last_verified": fm.get("last_verified", date),
    }
    # managed3キー(先頭) → approved_themes → その他未知キー(行保持)
    header: list[str] = [f"{k}: {updates[k]}" for k in _MANAGED_KEYS]
    header.append(f"approved_themes: {_themes_yaml(themes)}")
    for line in (fm_block.splitlines() if fm_block else []):
        if ":" not in line:
            continue
        k = line.partition(":")[0].strip()
        if k in _MANAGED_KEYS or k == "approved_themes":
            continue
        header.append(line)
    new_fm = "---\n" + "\n".join(header) + "\n---\n"
    log_line = f"- {date}: themes=[{', '.join(themes)}]"
    if fm:
        # 主経路（全_INDEXはP3-BでFM付与済）: 本文に承認ログ追記
        new_text = new_fm + _append_approval_log(body, log_line)
    else:
        # 後方互換（FM無し・希）: FM挿入 + 末尾に承認ログセクション
        sep = "" if (original == "" or original.endswith("\n")) else "\n"
        new_text = new_fm + original + sep + "\n" + _APPROVAL_LOG_HEADER + "\n\n" + log_line + "\n"
    index_path.write_text(new_text, encoding="utf-8")
    return _format_diff(original, new_text)


def _themes_yaml(themes: list[str]) -> str:
    """テーマリストをFM値文字列へ（空は []）."""
    return "[" + ", ".join(themes) + "]" if themes else "[]"


def _append_approval_log(body: str, log_line: str) -> str:
    """本文に ## テーマ承認ログ セクションを確保し、最新承認行を上に積む."""
    if _APPROVAL_LOG_HEADER not in body:
        if body == "" or body.endswith("\n\n"):
            sep = ""
        elif body.endswith("\n"):
            sep = "\n"
        else:
            sep = "\n\n"
        return body + sep + _APPROVAL_LOG_HEADER + "\n\n" + log_line + "\n"
    idx = body.index(_APPROVAL_LOG_HEADER) + len(_APPROVAL_LOG_HEADER)
    nl = body.index("\n", idx)
    return body[: nl + 1] + "\n" + log_line + body[nl + 1 :]


def _format_diff(before: str, after: str) -> str:
    """unified diff 文字列を返す（LLM誤記録検出用・§4.4）."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
