import subprocess
import re
import time
import logging

logger = logging.getLogger("Tunnel")


def start_tunnel(port: int = 8000):
    """
    Starts Pinggy SSH tunnel (ssh -p 443 -R0:localhost:port a.pinggy.io).
    Has ZERO warning/interstitial pages, opens directly in Telegram Mini App.
    """
    logger.info(f"Запуск прямого HTTPS туннеля через Pinggy на порт {port}...")
    cmd = [
        "ssh.exe",
        "-p", "443",
        f"-R0:localhost:{port}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=20",
        "-o", "TCPKeepAlive=yes",
        "a.pinggy.io"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore",
    )

    tunnel_url = None
    start_time = time.time()

    while time.time() - start_time < 25:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            continue

        match = re.search(r"https://[a-zA-Z0-9-]+\.(?:run\.pinggy-free\.link|free\.pinggy\.net)", line)
        if match:
            tunnel_url = match.group(0)
            logger.info(f"Получен прямой HTTPS URL для Telegram Mini App: {tunnel_url}")
            break

    if not tunnel_url:
        proc.terminate()
        raise RuntimeError("Не удалось получить HTTPS URL от Pinggy")

    return proc, tunnel_url
