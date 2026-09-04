"""2026-08-19 手動モード切替API + peak_block最後の砦のテスト.

対象:
- ManualOverride（set/clear/active/load・TTL期限切れ・期限警告・永続化・復元）
- ProxyServer._handle_mode（POST /proxy/mode・不正値400）
- ProxyServer._effective_route（manual=minimax 強制ルーティング）
- ProxyServer._handle_429_peak_block の GLM-4.7-Flash 最後の砦（60sタイムアウト・503 Retry-After）
- UpstreamClient.request_minimax のキー連鎖（key[0] 429 → key[1]）

設計正典: obsidian-ssot/00_SYSTEM/マルチLLMレビュー/2026-08-19_glm-rate-proxy手動モードAPI-設計レビュー/revised_proposal.md

実行: cd scripts/glm-rate-proxy && PYTHONPATH=src python3 -m pytest tests/test_manual_mode.py -q
"""

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web

import pytest

from glm_rate_proxy.manual_mode import ManualOverride
from glm_rate_proxy.model_router import ModelRouter
from glm_rate_proxy.proxy import ProxyServer
from glm_rate_proxy.upstream import RateLimitError, UpstreamError
from glm_rate_proxy.usage_tracker import UsageTracker
from tests.test_fallback_changes import _make_config, _ok_resp

BODY = json.dumps({"model": "glm-5.3", "max_tokens": 10,
                   "messages": [{"role": "user", "content": "hi"}]}).encode()


def _make_server(tmp_state_file="/tmp/test-manual-mode-never.json"):
    """_handle_mode/_effective_route 検証用の最小構築サーバ."""
    cfg = _make_config()
    server = ProxyServer.__new__(ProxyServer)
    server._config = cfg
    server._tracker = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
    router_cfg = dict(cfg.peak_hours, enabled=False)
    server._router = ModelRouter(cfg.thresholds, cfg.fallback, cfg.default_model, router_cfg)
    server._last_actual_model = None
    server._last_request_bytes = 0
    server._upstream = MagicMock()
    server._manual = ManualOverride(state_file=tmp_state_file)
    return server


class _StubRequest:
    """_handle_mode 用の最小 request スタブ（.json() のみ提供）."""

    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


# ---- ManualOverride ----

class TestManualOverride:
    def test_未設定時activeはnone(self):
        m = ManualOverride(state_file="/tmp/test-mm-none.json")
        assert m.active() is None

    @pytest.mark.asyncio
    async def test_setでminimax有効_expires_at設定(self):
        m = ManualOverride(state_file="/tmp/test-mm-set.json")
        await m.set("minimax", hours=8)
        assert m.active() == "minimax"
        assert m.expires_at() is not None
        assert m.expires_at() > time.time()

    @pytest.mark.asyncio
    async def test_clearでauto復帰(self):
        m = ManualOverride(state_file="/tmp/test-mm-clear.json")
        await m.set("minimax", hours=8)
        await m.clear()
        assert m.active() is None

    def test_期限切れstateはauto扱い(self):
        m = ManualOverride(state_file="/tmp/test-mm-expired.json")
        m._provider = "minimax"
        m._expires_at = time.time() - 1
        assert m.active() is None
        assert m._provider is None

    @pytest.mark.asyncio
    async def test_再起動復元_期限内ならminimax復元(self, tmp_path):
        f = str(tmp_path / "mm.json")
        m1 = ManualOverride(state_file=f)
        await m1.set("minimax", hours=8)
        m2 = ManualOverride(state_file=f)
        m2.load()
        assert m2.active() == "minimax"

    @pytest.mark.asyncio
    async def test_再起動復元_期限切れファイルは無視(self, tmp_path):
        f = str(tmp_path / "mm.json")
        m1 = ManualOverride(state_file=f)
        await m1.set("minimax", hours=1)
        # 期限切れをシミュレート（expires_atを過去へ書換）
        m1._expires_at = time.time() - 10
        m1._persist()
        m2 = ManualOverride(state_file=f)
        m2.load()
        assert m2.active() is None

    @pytest.mark.asyncio
    async def test_clearでstateファイル削除(self, tmp_path):
        f = str(tmp_path / "mm.json")
        m = ManualOverride(state_file=f)
        await m.set("minimax", hours=8)
        assert os.path.exists(f)
        await m.clear()
        assert not os.path.exists(f)

    def test_破損stateファイルは無視(self, tmp_path):
        f = str(tmp_path / "mm.json")
        open(f, "w").write("{not json")
        m = ManualOverride(state_file=f)
        m2 = ManualOverride(state_file=f)
        m2.load()  # 例外にならない
        assert m2.active() is None
        assert m.state_file == f  # pyflakes対策(not-used警告回避の参照)


