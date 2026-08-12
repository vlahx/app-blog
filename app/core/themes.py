from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_active_theme


@dataclass(frozen=True)
class ThemeInfo:
    slug: str
    name: str
    author: str
    version: str | None = None
    supports_color_scheme_toggle: bool = False


def _safe_theme_slug(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    ok = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if any(ch not in ok for ch in s):
        return None
    return s


def list_installed_themes() -> list[ThemeInfo]:
    """
    Detectează teme fie prin `themes/<slug>/templates/` (template override),
    fie prin `static/themes/<slug>/theme.css` (CSS-only).
    Include mereu "default".
    """
    out: list[ThemeInfo] = [load_theme_info("default")]
    base = PROJECT_ROOT / "themes"
    slugs: set[str] = set()

    if base.is_dir():
        for p in base.iterdir():
            if not p.is_dir():
                continue
            slug = _safe_theme_slug(p.name)
            if slug and slug != "default":
                slugs.add(slug)

    static_themes = PROJECT_ROOT / "static" / "themes"
    if static_themes.is_dir():
        for p in static_themes.iterdir():
            if not p.is_dir():
                continue
            slug = _safe_theme_slug(p.name)
            if slug and slug != "default":
                css = p / "theme.css"
                if css.is_file():
                    slugs.add(slug)

    for slug in sorted(slugs):
        out.append(load_theme_info(slug))
    return out


def load_theme_info(theme_slug: str) -> ThemeInfo:
    slug = _safe_theme_slug(theme_slug) or "default"
    manifest = PROJECT_ROOT / "themes" / slug / "theme.json"
    if not manifest.is_file():
        if slug == "default":
            # Default theme is always present even without a manifest.
            return ThemeInfo(
                slug="default",
                name="Default",
                author="Core",
                supports_color_scheme_toggle=True,
            )
        return ThemeInfo(slug=slug, name=slug, author="Unknown")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid manifest")
        name = str(data.get("name") or slug).strip() or slug
        author = str(data.get("author") or "Unknown").strip() or "Unknown"
        version = str(data.get("version")).strip() if data.get("version") else None
        supports = bool(
            data.get(
                "supports_color_scheme_toggle", True if slug == "default" else False
            )
        )
        return ThemeInfo(
            slug=slug,
            name=name,
            author=author,
            version=version,
            supports_color_scheme_toggle=supports,
        )
    except Exception:
        if slug == "default":
            return ThemeInfo(
                slug="default",
                name="Default",
                author="Core",
                supports_color_scheme_toggle=True,
            )
        return ThemeInfo(slug=slug, name=slug, author="Unknown")


def active_theme_info() -> ThemeInfo:
    return load_theme_info(get_active_theme())

