"""統合テスト: _handle_api配線・upstreamキー連鎖・tool_sanitizer・残ユーティリティ.

実行: cd scripts/glm-rate-proxy && PYTHONPATH=src python3 -m pytest tests/ -q
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from glm_rate_proxy.config import load_config
from glm_rate_proxy.proxy import ProxyServer, _extract_message_text
from glm_rate_proxy.tool_sanitizer import sanitize_for_minimax
from glm_rate_proxy.upstream import RateLimitError, UpstreamError, UpstreamClient


def _cfg():
    return load_config("/nonexistent/config.json")


BODY = json.dumps({"model": "glm-5.3", "max_tokens": 10,
                   "messages": [{"role": "user", "content": "hi"}]}).encode()


def _ok(model="glm-5.3", body=None):
    b = body or json.dumps({"model": model, "content": []}).encode()
    return {"status": 200, "headers": {"content-type": "application/json"}, "body": b}


# ---- _handle_api 統合（TestClient経由のエンドツーエンド配線） ----

async def _make_client():
    cfg = _cfg()
    server = ProxyServer(cfg)
    server._upstream = MagicMock()
    app = server.create_app()
    client = await TestClient(TestServer(app)).__aenter__()
    return client, server


@pytest.mark.asyncio
async def test_usage低ではzaiにglm53で送信される():
    client, server = _ = await _make_client()
    try:
        server._upstream.request_zai = AsyncMock(return_value=_ok())
        server._upstream.request_minimax = AsyncMock()
        server._tracker._usage_5h_pct = 10.0
        server._tracker._usage_week_pct = 5.0
        server._tracker._last_success_ts = 1.0

        resp = await client.post("/v1/messages", data=BODY,
                                 headers={"anthropic-version": "2023-06-01"})
        assert resp.status == 200
        server._upstream.request_zai.assert_awaited_once()
        server._upstream.request_minimax.assert_not_awaited()
        sent = json.loads(server._upstream.request_zai.await_args.args[3])
        assert sent["model"] == "glm-5.3"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_usage96pctでminimax配線に切替():
    client, server = _ = await _make_client()
    try:
        server._upstream.request_minimax = AsyncMock(return_value=_ok(model="MiniMax-M3"))
        server._upstream.request_zai = AsyncMock()
        server._tracker._usage_5h_pct = 96.0
        server._tracker._usage_week_pct = 30.0
        server._tracker._last_success_ts = 1.0

        resp = await client.post("/v1/messages", data=BODY,
                                 headers={"anthropic-version": "2023-06-01"})
        assert resp.status == 200
        server._upstream.request_minimax.assert_awaited_once()
        server._upstream.request_zai.assert_not_awaited()
        sent = json.loads(server._upstream.request_minimax.await_args.args[3])
        assert sent["model"] == "MiniMax-M3"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_zai429時は新チェーンでminimaxに逃げる():
    client, server = _ = await _make_client()
    try:
        server._upstream.request_zai = AsyncMock(
            side_effect=RateLimitError(429, b"rate limited"))
        server._upstream.request_minimax = AsyncMock(return_value=_ok(model="MiniMax-M3"))
        server._tracker._usage_5h_pct = 10.0
        server._tracker._last_success_ts = 1.0

        resp = await client.post("/v1/messages", data=BODY,
                                 headers={"anthropic-version": "2023-06-01"})
        assert resp.status == 200
        server._upstream.request_minimax.assert_awaited_once()
        assert server._last_actual_model == "MiniMax-M3"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_statusエンドポイント応答():
    client, server = _ = await _make_client()
    try:
        server._last_request_bytes = 1024
        resp = await client.get("/proxy/status")
        assert resp.status == 200
        d = await resp.json()
        assert d["mode"] == "normal"
        assert d["provider"] == "zai"
        assert d["zai_configured"] is True
        assert d["minimax_configured"] is True
        assert d["last_request_mb"] == 0.0
    finally:
        await client.close()


# ---- upstream.request_minimax キー連鎖 ----

def _client2(keys):
    c = UpstreamClient("https://zai", "https://mmx", "zai-key", keys, timeout=5)
    return c


@pytest.mark.asyncio
async def test_第1キー429で第2キーへ():
    c = _client2(["k1", "k2"])
    with patch.object(c, "_do_request", new=AsyncMock(return_value=_ok())):
        # 1回目429→2回目成功をside_effectで表現
        c._do_request = AsyncMock(side_effect=[RateLimitError(429, b"x"), _ok()])
        resp = await c.request_minimax("POST", "/v1/messages", {}, BODY)
        assert resp["status"] == 200
        assert c._do_request.await_count == 2
        # 2回目のx-api-keyが第2キー
        second_headers = c._do_request.await_args_list[1].args[3]
        assert second_headers["x-api-key"] == "k2"


@pytest.mark.asyncio
async def test_第1キー401で第2キーへ():
    c = _client2(["k1", "k2"])
    c._do_request = AsyncMock(side_effect=[UpstreamError(401, "unauth"), _ok()])
    resp = await c.request_minimax("POST", "/v1/messages", {}, BODY)
    assert resp["status"] == 200


@pytest.mark.asyncio
async def test_第1キー5xxは即raise_第2キー試さない():
    c = _client2(["k1", "k2"])
    c._do_request = AsyncMock(side_effect=UpstreamError(500, "server error"))
    with pytest.raises(UpstreamError):
        await c.request_minimax("POST", "/v1/messages", {}, BODY)
    assert c._do_request.await_count == 1


@pytest.mark.asyncio
async def test_両キー429でratelimiterror():
    c = _client2(["k1", "k2"])
    c._do_request = AsyncMock(side_effect=RateLimitError(429, b"x"))
    with pytest.raises(RateLimitError):
        await c.request_minimax("POST", "/v1/messages", {}, BODY)
    assert c._do_request.await_count == 2


@pytest.mark.asyncio
async def test_キー未設定時はupstreamerror401():
    c = _client2([])
    with pytest.raises(UpstreamError) as ei:
        await c.request_minimax("POST", "/v1/messages", {}, BODY)
    assert ei.value.status == 401


def test_単一キー文字列でも動く():
    c = UpstreamClient("https://z", "https://m", "k", "only-key", timeout=5)
    assert c._minimax_api_keys == ["only-key"]


def test_空キー除外():
    c = UpstreamClient("https://z", "https://m", "k", ["a", "", "b"], timeout=5)
    assert c._minimax_api_keys == ["a", "b"]


# ---- _sync_request（HTTP層・urlopenモック） ----

def test_httperror429はratelimiterror():
    import urllib.error
    c = _client2([])
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.HTTPError(
            "url", 429, "Too Many Requests", {}, None)  # type: ignore[arg-type]
        with pytest.raises(RateLimitError):
            c._sync_request("https://x", "POST", {}, b"{}")


def test_httperror500はupstreamerror():
    import urllib.error
    c = _client2([])
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.HTTPError(
            "url", 500, "Server Error", {}, None)  # type: ignore[arg-type]
        with pytest.raises(UpstreamError) as ei:
            c._sync_request("https://x", "POST", {}, b"{}")
        assert ei.value.status == 500


def test_接続エラーは502にwrap():
    c = _client2([])
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        with pytest.raises(UpstreamError) as ei:
            c._sync_request("https://x", "POST", {}, b"{}")
        assert ei.value.status == 502


# ---- tool_sanitizer ----

class TestSanitizer:
    def test_assistantのthinkingブロック除去(self):
        body = json.dumps({"messages": [
            {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "..."},
                {"type": "text", "text": "ok"}]}]}).encode()
        out = json.loads(sanitize_for_minimax(body))
        assert [b["type"] for b in out["messages"][0]["content"]] == ["text"]

    def test_tool_useにtool_call_id補完(self):
        body = json.dumps({"messages": [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu1", "name": "f", "input": {}}]}]}).encode()
        out = json.loads(sanitize_for_minimax(body))
        assert out["messages"][0]["content"][0]["tool_call_id"] == "tu1"

    def test_tool_resultのtool_use_id補完_文字列content配列化(self):
        body = json.dumps({"messages": [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu1", "name": "f", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_call_id": "tu1", "content": "result"}]}]}).encode()
        out = json.loads(sanitize_for_minimax(body))
        tr = out["messages"][1]["content"][0]
        assert tr["tool_use_id"] == "tu1"
        assert tr["content"] == [{"type": "text", "text": "result"}]

    def test_orphan_tool_result除去(self):
        body = json.dumps({"messages": [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "ghost", "content": "x"}]},
            {"role": "user", "content": [
                {"type": "text", "text": "keep"}]}]}).encode()
        out = json.loads(sanitize_for_minimax(body))
        assert out["messages"][0]["content"] == []
        assert out["messages"][1]["content"][0]["type"] == "text"

    def test_top_level_thinking除去(self):
        body = json.dumps({"thinking": {"type": "enabled"},
                           "messages": [{"role": "user", "content": "hi"}]}).encode()
        out = json.loads(sanitize_for_minimax(body))
        assert "thinking" not in out

    def test_非jsonはそのまま通す(self):
        assert sanitize_for_minimax(b"not json") == b"not json"

    def test_messagesなしはそのまま(self):
        body = json.dumps({"model": "x"}).encode()
        assert json.loads(sanitize_for_minimax(body))["model"] == "x"


# ---- proxy ユーティリティ ----

class TestCaptureModel:
    def test_json応答からmodel取得():
        pass  # staticmethodの性質上、下の関数形で検証


def _mk_server():
    cfg = _cfg()
    server = ProxyServer.__new__(ProxyServer)
    server._config = cfg
    server._tracker = MagicMock()
    server._router = MagicMock()
    server._upstream = MagicMock()
    server._last_actual_model = None
    server._last_request_bytes = 0
    return server


def test_capture_model_json():
    s = _mk_server()
    s._capture_model(json.dumps({"model": "glm-5.3"}).encode())
    assert s._last_actual_model == "glm-5.3"


def test_capture_model_sse():
    s = _mk_server()
    sse = "event: message_start\ndata: {\"type\":\"message_start\",\"message\":{\"model\":\"MiniMax-M3\"}}\n\n"
    s._capture_model(sse.encode())
    assert s._last_actual_model == "MiniMax-M3"


def test_capture_model_非jsonはskip():
    s = _mk_server()
    s._capture_model(b"<html>")
    assert s._last_actual_model is None


def test_capture_model_非dictはskip():
    s = _mk_server()
    s._capture_model(b"[1,2]")
    assert s._last_actual_model is None


def test_extract_model_from_sse_direct_model():
    assert ProxyServer._extract_model_from_sse("data: {\"model\": \"x\"}") == "x"


def test_extract_model_from_sse_done無視():
    assert ProxyServer._extract_model_from_sse("data: [DONE]") is None


def test_default_model_from_body_非json():
    assert ProxyServer._default_model_from_body(b"bad") is None


class TestApplyThinking:
    CFG = {"mode": "auto", "budget_tokens": 5000, "coding_keywords": ["fix", "edit"]}

    def test_キーワードhitでenabled(self):
        body = json.dumps({"messages": [{"role": "user", "content": "please fix this"}]}).encode()
        out = json.loads(ProxyServer._apply_thinking(body, self.CFG))
        assert out["thinking"]["type"] == "enabled"
        assert out["thinking"]["budget_tokens"] == 5000

    def test_キーワードmissでdisabled(self):
        body = json.dumps({"messages": [{"role": "user", "content": "hello"}]}).encode()
        out = json.loads(ProxyServer._apply_thinking(body, self.CFG))
        assert out["thinking"]["type"] == "disabled"

    def test_always_on(self):
        body = json.dumps({"messages": []}).encode()
        out = json.loads(ProxyServer._apply_thinking(
            body, {"mode": "always_on", "budget_tokens": 1000}))
        assert out["thinking"]["type"] == "enabled"

    def test_always_off(self):
        body = json.dumps({"messages": []}).encode()
        out = json.loads(ProxyServer._apply_thinking(body, {"mode": "always_off"}))
        assert out["thinking"]["type"] == "disabled"

    def test_非jsonはそのまま(self):
        assert ProxyServer._apply_thinking(b"bad", {"mode": "always_off"}) == b"bad"


def test_replace_model_非jsonはそのまま():
    assert ProxyServer._replace_model(b"bad", "x") == b"bad"


def test_extract_message_text_文字列content():
    d = {"messages": [{"role": "user", "content": "hello"}]}
    assert _extract_message_text(d) == "hello"


def test_extract_message_text_リストcontent():
    d = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "a"}, {"type": "image"}]}]}
    assert _extract_message_text(d) == "a"


# ---- usage_tracker ループ系 ----

@pytest.mark.asyncio
async def test_poll_loop継続と例外握り():
    """ループ内例外で死なず次周へ進むこと."""
    t = None
    from glm_rate_proxy.usage_tracker import UsageTracker
    t = UsageTracker("/tmp/test-status2.json", zai_api_key="k")
    calls = {"n": 0}

    async def flaky_poll():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")  # 1回目異常
        t._stop_event.set()  # 2回目で停止

    t._poll_once = flaky_poll  # type: ignore[method-assign]
    await t.start()
    # interval=60s だと2周目に時間がかかるため短縮
    t._monitor_interval = 0.05
    await t._task  # type: ignore[misc]
    assert calls["n"] == 2  # 例外後も2回目が走った


@pytest.mark.asyncio
async def test_stop時のタスクcancelパス():
    from glm_rate_proxy.usage_tracker import UsageTracker
    t = UsageTracker("/tmp/test-status3.json", zai_api_key="k", monitor_interval_sec=0.05)

    async def forever():
        await asyncio_sleep_forever()

    async def asyncio_sleep_forever():
        import asyncio
        await asyncio.Event().wait()  # 永久待ち

    await t.start()
    await t.stop()
    assert t._task is None
