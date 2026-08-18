"""aggregate_judgment_ledger.py（判断収束台帳_計測.md生成）の表駆動テスト.

正典は各レビューのrevised_proposal.md frontmatter。台帳は集約viewであり、
生成の冪等性・未解析の見える化・証跡クロス検証を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_aggregate_judgment_ledger.py -q
"""

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
    """スクリプトをデフォルトdry-run付きで実行する."""
    cmd = ["python3", str(SCRIPT), "--target", target, "--output", str(output), "--dry-run"]
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
    assert "| 2026-08-18 | テスト対象 | 21 | 3 | 2 | 判定用 |  |" in r.stdout
    assert "集約対象: 1件 / 未解析: 0件" in r.stdout


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
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "集約対象: 0件 / 未解析: 1件" in text


def test_review_log_md_is_not_picked_up(tmp_path):
    # review_log.md には本文中に findings_total が出現するが対象外（厳密glob）
    make_review(tmp_path, "2026-08-18_xレビュー", REVIEW_OK)
    (tmp_path / "2026-08-18_xレビュー" / "review_log.md").write_text(
        "findings_total: 99\n", encoding="utf-8"
    )
    r = run(str(tmp_path / "*" / "revised_proposal.md"), tmp_path / "台帳.md")
    text = (tmp_path / "台帳.md").read_text(encoding="utf-8")
    assert "| 99 |" not in text
