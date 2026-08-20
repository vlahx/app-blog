from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from app.core.config import (
    APP_DIR,
    PROJECT_ROOT,
    get_active_theme,
    get_nav_fixed_post_link,
    get_nav_fixed_post_links,
    get_site_brand_image_path,
    get_site_display_name,
    get_site_favicon_path,
    get_site_nav_icon_path,
    get_site_tagline,
    get_twitter_site,
    post_public_path,
)
from app.core.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    build_context,
    get_available_locales,
    get_translation,
    get_translations,
    resolve_locale,
    set_locale_cookie,
)
from app.core.themes import active_theme_info
from app.core.plugin_manager import is_plugin_enabled
from app.utils.open_graph import public_site_origin


def is_plugin_active(plugin_id: str) -> bool:
    """Verifică dacă un plugin este instalat fizic și activat"""
    p_file = APP_DIR / "plugins" / plugin_id / "plugin.py"
    if not p_file.is_file():
        return False
    try:
        return is_plugin_enabled(plugin_id)
    except Exception:
        return False


_LAST_APPLIED_THEME: str | None = None


def _apply_theme_loader(templates: Jinja2Templates, *, directory: str = "app/templates", force: bool = False) -> None:
    """
    Reconfigurează loader-ul în funcție de tema curentă.
    Asta permite schimbarea temei din Admin fără restart.
    """
    active = get_active_theme() or "minimal"
    if active == "default":
        active = "minimal"

    if not force and getattr(templates, "_applied_theme", None) == active and isinstance(templates.env.loader, ChoiceLoader):
        return

    templates._applied_theme = active
    loaders = []

    # Active theme templates (e.g. themes/elevate/templates)
    if active and active != "minimal":
        theme_dir = APP_DIR / "themes" / active / "templates"
        if theme_dir.is_dir():
            loaders.append(FileSystemLoader(str(theme_dir)))

    # Fallback minimal theme templates (themes/minimal/templates)
    minimal_dir = APP_DIR / "themes" / "minimal" / "templates"
    if minimal_dir.is_dir():
        loaders.append(FileSystemLoader(str(minimal_dir)))

    # Support plugin-specific template directories inside app/plugins/<plugin_id>/templates/
    plugins_dir = APP_DIR / "plugins"
    if plugins_dir.is_dir():
        for p in sorted(plugins_dir.iterdir()):
            if p.is_dir() and not p.name.startswith(("_", ".")) and not p.name.endswith(("_to_del", "_bak")):
                p_tpl = p / "templates"
                if p_tpl.is_dir():
                    loaders.append(FileSystemLoader(str(p_tpl)))

    base_dir = APP_DIR / "templates"
    if base_dir.is_dir():
        loaders.append(FileSystemLoader(str(base_dir)))

    templates.env.loader = ChoiceLoader(loaders)


