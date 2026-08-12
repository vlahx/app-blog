from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from app.core.config import (
    get_active_theme,
    get_nav_fixed_post_link,
    get_site_brand_image_path,
    get_site_display_name,
    get_site_favicon_path,
    get_site_nav_icon_path,
    get_site_tagline,
    post_public_path,
)
from app.core.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    build_context,
    get_translation,
    get_translations,
    resolve_locale,
    set_locale_cookie,
)
from app.core.themes import active_theme_info
from app.core.translation_db import get_available_locales
from app.utils.open_graph import public_site_origin


def _apply_theme_loader(templates: Jinja2Templates, *, directory: str = "templates") -> None:
    """
    Reconfigurează loader-ul în funcție de tema curentă.
    Asta permite schimbarea temei din Admin fără restart.
    """
    active = get_active_theme()
    loaders = []
    if active:
        theme_dir = os.path.join("themes", active, "templates")
        if os.path.isdir(theme_dir):
            loaders.append(FileSystemLoader(theme_dir))
    # Default theme is always available as fallback.
    default_dir = os.path.join("themes", "default", "templates")
    if os.path.isdir(default_dir):
        loaders.append(FileSystemLoader(default_dir))
    loaders.append(FileSystemLoader(directory))
    templates.env.loader = ChoiceLoader(loaders)


def build_templates(directory: str = "templates") -> Jinja2Templates:
    templates = Jinja2Templates(directory=directory)
    # THEME LOADER: caută întâi în `themes/<active>/templates`, apoi în `templates/` (default).
    _apply_theme_loader(templates, directory=directory)
    templates.env.globals["now"] = lambda: datetime.now(timezone.utc)
    templates.env.globals["site_display_name"] = get_site_display_name
    templates.env.globals["site_tagline"] = get_site_tagline
    templates.env.globals["post_public_path"] = post_public_path
    templates.env.globals["active_theme"] = get_active_theme
    templates.env.globals["active_theme_info"] = active_theme_info
    templates.env.globals["resolve_locale"] = resolve_locale
    templates.env.globals["get_translations"] = get_translations
    templates.env.globals["translate"] = lambda locale, key: get_translation(locale, key)
    templates.env.globals.setdefault("translate", lambda locale, key: get_translation(locale, key))
    templates.env.globals["get_available_locales"] = get_available_locales
    templates.env.globals["get_translations"] = get_translations
    templates.env.globals["translate"] = lambda locale, key: get_translation(locale, key)

    def _safe_translation_lookup(data: dict | None, path: str, default: str = "") -> str:
        if not isinstance(data, dict):
            return ""
        cur = data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return ""
            cur = cur[part]
        if isinstance(cur, str):
            return cur
        return ""

    templates.env.globals["t_safe"] = _safe_translation_lookup
    # Some Jinja2 versions can build an unhashable cache key; disabling cache avoids 500s.
    templates.env.cache = None
    return templates


def render_template(
    templates: Jinja2Templates,
    *,
    request,
    name: str,
    context: dict,
    status_code: int = 200,
):
    _apply_theme_loader(templates, directory="templates")
    ctx = dict(context)
    ctx.setdefault("request", request)
    root = public_site_origin(request)
    brand = get_site_brand_image_path()
    bpath = brand if brand.startswith("/") else f"/{brand}"
    ctx.setdefault("site_brand_image_abs", f"{root}{bpath}")
    fav = get_site_favicon_path()
    fpath = fav if fav.startswith("/") else f"/{fav}"
    ctx.setdefault("site_favicon_abs", f"{root}{fpath}")
    nav_icon = get_site_nav_icon_path()
    if nav_icon:
        ipath = nav_icon if nav_icon.startswith("/") else f"/{nav_icon}"
        ctx.setdefault("site_nav_icon_abs", f"{root}{ipath}")
    else:
        ctx.setdefault("site_nav_icon_abs", None)
    locale = getattr(request.state, "locale", None) or resolve_locale(request)
    if "lang" in request.query_params and request.query_params.get("lang", "").strip():
        requested_locale = request.query_params.get("lang", "").strip().lower()
        if requested_locale in SUPPORTED_LOCALES:
            locale = requested_locale
    if not locale:
        locale = DEFAULT_LOCALE
    ctx.setdefault("seo_site_name", get_site_display_name(locale))
    ctx.setdefault("nav_fixed_post_link", get_nav_fixed_post_link())
    from app.utils.auth import get_current_user_from_request
    current_user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    ctx["current_user"] = current_user
    ctx["user"] = current_user
    ctx["locale"] = locale
    ctx["site_display_name"] = lambda: get_site_display_name(locale)
    ctx["site_tagline"] = lambda: get_site_tagline(locale)
    ctx["translations"] = getattr(request.state, "translations", None) or get_translations(locale)
    ctx["lang"] = locale
    ctx["t"] = lambda key: get_translation(locale, key)
    ctx["current_locale"] = locale
    ctx.setdefault("get_available_locales", get_available_locales)
    ctx.setdefault("get_translations", get_translations)
    ctx.setdefault("translate", lambda key: get_translation(locale, key))
    # NU seta cheia "active_theme" aici: ar umbri globalul Jinja `active_theme()` (funcție),
    # iar în template ar apărea TypeError: 'str' object is not callable.
    ctx.setdefault("active_theme_slug", get_active_theme())
    ctx.setdefault("og_image_width", None)
    ctx.setdefault("og_image_height", None)
    ctx.setdefault("og_image_type", None)
    # admin/editor.html: |tojson pe cheie lipsă → Undefined → TypeError la serializare (500)
    ctx.setdefault("editor_document_base", f"{root.rstrip('/')}/")
    response = templates.TemplateResponse(request, name, ctx, status_code=status_code)
    set_locale_cookie(response, locale)
    return response

