"""HTTP proxy server for Claude Code -> ZAI API with rate-limit aware model routing."""

import json
import logging
from aiohttp import web

from .config import ProxyConfig
from .usage_tracker import UsageTracker
from .model_router import ModelRouter
from .upstream import UpstreamClient, RateLimitError, UpstreamError

logger = logging.getLogger("glm-rate-proxy")


class ProxyServer:
    def __init__(self, config: ProxyConfig):
        self._config = config
        self._tracker = UsageTracker(config.status_file)
        self._router = ModelRouter(
            config.thresholds, config.fallback, config.default_model,
            config.peak_hours,
        )
        self._upstream = UpstreamClient(
            config.zai_base_url, config.minimax_base_url,
            config.zai_api_key, config.minimax_api_key,
            config.upstream_timeout,
        )
        self._last_actual_model: str | None = None

    async def start(self) -> None:
        await self._upstream.start()

    async def stop(self) -> None:
        await self._upstream.stop()

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/v1/{path:.*}", self._handle_api)
        app.router.add_get("/proxy/status", self._handle_status)
        return app

    async def _handle_status(self, request: web.Request) -> web.Response:
        status = self._tracker.get_status()
        status["mode"] = self._router.current_mode
        _, provider = self._router.route_model(None, self._tracker.get_usage())
        status["provider"] = provider
        status["zai_configured"] = bool(self._config.zai_api_key)
        status["minimax_configured"] = bool(self._config.minimax_api_key)
        status["peak_block"] = self._router.current_mode == "peak_block"
        status["last_actual_model"] = self._last_actual_model
        return web.json_response(status)

    async def _handle_api(self, request: web.Request) -> web.Response:
        path = f"/v1/{request.match_info['path']}"
        method = request.method
        headers = dict(request.headers)
        body = await request.read()

        req_model = self._default_model_from_body(body)
        usage_pct = self._tracker.get_usage()
        model, provider = self._router.route_model(req_model, usage_pct)

        if model != req_model and body:
            body = self._replace_model(body, model)

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
        emergency_model = self._config.thresholds["emergency"]["model"]
        if emergency_model:
            body = self._replace_model(orig_body, emergency_model) if orig_body else orig_body
            try:
                resp = await self._upstream.request_zai(method, path, headers, body)
                logger.info(f"429 fallback to {emergency_model} succeeded")
                self._tracker.update_from_headers(resp["headers"])
                self._capture_model(resp["body"])
                return web.Response(
                    status=resp["status"],
                    content_type="application/json",
                    body=resp["body"],
                )
            except RateLimitError:
                logger.warning(f"429 even with {emergency_model}, trying MiniMax")
            except UpstreamError as e:
                logger.warning(f"Error with {emergency_model}: {e}, trying MiniMax")

        if self._config.minimax_api_key:
            fb_model, _ = self._router.get_fallback()
            body = self._replace_model(orig_body, fb_model) if orig_body else orig_body
            try:
                resp = await self._upstream.request_minimax(method, path, headers, body)
                logger.info(f"MiniMax fallback succeeded (model={fb_model})")
                self._tracker.update_from_headers(resp["headers"])
                self._capture_model(resp["body"])
                return web.Response(
                    status=resp["status"],
                    content_type="application/json",
                    body=resp["body"],
                )
            except RateLimitError:
                logger.error("MiniMax also rate limited")
            except UpstreamError as e:
                logger.error(f"MiniMax error: {e}")

        return web.Response(
            status=503,
            content_type="application/json",
            text=json.dumps({
                "error": "all_providers_rate_limited",
                "message": "ZAI API rate limited and MiniMax fallback also failed. Wait for reset.",
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
        """Extract actual model name from upstream response."""
        try:
            data = json.loads(body)
            model = data.get("model")
            if model:
                self._last_actual_model = model
                logger.debug(f"Captured actual model: {model}")
        except (json.JSONDecodeError, TypeError):
            pass

    @staticmethod
    def _default_model_from_body(body: bytes) -> str | None:
        try:
            data = json.loads(body)
            return data.get("model")
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _replace_model(body: bytes, new_model: str) -> bytes:
        try:
            data = json.loads(body)
            data["model"] = new_model
            return json.dumps(data).encode("utf-8")
        except (json.JSONDecodeError, TypeError):
            return body
