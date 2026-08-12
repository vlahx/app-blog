from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from app.core.i18n import get_translation, get_translations, resolve_locale, set_locale_cookie
from app.core.templates import build_templates, render_template
from app.core.translation_db import DEFAULT_TRANSLATION_CATALOG, list_translation_catalog, set_translation_entry
from app.models.db_models import AppSetting
from app.utils.db import SessionLocal


def test_resolve_locale_from_query_param() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "query_string": b"lang=en"})

    assert resolve_locale(request) == "en"


def test_get_translation_falls_back_to_default_locale() -> None:
    assert get_translation("ro", "ui.admin") == "Admin"
    assert get_translation("en", "ui.admin") == "Admin"


def test_resolve_locale_from_cookie() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", b"blog_locale=en")]})

    assert resolve_locale(request) == "en"


def test_set_locale_cookie_writes_cookie() -> None:
    response = Response()
    set_locale_cookie(response, "en")

    assert "blog_locale=en" in response.headers["set-cookie"]


def test_falls_back_to_english_source_for_missing_locale_entries() -> None:
    set_translation_entry("en", "tests.fallback.label", "English source value")

    assert get_translation("fr", "tests.fallback.label") == "English source value"


def test_get_translations_includes_english_fallback_values() -> None:
    set_translation_entry("en", "tests.fallback.group.title", "English group title")

    translations = get_translations("fr")

    assert translations["tests"]["fallback"]["group"]["title"] == "English group title"


def test_translation_catalog_uses_english_as_source_for_admin_ui() -> None:
    set_translation_entry("en", "ui.admin", "Admin")

    catalog = list_translation_catalog("fr")

    assert any(item["key"] == "ui.admin" and item["source_value"] == "Admin" for item in catalog)


def test_default_translation_catalog_contains_english_source_values() -> None:
    assert DEFAULT_TRANSLATION_CATALOG["ui.admin"] == "Admin"
    assert DEFAULT_TRANSLATION_CATALOG["blog.empty.title"] == "No posts yet"


def test_render_template_uses_request_locale_for_site_title_and_tagline() -> None:
    with SessionLocal() as db:
        for key in ("SITE_DISPLAY_NAME_ro", "SITE_TAGLINE_ro"):
            db.query(AppSetting).filter(AppSetting.key == key).delete(synchronize_session=False)
        db.add_all(
            [
                AppSetting(key="SITE_DISPLAY_NAME_ro", value="Titlu RO"),
                AppSetting(key="SITE_TAGLINE_ro", value="Tagline RO"),
            ]
        )
        db.commit()

    templates = build_templates("templates")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
    )
    request.state.locale = "ro"
    request.state.translations = {}

    response = render_template(
        templates,
        request=request,
        name="blog/index.html",
        context={"posts": [], "categories": [], "title": "Test"},
    )

    html = response.body.decode("utf-8")
    assert "Titlu RO" in html
    assert "Tagline RO" in html
