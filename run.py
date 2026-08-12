from __future__ import annotations

import os

import uvicorn

# Folosim ``app`` din ``main`` — acolo se face deja ``create_app()`` la import.
# Un al doilea ``create_app()`` aici dubla ``load_plugins`` și handler-ele globale (ex. share).
from main import app

_DEFAULT_PORT = 8000


def main() -> None:
    """Pornește uvicorn pe TCP (APP_PORT, implicit 8000)."""
    raw = os.environ.get("APP_PORT", "").strip()
    if raw:
        try:
            port = int(raw)
            if port <= 0:
                port = _DEFAULT_PORT
        except ValueError:
            port = _DEFAULT_PORT
    else:
        port = _DEFAULT_PORT

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
