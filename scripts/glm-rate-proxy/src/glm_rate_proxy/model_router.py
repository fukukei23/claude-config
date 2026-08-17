"""Model selection logic based on usage percentage and peak hours."""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("glm-rate-proxy")


def _is_peak_hour(peak_config: dict) -> bool:
    """ピーク時間帯（JST 15:00-19:00等）かどうかを判定。"""
    if not peak_config.get("enabled", False):
        return False
    tz_offset = peak_config.get("timezone_offset", 9)
    tz = timezone(timedelta(hours=tz_offset))
    now_hour = datetime.now(tz).hour
    start = peak_config.get("start_hour", 15)
    end = peak_config.get("end_hour", 19)
    return start <= now_hour < end


class ModelRouter:
    def __init__(self, thresholds: dict, fallback: dict, default_model: str,
                 peak_hours: dict | None = None):
        self._thresholds = thresholds
        self._fallback = fallback
        self._default_model = default_model
        self._current_mode = "normal"
        self._peak_hours = peak_hours or {}

    def determine_mode(self, usage_pct: float) -> str:
        """2段階判定: peak_block → normal → emergency.

        economy 段は廃止（2026-08-17 改訂・95%までは GLM-5.3 のまま）。
        呼び出し側で max(5h, 週間%) を渡すこと（router は内訳を知らない）。
        """
        if _is_peak_hour(self._peak_hours):
            mode = "peak_block"
        elif usage_pct < self._thresholds["normal"]["max_pct"]:
            mode = "normal"
        else:
            mode = "emergency"

        if mode != self._current_mode:
            logger.info(f"Mode changed: {self._current_mode} → {mode}"
                        + (f" (usage: {usage_pct:.1f}%)" if mode != "peak_block" else " (PEAK BLOCK)"))
            self._current_mode = mode
        return mode

    def route_model(self, original_model: str | None, usage_pct: float) -> tuple[str, str]:
        """Returns (model_to_use, provider)."""
        mode = self.determine_mode(usage_pct)

        if mode == "peak_block":
            fb_model = self._fallback["model"]
            return fb_model, self._fallback["provider"]

        if mode == "normal":
            model = original_model or self._default_model
            return model, "zai"

        # emergency: thresholds.emergency の model/provider（既定 MiniMax-M3/minimax）
        cfg = self._thresholds["emergency"]
        model = cfg.get("model") or self._fallback["model"]
        provider = cfg.get("provider", self._fallback["provider"])
        return model, provider

    def get_fallback(self) -> tuple[str, str]:
        """Returns (fallback_model, fallback_provider)."""
        return self._fallback["model"], self._fallback["provider"]

    @property
    def current_mode(self) -> str:
        return self._current_mode
