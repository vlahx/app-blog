from __future__ import annotations

import logging
import os
import smtplib
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from html import escape
from typing import Any

from app.core import plugin_db_settings as legacy_plugin_settings
from app.core.config import SMTP_DEBUG, SMTP_SKIP_TLS_VERIFY, get_site_display_name
from app.core.plugin_manager import get_plugin_setting as get_for_plugin

logger = logging.getLogger(__name__)

_NEWSLETTER_ID = "newsletter"


def _chain(plugin_key: str, legacy_key: str, env_key: str) -> str:
    """Prioritate: setări plugin newsletter → app_settings vechi → .env."""
    v = get_for_plugin(_NEWSLETTER_ID, plugin_key).strip()
    if v:
        return v
    v = legacy_plugin_settings.get_plugin_setting(legacy_key).strip()
    if v:
        return v
    return os.environ.get(env_key, "").strip()


def _smtp_use_tls() -> bool:
    raw = _chain("smtp_use_tls", "smtp_use_tls", "NEWSLETTER_SMTP_STARTTLS")
    if raw:
        return raw.lower() not in ("0", "false", "no", "off")
    return True


def _smtp_skip_cert_verify() -> bool:
    if SMTP_SKIP_TLS_VERIFY:
        return True
    if os.environ.get("NEWSLETTER_SMTP_TLS_VERIFY", "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return True
    raw = get_for_plugin(_NEWSLETTER_ID, "smtp_allow_self_signed").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    return (
        legacy_plugin_settings.get_plugin_setting("smtp_allow_self_signed")
        .strip()
        .lower()
        in ("1", "true", "yes", "on")
    )


def _smtp_ssl_context() -> ssl.SSLContext:
    if _smtp_skip_cert_verify():
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()


def _newsletter_mail_params() -> dict[str, Any] | None:
    host = _chain("smtp_host", "smtp_host", "NEWSLETTER_SMTP_HOST")
    if not host:
        return None
    port_raw = _chain("smtp_port", "smtp_port", "NEWSLETTER_SMTP_PORT") or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = _chain("smtp_user", "smtp_user", "NEWSLETTER_SMTP_USER")
    password = _chain(
        "smtp_password",
        "smtp_password",
        "NEWSLETTER_SMTP_PASSWORD",
    )
    from_addr = (
        _chain("from_email", "newsletter_from_email", "NEWSLETTER_FROM_EMAIL")
        or user
    )
    if not from_addr:
        return None
    from_name = os.environ.get("NEWSLETTER_FROM_NAME", "").strip()
    use_tls = _smtp_use_tls()
    ctx = _smtp_ssl_context()
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
        "from_name": from_name,
        "use_tls": use_tls,
        "ctx": ctx,
    }


@contextmanager
def _smtp_connected(p: dict[str, Any]) -> Iterator[smtplib.SMTP | smtplib.SMTP_SSL]:
    host = p["host"]
    port = p["port"]
    user = p["user"]
    password = p["password"]
    use_tls = p["use_tls"]
    ctx = p["ctx"]

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as smtp:
                if SMTP_DEBUG:
                    smtp.set_debuglevel(1)
                if user and password:
                    smtp.login(user, password)
                yield smtp
        else:
            with smtplib.SMTP(host, port, timeout=60) as smtp:
                if SMTP_DEBUG:
                    smtp.set_debuglevel(1)
                smtp.ehlo()
                if use_tls:
                    smtp.starttls(context=ctx)
                    smtp.ehlo()
                if user and password:
                    smtp.login(user, password)
                yield smtp
    except (OSError, smtplib.SMTPException) as e:
        logger.warning(
            "email_notify: SMTP eșuat host=%s port=%s starttls=%s authed_user=%s err=%s",
            host,
            port,
            use_tls and port != 465,
            bool(user and password),
            e,
            exc_info=True,
        )
        if isinstance(e, smtplib.SMTPNotSupportedError) and not use_tls and port != 465:
            logger.warning(
                "email_notify: pe portul %s LOGIN necesită de obicei STARTTLS — "
                "bifează „STARTTLS (port 587)”. Pentru cert self-signed: "
                "„Certificat SMTP self-signed” sau NEWSLETTER_SMTP_TLS_VERIFY=false în .env.",
                port,
            )
        elif isinstance(e, ssl.SSLError):
            logger.warning(
                "email_notify: TLS/certificat — pentru mailserver intern/self-signed bifează "
                "„Certificat SMTP self-signed” în Admin → Newsletter sau pune "
                "NEWSLETTER_SMTP_TLS_VERIFY=false / SMTP_SKIP_TLS_VERIFY=true în .env."
            )
        raise


