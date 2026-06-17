"""api_base.py の単体テスト"""
import json
from pathlib import Path

from lib.api_base import make_error_result, make_success_result


def test_make_error_result_returns_normalized_json():
    """例外メッセージを統一JSON形式に正規化する"""
    result = make_error_result("ConnectionError: timeout")
    assert result["status"] == "error"
    assert result["summary"] is None
    assert result["full_data"] is None
    assert result["error"] == "ConnectionError: timeout"


def test_make_success_result_saves_full_data_and_returns_summary(
    tmp_path, monkeypatch
):
    """成功時: full_dataをキャッシュファイルに保存し、summaryのみ返す"""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = make_success_result(
        summary="ジャンル: HIPHOP / BPM: 90",
        full_data={"sections": ["intro", "verse", "chorus"], "bpm": 90},
        cache_key="gemini_abc123",
    )

    assert result["status"] == "ok"
    assert result["summary"] == "ジャンル: HIPHOP / BPM: 90"
    assert result["error"] is None
    assert result["full_data"].endswith(".json")
    cache_path = Path(result["full_data"])
    assert cache_path.exists()
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved["bpm"] == 90
