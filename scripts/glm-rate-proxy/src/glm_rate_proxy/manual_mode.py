"""手動プロバイダ指定（manual override）の状態管理.

POST /proxy/mode で「今日はMiniMax固定」を切り替えるための状態を保持する:
- TTL（既定8時間・上限72）で自動 auto 復帰（切りっぱなし忘れ防止）
- /tmp/glm-rate-proxy-manual.json へ永続化（クラッシュ→systemd再起動でも意図維持）
- 期限30分前に WARNING ログを1回出力（journalctl で気づける）

設計正典: 00_SYSTEM/マルチLLMレビュー/2026-08-19_glm-rate-proxy手動モードAPI-設計レビュー/revised_proposal.md
"""

import asyncio
import json
import logging
import os
import time

logger = logging.getLogger("glm-rate-proxy")

DEFAULT_STATE_FILE = "/tmp/glm-rate-proxy-manual.json"
# 期限何秒前に警告ログを出すか
TTL_WARNING_SEC = 1800
# 手動指定を許可するprovider（2026-09-04: "glm" 追加・peak_block中のみ有効）
ALLOWED_PROVIDERS = ("minimax", "glm")


class ManualOverride:
    """manual provider override（"minimax"=常時MiniMax・"glm"=peak_block中のみGLM・None=auto）."""

    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self._state_file = state_file
        self._provider: str | None = None
        self._expires_at: float | None = None
        self._expiry_warned = False
        self._lock = asyncio.Lock()

    @property
    def state_file(self) -> str:
        return self._state_file

    def load(self) -> None:
        """起動時復元。期限切れ・形式不正ファイルは無視（安全側=auto）."""
        try:
            data = json.load(open(self._state_file))
        except (OSError, json.JSONDecodeError):
            return
        if (isinstance(data, dict) and data.get("provider") in ALLOWED_PROVIDERS
                and data.get("expires_at", 0) > time.time()):
            self._provider = data["provider"]
            self._expires_at = float(data["expires_at"])
            logger.info(
                f"Restored manual override: provider={self._provider} "
                f"expires_at={self._expires_at:.0f}")

    async def set(self, provider: str, hours: float) -> None:
        async with self._lock:
            self._provider = provider
            self._expires_at = time.time() + hours * 3600
            self._expiry_warned = False
            self._persist()

    async def clear(self) -> None:
        async with self._lock:
            self._provider = None
            self._expires_at = None
            self._persist()

    def active(self) -> str | None:
        """有効な手動指定があれば provider を返す。期限切れは None 化して auto 復帰."""
        if self._provider is None:
            return None
        now = time.time()
        if self._expires_at is not None and now >= self._expires_at:
            logger.info("Manual override expired, returning to auto")
            self._provider = None
            self._expires_at = None
            self._persist()
            return None
        if (self._expires_at is not None and not self._expiry_warned
                and self._expires_at - now <= TTL_WARNING_SEC):
            logger.warning(
                f"manual override expires in 30min (provider={self._provider})")
            self._expiry_warned = True
        return self._provider

    def expires_at(self) -> float | None:
        return self._expires_at

    def _persist(self) -> None:
        """状態をファイルへ。auto ならファイルを削除（*_lock 内でのみ呼ぶこと）."""
        try:
            if self._provider is None:
                if os.path.exists(self._state_file):
                    os.remove(self._state_file)
            else:
                with open(self._state_file, "w") as f:
                    json.dump({"provider": self._provider,
                               "expires_at": self._expires_at}, f)
        except OSError as e:
            logger.warning(f"manual override persist failed: {e}")
