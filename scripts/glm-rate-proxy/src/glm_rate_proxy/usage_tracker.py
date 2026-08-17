"""Usage rate tracker for ZAI API via monitor endpoint polling.

ZAI はレスポンスヘッダに rate limit 情報を返さない（2026-08-17 実測）ため、
サブスク管理UIが内部で使う monitor API を定期ポーリングして
5h% (unit=3) と週間% (unit=6) を別々に保持する。
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("glm-rate-proxy")


class UsageTracker:
    """ZAI monitor API を定期ポーリングして 5h/週間% を別管理する。

    既存呼び出し API（get_usage / get_status / set_usage / update_from_headers）は
    維持し、get_usage は max(5h, week) を返す安全側に倒した値を提供する。
    """

    MONITOR_URL = "https://api.z.ai/api/monitor/usage/quota/limit"

    def __init__(
        self,
        status_file: str,
        zai_api_key: str = "",
        monitor_interval_sec: float = 60.0,
        monitor_timeout_sec: float = 10.0,
    ):
        self._status_file = status_file
        self._zai_api_key = zai_api_key
        self._monitor_interval = float(monitor_interval_sec)
        self._monitor_timeout = float(monitor_timeout_sec)

        # 内部状態（threading.Lock で保護）
        self._usage_5h_pct: float = 0.0
        self._usage_week_pct: float = 0.0
        self._last_success_ts: float = 0.0
        self._last_error: str | None = None
        self._poll_count: int = 0
        self._error_count: int = 0
        self._last_update: str = datetime.now(timezone.utc).isoformat()
        self._start_time: float = time.time()
        self._lock = threading.Lock()

        # バックグラウンドタスク管理
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._client: httpx.AsyncClient | None = None

    # ---- 公開 API（既存呼び出し互換） ----

    def get_usage(self) -> float:
        """より厳しい方の使用率（max(5h, week)）を返す。未取得時は 0.0。"""
        with self._lock:
            if self._last_success_ts == 0.0:
                return 0.0
            return max(self._usage_5h_pct, self._usage_week_pct)

    def get_usage_breakdown(self) -> dict:
        with self._lock:
            return {
                "usage_5h_pct": round(self._usage_5h_pct, 1),
                "usage_week_pct": round(self._usage_week_pct, 1),
                "last_success_ts": self._last_success_ts,
                "last_error": self._last_error,
                "poll_count": self._poll_count,
                "error_count": self._error_count,
            }

    def get_status(self) -> dict:
        """既存キー全保持 + 5h/週・monitor エラー状況の追加キーで公開。"""
        with self._lock:
            return {
                # 既存キー（proxy-doctor 互換）— usage_pct は max 値
                "usage_pct": round(max(self._usage_5h_pct, self._usage_week_pct), 1),
                "request_count": self._poll_count,
                "last_updated": self._last_update,
                "uptime_seconds": int(time.time() - self._start_time),
                # 追加キー（5h/週の内訳・monitor 状態）
                "usage_5h_pct": round(self._usage_5h_pct, 1),
                "usage_week_pct": round(self._usage_week_pct, 1),
                "monitor_error_count": self._error_count,
                "monitor_last_error": self._last_error,
            }

    def update_from_headers(self, headers: dict) -> float:
        """既存呼び出し互換（no-op）。ヘッダからの取得は機能不全のため
        monitor ポーリングに一本化した。現状の max 値を返すだけ。"""
        with self._lock:
            self._last_update = datetime.now(timezone.utc).isoformat()
            result = max(self._usage_5h_pct, self._usage_week_pct)
        self._write_status()
        return result

    def set_usage(self, pct: float) -> None:
        """テスト/手動操作用。両軸に同じ値を設定。"""
        with self._lock:
            self._usage_5h_pct = float(pct)
            self._usage_week_pct = float(pct)
            self._last_update = datetime.now(timezone.utc).isoformat()
        self._write_status()

    # ---- バックグラウンドポーリング ----

    async def start(self) -> None:
        """aiohttp の on_startup から呼ばれる。バックグラウンドタスク起動。"""
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._monitor_timeout)
        self._task = asyncio.create_task(self._poll_loop(), name="usage-tracker-poll")
        logger.info(f"ZAI monitor polling started (interval={self._monitor_interval}s)")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                # cancel後のawaitでCancelledErrorを回収（未回収例外警告防止）
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _poll_loop(self) -> None:
        assert self._stop_event is not None
        # 初回は即時取得、以降は間隔で
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception as e:  # noqa: BLE001 — ループ継続のため広めに捕捉
                logger.error(f"UsageTracker loop exception: {e}")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._monitor_interval
                )
            except asyncio.TimeoutError:
                pass  # 通常ループ継続

    async def _poll_once(self) -> None:
        if not self._zai_api_key:
            with self._lock:
                self._last_error = "zai_api_key not configured"
                self._error_count += 1
            return
        if self._client is None:
            return
        try:
            resp = await self._client.get(
                self.MONITOR_URL,
                headers={
                    "Authorization": f"Bearer {self._zai_api_key}",
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                with self._lock:
                    self._last_error = f"HTTP {resp.status_code}"
                    self._error_count += 1
                return
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            with self._lock:
                # 例外型名+短縮メッセージのみ（URL等の混入防止・サニタイズ）
                self._last_error = f"{type(e).__name__}: {str(e)[:120]}"
                self._error_count += 1
            return

        five_h, week = self._parse_quotas(data)
        with self._lock:
            # 片方だけ欠けていたら前回値を維持（0に戻さない）
            if five_h is not None:
                self._usage_5h_pct = five_h
            if week is not None:
                self._usage_week_pct = week
            self._last_success_ts = time.time()
            self._last_error = None
            self._poll_count += 1
            self._last_update = datetime.now(timezone.utc).isoformat()
        logger.debug(f"Usage updated: 5h={five_h}% week={week}%")
        self._write_status()

    @staticmethod
    def _parse_quotas(data: dict) -> tuple[float | None, float | None]:
        """ZAI monitor API レスポンスから 5h/週間の percentage を抽出。

        期待構造: data["data"]["limits"] に unit=3 (5h) / unit=6 (week) の
        TOKENS_LIMIT エントリが含まれる。
        """
        five_h: float | None = None
        week: float | None = None
        try:
            limits = data.get("data", {}).get("limits", [])
        except AttributeError:
            return five_h, week
        if not isinstance(limits, list):
            return five_h, week
        for entry in limits:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "TOKENS_LIMIT":
                continue
            pct = entry.get("percentage")
            if pct is None:
                continue
            try:
                pct_v = float(pct)
            except (ValueError, TypeError):
                continue
            unit = entry.get("unit")
            if unit == 3:
                five_h = pct_v
            elif unit == 6:
                week = pct_v
        return five_h, week

    def _write_status(self) -> None:
        try:
            with open(self._status_file, "w") as f:
                json.dump(self.get_status(), f)
        except OSError:
            pass
