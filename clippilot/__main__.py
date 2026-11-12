"""Startet ClipPilot: Server auf diesem Rechner + Browser-Fenster."""
import os
import socket
import sys
import threading
import time
import webbrowser

from . import config


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((config.HOST, port)) == 0


def main():
    url = f"http://{config.HOST}:{config.PORT}"
    no_browser = "--no-browser" in sys.argv or os.environ.get("CLIPPILOT_NO_BROWSER")
    if _port_open(config.PORT):
        print(f"ClipPilot läuft schon. Ich öffne das Fenster: {url}")
        if not no_browser:
            webbrowser.open(url)
        return
    import uvicorn

    def open_when_ready():
        for _ in range(100):
            if _port_open(config.PORT):
                break
            time.sleep(0.2)
        if not no_browser:
            webbrowser.open(url)

    threading.Thread(target=open_when_ready, daemon=True).start()
    print("=" * 60)
    print("  ClipPilot läuft.")
    print(f"  Adresse im Browser: {url}")
    print("  Dieses Fenster offen lassen. Zum Beenden: Fenster schließen.")
    print("=" * 60)
    uvicorn.run("clippilot.server:app", host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