# ---- POST /proxy/mode ----

class TestHandleMode:
    @pytest.mark.asyncio
    async def test_minimax指定で200_state反映(self):
        server = _make_server()
        resp = await server._handle_mode(_StubRequest({"provider": "minimax", "hours": 10}))
        assert resp.status == 200
        assert server._manual.active() == "minimax"
        data = json.loads(resp.body)
        assert data["manual_provider"] == "minimax"
        assert data["manual_expires_at"] is not None

    @pytest.mark.asyncio
    async def test_auto指定で200_解除(self):
        server = _make_server()
        await server._manual.set("minimax", hours=8)
        resp = await server._handle_mode(_StubRequest({"provider": "auto"}))
        assert resp.status == 200
        assert server._manual.active() is None

    @pytest.mark.asyncio
    async def test_不正provider値は400(self):
        server = _make_server()
        resp = await server._handle_mode(_StubRequest({"provider": "zai"}))
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_hours範囲外は400(self):
        server = _make_server()
        assert (await server._handle_mode(
            _StubRequest({"provider": "minimax", "hours": 0}))).status == 400
        assert (await server._handle_mode(
            _StubRequest({"provider": "minimax", "hours": 73}))).status == 400
        assert (await server._handle_mode(
            _StubRequest({"provider": "minimax", "hours": -1}))).status == 400

    @pytest.mark.asyncio
    async def test_非json_bodyは400(self):
        server = _make_server()
        resp = await server._handle_mode(_StubRequest(ValueError("bad json")))
        assert resp.status == 400

    def test_ルート登録(self):
        """create_app が POST /proxy/mode を登録しているか."""
        server = _make_server()
        app = server.create_app()
        routes = [f"{r.method} {r.resource.canonical}" for r in app.router.routes()]
        assert any("POST /proxy/mode" in r for r in routes)


# ---- manual=minimax 強制ルーティング ----

class TestManualRouting:
    @pytest.mark.asyncio
    async def test_manual中はminimaxへ強制_使用率無視(self):
        """manual=minimax中: peak/使用率に依存せずMiniMax-M3へ強制."""
        server = _make_server()
        await server._manual.set("minimax", hours=8)
        model, provider = server._effective_route("glm-5.3", 10.0)
        assert provider == "minimax"
        assert model == "MiniMax-M3"

    @pytest.mark.asyncio
    async def test_非manual時は通常ルーティング(self):
        server = _make_server()
        model, provider = server._effective_route("glm-5.3", 10.0)
        assert provider == "zai"
        assert model == "glm-5.3"

    @pytest.mark.asyncio
    async def test_manual期限切れ後は通常ルーティングに復帰(self):
        server = _make_server()
        server._manual._provider = "minimax"
        server._manual._expires_at = time.time() - 1
        model, provider = server._effective_route("glm-5.3", 10.0)
        assert provider == "zai"


# ---- peak_block 最後の砦 ----

def _make_peak_server():
    server = _make_server()
    server._router._current_mode = "peak_block"
    return server