def build_templates(directory: str = "app/templates") -> Jinja2Templates:
    target_dir = str(APP_DIR / "templates")
    templates = Jinja2Templates(directory=target_dir)
    # THEME LOADER: caută întâi în `app/themes/<active>/templates`, apoi în `app/templates/`.
    _apply_theme_loader(templates, force=True)
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
    templates.env.globals["is_plugin_active"] = is_plugin_active

    def _safe_translation_lookup(data: dict | None, path: str, default: str = "") -> str:
        if not isinstance(data, dict):
            return default or path
        if path in data and isinstance(data[path], str) and data[path].strip():
            return data[path].strip()
        cur = data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default or path
            cur = cur[part]
        if isinstance(cur, str) and cur.strip():
            return cur.strip()
        return default or path

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
    templates.env.globals["is_plugin_active"] = is_plugin_active
    ctx = dict(context)
    ctx.setdefault("request", request)
    root = public_site_origin(request)
    brand = get_site_brand_image_path()
    bpath = brand if brand.startswith("/") else f"/{brand}"
    ctx.setdefault("site_brand_image_abs", f"{root}{bpath}")
    fav = get_site_favicon_path()
    fpath = fav if fav.startswith("/") else f"/{fav}"
    ctx.setdefault("site_favicon_rel", fpath)
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
    ctx.setdefault("twitter_site", get_twitter_site())
    available_locales = get_available_locales()
    ctx.setdefault("available_locales", available_locales)
    fixed_nav_posts = []
    for item in get_nav_fixed_post_links(locale=locale):
        if item.get("label") or item.get("url") or item.get("slug"):
            fixed_nav_posts.append(item)
    ctx.setdefault("nav_fixed_post_link", fixed_nav_posts[0] if fixed_nav_posts else None)
    ctx.setdefault("fixed_nav_posts", fixed_nav_posts)
    from app.utils.auth import get_current_user_from_request, user_has_role, get_user_roles
    current_user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
    if current_user:
        try:
            setattr(current_user, "roles_list", get_user_roles(current_user))
        except Exception:
            pass
    ctx["current_user"] = current_user
    ctx["user"] = current_user
    ctx["has_role"] = lambda *roles: user_has_role(current_user, *roles) if current_user else False
    ctx["locale"] = locale
    ctx["site_display_name"] = lambda: get_site_display_name(locale)
    ctx["site_tagline"] = lambda: get_site_tagline(locale)
    ctx["translations"] = getattr(request.state, "translations", None) or get_translations(locale)
    ctx["lang"] = locale
    from app.core.i18n import get_plugin_translation
    ctx["t"] = lambda key: get_translation(locale, key)
    ctx["t_shop"] = lambda key, default_val="": get_plugin_translation("minishop", locale, key, default_val)
    ctx["t_plugin"] = lambda plugin_id, key, default_val="": get_plugin_translation(plugin_id, locale, key, default_val)
    ctx["current_locale"] = locale
    cur_path = request.url.path if hasattr(request, "url") else "/"
    cur_query = ("?" + request.url.query) if hasattr(request, "url") and request.url.query else ""
    ctx.setdefault("current_path", cur_path)
    ctx.setdefault("current_path_with_query", f"{cur_path}{cur_query}")
    ctx.setdefault("common", {"langSelector": "Limbă" if locale == "ro" else "Language"})
    ctx.setdefault("year", datetime.now(timezone.utc).year)
    ctx.setdefault("footer", {"company": get_site_display_name(locale)})
    ctx.setdefault("total_pages", 1)
    ctx.setdefault("current_page", 1)
    ctx.setdefault("pages", [1])
    ctx.setdefault("get_available_locales", get_available_locales)
    ctx.setdefault("get_translations", get_translations)
    ctx.setdefault("translate", lambda key: get_translation(locale, key))
    ctx["is_plugin_active"] = is_plugin_active
    # NU seta cheia "active_theme" aici: ar umbri globalul Jinja `active_theme()` (funcție),
    # iar în template ar apărea TypeError: 'str' object is not callable.
    ctx.setdefault("active_theme_slug", get_active_theme() or "minimal")
    ctx.setdefault("og_image_width", None)
    ctx.setdefault("og_image_height", None)
    ctx.setdefault("og_image_type", None)
    from app.core.template_hooks import (
        render_admin_navs,
        render_admin_top_bars,
        render_footer_col1,
        render_footer_col2,
        render_footer_col3,
        render_footer_col4,
        render_footer_bottom,
        render_navbar_links,
    )
    ctx.setdefault("plugin_area_admin_nav", render_admin_navs(request))
    ctx.setdefault("plugin_area_admin_top_bar", render_admin_top_bars(request))
    ctx.setdefault("plugin_area_navbar_links", render_navbar_links(request))
    ctx.setdefault("plugin_area_footer_col1", render_footer_col1(request))
    ctx.setdefault("plugin_area_footer_col2", render_footer_col2(request))
    ctx.setdefault("plugin_area_footer_col3", render_footer_col3(request))
    ctx.setdefault("plugin_area_footer_col4", render_footer_col4(request))
    ctx.setdefault("plugin_area_footer_bottom", render_footer_bottom(request))
    ctx.setdefault("editor_document_base", f"{root.rstrip('/')}/")
    response = templates.TemplateResponse(request, name, ctx, status_code=status_code)
    set_locale_cookie(response, locale)
    return response
