"""Upstream API communication (ZAI and MiniMax) using httpx."""

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
                 zai_api_key: str, minimax_api_key, timeout: float):
        """minimax_api_key は str(単一) または list[str](優先順・先頭が優先)。

        複数キー時は request_minimax で先頭から順に試行し、
        429/401/403 で次キーへフォールバックする（Pro優先＋旧フォールバック）。
        """
        self._zai_base_url = zai_base_url.rstrip("/")
        self._minimax_base_url = minimax_base_url.rstrip("/")
        self._zai_api_key = zai_api_key
        # list正規化: 空は [] 、strは [str]、listはそのまま（空文字フィルタ）
        if isinstance(minimax_api_key, str):
            keys = [minimax_api_key] if minimax_api_key else []
        else:
            keys = [k for k in minimax_api_key if k]
        self._minimax_api_keys = keys
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
        """MiniMaxへリクエスト。複数キー時は先頭(優先)から試行し、
        429/401/403で次キー(フォールバック)へ。全キー失敗なら最後の例外をraise。"""
        if not self._minimax_api_keys:
            # キー未設定: 既存挙動(空x-api-keyで401)を維持しつつ呼出元へ伝播
            raise UpstreamError(401, "MiniMax API key not configured")
        clean_path = path.removeprefix("/v1")
        url = f"{self._minimax_base_url}{clean_path}"
        base_fwd = {k: v for k, v in headers.items() if k.lower() not in ("host",)}
        base_fwd["content-type"] = "application/json"

        last_exc: Exception | None = None
        for idx, key in enumerate(self._minimax_api_keys):
            fwd = dict(base_fwd)
            fwd["x-api-key"] = key
            try:
                resp = await self._do_request(url, method, fwd, body)
                if idx > 0:
                    logger.info(f"MiniMax fallback key#{idx} succeeded")
                return resp
            except RateLimitError as e:
                last_exc = e
                if len(self._minimax_api_keys) > 1:
                    logger.warning(f"MiniMax key#{idx} 429, trying next key")
            except UpstreamError as e:
                last_exc = e
                # 401/403(認証系)のみ次キーへ。それ以外(5xx等)は即raise
                if e.status in (401, 403) and len(self._minimax_api_keys) > 1:
                    logger.warning(
                        f"MiniMax key#{idx} auth error {e.status}, trying next key")
                else:
                    raise
        # 全キー失敗: 最後の例外(429 or 認証エラー)を伝播
        assert last_exc is not None
        raise last_exc

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
