"""SSOT体系化 承認スキーマ自動化 Phase0: テーマ分類器（dry-run検証用）.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md

Phase0 は既存 approved_themes に対する LLM 分類の採用率を検証する（承認せず）。
LLM 呼び出しは Gemini API 直接（gemini_text.py 経由・spec§2・GLM 不可）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from scripts.obsidian.dir_manifests import _parse_frontmatter

CONFIDENCE_THRESHOLD = 0.7


def _parse_llm_themes(raw: str) -> dict:
    """Gemini のテキスト出力から {themes, confidence} を抽出する.

    Args:
        raw: Gemini 応答テキスト（JSON / JSONコードブロック / 埋め込みJSON を許容）。

    Returns:
        ``{"themes": list[str], "confidence": float}``。
        空入力は ``{"themes": [], "confidence": 0.0}``。
        confidence 省略時は 0.5（判定保留の中立値）。
    """
    if not raw or not raw.strip():
        return {"themes": [], "confidence": 0.0}

    # JSON コードブロック → 埋め込み JSON の順で抽出
    block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    inline_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    json_str = block_match.group(1) if block_match else (
        inline_match.group(0) if inline_match else None
    )

    if json_str is None:
        return {"themes": [], "confidence": 0.0}

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return {"themes": [], "confidence": 0.0}

    themes = [str(t).strip() for t in data.get("themes", []) if str(t).strip()]
    confidence = data.get("confidence", 0.5)
    return {"themes": themes, "confidence": float(confidence)}


def _map_to_existing(proposed: list[str], approved: list[str]) -> dict:
    """推論テーマを既存 approved_themes にマップする（spec§4 マッピング戦略）.

    Args:
        proposed: LLM が推論したテーマ名リスト。
        approved: 当該PJの既存 approved_themes リスト。

    Returns:
        ``{"matched": list[str], "new": list[str]}``。
        matched は既存テーマ名に正規化（部分一致で包含方向も許容）・重複排除。
        new は既存に該当しない新規候補（spec§4「要確認」）。
    """
    matched: list[str] = []
    new: list[str] = []
    for p in proposed:
        found = None
        for a in approved:
            if p == a or p in a or a in p:
                found = a
                break
        if found:
            if found not in matched:
                matched.append(found)
        else:
            if p not in new:
                new.append(p)
    return {"matched": matched, "new": new}


def compute_adoption_rate(per_file_results: list[dict]) -> float:
    """分類結果リストから採用率（matched 1件以上のファイル比率）を算出する.

    Args:
        per_file_results: 各ファイルの ``_map_to_existing`` 結果のリスト。

    Returns:
        0.0〜1.0 の採用率。結果が空なら 0.0。
        Phase0 ゲート（spec§3.1）は ≥0.90。
    """
    if not per_file_results:
        return 0.0
    adopted = sum(1 for r in per_file_results if r.get("matched"))
    return adopted / len(per_file_results)


def _call_gemini(prompt: str) -> str:
    """gemini_text.py 経由で Gemini API を呼び応答テキストを返す（spec§2 直接呼出）.

    Raises:
        RuntimeError: gemini_text.py が非0終了した場合。
    """
    gemini_script = Path.home() / ".claude/scripts/api/gemini_text.py"
    result = subprocess.run(
        [sys.executable, str(gemini_script), prompt],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini_text.py failed: {result.stderr.strip()}")
    return result.stdout


def _classify_file_themes(file_path: Path | str, approved: list[str]) -> dict:
    """1ファイルを Gemini 分類し既存テーマにマップした結果を返す.

    Args:
        file_path: 対象 ``01_DECISIONS/<project>/`` 配下の markdown ファイル。
        approved: 当該PJの既存 approved_themes。

    Returns:
        ``{"matched", "new", "proposed", "confidence", "needs_review"}``。
        needs_review は confidence < 0.7（spec§6・自動承認対象外）。
    """
    content = Path(file_path).read_text(encoding="utf-8")[:2000]
    approved_str = " / ".join(approved) if approved else "（既存テーマなし）"
    prompt = (
        "以下は SSOT の意思決定ログ1件です。"
        f"既存テーマ群 [{approved_str}] のいずれかに該当するテーマを選び、"
        "該当なしなら新規テーマ名を簡潔に提案してください。\n"
        'JSON形式 {"themes": [...], "confidence": 0.0〜1.0} で出力。\n\n'
        f"文書:\n{content}"
    )
    raw = _call_gemini(prompt)
    parsed = _parse_llm_themes(raw)
    mapped = _map_to_existing(parsed["themes"], approved)
    confidence = parsed["confidence"]
    return {
        "matched": mapped["matched"],
        "new": mapped["new"],
        "proposed": parsed["themes"],
        "confidence": confidence,
        "needs_review": confidence < CONFIDENCE_THRESHOLD,
    }


def _load_approved_themes(index_path: Path | str) -> list[str]:
    """_INDEX.md frontmatter の approved_themes（[A, B] 形式）をリスト化する.

    frontmatter 無し / approved_themes 無し / 空リストはいずれも [] を返す。
    """
    text = Path(index_path).read_text(encoding="utf-8")
    fm, _, _ = _parse_frontmatter(text)
    raw = fm.get("approved_themes", "").strip()
    raw = raw.lstrip("[").rstrip("]")
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def run_dry_run(project: str, ssot_root: Path | str | None = None) -> dict:
    """対象PJの全ファイルを dry-run 分類し採用率を集計する（承認せず・spec§3.1 Phase0）.

    Args:
        project: ``01_DECISIONS/<project>`` のプロジェクト名。
        ssot_root: SSOT ルート（省略時は ``~/projects/obsidian-ssot``）。

    Returns:
        ``{"per_file", "adoption_rate", "total", "approved"}``。
        Phase0 ゲートは adoption_rate ≥ 0.90。
    """
    if ssot_root is None:
        ssot_root = Path.home() / "projects/obsidian-ssot"
    proj_dir = Path(ssot_root) / "01_DECISIONS" / project
    approved = _load_approved_themes(proj_dir / "_INDEX.md")

    per_file: list[dict] = []
    for f in sorted(proj_dir.glob("*.md")):
        if f.name == "_INDEX.md":
            continue
        try:
            res = _classify_file_themes(f, approved)
        except RuntimeError as e:
            res = {"matched": [], "new": [], "proposed": [], "confidence": 0.0, "needs_review": True}
            res["error"] = str(e)
        res["file"] = f.name
        per_file.append(res)

    return {
        "per_file": per_file,
        "adoption_rate": compute_adoption_rate(per_file),
        "total": len(per_file),
        "approved": approved,
    }
