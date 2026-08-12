#!/usr/bin/env python3
"""
Trimite o notificare de test ca la o abonare nouă (aceeași cale ca în producție).

Necesită același mediu Python ca aplicația (SQLAlchemy etc.):

  Din containerul aplicației (recomandat):
    docker compose exec <nume-serviciu> python3 scripts/test_newsletter_smtp.py
    docker compose exec <nume-serviciu> python3 scripts/test_newsletter_smtp.py abonat@exemplu.tld

  Local, cu venv:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 scripts/test_newsletter_smtp.py

Fără argument pentru abonat: folosește adresa de test implicită în corpul mesajului.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def _fail_import(original: ModuleNotFoundError) -> int:
    print("Eroare: nu se pot încărca dependențele aplicației.", file=sys.stderr)
    print(f"Detaliu: {original}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "Rulează scriptul în containerul unde rulează aplicația, de exemplu:",
        file=sys.stderr,
    )
    print(
        "  docker compose exec <serviciu> python3 scripts/test_newsletter_smtp.py",
        file=sys.stderr,
    )
    print(
        "sau instalează local: pip install -r requirements.txt",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    test_email = (
        sys.argv[1].strip()
        if len(sys.argv) > 1
        else "test-newsletter@localhost"
    )

    os.chdir(_ROOT)

    try:
        from app.utils.db import init_db
        from app.core.plugin_manager import get_plugin_settings
        from app.utils.email_notify import try_send_newsletter_subscribe_notice
    except ModuleNotFoundError as e:
        return _fail_import(e)

    init_db()

    settings = get_plugin_settings("newsletter")
    preview = {k: ("***" if "password" in k else v) for k, v in sorted(settings.items())}
    print("Setări newsletter din DB (plugin_settings), fără parolă în clar:")
    for k, v in preview.items():
        print(f"  {k}: {v}")
    if not settings.get("smtp_host"):
        print(
            "\nLipsește smtp_host în setările pluginului „newsletter” "
            "(sau folosește fallback .env)."
        )

    print(f"\nTrimit notificare ca și cum s-ar fi abonat: {test_email!r}\n...")
    ok = try_send_newsletter_subscribe_notice(test_email)
    if ok:
        print("OK — verifică inbox-ul setat la „E-mail notificări” / notify_email.")
        return 0
    print(
        "Eșuat — vezi logurile aplicației sau pornește cu SMTP_DEBUG=true "
        "în .env pentru dialog SMTP detaliat."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