class TestPeakBlockLastResort:
    @pytest.mark.asyncio
    async def test_minimax失敗時glm47flashへ逃避(self):
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(
            return_value=_ok_resp(model="GLM-4.7-Flash"))

        resp = await server._handle_429_peak_block("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_zai.assert_awaited_once()
        sent = json.loads(server._upstream.request_zai.await_args.args[3])
        assert sent["model"] == "GLM-4.7-Flash"

    @pytest.mark.asyncio
    async def test_全滅時503_retry_after付き(self):
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))

        resp = await server._handle_429_peak_block("POST", "/v1/messages", {}, BODY)
        assert resp.status == 503
        assert resp.headers.get("Retry-After") == "600"

    @pytest.mark.asyncio
    async def test_minimax成功時はzai不呼(self):
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        server._upstream.request_zai = AsyncMock()

        resp = await server._handle_429_peak_block("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._upstream.request_zai.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_47flash呼出は60sタイムアウトでラップされる(self):
        """4.7-Flash試行が asyncio.wait_for(timeout=60) で包まれていること."""
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_zai = AsyncMock(return_value=_ok_resp())
        recorded = {}

        async def spy(fut, timeout=None):
            recorded["timeout"] = timeout
            raise asyncio.TimeoutError

        with patch("asyncio.wait_for", new=spy):
            resp = await server._handle_429_peak_block("POST", "/v1/messages", {}, BODY)
        assert resp.status == 503
        assert recorded["timeout"] == 60.0

    @pytest.mark.asyncio
    async def test_47flashタイムアウト時も503_retry_after付き(self):
        server = _make_peak_server()
        server._upstream.request_minimax = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))

        async def _hang(*a, **k):
            await asyncio.sleep(300)
            return _ok_resp()

        server._upstream.request_zai = AsyncMock(side_effect=_hang)
        # wait_forを本物で動かし timeout=0.01 に差し替えて即タイムアウト検証
        real = asyncio.wait_for

        async def fast(fut, timeout=None):
            return await real(fut, timeout=0.01)

        with patch("asyncio.wait_for", new=fast):
            resp = await server._handle_429_peak_block("POST", "/v1/messages", {}, BODY)
        assert resp.status == 503
        assert resp.headers.get("Retry-After") == "600"


# ---- UpstreamClient キー連鎖（手動モード/minimax経路の根幹・従来未テスト） ----

class TestMinimaxKeyChain:
    @pytest.mark.asyncio
    async def test_key0が429ならkey1へ(self):
        from glm_rate_proxy.upstream import UpstreamClient
        client = UpstreamClient("https://zai", "https://mm", "zai-key",
                                ["key0", "key1"], 30)
        calls = []

        async def fake_do(url, method, headers, body):
            calls.append(headers.get("x-api-key"))
            if len(calls) == 1:
                raise RateLimitError(429, b"rate limited")
            return _ok_resp()

        client._do_request = fake_do
        resp = await client.request_minimax("POST", "/v1/messages", {}, BODY)
        assert resp["status"] == 200
        assert calls == ["key0", "key1"]

    @pytest.mark.asyncio
    async def test_全キー429なら最後の429をraise(self):
        from glm_rate_proxy.upstream import UpstreamClient
        client = UpstreamClient("https://zai", "https://mm", "zai-key",
                                ["key0", "key1"], 30)

        async def fake_do(url, method, headers, body):
            raise RateLimitError(429, b"rate limited")

        client._do_request = fake_do
        with pytest.raises(RateLimitError):
            await client.request_minimax("POST", "/v1/messages", {}, BODY)

    @pytest.mark.asyncio
    async def test_5xxは次キーへ行かず即raise(self):
        from glm_rate_proxy.upstream import UpstreamClient
        client = UpstreamClient("https://zai", "https://mm", "zai-key",
                                ["key0", "key1"], 30)
        calls = []

        async def fake_do(url, method, headers, body):
            calls.append(headers.get("x-api-key"))
            raise UpstreamError(500, "minimax down")

        client._do_request = fake_do
        with pytest.raises(UpstreamError):
            await client.request_minimax("POST", "/v1/messages", {}, BODY)
        assert calls == ["key0"]


