"""Configuration loader for glm-rate-proxy."""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field


DEFAULTS = {
    "zai_base_url": "https://api.z.ai/api/anthropic",
    "minimax_base_url": "https://api.minimax.io/anthropic/v1",
    "listen_host": "127.0.0.1",
    "listen_port": 8787,
    "upstream_timeout": 30.0,
    "log_level": "INFO",
    "default_model": "glm-5.2",
    "status_file": "/tmp/glm-rate-proxy-status.json",
    "thresholds": {
        "normal": {"max_pct": 80, "model": None},
        # economy(usage 80-95%)は MiniMax-M3 へ（コスト0・品質向上）
        # 両プロバイダ月額サブスク既払い・MiniMax枠超過時は429→emergency(GLM-4.7-Flash)へ逆フォールバック
        "economy": {"max_pct": 95, "model": "MiniMax-M3", "provider": "minimax"},
        "emergency": {"max_pct": 100, "model": "GLM-4.7-Flash"},
    },
    "fallback": {
        "provider": "minimax",
        "model": "MiniMax-M3",
    },
    "peak_hours": {
        "enabled": True,
        "start_hour": 15,
        "end_hour": 19,
        "timezone_offset": 9,
    },
    "thinking": {
        "mode": "auto",
        "budget_tokens": 8000,
        "coding_keywords": [
            "edit", "fix", "implement", "debug", "write", "refactor",
            "create", "add", "modify", "update", "build", "test", "generate",
        ],
    },
}


@dataclass
class ProxyConfig:
    zai_base_url: str = DEFAULTS["zai_base_url"]
    minimax_base_url: str = DEFAULTS["minimax_base_url"]
    zai_api_key: str = ""
    minimax_api_key: str = ""
    minimax_api_key_fallback: str = ""
    listen_host: str = "127.0.0.1"
    listen_port: int = 8787
    upstream_timeout: float = 30.0
    log_level: str = "INFO"
    default_model: str = "glm-5.2"
    status_file: str = "/tmp/glm-rate-proxy-status.json"
    thresholds: dict = field(default_factory=lambda: DEFAULTS["thresholds"].copy())
    fallback: dict = field(default_factory=lambda: DEFAULTS["fallback"].copy())
    peak_hours: dict = field(default_factory=lambda: DEFAULTS["peak_hours"].copy())
    thinking: dict = field(default_factory=lambda: DEFAULTS["thinking"].copy())

    @property
    def minimax_api_keys(self) -> list[str]:
        """MiniMax APIキーの優先順リスト（Pro優先＋旧フォールバック）。
        先頭=minimax_api_key(優先/Pro)、次=minimax_api_key_fallback(予備/旧)。
        空文字は除外される。"""
        return [k for k in (self.minimax_api_key, self.minimax_api_key_fallback) if k]


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str | None = None) -> ProxyConfig:
    if config_path is None:
        config_path = str(
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            / "glm-rate-proxy"
            / "config.json"
        )

    merged = DEFAULTS.copy()
    if os.path.exists(config_path):
        with open(config_path) as f:
            user_config = json.load(f)
        merged = _deep_merge(merged, user_config)

    cfg = ProxyConfig(
        zai_base_url=merged["zai_base_url"],
        minimax_base_url=merged["minimax_base_url"],
        zai_api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        minimax_api_key=os.environ.get("MINIMAX_API_KEY", ""),
        minimax_api_key_fallback=os.environ.get("MINIMAX_API_KEY_FALLBACK", ""),
        listen_host=merged["listen_host"],
        listen_port=int(merged["listen_port"]),
        upstream_timeout=float(merged["upstream_timeout"]),
        log_level=merged["log_level"],
        default_model=merged["default_model"],
        status_file=merged["status_file"],
        thresholds=merged["thresholds"],
        fallback=merged["fallback"],
        peak_hours=merged["peak_hours"],
        thinking=merged["thinking"],
    )
    # GLM_PEAK_BLOCK=false でピークブロック無効化
    env_peak = os.environ.get("GLM_PEAK_BLOCK", "").lower()
    if env_peak in ("false", "0", "no", "off"):
        cfg.peak_hours["enabled"] = False
    return cfg
