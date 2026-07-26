"""Usage rate tracker for ZAI API."""

import json
import threading
import time
from datetime import datetime, timezone


class UsageTracker:
    def __init__(self, status_file: str):
        self._status_file = status_file
        self._usage_pct: float = 0.0
        self._request_count: int = 0
        self._last_update: str = datetime.now(timezone.utc).isoformat()
        self._lock = threading.Lock()
        self._start_time = time.time()

    def update_from_headers(self, headers: dict) -> float:
        # Try standard rate limit headers
        for key, val in headers.items():
            k = key.lower()
            if k in ("x-ratelimit-used-percentage", "x-ratelimit-5h-percentage"):
                try:
                    pct = float(val)
                    with self._lock:
                        self._usage_pct = pct
                        self._request_count += 1
                        self._last_update = datetime.now(timezone.utc).isoformat()
                    self._write_status()
                    return pct
                except (ValueError, TypeError):
                    pass

        # Try ZAI-specific nested header
        for key, val in headers.items():
            if "rate" in key.lower() and "limit" in key.lower():
                try:
                    data = json.loads(val) if isinstance(val, str) else val
                    if isinstance(data, dict):
                        pct = data.get("used_percentage") or data.get("five_hour", {}).get("used_percentage")
                        if pct is not None:
                            with self._lock:
                                self._usage_pct = float(pct)
                                self._request_count += 1
                                self._last_update = datetime.now(timezone.utc).isoformat()
                            self._write_status()
                            return float(pct)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

        # Fallback: increment count only
        with self._lock:
            self._request_count += 1
            self._last_update = datetime.now(timezone.utc).isoformat()
        self._write_status()
        return self._usage_pct

    def set_usage(self, pct: float) -> None:
        with self._lock:
            self._usage_pct = pct
            self._last_update = datetime.now(timezone.utc).isoformat()
        self._write_status()

    def get_usage(self) -> float:
        with self._lock:
            return self._usage_pct

    def get_status(self) -> dict:
        with self._lock:
            return {
                "usage_pct": round(self._usage_pct, 1),
                "request_count": self._request_count,
                "last_updated": self._last_update,
                "uptime_seconds": int(time.time() - self._start_time),
            }

    def _write_status(self) -> None:
        try:
            with open(self._status_file, "w") as f:
                json.dump(self.get_status(), f)
        except OSError:
            pass
