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
    if not _SETTINGS_PATH.is_file():
        return {}
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_settings(updates: dict[str, Any]) -> None:
    """Actualizează doar chei permise; șir gol → elimină cheia (revine la .env)."""
    cur = read_settings()
    for key, val in updates.items():
        if key in _STR_KEYS:
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

    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
