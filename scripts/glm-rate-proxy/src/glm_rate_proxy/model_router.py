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
        if _is_peak_hour(self._peak_hours):
            mode = "peak_block"
        elif usage_pct < self._thresholds["normal"]["max_pct"]:
            mode = "normal"
        elif usage_pct < self._thresholds["economy"]["max_pct"]:
            mode = "economy"
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

        override_model = self._thresholds[mode]["model"]
        if override_model:
            # thresholds で provider 指定があればそれに従う（既定は zai）
            # economy=MiniMax-M3 のような別プロバイダ切り替えに使用
            provider = self._thresholds[mode].get("provider", "zai")
            return override_model, provider

        return original_model or self._default_model, "zai"

    def get_fallback(self) -> tuple[str, str]:
        """Returns (fallback_model, fallback_provider)."""
        return self._fallback["model"], self._fallback["provider"]

    @property
    def current_mode(self) -> str:
        return self._current_mode
