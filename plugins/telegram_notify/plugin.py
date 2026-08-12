from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.events import subscribe
from app.core.plugin_manager import get_plugin_setting
from app.utils.telegram_notify import send_telegram_message

logger = logging.getLogger(__name__)


def register(_app: FastAPI, plugin_id: str = "telegram_notify") -> None:
    def on_newsletter_subscribed(email: str, is_new: bool = False, **kwargs: object) -> None:
        if not is_new:
            return

        # Preferă setările per-plugin; dacă lipsesc, send_telegram_message folosește app_settings/.env
        bot_token = get_plugin_setting(plugin_id, "bot_token").strip() or None
        chat_id = get_plugin_setting(plugin_id, "chat_id").strip() or None
        text = f"Newsletter — abonare nouă:\n{email}"
        if not send_telegram_message(text, bot_token=bot_token, chat_id=chat_id):
            logger.debug("telegram_notify: mesajul nu s-a trimis (config sau API)")

    subscribe("newsletter.subscribed", on_newsletter_subscribed)
