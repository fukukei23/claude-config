"""Entry point for glm-rate-proxy."""

import asyncio
import logging
import signal
import sys

from aiohttp import web

from .config import load_config
from .proxy import ProxyServer


def main():
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("glm-rate-proxy")

    server = ProxyServer(config)
    app = server.create_app()

    async def on_startup(app):
        await server.start()

    async def on_cleanup(app):
        await server.stop()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    logger.info(f"Starting proxy on {config.listen_host}:{config.listen_port}")
    logger.info(f"ZAI: {config.zai_base_url} (key={'set' if config.zai_api_key else 'MISSING'})")
    logger.info(f"MiniMax: {config.minimax_base_url} (key={'set' if config.minimax_api_key else 'MISSING'})")
    logger.info(f"Thresholds: normal<{config.thresholds['normal']['max_pct']}% "
                f"economy<{config.thresholds['economy']['max_pct']}% "
                f"emergency<{config.thresholds['emergency']['max_pct']}%")
    peak = config.peak_hours
    logger.info(f"Peak block: {'ENABLED' if peak.get('enabled') else 'DISABLED'} "
                f"(JST {peak.get('start_hour', 15)}:00-{peak.get('end_hour', 19)}:00)")

    web.run_app(
        app,
        host=config.listen_host,
        port=config.listen_port,
        print=None,
        handle_signals=True,
    )


if __name__ == "__main__":
    main()
