"""2026-08-17 フォールバック根本改善のテスト.

対象:
- UsageTracker._parse_quotas（monitor APIレスポンス解析）
- UsageTracker.get_usage（max(5h, week)判定・未取得時0.0・失敗時前回値維持）
- ModelRouter.determine_mode / route_model（95%一括の2段階ルーティング）
- ProxyServer._handle_429（新チェーン: MiniMax先 → GLM-4.7-Flash最後の砦 → 503）

実行: cd scripts/glm-rate-proxy && PYTHONPATH=src python3 -m pytest tests/ -q
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from glm_rate_proxy.config import load_config
from glm_rate_proxy.model_router import ModelRouter
from glm_rate_proxy.proxy import ProxyServer
from glm_rate_proxy.upstream import RateLimitError, UpstreamError
from glm_rate_proxy.usage_tracker import UsageTracker


def _make_config():
    """テスト用設定（ユーザーconfig.jsonの影響を受けないようDEFAULTSベース）."""
    cfg = load_config("/nonexistent/config.json")
    return cfg


# ---- _parse_quotas ----

class TestParseQuotas:
    def test_実api構造から5hと週を抽出(self):
        data = {"code": 200, "data": {"limits": [
            {"type": "TIME_LIMIT", "unit": 5, "number": 1, "percentage": 1},
            {"type": "TOKENS_LIMIT", "unit": 3, "number": 5, "percentage": 2},
            {"type": "TOKENS_LIMIT", "unit": 6, "number": 1, "percentage": 91},
        ]}}
        assert UsageTracker._parse_quotas(data) == (2.0, 91.0)

    def test_5hのみの場合_週はnone(self):
        data = {"data": {"limits": [{"type": "TOKENS_LIMIT", "unit": 3, "percentage": 50}]}}
        assert UsageTracker._parse_quotas(data) == (50.0, None)

    def test_週のみの場合_5hはnone(self):
        data = {"data": {"limits": [{"type": "TOKENS_LIMIT", "unit": 6, "percentage": 80}]}}
        assert UsageTracker._parse_quotas(data) == (None, 80.0)

    def test_空レスポンス(self):
        assert UsageTracker._parse_quotas({}) == (None, None)
        assert UsageTracker._parse_quotas({"data": {}}) == (None, None)

    def test_percentage文字列も数値化(self):
        data = {"data": {"limits": [{"type": "TOKENS_LIMIT", "unit": 3, "percentage": "7"}]}}
        assert UsageTracker._parse_quotas(data) == (7.0, None)

    def test_percentage不正値は無視(self):
        data = {"data": {"limits": [{"type": "TOKENS_LIMIT", "unit": 3, "percentage": "abc"}]}}
        assert UsageTracker._parse_quotas(data) == (None, None)

    def test_tokens_limit以外は無視(self):
        data = {"data": {"limits": [
            {"type": "TIME_LIMIT", "unit": 3, "percentage": 99},
        ]}}
        assert UsageTracker._parse_quotas(data) == (None, None)

    def test_limitsがリストでない場合もクラッシュしない(self):
        data = {"data": {"limits": "broken"}}
        assert UsageTracker._parse_quotas(data) == (None, None)


# ---- UsageTracker.get_usage ----

class TestGetUsage:
    def _tracker(self):
        return UsageTracker("/tmp/test-status.json", zai_api_key="dummy")

    def test_未取得時は0(self):
        assert self._tracker().get_usage() == 0.0

    def test_5hと週のmaxを返す(self):
        t = self._tracker()
        t.set_usage(10.0)
        # set_usage は両軸同値なので直接片方だけ更新を模倣
        t._usage_5h_pct = 30.0
        t._usage_week_pct = 91.0
        t._last_success_ts = 1.0
        assert t.get_usage() == 91.0

    def test_5hの方が大きければ5hを返す(self):
        t = self._tracker()
        t._usage_5h_pct = 96.0
        t._usage_week_pct = 20.0
        t._last_success_ts = 1.0
        assert t.get_usage() == 96.0

    def test_statusに内訳キーが含まれる(self):
        t = self._tracker()
        t._usage_5h_pct = 7.0
        t._usage_week_pct = 1.0
        s = t.get_status()
        assert s["usage_pct"] == 7.0
        assert s["usage_5h_pct"] == 7.0
        assert s["usage_week_pct"] == 1.0
        assert "monitor_error_count" in s
        assert "monitor_last_error" in s

    @pytest.mark.asyncio
    async def test_monitor失敗時は前回値を維持(self):
        """HTTPエラー→前回値維持（0%に落ちない）の検証."""
        t = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
        t._usage_5h_pct = 60.0
        t._usage_week_pct = 40.0
        t._last_success_ts = 1.0

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        t._client = mock_client

        await t._poll_once()
        assert t.get_usage() == 60.0  # 前回値維持
        assert t.get_usage_breakdown()["error_count"] == 1


# ---- ModelRouter（95%一括の2段階） ----

class TestModelRouter:
    def _router(self):
        cfg = _make_config()
        # peak_hours無効化（時間依存を排除）
        router_cfg = dict(cfg.peak_hours, enabled=False)
        return ModelRouter(cfg.thresholds, cfg.fallback, cfg.default_model, router_cfg)

    def test_94_9はnormal(self):
        assert self._router().determine_mode(94.9) == "normal"

    def test_95はemergency(self):
        assert self._router().determine_mode(95.0) == "emergency"

    def test_80台もnormal_economy廃止(self):
        assert self._router().determine_mode(85.0) == "normal"

    def test_normal時glm53_zai(self):
        model, provider = self._router().route_model("glm-5.3", 10.0)
        assert model == "glm-5.3"
        assert provider == "zai"

    def test_emergency時minimax_m3(self):
        model, provider = self._router().route_model("glm-5.3", 96.0)
        assert model == "MiniMax-M3"
        assert provider == "minimax"

    def test_モード切替時にログ出力(self):
        r = self._router()
        r.determine_mode(10.0)
        assert r.current_mode == "normal"
        r.determine_mode(96.0)
        assert r.current_mode == "emergency"


# ---- _handle_429 新チェーン ----

def _make_server():
    cfg = _make_config()
    server = ProxyServer.__new__(ProxyServer)  # __init__ を使わず最小構築
    server._config = cfg
    server._tracker = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
    router_cfg = dict(cfg.peak_hours, enabled=False)
    server._router = ModelRouter(cfg.thresholds, cfg.fallback, cfg.default_model, router_cfg)
    server._last_actual_model = None
    server._last_request_bytes = 0
    server._upstream = MagicMock()
    return server


def _ok_resp(model="MiniMax-M3"):
    body = json.dumps({"model": model, "content": []}).encode()
    return {"status": 200, "headers": {"content-type": "application/json"}, "body": body}


BODY = json.dumps({"model": "glm-5.3", "max_tokens": 10,
                   "messages": [{"role": "user", "content": "hi"}]}).encode()


class TestHandle429Chain:
    @pytest.mark.asyncio
    async def test_第1候補_minimaxが呼ばれglm47flashは呼ばれない(self):
        """新チェーン: ZAI 429 → 先にMiniMax（成功すればGLM-4.7-Flashは不呼）."""
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        server._upstream.request_zai = AsyncMock()

        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_minimax.assert_awaited_once()
        server._upstream.request_zai.assert_awaited_not_called()

    @pytest.mark.asyncio
    async def test_第2候補_minimax429時glm47flashをzaiに再試行(self):
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(
            return_value=_ok_resp(model="GLM-4.7-Flash"))

        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_minimax.assert_awaited_once()
        server._upstream.request_zai.assert_awaited_once()
        # ZAIに送られたbodyのmodelがGLM-4.7-Flashに置換されているか
        sent_body = json.loads(server._upstream.request_zai.await_args.args[3])
        assert sent_body["model"] == "GLM-4.7-Flash"

    @pytest.mark.asyncio
    async def test_全滅時503(self):
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))

        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 503

    @pytest.mark.asyncio
    async def test_minimax呼び出し時のmodel置換(self):
        """MiniMaxへ送るbodyのmodelがfallbackモデルに置換されるか."""
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        await server._handle_429("POST", "/v1/messages", {}, BODY)
        sent_body = json.loads(server._upstream.request_minimax.await_args.args[3])
        assert sent_body["model"] == "MiniMax-M3"
