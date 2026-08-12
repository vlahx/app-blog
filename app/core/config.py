from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.models.db_models import AppSetting

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


SESSION_SECRET = (
    os.environ.get("SESSION_SECRET", "").strip() or "dev-insecure-session-secret"
)

# URL public (https://domeniu.tld) — doar din .env (Caddy / domeniu). Folosit la OG, TinyMCE, canonice.
# Nu se suprascrie din admin; fiecare container își are .env-ul lui.
def _normalize_public_site_url(raw: str) -> str:
    """
    Docker / .env greșit pot lăsa literal ``PUBLIC_SITE_URL=None`` → string ``"None"``.
    Asta rupe TinyMCE (document_base_url) și poate genera request-uri ciudate.
    """
    u = (raw or "").strip().rstrip("/")
    if not u or u.lower() in ("none", "null", "undefined"):
        return ""
    return u


PUBLIC_SITE_URL = _normalize_public_site_url(os.environ.get("PUBLIC_SITE_URL", ""))

# Nume afișat (navbar, meta og:site_name). Suprascrie din admin (site_settings.json) sau .env.
SITE_DISPLAY_NAME = (
    os.environ.get("SITE_DISPLAY_NAME", "").strip() or "Blog"
)
SITE_TAGLINE = (
    os.environ.get("SITE_TAGLINE", "").strip()
    or "Jurnal de drum, articole și povești de pe șosea."
)

# Favicon (`<link rel="icon">`). Cale relativă, începe cu `/`.
SITE_FAVICON_PATH = (
    os.environ.get("SITE_FAVICON_PATH", "/static/images/favicon.ico").strip()
    or "/static/images/post_images/favicon.ico"
)

# Apple touch / fallback brand. Cale relativă, începe cu `/`.
SITE_BRAND_IMAGE_PATH = (
    os.environ.get("SITE_BRAND_IMAGE_PATH", "/static/images/site-brand.svg").strip()
    or "/static/images/site-brand.svg"
)

# og:image / twitter:image — fișier static PNG sau JPEG (~1200×630), cale relativă cu `/`.
# Dacă articolul are doar WebP sau altceva, meta folosește tot acest fișier.
OG_CARD_IMAGE_PATH = (
    os.environ.get("OG_CARD_IMAGE_PATH", "/static/images/og/camionagiul.png").strip()
    or "/static/images/og/camionagiul.png"
)

# Icon navbar / hero (opțional). Gol → SVG implicit în template.
SITE_NAV_ICON_PATH = os.environ.get("SITE_NAV_ICON_PATH", "").strip()

# Link fix în navbar către un articol publicat: slug-ul din `/blog/<slug>`. Suprascrie din admin.
NAV_FIXED_POST_SLUG = os.environ.get("NAV_FIXED_POST_SLUG", "").strip()
NAV_FIXED_POST_LABEL = os.environ.get("NAV_FIXED_POST_LABEL", "").strip()

# Tema activă (numele folderului din `themes/<name>/templates`). Suprascrie din admin.
ACTIVE_THEME = os.environ.get("ACTIVE_THEME", "").strip() or "default"


# La upload, fără crop: imaginea încape în max_edge×max_edge (PIL thumbnail). Folosit dacă POST_IMAGE_CROP_OG=false.
def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v > 0 else default
    except ValueError:
        return default


POST_IMAGE_MAX_EDGE = _int_env("POST_IMAGE_MAX_EDGE", 1200)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return default


# Articole la /slug în loc de /blog/slug (redirect 301 de la /blog/slug când e activ).
FLAT_POST_URLS = _bool_env("FLAT_POST_URLS", False)

# Sluguri interzise la rădăcină când FLAT_POST_URLS e activ (nu pot fi articole).
ROOT_SLUG_BLOCKLIST = frozenset(
    {
        "admin",
        "api",
        "static",
        "docs",
        "redoc",
        "openapi.json",
        "robots.txt",
        "favicon.ico",
        "login",
        "logout",
        "newsletter",
    }
)

