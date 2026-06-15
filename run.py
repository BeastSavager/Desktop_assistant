"""
Jarvis AI Assistant — Web launcher

Starts the local web server and opens the browser once it is healthy. This is
the entry point for the packaged .exe (see jarvis.spec) and also works directly:

    python run.py

Binds to loopback only. Picks the configured port, or the next free one.
"""

import logging
import socket
import threading
import time
import webbrowser

import uvicorn

from config import WEB_HOST, WEB_PORT
from server import _brain, app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-16s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.run")


def _pick_port(host: str, start: int, tries: int = 20) -> int:
    """Return the first bindable port at/after ``start``."""
    for candidate in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    return start


def _open_when_ready(url: str) -> None:
    """Poll /health, then open the browser once the server responds."""
    import httpx

    for _ in range(120):  # up to ~60s (cold model load can be slow)
        try:
            if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                logger.info("Server healthy — opening %s", url)
                webbrowser.open(url)
                return
        except Exception:  # noqa: BLE001 - server not up yet
            pass
        time.sleep(0.5)
    logger.warning("Health check timed out; opening %s anyway", url)
    webbrowser.open(url)


def main() -> None:
    host = WEB_HOST
    port = _pick_port(host, WEB_PORT)
    url = f"http://{host}:{port}"
    logger.info("Starting Jarvis web app at %s", url)
    # Warm the model up in the background so the first chat is fast.
    threading.Thread(target=_brain.warmup, daemon=True).start()
    threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