def _resolved_display_name(p: dict[str, Any]) -> str:
    """
    Ca pe s366: expeditorul e mereu „Nume <adresă>”, nu doar adresa brută —
    unele filtre notează mai bine mesajele cu display name.
    """
    for raw in (
        (p.get("from_name") or "").strip(),
        os.environ.get("NEWSLETTER_FROM_NAME", "").strip(),
    ):
        if raw:
            return raw
    return get_site_display_name()


def _format_from(p: dict[str, Any]) -> str:
    fn = _resolved_display_name(p)
    fa = p["from_addr"]
    return formataddr((fn, fa))


def _set_text_and_html_body(msg: EmailMessage, text_body: str) -> None:
    """multipart/alternative dintr-un singur corp text (HTML generat ca <pre>)."""
    text = text_body or ""
    msg.set_content(text, charset="utf-8")
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="ro"><head><meta charset="utf-8" /></head>\n'
        '<body style="font-family:system-ui,sans-serif;line-height:1.5;font-size:16px;">'
        f'<pre style="white-space:pre-wrap;font-family:inherit;margin:0">{escape(text)}</pre>'
        "</body></html>\n"
    )
    msg.add_alternative(html, subtype="html")


def _set_multipart_text_html(
    msg: EmailMessage, text_body: str, html_body: str
) -> None:
    """plain + HTML (ex. template newsletter articol)."""
    msg.set_content(text_body or "", charset="utf-8")
    msg.add_alternative(html_body or "", subtype="html")


def _list_unsubscribe_headers(msg: EmailMessage, unsubscribe_url: str) -> None:
    msg["List-Unsubscribe"] = f"<{unsubscribe_url.strip()}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"


def _ensure_core_headers(msg: EmailMessage) -> None:
    """
    Antete RFC minime. Fără Date / Message-ID, unele stack-uri (ex. amavis BAD-HEADER-0)
    resping mesajul chiar dacă SMTP client returnează OK.
    """
    if "Date" not in msg:
        msg["Date"] = formatdate(localtime=True)
    if "Message-ID" not in msg:
        _, addr = parseaddr(msg.get("From", ""))
        dom = addr.rsplit("@", 1)[-1] if "@" in addr else "localhost"
        msg["Message-ID"] = make_msgid(domain=dom)


def try_send_newsletter_subscribe_notice(subscriber_email: str) -> bool:
    """
    Notificare admin la abonare nouă (către notify_email).
    """
    p = _newsletter_mail_params()
    if not p:
        return False
    notify_to = _chain(
        "notify_email",
        "newsletter_notify_email",
        "NEWSLETTER_NOTIFY_EMAIL",
    )
    if not notify_to:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Newsletter — abonare nouă"
    msg["From"] = _format_from(p)
    msg["To"] = notify_to
    _set_text_and_html_body(msg, f"S-a abonat un cititor nou:\n{subscriber_email}\n")
    _ensure_core_headers(msg)

    try:
        with _smtp_connected(p) as smtp:
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        return False
    return True


def send_newsletter_post_to_subscribers(
    *,
    subject: str,
    deliveries: list[tuple[str, str, str, str | None]],
) -> int:
    """
    Trimite newsletter la articol nou.

    ``deliveries``: listă de ``(email_destinatar, text_plain, html, unsubscribe_url)``.
    ``unsubscribe_url`` poate fi absolut; dacă e setat, se adaugă antetele List-Unsubscribe.
    """
    if not deliveries:
        return 0
    p = _newsletter_mail_params()
    if not p:
        logger.warning("email_notify: broadcast articol — lipsește config SMTP sau From.")
        return 0

    sent = 0
    from_hdr = _format_from(p)
    try:
        with _smtp_connected(p) as smtp:
            for to_addr, text_body, html_body, unsub_url in deliveries:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = from_hdr
                msg["To"] = to_addr
                _set_multipart_text_html(msg, text_body, html_body)
                if unsub_url:
                    _list_unsubscribe_headers(msg, unsub_url)
                _ensure_core_headers(msg)
                try:
                    smtp.send_message(msg)
                    sent += 1
                except (OSError, smtplib.SMTPException) as one_err:
                    logger.warning(
                        "email_notify: trimitere eșuată către un destinatar: %s",
                        one_err,
                    )
    except (OSError, smtplib.SMTPException):
        return sent
    if sent:
        logger.info(
            "email_notify: broadcast articol — trimise %s/%s mesaje.",
            sent,
            len(deliveries),
        )
    return sent
