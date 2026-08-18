"""2026-08-17 フォールバック根本改善のテスト.

対象:
- UsageTracker._parse_quotas（monitor APIレスポンス解析）
- UsageTracker.get_usage（max(5h, week)判定・未取得時0.0・失敗時前回値維持）
- ModelRouter.determine_mode / route_model（95%一括の2段階ルーティング）
- ProxyServer._handle_429（新チェーン: MiniMax先 → GLM-4.7-Flash最後の砦 → 503）

実行: cd scripts/glm-rate-proxy && PYTHONPATH=src python3 -m pytest tests/ -q
"""

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
        server._upstream.request_zai.assert_not_awaited()

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


# ---- _handle_429 追加エッジケース ----

class TestHandle429EdgeCases:
    @pytest.mark.asyncio
    async def test_minimaxが5xxエラー時もglm47flashへ(self):
        """MiniMaxのUpstreamError(429以外)→GLM-4.7-Flashへフォールバック."""
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=UpstreamError(500, "minimax down"))
        server._upstream.request_zai = AsyncMock(
            return_value=_ok_resp(model="GLM-4.7-Flash"))
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_zai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_minimaxキー未設定時はglm47flash直行(self):
        """minimax_api_keys空 → MiniMax不呼でGLM-4.7-Flashへ."""
        server = _make_server()
        # minimax_api_keys は property（minimax_api_key + fallback から生成）のため元キーを空に
        server._config.minimax_api_key = ""
        server._config.minimax_api_key_fallback = ""
        server._upstream.request_minimax = AsyncMock()
        server._upstream.request_zai = AsyncMock(
            return_value=_ok_resp(model="GLM-4.7-Flash"))
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_minimax.assert_not_awaited()
        server._upstream.request_zai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ボディなしリクエストでもクラッシュしない(self):
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        resp = await server._handle_429("GET", "/v1/models", {}, b"")
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_429時もminimax向けsanitizeが適用される(self):
        """429フォールバックのMiniMax分岐で tool_use 正規化が入るか（thinking除去）."""
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        body_with_thinking = json.dumps({
            "model": "glm-5.3", "thinking": {"type": "enabled", "budget_tokens": 8000},
            "messages": [{"role": "user", "content": "hi"}]}).encode()
        await server._handle_429("POST", "/v1/messages", {}, body_with_thinking)
        sent = json.loads(server._upstream.request_minimax.await_args.args[3])
        assert "thinking" not in sent  # MiniMax非対応のthinkingが除去される


# ---- _handle_429_peak_block（ピーク時間帯） ----

def _make_peak_server():
    server = _make_server()
    server._router._current_mode = "peak_block"
    return server


class TestHandle429PeakBlock:
    @pytest.mark.asyncio
    async def test_ピーク中minimax成功(self):
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_ピーク中minimax429なら47flash最後の砦へ(self):
        """ピーク時間帯の設計（2026-08-19改訂）: MiniMax全滅時のみ
        GLM-4.7-Flash（ZAI無料枠）へ1回逃がる。4.7-Flashも429なら503."""
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 503
        assert resp.headers.get("Retry-After") == "600"
        # 最後の砦としてZAI（4.7-Flash）が1回呼ばれていること
        server._upstream.request_zai.assert_awaited_once()


# ---- _handle_upstream_error（ZAI 5xx → MiniMax） ----

class TestHandleUpstreamError:
    @pytest.mark.asyncio
    async def test_zai5xx時minimaxへフォールバック(self):
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        err = UpstreamError(502, "bad gateway")
        resp = await server._handle_upstream_error("POST", "/v1/messages", {}, BODY, err)
        assert resp.status == 200
        server._upstream.request_minimax.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_元エラーステータスを維持_minimax失敗時(self):
        server = _make_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        err = UpstreamError(503, "unavailable")
        resp = await server._handle_upstream_error("POST", "/v1/messages", {}, BODY, err)
        assert resp.status == 503


# ---- UsageTracker ライフサイクル ----

class TestTrackerLifecycle:
    @pytest.mark.asyncio
    async def test_start二重呼び出しガード(self):
        t = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
        await t.start()
        task1 = t._task
        await t.start()  # 2回目
        assert t._task is task1  # 同一タスクのまま（二重起動しない）
        await t.stop()

    @pytest.mark.asyncio
    async def test_stopは冪等(self):
        t = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
        await t.start()
        await t.stop()
        await t.stop()  # 2回目もクラッシュしない
        assert t._task is None
        assert t._client is None

    @pytest.mark.asyncio
    async def test_キー未設定時はエラーカウントのみ(self):
        t = UsageTracker("/tmp/test-status.json", zai_api_key="")
        await t._poll_once()
        assert t.get_usage_breakdown()["error_count"] == 1
        assert "not configured" in t.get_usage_breakdown()["last_error"]

    @pytest.mark.asyncio
    async def test_ポーリング成功で値が更新される(self):
        t = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"data": {"limits": [
            {"type": "TOKENS_LIMIT", "unit": 3, "percentage": 15},
            {"type": "TOKENS_LIMIT", "unit": 6, "percentage": 42},
        ]}})
        t._client = AsyncMock()
        t._client.get = AsyncMock(return_value=mock_resp)
        await t._poll_once()
        assert t.get_usage() == 42.0
        assert t.get_usage_breakdown()["poll_count"] == 1
        assert t.get_usage_breakdown()["last_error"] is None


# ---- _is_peak_hour 境界 ----

class TestPeakHour:
    def _peak_cfg(self, start=15, end=19):
        return {"enabled": True, "start_hour": start, "end_hour": end, "timezone_offset": 9}

    def test_境界内_15時はtrue(self):
        with patch("glm_rate_proxy.model_router.datetime") as mock_dt:
            from datetime import datetime as real_dt, timezone, timedelta
            jst = timezone(timedelta(hours=9))
            mock_dt.now.return_value = real_dt(2026, 8, 17, 15, 0, tzinfo=jst)
            from glm_rate_proxy.model_router import _is_peak_hour
            assert _is_peak_hour(self._peak_cfg()) is True

    def test_境界外_19時はfalse(self):
        with patch("glm_rate_proxy.model_router.datetime") as mock_dt:
            from datetime import datetime as real_dt, timezone, timedelta
            jst = timezone(timedelta(hours=9))
            mock_dt.now.return_value = real_dt(2026, 8, 17, 19, 0, tzinfo=jst)
            from glm_rate_proxy.model_router import _is_peak_hour
            assert _is_peak_hour(self._peak_cfg()) is False

    def test_無効化時は常にfalse(self):
        from glm_rate_proxy.model_router import _is_peak_hour
        assert _is_peak_hour({"enabled": False}) is False


# ---- config monitor設定 ----

class TestMonitorConfig:
    def test_デフォルトは有効60秒(self):
        cfg = load_config("/nonexistent/config.json")
        assert cfg.monitor_enabled is True
        assert cfg.monitor_interval_sec == 60.0
        assert cfg.monitor_timeout_sec == 10.0

    def test_config_jsonで上書き可能(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(
            {"monitor": {"enabled": False, "interval_sec": 30}}))
        cfg = load_config(str(cfg_file))
        assert cfg.monitor_enabled is False
        assert cfg.monitor_interval_sec == 30.0
