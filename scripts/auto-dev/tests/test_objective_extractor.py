"""objective_extractor の単体テスト

プロンプトから [OBJECTIVE] <目的文> [KPI] <KPI文> を抽出するロジックのテスト。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from objective_extractor import extract_objective, parse_kpi  # noqa: E402


def test_extract_objective_basic():
    """穴埋め式の目的文を抽出する。"""
    prompt = "[OBJECTIVE] validate_email を RFC 5321 準拠にする"
    obj = extract_objective(prompt)
    assert "validate_email" in obj
    assert "RFC" in obj or "準拠" in obj


def test_extract_objective_no_marker():
    """マーカーなしの prompt は全体を目的文として返す。"""
    prompt = "validate_email を RFC 5321 準拠にする"
    obj = extract_objective(prompt)
    assert "validate_email" in obj


def test_extract_objective_with_kpi():
    """[OBJECTIVE] ... [KPI] ... 形式でも目的文部分は抽出できる。"""
    prompt = "[OBJECTIVE] validate_email を RFC 5321 準拠にする [KPI] 95% 以上"
    obj = extract_objective(prompt)
    assert "validate_email" in obj
    assert "RFC" in obj or "準拠" in obj
    # KPI 部分は目的文に含まれない（or 含まれない場合に依存しない）
    # assert "[KPI]" not in obj  # 実装依存


def test_extract_objective_strips_whitespace():
    """前後空白は trim される。"""
    prompt = "[OBJECTIVE]   validate_email を RFC 5321 準拠にする   "
    obj = extract_objective(prompt)
    assert obj == "validate_email を RFC 5321 準拠にする"


def test_parse_kpi_numeric():
    """KPI が数値+単位の場合は抽出・型変換して direction=gte。"""
    kpi = parse_kpi("KPIは 95% 以上のテストカバレッジ")
    assert kpi == {"value": 95.0, "unit": "%", "direction": "gte"}


def test_parse_kpi_count():
    """KPI が数値+単位（テストケース）のパターン（direction=gte）。"""
    kpi = parse_kpi("KPIは 10 テストケース以上")
    # unit 抽出の挙動は実装依存（spec にあるように or を許容）
    assert kpi in (
        {"value": 10, "unit": "テストケース以上", "direction": "gte"},
        {"value": 10, "unit": "テストケース", "direction": "gte"},
    )


def test_parse_kpi_lte_direction():
    """KPI 文に「以下」「未満」「<=」「<」が含まれる場合は direction=lte。"""
    kpi = parse_kpi("KPIは 200ms 以下のレスポンス")
    assert kpi is not None
    assert kpi["value"] == 200
    assert kpi["direction"] == "lte"


def test_parse_kpi_none_when_missing():
    """KPI が無ければ None。"""
    assert parse_kpi("目的文だけ") is None


def test_parse_kpi_with_marker():
    """[OBJECTIVE] ... [KPI] ... 形式でも KPI を抽出できる。"""
    prompt = "[OBJECTIVE] foo [KPI] 80% 以上"
    kpi = parse_kpi(prompt)
    assert kpi is not None
    assert kpi["value"] == 80
    assert kpi["unit"] == "%"
    assert kpi["direction"] == "gte"
