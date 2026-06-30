"""Upstream API communication (ZAI and MiniMax) using httpx."""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("glm-rate-proxy")


class RateLimitError(Exception):
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.body = body
        super().__init__(f"Rate limited: {status}")


class UpstreamError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"Upstream error {status}: {message}")


class UpstreamClient:
    def __init__(self, zai_base_url: str, minimax_base_url: str,
                 zai_api_key: str, minimax_api_key: str, timeout: float):
        self._zai_base_url = zai_base_url.rstrip("/")
        self._minimax_base_url = minimax_base_url.rstrip("/")
        self._zai_api_key = zai_api_key
        self._minimax_api_key = minimax_api_key
        self._timeout = timeout

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def request_zai(self, method: str, path: str,
                          headers: dict, body: bytes) -> dict:
        url = f"{self._zai_base_url}{path}"
        fwd = {k: v for k, v in headers.items() if k.lower() not in ("host",)}
        fwd["x-api-key"] = self._zai_api_key
        fwd["content-type"] = "application/json"
        return await self._do_request(url, method, fwd, body)

    async def request_minimax(self, method: str, path: str,
                              headers: dict, body: bytes) -> dict:
        clean_path = path.removeprefix("/v1")
        url = f"{self._minimax_base_url}{clean_path}"
        fwd = {k: v for k, v in headers.items() if k.lower() not in ("host",)}
        fwd["x-api-key"] = self._minimax_api_key
        fwd["content-type"] = "application/json"
        return await self._do_request(url, method, fwd, body)

    async def _do_request(self, url: str, method: str,
                          headers: dict, body: bytes) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_request, url, method, headers, body
        )

    def _sync_request(self, url: str, method: str,
                      headers: dict, body: bytes) -> dict:
        import gzip
        # Don't accept gzip to avoid decompression issues
        skip = {"accept-encoding", "transfer-encoding", "content-length", "host"}
        clean_headers = {k: v for k, v in headers.items() if k.lower() not in skip}
        clean_headers["accept-encoding"] = "identity"
        if body:
            clean_headers["content-length"] = str(len(body))
        req = urllib.request.Request(url, data=body, headers=clean_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_body = resp.read()
                # Handle gzip anyway in case server ignores accept-encoding
                if resp.headers.get("content-encoding") == "gzip":
                    resp_body = gzip.decompress(resp_body)
                resp_headers = {k: v for k, v in resp.headers.items()
                                if k.lower() != "content-encoding"}
                return {
                    "status": resp.status,
                    "headers": resp_headers,
                    "body": resp_body,
                }
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            if e.code == 429:
                raise RateLimitError(429, resp_body)
            raise UpstreamError(e.code, resp_body.decode("utf-8", errors="replace")[:500])
        except Exception as e:
            logger.error(f"Connection error to {url}: {e}")
            raise UpstreamError(502, str(e))
