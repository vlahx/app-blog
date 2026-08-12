from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping

from app.core.config import TELEGRAM_AUTH_TTL_SECONDS, get_telegram_bot_token

TELEGRAM_FIELDS = {"id", "first_name", "last_name", "username", "photo_url", "auth_date"}


def _data_check_string(params: Mapping[str, str]) -> str:
    # Telegram docs: sort by key and join as key=value separated by '\n', excluding non-Telegram payload keys (e.g. hash, next).
    items = [(k, str(v)) for k, v in params.items() if k in TELEGRAM_FIELDS]
    items.sort(key=lambda x: x[0])
    return "\n".join([f"{k}={v}" for k, v in items])


def verify_telegram_login(params: Mapping[str, str]) -> bool:
    """
    Verifies Telegram Login Widget payload.
    Expected fields include: id, first_name, last_name, username, photo_url, auth_date, hash.
    """
    token = get_telegram_bot_token()
    if not token:
        return False
    received_hash = (params.get("hash") or "").strip()
    if not received_hash:
        return False

    data_check = _data_check_string(params)
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    computed = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()

    if computed != received_hash:
        return False

    auth_date_raw = (params.get("auth_date") or "").strip()
    try:
        auth_date = int(auth_date_raw)
    except ValueError:
        return False

    now = int(time.time())
    if abs(now - auth_date) > TELEGRAM_AUTH_TTL_SECONDS:
        return False

    return True
