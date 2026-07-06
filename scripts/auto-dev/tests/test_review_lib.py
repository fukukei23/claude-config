"""review_lib.py の JSON 抽出と severity 正規化テスト

multi-llm-review スキルのコアロジック（JSON 抽出・severity 正規化）を
Python 関数化した review_lib.py の単体テスト。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from review_lib import extract_json_from_text, normalize_severity  # noqa: E402


def test_extract_json_from_text_simple_object():
    """前後の散文に挟まれた素の JSON オブジェクトを抽出。"""
    text = 'Some prose. {"critical": ["x"], "high": ["y"]} More prose.'
    assert extract_json_from_text(text) == {"critical": ["x"], "high": ["y"]}


def test_extract_json_from_text_code_fenced():
    """```json ... ``` フェンス内の JSON を抽出（フェンス優先）。"""
    text = '```json\n{"critical": ["a"]}\n```'
    assert extract_json_from_text(text) == {"critical": ["a"]}


def test_extract_json_from_text_code_fenced_no_lang():
    """言語指定なしフェンス ``` ... ``` 内の JSON も抽出。"""
    text = '```\n{"low": ["b"]}\n```'
    assert extract_json_from_text(text) == {"low": ["b"]}


def test_extract_json_from_text_with_surrounding_text():
    """日本語の前置き／後置きが前後にある JSON を抽出。"""
    text = '結果は以下の通り。\n{"low": ["minor"]}\n以上です。'
    assert extract_json_from_text(text) == {"low": ["minor"]}


def test_extract_json_from_text_nested_object():
    """ネストしたオブジェクトも greedy match で正しく抽出。"""
    text = 'prefix {"a": {"b": 1}, "c": [1, 2]} suffix'
    assert extract_json_from_text(text) == {"a": {"b": 1}, "c": [1, 2]}


def test_extract_json_from_text_invalid_raises():
    """JSON オブジェクトが無い場合は ValueError。"""
    with pytest.raises(ValueError, match="JSON object not found"):
        extract_json_from_text("no json here")


def test_extract_json_from_text_invalid_only_primitive():
    """プリミティブだけの場合はオブジェクトではないので ValueError。"""
    with pytest.raises(ValueError, match="JSON object not found"):
        extract_json_from_text("42 and true")


def test_normalize_severity_known():
    """既知の severity は正規化して返す。"""
    assert normalize_severity("critical") == "critical"
    assert normalize_severity("HIGH") == "high"
    assert normalize_severity("Med") == "med"
    assert normalize_severity("medium") == "med"
    assert normalize_severity("low") == "low"


def test_normalize_severity_unknown_defaults_to_low():
    """未知の severity は 'low' にフォールバック（安全側）。"""
    assert normalize_severity("warning") == "low"
    assert normalize_severity("info") == "low"


def test_normalize_severity_empty_defaults_to_low():
    """空文字列は 'low' にフォールバック。"""
    assert normalize_severity("") == "low"