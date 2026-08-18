"""HTTP proxy server for Claude Code -> ZAI API with rate-limit aware model routing."""

import asyncio
import json
import logging
from aiohttp import web

from .config import ProxyConfig
from .usage_tracker import UsageTracker
from .model_router import ModelRouter
from .upstream import UpstreamClient, RateLimitError, UpstreamError
from .tool_sanitizer import sanitize_for_minimax
from .manual_mode import ManualOverride

logger = logging.getLogger("glm-rate-proxy")


def _extract_message_text(data: dict) -> str:
    parts = []
    for m in data.get("messages", []):
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c.get("text", ""))
    return " ".join(parts)


class ProxyServer:
    def __init__(self, config: ProxyConfig):
        self._config = config
        self._tracker = UsageTracker(
            config.status_file,
            zai_api_key=config.zai_api_key,
            monitor_interval_sec=config.monitor_interval_sec,
            monitor_timeout_sec=config.monitor_timeout_sec,
        )
        self._router = ModelRouter(
            config.thresholds, config.fallback, config.default_model,
            config.peak_hours,
        )
        self._upstream = UpstreamClient(
            config.zai_base_url, config.minimax_base_url,
            config.zai_api_key, config.minimax_api_keys,
            config.upstream_timeout,
        )
        self._last_actual_model: str | None = None
        # 手動プロバイダ指定（POST /proxy/mode・再起動でも復元）
        self._manual = ManualOverride()
        self._manual.load()
        # 直近リクエストの実ペイロードサイズ（バイト）
        # Claude Code -> proxy 間の生body長 = 真のAPIリクエストサイズ
        # (ツール定義+システムプロンプト+履歴 全部入り)
        self._last_request_bytes: int = 0

    async def start(self) -> None:
        await self._upstream.start()

    async def stop(self) -> None:
        # tracker停止をここに集約（on_cleanup から直接 _tracker.stop() しない・二重stop解消）
        # upstream.stop 失敗時も tracker は停止保証（try/finally）
        try:
            await self._upstream.stop()
        finally:
            await self._tracker.stop()

    async def tracker_start(self) -> None:
        """UsageTracker の monitor ポーリング開始（on_startup から呼ばれる）。"""
        await self._tracker.start()

    def create_app(self) -> web.Application:
        # client_max_size: 受信リクエストボディ上限。
        # 未指定だとaiohttpデフォルト1MBになり、画像添付リクエストが413で弾かれる
        # （CCは「Request too large (max 32MB)」と誤表示）。32MB=Anthropic API上限に合わせる。
        app = web.Application(client_max_size=32 * 1024 * 1024)
        app.router.add_route("*", "/v1/{path:.*}", self._handle_api)
        app.router.add_get("/proxy/status", self._handle_status)
        app.router.add_post("/proxy/mode", self._handle_mode)
        return app

    async def _handle_status(self, request: web.Request) -> web.Response:
        status = self._tracker.get_status()
        status["mode"] = self._router.current_mode
        _, provider = self._router.route_model(None, self._tracker.get_usage())
        status["provider"] = provider
        # 手動モード状態（切替忘れの気づき用）
        status["manual_provider"] = self._manual.active()
        status["manual_expires_at"] = self._manual.expires_at()
        if status["manual_provider"] == "minimax":
            status["provider"] = "minimax"
        status["zai_configured"] = bool(self._config.zai_api_key)
        status["minimax_configured"] = bool(self._config.minimax_api_keys)
        status["peak_block"] = self._router.current_mode == "peak_block"
        status["last_actual_model"] = self._last_actual_model
        # 直近リクエストの実サイズ（MB）= 32MB API上限の真の目安
        status["last_request_mb"] = round(self._last_request_bytes / 1048576, 1)
        return web.json_response(status)

    async def _handle_mode(self, request: web.Request) -> web.Response:
        """POST /proxy/mode — 手動プロバイダ切替（再起動なし）.

        body: {"provider": "minimax" | "auto", "hours": 1-72（既定8）}
        manual=minimax 中は全リクエストを MiniMax-M3 へ強制（使用率/peak無視）。
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)
        if not isinstance(data, dict):
            return web.json_response({"error": "invalid_body"}, status=400)

        provider = data.get("provider")
        if provider == "auto":
            await self._manual.clear()
            logger.info("Manual mode cleared (auto)")
            return web.json_response(self._manual_status())
        if provider != "minimax":
            return web.json_response(
                {"error": "provider must be 'minimax' or 'auto'"}, status=400)

        hours = data.get("hours", 8)
        if not isinstance(hours, (int, float)) or isinstance(hours, bool) \
                or not (1 <= hours <= 72):
            return web.json_response({"error": "hours must be 1-72"}, status=400)

        await self._manual.set("minimax", float(hours))
        logger.info(f"Manual mode set: provider=minimax hours={hours}")
        return web.json_response(self._manual_status())

    def _manual_status(self) -> dict:
        return {"manual_provider": self._manual.active(),
                "manual_expires_at": self._manual.expires_at()}

    def _effective_route(self, req_model: str | None,
                         usage_pct: float) -> tuple[str, str]:
        """通常ルーティング + 手動モード上書き。manual=minimax 中は
        peak時間帯・使用率しきい値を無視して MiniMax-M3 へ強制する。"""
        model, provider = self._router.route_model(req_model, usage_pct)
        if self._manual.active() == "minimax":
            fb_model, _ = self._router.get_fallback()
            model = fb_model
            provider = "minimax"
        return model, provider

    async def _handle_api(self, request: web.Request) -> web.Response:
        path = f"/v1/{request.match_info['path']}"
        method = request.method
        headers = dict(request.headers)
        body = await request.read()

        # 実ペイロードサイズ記録（32MB API上限の実測値）
        self._last_request_bytes = len(body)

        req_model = self._default_model_from_body(body)
        usage_pct = self._tracker.get_usage()
        model, provider = self._effective_route(req_model, usage_pct)

        if model != req_model and body:
            body = self._replace_model(body, model)

        if body:
            body = self._apply_thinking(body, self._config.thinking)
            # フォールバック先 (minimax) の tool_use 形式に揃える
            if provider == "minimax":
                body = sanitize_for_minimax(body)

        logger.info(f"{method} {path} model={model} mode={self._router.current_mode} usage={usage_pct:.1f}%")

        try:
            if provider == "minimax":
                resp = await self._upstream.request_minimax(method, path, headers, body)
            else:
                resp = await self._upstream.request_zai(method, path, headers, body)

            self._tracker.update_from_headers(resp["headers"])
            self._capture_model(resp["body"])
            return web.Response(
                status=resp["status"],
                content_type=resp["headers"].get("content-type", "application/json"),
                body=resp["body"],
            )

        except RateLimitError:
            logger.warning(f"429 from {provider} (model={model}), trying fallback chain")
            return await self._handle_429(method, path, headers, body)

        except UpstreamError as e:
            logger.warning(f"Upstream error from {provider}: {e.status} — trying MiniMax fallback")
            return await self._handle_upstream_error(method, path, headers, body, e)

    async def _handle_429(self, method: str, path: str,
                          headers: dict, orig_body: bytes) -> web.Response:
        # peak_block (JST 15-19時) は GLM を使わない設計。
        # MiniMax が 429 でも通常は GLM には逃げず MiniMax の短いリトライのみ行う
        # （MiniMax 全滅時のみ 4.7-Flash 最後の砦へ逃がす・2026-08-19 改訂）。
        if self._router.current_mode == "peak_block":
            return await self._handle_429_peak_block(method, path, headers, orig_body)

        # 新チェーン（2026-08-17 改訂・ユーザー確定）:
        #   ZAI 429 → ① MiniMax-M3（高性能側・keys[0]=Pro → keys[1]=旧の連鎖を内包）
        #           → ② GLM-4.7-Flash（ZAI 無料枠・最後の砦） → ③ 503
        if self._config.minimax_api_keys:
            fb_model, _ = self._router.get_fallback()
            body = self._replace_model(orig_body, fb_model) if orig_body else orig_body
            if body:
                body = sanitize_for_minimax(body)
            try:
                resp = await self._upstream.request_minimax(method, path, headers, body)
                logger.info(f"429 -> MiniMax succeeded (model={fb_model})")
                self._tracker.update_from_headers(resp["headers"])
                self._capture_model(resp["body"])
                return web.Response(
                    status=resp["status"],
                    content_type="application/json",
                    body=resp["body"],
                )
            except RateLimitError:
                logger.warning("MiniMax also rate limited, trying GLM-4.7-Flash via ZAI")
            except UpstreamError as e:
                logger.warning(f"MiniMax error: {e}, trying GLM-4.7-Flash via ZAI")

        # 最後の砦: GLM-4.7-Flash（thresholds とは独立の定数・無料枠で無制限運用）
        last_resort_model = "GLM-4.7-Flash"
        body = self._replace_model(orig_body, last_resort_model) if orig_body else orig_body
        try:
            resp = await self._upstream.request_zai(method, path, headers, body)
            logger.info(f"429 -> ZAI last resort ({last_resort_model}) succeeded")
            self._tracker.update_from_headers(resp["headers"])
            self._capture_model(resp["body"])
            return web.Response(
                status=resp["status"],
                content_type="application/json",
                body=resp["body"],
            )
        except RateLimitError:
            logger.error(f"Even last resort ({last_resort_model}) rate limited")
        except UpstreamError as e:
            logger.error(f"Last resort error: {e}")

        return web.Response(
            status=503,
            headers={"Retry-After": "600"},
            content_type="application/json",
            text=json.dumps({
                "error": "all_providers_rate_limited",
                "message": "MiniMax and ZAI last resort both rate limited. Wait for reset.",
            }),
        )

    async def _handle_429_peak_block(self, method: str, path: str,
                                     headers: dict, orig_body: bytes) -> web.Response:
        """peak_block 中の 429 処理: MiniMax を1回リトライ → 全滅時のみ 4.7-Flash → 503。

        設計上、peak_block (JST 15-19時) は GLM を使わない（ZAI 側のピーク
        制限を避けるため）。MiniMax が 429 でも通常は GLM-4.7-Flash へは逃げず
        MiniMax の短いリトライ (1秒待ち・1回) のみ行う。ただし MiniMax 両キー
        全滅時は 503 が確定しているため、最後の砦として 4.7-Flash（ZAI無料枠）
        を60sタイムアウト付きで1回だけ試行する（2026-08-19 改訂）。
        """
        if self._config.minimax_api_keys:
            fb_model, _ = self._router.get_fallback()
            body = self._replace_model(orig_body, fb_model) if orig_body else orig_body
            await asyncio.sleep(1.0)
            try:
                resp = await self._upstream.request_minimax(method, path, headers, body)
                logger.info(f"MiniMax retry succeeded in peak_block (model={fb_model})")
                self._tracker.update_from_headers(resp["headers"])
                self._capture_model(resp["body"])
                return web.Response(
                    status=resp["status"],
                    content_type="application/json",
                    body=resp["body"],
                )
            except RateLimitError:
                logger.error("MiniMax rate limited in peak_block, trying GLM-4.7-Flash last resort")
            except UpstreamError as e:
                logger.error(f"MiniMax error in peak_block: {e}, trying GLM-4.7-Flash last resort")

        # 最後の砦（2026-08-19 改訂・3機レビュー採用）: MiniMax全滅時のみ
        # 4.7-Flash（ZAI無料枠）へ1回逃がす。60sタイムアウトでZAIゲートウェイ
        # 遅延時の全タブハングを防止（試さなければ結末は同じ503のため試す方が合理的）。
        last_resort_model = "GLM-4.7-Flash"
        lr_body = self._replace_model(orig_body, last_resort_model) if orig_body else orig_body
        try:
            resp = await asyncio.wait_for(
                self._upstream.request_zai(method, path, headers, lr_body),
                timeout=60.0)
            logger.info(
                "peak_block: MiniMax exhausted, escaping to GLM-4.7-Flash "
                "(last resort) succeeded")
            self._tracker.update_from_headers(resp["headers"])
            self._capture_model(resp["body"])
            return web.Response(
                status=resp["status"],
                content_type="application/json",
                body=resp["body"],
            )
        except asyncio.TimeoutError:
            logger.error("peak_block: GLM-4.7-Flash last resort timed out (60s)")
        except RateLimitError:
            logger.error("peak_block: GLM-4.7-Flash last resort rate limited")
        except UpstreamError as e:
            logger.error(f"peak_block: GLM-4.7-Flash last resort error: {e}")

        return web.Response(
            status=503,
            headers={"Retry-After": "600"},
            content_type="application/json",
            text=json.dumps({
                "error": "peak_block_all_providers_limited",
                "message": "MiniMax and GLM-4.7-Flash last resort both failed during peak block. Wait for reset.",
            }),
        )

    async def _handle_upstream_error(self, method: str, path: str,
                                       headers: dict, orig_body: bytes,
                                       original_error: UpstreamError) -> web.Response:
        """Handle non-429 errors from ZAI by falling back to MiniMax."""
        if not self._config.minimax_api_key:
            logger.error("MiniMax API key not configured, cannot fallback")
            return web.Response(
                status=original_error.status,
                content_type="application/json",
                text=json.dumps({
                    "error": "upstream_error",
                    "message": f"ZAI error: {original_error}",
                }),
            )

        fb_model, _ = self._router.get_fallback()
        body = self._replace_model(orig_body, fb_model) if orig_body else orig_body
        try:
            resp = await self._upstream.request_minimax(method, path, headers, body)
            logger.info(f"MiniMax fallback succeeded after ZAI error (model={fb_model})")
            self._tracker.update_from_headers(resp["headers"])
            self._capture_model(resp["body"])
            return web.Response(
                status=resp["status"],
                content_type=resp["headers"].get("content-type", "application/json"),
                body=resp["body"],
            )
        except RateLimitError:
            logger.error("MiniMax also rate limited after ZAI error")
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({
                    "error": "all_providers_failed",
                    "message": "ZAI error and MiniMax also rate limited.",
                }),
            )
        except UpstreamError as e:
            logger.error(f"MiniMax also failed: {e}")
            return web.Response(
                status=original_error.status,
                content_type="application/json",
                text=json.dumps({
                    "error": "all_providers_failed",
                    "message": f"ZAI: {original_error}, MiniMax: {e}",
                }),
            )

    def _capture_model(self, body: bytes) -> None:
        """Extract actual model name from upstream response.

        通常の JSON レスポンスと SSE ストリーム (event:/data: 形式) の両方に対応。
        SSE の場合は message_start イベントから model を抽出する。
        """
        text = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body)

        # SSE ストリーム: "event: ...\\ndata: {...}" 形式
        stripped = text.lstrip()
        if stripped.startswith("event:") or stripped.startswith("data:"):
            model = self._extract_model_from_sse(text)
            if model:
                self._last_actual_model = model
                logger.info(f"Captured actual model (SSE): {model}")
            return

        # 通常の JSON レスポンス
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"_capture_model: non-JSON body, skipping ({e})")
            return

        if not isinstance(data, dict):
            return

        model = data.get("model")
        if model:
            self._last_actual_model = model
            logger.info(f"Captured actual model: {model}")

    @staticmethod
    def _extract_model_from_sse(text: str) -> str | None:
        """SSE ストリームから message.model を抽出する。

        message_start イベントの data ペイロード
        {"message": {"model": "..."}} を探す。
        """
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            # message_start: {"message": {"model": "..."}}
            msg = data.get("message")
            if isinstance(msg, dict) and msg.get("model"):
                return msg["model"]
            # 直接 model を持つイベントのフォールバック
            if data.get("model"):
                return data["model"]
        return None


    @staticmethod
    def _default_model_from_body(body: bytes) -> str | None:
        try:
            data = json.loads(body)
            return data.get("model")
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _apply_thinking(body: bytes, thinking_config: dict) -> bytes:
        try:
            data = json.loads(body)
            mode = thinking_config.get("mode", "always_off")
            budget = thinking_config.get("budget_tokens", 8000)
            keywords = thinking_config.get("coding_keywords", [])

            if mode == "always_off":
                enable = False
            elif mode == "always_on":
                enable = True
            else:
                text = _extract_message_text(data).lower()
                enable = any(kw in text for kw in keywords)

            if enable:
                data["thinking"] = {"type": "enabled", "budget_tokens": budget}
                logger.debug(f"Thinking enabled (budget={budget})")
            else:
                data["thinking"] = {"type": "disabled"}

            return json.dumps(data).encode("utf-8")
        except (json.JSONDecodeError, TypeError):
            return body

    @staticmethod
    def _replace_model(body: bytes, new_model: str) -> bytes:
        try:
            data = json.loads(body)
            data["model"] = new_model
            return json.dumps(data).encode("utf-8")
        except (json.JSONDecodeError, TypeError):
            return body