# Cu CROP_OG=true: crop centrat + resize exact la OUTPUT_* (implicit 1200×630 ≈ 1,91:1, ca OG clasic / ~19:10).
# Pentru upload TinyMCE, default-ul este fără crop și dimensiunea maximă a laturei la 1200px.
POST_IMAGE_CROP_OG = _bool_env("POST_IMAGE_CROP_OG", False)
POST_IMAGE_OUTPUT_WIDTH = _int_env("POST_IMAGE_OUTPUT_WIDTH", 1200)
POST_IMAGE_OUTPUT_HEIGHT = _int_env("POST_IMAGE_OUTPUT_HEIGHT", 630)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip()
TELEGRAM_AUTH_TTL_SECONDS = int(
    os.environ.get("TELEGRAM_AUTH_TTL_SECONDS", "86400").strip()
)
TELEGRAM_AUTH_URL = (
    os.environ.get("TELEGRAM_AUTH_URL", "").strip() or "/admin/login/telegram"
)

# Chat ID (sau @channel) unde trimite botul notificări (ex. abonare newsletter). Același TELEGRAM_BOT_TOKEN ca la login.
TELEGRAM_NOTIFY_CHAT_ID = os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip()

# Admin → Plugin-uri: buton care trimite SIGTERM procesului (Docker cu restart: unless-stopped repornește containerul).
ADMIN_ENABLE_CONTAINER_RESTART = _bool_env("ADMIN_ENABLE_CONTAINER_RESTART", False)

# Newsletter / SMTP: log hexdump tranzacție; fără verificare cert (ex. server intern Docker cu cert self-signed).
SMTP_DEBUG = _bool_env("SMTP_DEBUG", False)
SMTP_SKIP_TLS_VERIFY = _bool_env("SMTP_SKIP_TLS_VERIFY", False)


def _runtime() -> dict:
    from app.core.site_settings import read_settings

    return read_settings()


def _db_runtime() -> dict[str, str]:
    try:
        from app.utils.db import SessionLocal

        with SessionLocal() as db:
            rows = db.query(AppSetting).all()
            return {row.key: row.value for row in rows if row and row.key}
    except Exception:
        return {}


def get_public_site_url() -> str:
    """Baza absolută a site-ului — exclusiv din PUBLIC_SITE_URL (.env)."""
    return PUBLIC_SITE_URL


