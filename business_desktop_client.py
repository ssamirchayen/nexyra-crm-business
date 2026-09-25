from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path


def load_client_env() -> None:
    path = Path(__file__).resolve().parent / ".env.client"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_client_env()
    url = os.getenv("NEXYRA_BUSINESS_WEB_URL", "http://127.0.0.1:8080").rstrip("/")
    title = os.getenv("NEXYRA_BUSINESS_CLIENT_TITLE", "Nexyra Business")

    try:
        import webview  # type: ignore
    except ImportError:
        webbrowser.open(url)
        return 0

    webview.create_window(title, url=url, width=1440, height=900, min_size=(1080, 700))
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
