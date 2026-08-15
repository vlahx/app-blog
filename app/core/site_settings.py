from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS_PATH = _PROJECT_ROOT / "db" / "site_settings.json"

_STR_KEYS = frozenset(
    {
        "SITE_DISPLAY_NAME",
        "SITE_TAGLINE",
        "SITE_FAVICON_PATH",
        "SITE_BRAND_IMAGE_PATH",
        "OG_CARD_IMAGE_PATH",
        "SITE_NAV_ICON_PATH",
        "NAV_FIXED_POST_SLUG",
        "NAV_FIXED_POST_LABEL",
        "ACTIVE_THEME",
        "STATIC_NAV_LINKS",
    }
)
_INT_KEYS = frozenset(
    {
        "POST_IMAGE_MAX_EDGE",
        "POST_IMAGE_OUTPUT_WIDTH",
        "POST_IMAGE_OUTPUT_HEIGHT",
    }
)
_BOOL_KEYS = frozenset({"POST_IMAGE_CROP_OG", "FLAT_POST_URLS"})


def read_settings() -> dict[str, Any]:
    data = {}
    if _SETTINGS_PATH.is_file():
        try:
            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    data = raw
        except (OSError, json.JSONDecodeError):
            pass

    if "STATIC_NAV_LINKS" not in data:
        try:
            from app.utils.db import SessionLocal
            from app.models.db_models import AppSetting
            with SessionLocal() as db:
                row = db.query(AppSetting).filter(AppSetting.key == "STATIC_NAV_LINKS").first()
                if row and row.value:
                    data["STATIC_NAV_LINKS"] = json.loads(row.value)
        except Exception:
            pass

    return data


def write_settings(updates: dict[str, Any]) -> None:
    """Actualizează doar chei permise; șir gol → elimină cheia (revine la .env)."""
    cur = read_settings()
    for key, val in updates.items():
        if key == "STATIC_NAV_LINKS":
            if val is None:
                cur.pop(key, None)
            elif isinstance(val, list):
                cleaned = []
                seen: set[str] = set()
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    slug = str(item.get("slug") or item.get("value") or "").strip()
                    label = str(item.get("label") or item.get("fixed_label") or item.get("title") or slug).strip()
                    if not slug:
                        continue
                    lowered = slug.lower()
                    if lowered in seen:
                        continue
                    seen.add(lowered)
                    cleaned.append({"slug": slug, "label": label, "fixed_label": label})
                if cleaned:
                    cur[key] = cleaned
                else:
                    cur.pop(key, None)
            else:
                cur.pop(key, None)
            cur.pop("NAV_FIXED_POST_SLUG", None)
            cur.pop("NAV_FIXED_POST_LABEL", None)
        elif key in _STR_KEYS:
            if val is None or str(val).strip() == "":
                cur.pop(key, None)
            else:
                cur[key] = str(val).strip()
        elif key in _INT_KEYS:
            if val is None or val == "":
                cur.pop(key, None)
            else:
                try:
                    n = int(val)
                    if n > 0:
                        cur[key] = n
                    else:
                        cur.pop(key, None)
                except (TypeError, ValueError):
                    pass
        elif key in _BOOL_KEYS:
            if isinstance(val, str):
                cur[key] = val.strip().lower() in ("1", "true", "yes", "on")
            else:
                cur[key] = bool(val)

    for k in list(cur.keys()):
        if k not in _STR_KEYS | _INT_KEYS | _BOOL_KEYS:
            del cur[k]

    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        if "STATIC_NAV_LINKS" in updates:
            from app.core.config import invalidate_nav_fixed_post_links_cache
            invalidate_nav_fixed_post_links_cache()
    except Exception:
        pass

    try:
        from app.utils.db import SessionLocal
        from app.models.db_models import AppSetting
        with SessionLocal() as db:
            row = db.query(AppSetting).filter(AppSetting.key == "STATIC_NAV_LINKS").first()
            val_str = json.dumps(cur.get("STATIC_NAV_LINKS", [])) if "STATIC_NAV_LINKS" in cur else ""
            if row:
                row.value = val_str
            else:
                db.add(AppSetting(key="STATIC_NAV_LINKS", value=val_str))
            db.commit()
    except Exception:
        pass
