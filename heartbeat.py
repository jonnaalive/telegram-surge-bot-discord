"""Lightweight heartbeat client for existing bots.

Copy this file to your bot project and call send_heartbeat() after your task completes.

Required env vars:
    MONITOR_URL      — e.g. http://168.107.16.244:8080
    MONITOR_API_KEY  — shared secret
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)


def _get_url():
    return os.environ.get("MONITOR_URL", "")

def _get_key():
    return os.environ.get("MONITOR_API_KEY", "")


async def send_heartbeat(bot_name: str, metadata: dict | None = None):
    """Async heartbeat — fire and forget, never raises."""
    url = _get_url()
    if not url:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{url}/api/heartbeat",
                json={
                    "bot_name": bot_name,
                    "api_key": _get_key(),
                    "metadata": metadata,
                },
            )
    except Exception as e:
        logger.debug("Heartbeat failed (ignored): %s", e)


def send_heartbeat_sync(bot_name: str, metadata: dict | None = None):
    """Sync heartbeat — runs in a daemon thread, never blocks the caller."""
    url = _get_url()
    if not url:
        return

    def _send():
        try:
            import urllib.request
            import json
            data = json.dumps({
                "bot_name": bot_name,
                "api_key": _get_key(),
                "metadata": metadata,
            }).encode()
            req = urllib.request.Request(
                f"{url}/api/heartbeat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug("Heartbeat failed (ignored): %s", e)

    t = threading.Thread(target=_send, daemon=True)
    t.start()