# ---- manual=glm（peak_block中のみ有効・2026-09-04 spec） ----

def _make_always_peak_server():
    """_is_peak_hour を常にTrueにするrouterを持つサーバ（start=0,end=24）.

    実時刻に依存せず peak_block 状態を再現するためのヘルパー。
    """
    cfg = _make_config()
    server = ProxyServer.__new__(ProxyServer)
    server._config = cfg
    server._tracker = UsageTracker("/tmp/test-status.json", zai_api_key="dummy")
    router_cfg = dict(cfg.peak_hours, enabled=True, start_hour=0, end_hour=24)
    server._router = ModelRouter(cfg.thresholds, cfg.fallback, cfg.default_model, router_cfg)
    server._last_actual_model = None
    server._last_request_bytes = 0
    server._upstream = MagicMock()
    server._manual = ManualOverride(state_file="/tmp/test-manual-glm-never.json")
    return server


class TestManualGlmOverride:
    @pytest.mark.asyncio
    async def test_setでglm有効(self):
        m = ManualOverride(state_file="/tmp/test-mm-glm.json")
        await m.set("glm", hours=8)
        assert m.active() == "glm"

    @pytest.mark.asyncio
    async def test_再起動復元_期限内ならglm復元(self, tmp_path):
        f = str(tmp_path / "mm.json")
        m1 = ManualOverride(state_file=f)
        await m1.set("glm", hours=8)
        m2 = ManualOverride(state_file=f)
        m2.load()
        assert m2.active() == "glm"

    @pytest.mark.asyncio
    async def test_glm指定で200_state反映(self):
        server = _make_always_peak_server()
        resp = await server._handle_mode(_StubRequest({"provider": "glm", "hours": 4}))
        assert resp.status == 200
        data = json.loads(resp.body)
        assert data["manual_provider"] == "glm"

    @pytest.mark.asyncio
    async def test_peak_block中glm_manualはGLMへ強制(self):
        server = _make_always_peak_server()
        await server._manual.set("glm", hours=4)
        model, provider = server._effective_route("glm-5.3", 10.0)
        assert provider == "zai"
        assert model == "glm-5.3"

    @pytest.mark.asyncio
    async def test_peak_block中glm_manual_モデル指定なしは既定モデル(self):
        server = _make_always_peak_server()
        await server._manual.set("glm", hours=4)
        model, provider = server._effective_route(None, 10.0)
        assert provider == "zai"
        assert model == server._router.default_model

    @pytest.mark.asyncio
    async def test_非peak時glm_manualは効果なし_emergencyのまま(self):
        """glm manualはpeak_block外では無効=emergency(usage 99%)ならMiniMaxのまま."""
        server = _make_server()
        await server._manual.set("glm", hours=4)
        model, provider = server._effective_route("glm-5.3", 99.0)
        assert provider == "minimax"

    @pytest.mark.asyncio
    async def test_peak_block中glm_manual時の429は通常チェーン(self):
        """manual=glm中はpeak_block専用429分岐を通らず通常チェーン(MiniMax保険)へ."""
        server = _make_always_peak_server()
        server._router._current_mode = "peak_block"
        await server._manual.set("glm", hours=4)
        server._handle_429_peak_block = AsyncMock(
            return_value=web.Response(status=599))
        server._upstream.request_minimax = AsyncMock(return_value=_ok_resp())
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 200
        server._handle_429_peak_block.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_peak_block中manual無しの429はpeak_block分岐維持(self):
        """baseline: manual無し+peak_block時は従来通りpeak_block分岐に入る."""
        server = _make_always_peak_server()
        server._router._current_mode = "peak_block"
        server._handle_429_peak_block = AsyncMock(
            return_value=web.Response(status=599))
        resp = await server._handle_429("POST", "/v1/messages", {}, BODY)
        assert resp.status == 599
        server._handle_429_peak_block.assert_awaited_once()
