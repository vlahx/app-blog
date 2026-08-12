from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_telegram_bot_token, get_telegram_notify_chat_id

logger = logging.getLogger(__name__)


def send_telegram_message(
    text: str,
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    timeout_sec: float = 12.0,
) -> bool:
    """
    Trimite mesaj text prin Bot API.
    Parametrii `bot_token` / `chat_id` opționali (ex. din setări per-plugin); altfel folosește
    get_telegram_bot_token / get_telegram_notify_chat_id (app_settings sau .env).
    """
    token = (bot_token or get_telegram_bot_token()).strip()
    chat_raw = (chat_id or get_telegram_notify_chat_id()).strip()
    if not token or not chat_raw:
        logger.debug("telegram_notify: lipsește token sau chat_id; skip")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": chat_raw, "text": text, "disable_web_page_preview": "true"}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        ok = bool(data.get("ok"))
        if not ok:
            logger.warning("telegram_notify: API răspuns non-ok: %s", raw[:500])
        return ok
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace") if e.fp else ""
        logger.warning("telegram_notify: HTTP %s %s", e.code, err[:500])
        return False
    except urllib.error.URLError as e:
        logger.warning("telegram_notify: rețea %s", e)
        return False
