from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from app.core.translation_db import (
    DEFAULT_LOCALE,
    get_available_locales,
    get_translation_from_db,
    get_translations_from_db,
    ensure_default_locale,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"
TRANSLATIONS_DIR = PROJECT_ROOT / "translations"
SUPPORTED_LOCALES = {"en", "ro"}
DEFAULT_FALLBACK_LOCALE = DEFAULT_LOCALE


def get_supported_locales() -> set[str]:
    locales = get_available_locales()
    if locales:
        return {row["code"] for row in locales}
    return set(SUPPORTED_LOCALES)


def _load_locale_data(locale: str) -> dict[str, Any]:
    normalized = (locale or DEFAULT_LOCALE).strip().lower()
    return get_translations_from_db(normalized)


def resolve_locale(request: Request | None = None, fallback: str = DEFAULT_LOCALE) -> str:
    if request is None:
        return fallback

    lang = None
    try:
        query_params = request.query_params
    except (AttributeError, KeyError, RuntimeError):
        query_params = None
    if query_params:
        lang = query_params.get("lang", "").strip().lower()

    headers = None
    if hasattr(request, "scope") and isinstance(getattr(request, "scope", None), dict) and "headers" in request.scope:
        try:
            headers = request.headers
        except (KeyError, RuntimeError, AttributeError):
            headers = None
    if not lang and headers is not None:
        lang = headers.get("x-locale", "").strip().lower()

    cookies = None
    if hasattr(request, "scope") and isinstance(getattr(request, "scope", None), dict) and "headers" in request.scope:
        try:
            cookies = request.cookies
        except (KeyError, RuntimeError, AttributeError):
            cookies = None
    if not lang and cookies is not None:
        lang = cookies.get("blog_locale", "").strip().lower()

    if not lang and headers is not None:
        accept_lang = headers.get("accept-language", "").strip().lower()
        if accept_lang:
            supported = get_supported_locales()
            for part in accept_lang.split(","):
                code_sub = part.split(";")[0].strip().split("-")[0]
                if code_sub in supported:
                    lang = code_sub
                    break

    if not lang:
        app = getattr(request, "app", None)
        lang = getattr(getattr(app, "state", None), "default_locale", None)
    if not lang:
        lang = fallback
    if lang not in get_supported_locales():
        lang = fallback
    return lang


def set_locale_cookie(response: Response, locale: str, *, path: str = "/", max_age: int = 60 * 60 * 24 * 365) -> None:
    normalized = locale if locale in get_supported_locales() else DEFAULT_LOCALE
    response.set_cookie(
        key="blog_locale",
        value=normalized,
        path=path,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=False,
    )


def get_translation(locale: str, key: str) -> str:
    normalized = (locale or DEFAULT_LOCALE).strip().lower()
    if normalized in get_supported_locales():
        val = get_translation_from_db(normalized, key, )
        if val:
            return val
        if normalized != DEFAULT_LOCALE:
            fb = get_translation_from_db(DEFAULT_LOCALE, key, )
            if fb:
                return fb
    data = _load_locale_data(normalized)
    value: Any = data
    for part in key.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return key
    if isinstance(value, str) and value:
        return value
    return key
_COMPOSED_TRANSLATIONS_CACHE: dict[str, dict[str, Any]] = {}


def clear_i18n_cache() -> None:
    global _COMPOSED_TRANSLATIONS_CACHE
    _COMPOSED_TRANSLATIONS_CACHE.clear()


def get_translations(locale: str) -> dict[str, Any]:
    global _COMPOSED_TRANSLATIONS_CACHE
    normalized = (locale or DEFAULT_LOCALE).strip().lower()
    if normalized not in get_supported_locales():
        normalized = DEFAULT_LOCALE

    if normalized in _COMPOSED_TRANSLATIONS_CACHE:
        return _COMPOSED_TRANSLATIONS_CACHE[normalized]

    data = _load_locale_data(normalized)
    if normalized == DEFAULT_LOCALE:
        _COMPOSED_TRANSLATIONS_CACHE[normalized] = data
        return data

    fallback = _load_locale_data(DEFAULT_LOCALE)

    def _merge(a: Any, b: Any) -> Any:
        if isinstance(a, dict) and isinstance(b, dict):
            merged = dict(b)
            for key, value in a.items():
                if key not in merged:
                    merged[key] = value
                else:
                    merged[key] = _merge(value, merged[key])
            return merged
        return a if a is not None else b

    res = _merge(data, fallback)
    _COMPOSED_TRANSLATIONS_CACHE[normalized] = res
    return res


def get_translation_value(locale: str, key: str) -> str:
    return get_translation(locale, key)


def build_context(locale: str, **extra: Any) -> dict[str, Any]:
    translations = get_translations(locale)
    return {"locale": locale, "translations": translations, **extra}


def get_site_default_locale() -> str:
    try:
        from app.core.translation_db import get_available_locales
        locales = get_available_locales()
        for loc in locales:
            if loc.get("is_default"):
                return loc["code"]
    except Exception:
        pass
    return "ro"


def get_plugin_translation(plugin_id: str, locale: str, key: str, default_val: str = "") -> str:
    def_locale = get_site_default_locale()
    norm_locale = (locale or def_locale).strip().lower()
    
    db_val = get_translation_from_db(norm_locale, f"plugins.{plugin_id}.{key}")
    if db_val:
        return db_val
    if norm_locale != def_locale:
        db_fb = get_translation_from_db(def_locale, f"plugins.{plugin_id}.{key}")
        if db_fb:
            return db_fb

    p_dir = APP_DIR / "plugins" / plugin_id / "locales"

    target_file = p_dir / f"{norm_locale}.json"
    if target_file.is_file():
        try:
            with target_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    def_file = p_dir / f"{def_locale}.json"
    if def_file.is_file():
        try:
            with def_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    ro_file = p_dir / "ro.json"
    if ro_file.is_file():
        try:
            with ro_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return data[key]
        except Exception:
            pass

    return default_val or key