"""Token semnat (itsdangerous) pentru link de dezabonare newsletter, fără DB."""

from __future__ import annotations

from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import SESSION_SECRET

_SALT = "newsletter-unsub-v1"
_MAX_AGE_SECONDS = 365 * 24 * 3600


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SESSION_SECRET, salt=_SALT)


def make_unsubscribe_token(email: str) -> str:
    return _serializer().dumps(email.strip().lower())


def parse_unsubscribe_token(
    token: str, *, max_age: int = _MAX_AGE_SECONDS
) -> str | None:
    try:
        raw = _serializer().loads(token, max_age=max_age)
        return str(raw).strip().lower() if raw else None
    except (BadSignature, SignatureExpired):
        return None


def public_unsubscribe_url(token: str) -> str:
    """URL absolut dacă avem PUBLIC_SITE_URL, altfel relativ (mai slab pentru clienți de mail)."""
    from app.core.config import get_public_site_url

    q = quote(token, safe="")
    path = f"/newsletter/unsubscribe?t={q}"
    base = (get_public_site_url() or "").strip().rstrip("/")
    if base:
        return f"{base}{path}"
    return path