def _get_localized_setting(d: dict, key: str, locale: str | None = None, fallback: str = "") -> str:
    if not isinstance(d, dict):
        return fallback
    if locale:
        locale_key = f"{key}_{locale}"
        raw = d.get(locale_key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raw = d.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return fallback


def get_site_display_name(locale: str | None = None) -> str:
    d = {**_runtime(), **_db_runtime()}
    raw = _get_localized_setting(d, "SITE_DISPLAY_NAME", locale, SITE_DISPLAY_NAME)
    return raw or SITE_DISPLAY_NAME


def get_site_tagline(locale: str | None = None) -> str:
    d = {**_runtime(), **_db_runtime()}
    raw = _get_localized_setting(d, "SITE_TAGLINE", locale, SITE_TAGLINE)
    return raw or SITE_TAGLINE


def get_site_favicon_path() -> str:
    d = _runtime()
    raw = d.get("SITE_FAVICON_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    return SITE_FAVICON_PATH


def get_site_brand_image_path() -> str:
    d = _runtime()
    raw = d.get("SITE_BRAND_IMAGE_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    return SITE_BRAND_IMAGE_PATH


def get_og_card_image_path() -> str:
    d = _runtime()
    raw = d.get("OG_CARD_IMAGE_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    return OG_CARD_IMAGE_PATH


def get_site_nav_icon_path() -> str:
    """Cale relativă cu `/` sau gol pentru fallback SVG în template."""
    d = _runtime()
    raw = d.get("SITE_NAV_ICON_PATH")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
        return v if v.startswith("/") else f"/{v}"
    if SITE_NAV_ICON_PATH:
        v = SITE_NAV_ICON_PATH.strip()
        return v if v.startswith("/") else f"/{v}"
    return ""


def get_nav_fixed_post_slug_setting() -> str:
    d = _runtime()
    raw = d.get("NAV_FIXED_POST_SLUG")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return NAV_FIXED_POST_SLUG


def get_nav_fixed_post_label_setting() -> str:
    d = _runtime()
    raw = d.get("NAV_FIXED_POST_LABEL")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return NAV_FIXED_POST_LABEL


def get_flat_post_urls() -> bool:
    """True → articole la /slug; False → /blog/slug."""
    d = _runtime()
    if "FLAT_POST_URLS" not in d:
        return FLAT_POST_URLS
    v = d["FLAT_POST_URLS"]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return FLAT_POST_URLS


def get_active_theme() -> str:
    """
    Numele temei active (ex. "default", "minimal").
    Limităm la caractere sigure ca să evităm path traversal.
    """
    d = _runtime()
    raw = d.get("ACTIVE_THEME")
    if isinstance(raw, str) and raw.strip():
        v = raw.strip()
    else:
        v = ACTIVE_THEME
    v = (v or "").strip().lower()
    if not v:
        return "default"
    ok = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if any(ch not in ok for ch in v):
        return "default"
    if v != "default":
        theme_templates = PROJECT_ROOT / "themes" / v / "templates"
        if not theme_templates.is_dir():
            return "default"
    return v


def is_static_page_slug(slug: str) -> bool:
    if not slug:
        return False
    s = slug.strip().lower()
    nav_slug = (get_nav_fixed_post_slug_setting() or "").strip().lower()
    return bool(nav_slug and nav_slug == s)


def post_public_path(slug: str) -> str:
    s = (slug or "").strip().strip("/")
    if not s:
        return "/"
    if get_flat_post_urls() or is_static_page_slug(s):
        return f"/{s}"
    return f"/blog/{s}"


def get_nav_fixed_post_link() -> dict[str, str] | None:
    """
    Dacă e setat un slug valid pentru un articol publicat (nu draft), returnează href + label pentru navbar.
    """
    slug = get_nav_fixed_post_slug_setting()
    if not slug:
        return None
    from sqlalchemy import select

    from app.models.db_models import Post as PostModel
    from app.utils.db import SessionLocal

    label_override = get_nav_fixed_post_label_setting()
    with SessionLocal() as db:
        row = db.execute(select(PostModel).where(PostModel.slug == slug)).scalars().first()
        if row is None or bool(row.draft):
            return None
        label = label_override or row.title
        return {"href": post_public_path(slug), "label": label}


def get_post_image_crop_og() -> bool:
    d = _runtime()
    if "POST_IMAGE_CROP_OG" not in d:
        return POST_IMAGE_CROP_OG
    v = d["POST_IMAGE_CROP_OG"]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return POST_IMAGE_CROP_OG


def get_post_image_max_edge() -> int:
    d = _runtime()
    if "POST_IMAGE_MAX_EDGE" not in d:
        return POST_IMAGE_MAX_EDGE
    try:
        n = int(d["POST_IMAGE_MAX_EDGE"])
        return n if n > 0 else POST_IMAGE_MAX_EDGE
    except (TypeError, ValueError):
        return POST_IMAGE_MAX_EDGE


def get_post_image_output_width() -> int:
    d = _runtime()
    if "POST_IMAGE_OUTPUT_WIDTH" not in d:
        return POST_IMAGE_OUTPUT_WIDTH
    try:
        n = int(d["POST_IMAGE_OUTPUT_WIDTH"])
        return n if n > 0 else POST_IMAGE_OUTPUT_WIDTH
    except (TypeError, ValueError):
        return POST_IMAGE_OUTPUT_WIDTH


def get_post_image_output_height() -> int:
    d = _runtime()
    if "POST_IMAGE_OUTPUT_HEIGHT" not in d:
        return POST_IMAGE_OUTPUT_HEIGHT
    try:
        n = int(d["POST_IMAGE_OUTPUT_HEIGHT"])
        return n if n > 0 else POST_IMAGE_OUTPUT_HEIGHT
    except (TypeError, ValueError):
        return POST_IMAGE_OUTPUT_HEIGHT


def get_telegram_bot_token() -> str:
    """Token: app_settings, apoi setarea plugin `telegram_notify`, apoi .env."""
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_bot_token")
    if v:
        return v
    v2 = plugin_get("telegram_notify", "bot_token")
    return v2 if v2 else TELEGRAM_BOT_TOKEN


def get_telegram_notify_chat_id() -> str:
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_notify_chat_id")
    if v:
        return v
    v2 = plugin_get("telegram_notify", "chat_id")
    return v2 if v2 else TELEGRAM_NOTIFY_CHAT_ID


def get_telegram_bot_username() -> str:
    from app.core.plugin_db_settings import get_plugin_setting as legacy_get
    from app.core.plugin_manager import get_plugin_setting as plugin_get

    v = legacy_get("telegram_bot_username")
    if v:
        return v
    v2 = plugin_get("telegram_notify", "bot_username")
    return v2 if v2 else TELEGRAM_BOT_USERNAME
