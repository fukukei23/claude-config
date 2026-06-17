"""api_base.py の単体テスト"""
from lib.api_base import make_error_result


def test_make_error_result_returns_normalized_json():
    """例外メッセージを統一JSON形式に正規化する"""
    result = make_error_result("ConnectionError: timeout")
    assert result["status"] == "error"
    assert result["summary"] is None
    assert result["full_data"] is None
    assert result["error"] == "ConnectionError: timeout"
