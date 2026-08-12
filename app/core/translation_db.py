from __future__ import annotations

from typing import Any

from app.models.db_models import TranslationEntry, TranslationLocale
from app.utils.db import SessionLocal, init_db

DEFAULT_LOCALE = "en"
SUPPORTED_DEFAULT_LOCALES = {"en", "ro"}
DEFAULT_TRANSLATION_CATALOG: dict[str, str] = {
    "blog.empty.title": "No posts yet",
    "blog.empty.description": "The first post will appear soon. In the meantime, you can explore the available categories.",
    "blog.empty.cta": "Create the first post",
    "blog.notFound.message": "There is no article with the slug:",
    "blog.notFound.backToBlog": "Back to blog",
    "ui.admin": "Admin",
    "site.title": "Blog",
    "site.tagline": "A simple blog",
    "home.categories.title": "Explore by category",
    "home.categories.all": "All",
    "home.badges.python": "Python",
    "home.badges.highways": "Highways",
    "home.badges.europe": "Europe",
    "home.badges.technical": "Technical",
    "home.badges.programming": "Programming",
    "home.postCard.defaultExcerpt": "Discover the full story of this road journey...",
    "home.postCard.readMore": "Read the story →",
    "home.breadcrumb.home": "Home",
    "home.postPage.backToBlog": "Back to Journal",
    "home.postPage.byRoad": "Written on the road",
    "footer.quickNav": "Quick Navigation",
    "footer.home": "🏠 Home",
    "footer.categories": "📁 Categories",
    "footer.newsletter": "📧 Newsletter",
    "footer.admin": "⚡ Admin Panel",
    "footer.aboutBlog": "About Blog",
    "footer.theme": "Theme",
    "footer.description": "Road journal, articles, and community stories.",
    "footer.rights": "All rights reserved.",
    "footer.communityTitle": "Community",
    "footer.communityText": "Road journal, technical articles, and stories from the community of drivers and enthusiasts.",
    "shop.navLink": "🛒 Shop",
    "shop.title": "🛒 Club Store",
    "shop.subtitle": "Exclusive products, road equipment, and digital plugins for the community.",
    "shop.allProducts": "All Products",
    "shop.digitalBadge": "⚡ Digital Product",
    "shop.physicalBadge": "📦 Physical Delivery",
    "shop.viewDetails": "View Details →",
    "shop.finalPrice": "Final Price",
    "shop.buyNow": "Buy Now",
    "shop.reviewsTitle": "Reviews & Ratings",
    "shop.addReview": "Add a Review",
    "shop.orderSuccess": "Order Successfully Placed!",
    "shop.downloadFile": "Download File",
}


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    return locale.strip().lower()


def _flatten_translation_rows(rows: list[TranslationEntry]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for row in rows:
        if not row.key:
            continue
        parts = row.key.split(".")
        cur = data
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = row.value
    return data


def _merge_translation_maps(locale_data: dict[str, Any], fallback_data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(set(locale_data) | set(fallback_data)):
        locale_value = locale_data.get(key)
        fallback_value = fallback_data.get(key)
        if isinstance(locale_value, dict) and isinstance(fallback_value, dict):
            result[key] = _merge_translation_maps(locale_value, fallback_value)
        elif isinstance(locale_value, str) and locale_value.strip():
            result[key] = locale_value
        elif fallback_value is not None:
            result[key] = fallback_value
        elif key in locale_data:
            result[key] = locale_value
    return result


def get_available_locales() -> list[dict[str, Any]]:
    init_db()
    with SessionLocal() as db:
        rows = db.query(TranslationLocale).filter(TranslationLocale.enabled.is_(True)).order_by(TranslationLocale.is_default.desc(), TranslationLocale.code.asc()).all()
        return [
            {"code": row.code, "name": row.name or row.code, "enabled": row.enabled, "is_default": row.is_default}
            for row in rows
        ]


def list_translation_catalog(locale: str, *, source_locale: str = DEFAULT_LOCALE) -> list[dict[str, Any]]:
    locale = _normalize_locale(locale)
    source_locale = _normalize_locale(source_locale)
    init_db()
    with SessionLocal() as db:
        source_rows = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == source_locale)
            .order_by(TranslationEntry.key)
            .all()
        )
        target_rows = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale)
            .order_by(TranslationEntry.key)
            .all()
        ) if locale != source_locale else source_rows

    target_lookup = {row.key: row.value for row in target_rows if row.key}
    return [
        {
            "key": row.key,
            "source_value": row.value or "",
            "target_value": target_lookup.get(row.key, ""),
        }
        for row in source_rows
        if row.key
    ]


