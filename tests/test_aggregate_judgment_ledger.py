"""aggregate_judgment_ledger.py（判断収束台帳_計測.md生成）の表駆動テスト.

正典は各レビューのrevised_proposal.md frontmatter。台帳は集約viewであり、
生成の冪等性・未解析の見える化・証跡クロス検証を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_aggregate_judgment_ledger.py -q
"""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "obsidian" / "aggregate_judgment_ledger.py"

REVIEW_OK = """---
date: 2026-08-18
target: テスト対象
findings_total: 21
converted_to_cmd: 3
overturned_by_measurement: 2
---

# 改訂案

## 実測証跡

### 証跡1

grep -c ...

### 証跡2

wc -l ...
"""


def run(target: str, output: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    """スクリプトを書込モードで実行する（dry-runは extra=["--dry-run"] で指定）."""
    cmd = ["python3", str(SCRIPT), "--target", target, "--output", str(output)]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True)


def make_review(root: Path, name: str, content: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    f = d / "revised_proposal.md"
    f.write_text(content, encoding="utf-8")
    return f


def test_generates_row_from_frontmatter(tmp_path):
    make_review(tmp_path, "2026-08-18_テスト対象レビュー", REVIEW_OK)
    out = tmp_path / "台帳.md"
    r = run(str(tmp_path / "*" / "revised_proposal.md"), out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    # v2列追加（decision_changed / negative_effect）・REVIEW_OKに値が無ければ —
    assert "| 2026-08-18 | テスト対象 | 21 | 3 | 2 | — | — | 判定用 |  |" in text
    assert "集約対象: 1件 / 未解析: 0件" in text


def test_bom_crlf_review_is_parsed(tmp_path):
    # BOM付き + CRLFのレビューでも解析できる
    content = "﻿" + REVIEW_OK.replace("\n", "\r\n")
    make_review(tmp_path, "2026-08-18_BOMレビュー", content)
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    assert r.returncode == 0, r.stderr
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "| 21 | 3 | 2 |" in text


def test_missing_frontmatter_is_listed_as_unparsed(tmp_path):
    (tmp_path / "2026-08-13_旧レビュー").mkdir()
    (tmp_path / "2026-08-13_旧レビュー" / "revised_proposal.md").write_text(
        "# 改訂案（frontmatter無し）\n", encoding="utf-8"
    )
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    assert r.returncode == 0, r.stderr
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "集約対象: 0件 / 未解析: 1件" in text
    assert "2026-08-13_旧レビュー/revised_proposal.md" in text


def test_non_numeric_frontmatter_is_unparsed(tmp_path):
    content = REVIEW_OK.replace("findings_total: 21", "findings_total: 不明")
    make_review(tmp_path, "2026-08-18_壊れレビュー", content)
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "集約対象: 0件 / 未解析: 1件" in text


def test_review_log_md_is_not_picked_up(tmp_path):
    # review_log.md には本文中に findings_total が出現するが対象外（厳密glob）
    make_review(tmp_path, "2026-08-18_xレビュー", REVIEW_OK)
    (tmp_path / "2026-08-18_xレビュー" / "review_log.md").write_text(
        "findings_total: 99\n", encoding="utf-8"
    )
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "| 99 |" not in text


def test_overturned_without_evidence_is_flagged(tmp_path):
    # overturned>0 なのに証跡0件 → 要修正（frontmatterの嘘を機械検出）
    content = REVIEW_OK.replace(
        "### 証跡1\n\ngrep -c ...\n\n### 証跡2\n\nwc -l ...\n", ""
    )
    make_review(tmp_path, "2026-08-18_無証拠レビュー", content)
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "⚠️要修正(証跡0)" in text


def test_overturned_greater_than_evidence_is_flagged(tmp_path):
    # overturned=5 > 証跡2件 → 要修正（証拠不足・数値の盛り検出）
    content = REVIEW_OK.replace(
        "overturned_by_measurement: 2", "overturned_by_measurement: 5"
    )
    make_review(tmp_path, "2026-08-18_盛りレビュー", content)
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "⚠️要修正(証跡不足)" in text


def test_overturned_zero_with_no_evidence_is_ok(tmp_path):
    # overturned=0・証跡0 は正当（空欄ステータス）
    content = REVIEW_OK.replace(
        "overturned_by_measurement: 2", "overturned_by_measurement: 0"
    )
    content = content.replace(
        "## 実測証跡\n\n### 証跡1\n\ngrep -c ...\n\n### 証跡2\n\nwc -l ...\n", ""
    )
    make_review(tmp_path, "2026-08-18_通常レビュー", content)
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "⚠️要修正" not in text


def test_idempotent_two_runs_identical(tmp_path):
    # 2回連続実行で出力が完全一致（冪等・出力に時刻等の非決定要素を含まない）
    make_review(tmp_path, "2026-08-18_レビューA", REVIEW_OK)
    make_review(tmp_path, "2026-08-18_レビューB", REVIEW_OK)
    out = tmp_path / "台帳.md"
    run(str(tmp_path / "*" / "revised_proposal.md"), out)
    first = out.read_text(encoding="utf-8")
    run(str(tmp_path / "*" / "revised_proposal.md"), out)
    assert out.read_text(encoding="utf-8") == first


def test_empty_target_generates_empty_table(tmp_path):
    # 対象0件でも空表を生成（クラッシュしない）
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    assert r.returncode == 0, r.stderr
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "（計測対象レビューなし）" in text


def test_dry_run_does_not_write(tmp_path):
    make_review(tmp_path, "2026-08-18_レビュー", REVIEW_OK)
    out = tmp_path / "台帳.md"
    r = run(str(tmp_path / "*" / "revised_proposal.md"), out, extra=["--dry-run"])
    assert r.returncode == 0
    assert not out.exists()
    assert "| 21 | 3 | 2 |" in r.stdout


def test_date_and_target_fallback_from_dirname(tmp_path):
    # frontmatterにdate/targetが無い → ディレクトリ名のYYYY-MM-DD接頭辞から補完
    content = REVIEW_OK.replace("date: 2026-08-18\ntarget: テスト対象\n", "")
    make_review(tmp_path, "2026-08-16_フロント欠損レビュー", content)
    run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "| 2026-08-16 | フロント欠損レビュー | 21 | 3 | 2 |" in text


def test_manual_retrospective_section_is_in_header(tmp_path):
    # 遡及手記載セクションはHEADER固定文言（再生成で消えない）
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md", extra=["--dry-run"])
    assert r.returncode == 0
    assert "手記載（遡及" in r.stdout
    assert "判定用(遡及)" in r.stdout


# ---------------------------------------------------------------
# 二源化（ingest DB 一次・glob 照合・バックログL825・台帳スキーマv2）

DB_ROW = {
    "ts": "2026-09-01T01:00:00+0900",
    "round_id": "20260901-010000",
    "topic": "ingestテスト",
    "proposal_path": "__PLACEHOLDER__",
    "findings_total": 21,
    "overturned_by_measurement": 2,
    "decision_changed": "no",
    "negative_effect": False,
    "converted_to_cmd": 3,
    "evidence": 2,
    "schema_ok": True,
    "source": "annotate",
}


def make_db(tmp_path: Path, rows: list[dict]) -> Path:
    """judgment-ledger.jsonl 相当のDBファイルを作る."""
    db = tmp_path / "judgment-ledger.jsonl"
    with open(db, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return db


def run_with_db(target: str, output: Path, db: Path) -> subprocess.CompletedProcess:
    cmd = ["python3", str(SCRIPT), "--target", target, "--output", str(output),
           "--ledger-db", str(db)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_db_row_rendered_with_v2_columns(tmp_path):
    # DB行 + 対応ファイル存在 → 台帳に行が出る（v2列 decision_changed / negative_effect 含む）
    prop = make_review(tmp_path, "2026-09-01_対象レビュー", REVIEW_OK)
    db = make_db(tmp_path, [{**DB_ROW, "proposal_path": str(prop.resolve())}])
    out = tmp_path / "台帳.md"
    r = run_with_db(str(tmp_path / "*" / "revised_proposal.md"), out, db)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "| 21 | 3 | 2 |" in text           # findings / converted / overturned
    assert "| no | false |" in text            # decision_changed / negative_effect
    assert "ingest漏れ" not in text            # DBと照合済みなので警告無し


def test_db_row_without_file_shows_計測未完(tmp_path):
    # fail条件①: DBにあってファイルが無いroundは「計測未完(未作成)」として台帳に載る
    db = make_db(tmp_path, [{**DB_ROW, "proposal_path": str(tmp_path / "ghost.md")}])
    out = tmp_path / "台帳.md"
    r = run_with_db(str(tmp_path / "*" / "revised_proposal.md"), out, db)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "計測未完(未作成)" in text
    assert "ingestテスト" in text              # topic が載る（静かに漏れない）


def test_glob_file_without_db_row_warns_ingest漏れ(tmp_path):
    # fail条件②: globにあってDBに無い = ingest漏れ警告付きで載せる
    make_review(tmp_path, "2026-08-18_未ingestレビュー", REVIEW_OK)
    db = make_db(tmp_path, [])
    out = tmp_path / "台帳.md"
    r = run_with_db(str(tmp_path / "*" / "revised_proposal.md"), out, db)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "⚠️ingest漏れ" in text
    assert "2026-08-18_未ingestレビュー" in text  # 警告付きでも行は载る


def test_db_file_value_mismatch_is_flagged(tmp_path):
    # 照合: DBとfrontmatterの数値が食い違う → ⚠️不一致（正典はfrontmatter）
    prop = make_review(tmp_path, "2026-09-01_不一致レビュー", REVIEW_OK)  # ft=21
    db = make_db(tmp_path, [{**DB_ROW, "proposal_path": str(prop.resolve()),
                             "findings_total": 99}])
    out = tmp_path / "台帳.md"
    r = run_with_db(str(tmp_path / "*" / "revised_proposal.md"), out, db)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "⚠️不一致" in text


def test_withdrawal_criterion_in_header(tmp_path):
    # 撤退基準（過去10回 decision_changed=no 且つ overturned=0 → 頻度見直し）が台帳ヘッダに明記される
    db = make_db(tmp_path, [])
    out = tmp_path / "台帳.md"
    r = run_with_db(str(tmp_path / "*" / "revised_proposal.md"), out, db)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "撤退基準" in text
    assert "decision_changed=no" in text


def test_no_db_option_keeps_legacy_behavior(tmp_path):
    # --ledger-db 無し = 従来どおりglob単源（後方互換・既存テスト全てこの経路）
    make_review(tmp_path, "2026-08-18_従来レビュー", REVIEW_OK)
    out = tmp_path / "台帳.md"
    r = run(str(tmp_path / "*" / "revised_proposal.md"), out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "| 21 | 3 | 2 |" in text
    assert "ingest漏れ" not in text