def seed_default_translation_catalog() -> None:
    init_db()
    with SessionLocal() as db:
        for key, value in DEFAULT_TRANSLATION_CATALOG.items():
            row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == DEFAULT_LOCALE, TranslationEntry.key == key)
                .first()
            )
            if row is None:
                db.add(TranslationEntry(locale_code=DEFAULT_LOCALE, key=key, value=value))
            elif not (row.value or "").strip():
                row.value = value
        db.commit()


def ensure_default_locale() -> None:
    init_db()
    with SessionLocal() as db:
        has_default = db.query(TranslationLocale).filter(TranslationLocale.is_default.is_(True)).first()
        for code in SUPPORTED_DEFAULT_LOCALES:
            row = db.query(TranslationLocale).filter(TranslationLocale.code == code).first()
            if row is None:
                is_def = not has_default and (code == "ro")
                db.add(TranslationLocale(code=code, name="English" if code == "en" else "Română", enabled=True, is_default=is_def))
            else:
                row.enabled = True
        if not has_default:
            ro_row = db.query(TranslationLocale).filter(TranslationLocale.code == "ro").first()
            if ro_row:
                ro_row.is_default = True
            else:
                any_row = db.query(TranslationLocale).first()
                if any_row:
                    any_row.is_default = True
        db.commit()
    seed_default_translation_catalog()


def get_translation_from_db(locale: str, key: str, default: str | None = None) -> str:
    locale = _normalize_locale(locale)
    init_db()
    with SessionLocal() as db:
        row = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
            .first()
        )
        if row is not None and (row.value or "").strip():
            return row.value.strip()
    return ""


def get_translations_from_db(locale: str) -> dict[str, Any]:
    locale = _normalize_locale(locale)
    init_db()
    with SessionLocal() as db:
        rows = db.query(TranslationEntry).filter(TranslationEntry.locale_code == locale).all()
    data = _flatten_translation_rows(rows)
    return data


def set_translation_entry(locale: str, key: str, value: str) -> None:
    locale = _normalize_locale(locale)
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.commit()
        row = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
            .first()
        )
        if row is None:
            db.add(TranslationEntry(locale_code=locale, key=key, value=value or ""))
        else:
            row.value = value or ""
        db.commit()


def set_translation_values(locale: str, values: dict[str, str]) -> None:
    locale = _normalize_locale(locale)
    init_db()
    if not values:
        return
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.commit()

        for key, value in values.items():
            if not key:
                continue
            row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
                .first()
            )
            if row is None:
                db.add(TranslationEntry(locale_code=locale, key=key, value=value or ""))
            else:
                row.value = value or ""
        db.commit()


def seed_locale_from_default(locale: str) -> None:
    locale = _normalize_locale(locale)
    if locale == DEFAULT_LOCALE:
        return
    init_db()
    with SessionLocal() as db:
        locale_row = db.query(TranslationLocale).filter(TranslationLocale.code == locale).first()
        if locale_row is None:
            db.add(TranslationLocale(code=locale, name=locale.upper(), enabled=True, is_default=False))
            db.flush()

        source_rows = db.query(TranslationEntry).filter(TranslationEntry.locale_code == DEFAULT_LOCALE).all()
        for source_row in source_rows:
            target_row = (
                db.query(TranslationEntry)
                .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == source_row.key)
                .first()
            )
            if target_row is None:
                db.add(TranslationEntry(locale_code=locale, key=source_row.key, value=source_row.value or ""))
            elif not (target_row.value or "").strip():
                target_row.value = source_row.value or ""
        db.commit()


def delete_translation_entry(locale: str, key: str) -> None:
    locale = _normalize_locale(locale)
    init_db()
    with SessionLocal() as db:
        row = (
            db.query(TranslationEntry)
            .filter(TranslationEntry.locale_code == locale, TranslationEntry.key == key)
            .first()
        )
        if row is not None:
            db.delete(row)
            db.commit()


def delete_locale(locale_code: str) -> bool:
    locale = _normalize_locale(locale_code)
    if locale == DEFAULT_LOCALE:
        return False
    init_db()
    with SessionLocal() as db:
        db.query(TranslationEntry).filter(TranslationEntry.locale_code == locale).delete()
        db.query(TranslationLocale).filter(TranslationLocale.code == locale).delete()
        db.commit()
    return True


def set_default_locale(locale_code: str) -> None:
    locale = _normalize_locale(locale_code)
    init_db()
    with SessionLocal() as db:
        rows = db.query(TranslationLocale).all()
        for r in rows:
            r.is_default = (r.code == locale)
        db.commit()