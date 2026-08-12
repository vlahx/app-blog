from __future__ import annotations

import logging
import re
from html import escape
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import PROJECT_ROOT, get_site_display_name
from app.core.events import publish, subscribe
from app.core.i18n import get_translation, resolve_locale
from app.core.plugin_manager import get_plugin_setting
from app.core.template_hooks import register_post_article_footer
from app.utils.email_notify import (
    send_newsletter_post_to_subscribers,
    try_send_newsletter_subscribe_notice,
)
from app.utils.newsletter_subscribers import append_subscriber_if_new, list_subscribers_detailed
from app.utils.newsletter_tokens import make_unsubscribe_token, public_unsubscribe_url

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logger = logging.getLogger(__name__)


def _normalize_email(raw: str) -> str:
    return " ".join(raw.split()).strip().lower()


def _jinja_env() -> Environment:
    tpl_dir = PROJECT_ROOT / "templates" / "email"
    return Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def register(app: FastAPI, plugin_id: str = "newsletter") -> None:
    @app.get("/newsletter", include_in_schema=False)
    async def newsletter_get(request: Request, ok: str | None = None, err: str | None = None):
        return RedirectResponse(url="/?newsletter_ok=1" if ok == "1" else "/", status_code=303)

    @app.get("/newsletter/unsubscribe", include_in_schema=False)
    async def newsletter_unsubscribe_get(request: Request, t: str | None = None):
        from app.utils.newsletter_subscribers import remove_subscriber
        from app.utils.newsletter_tokens import parse_unsubscribe_token

        if not t or not str(t).strip():
            q = quote("Link de dezabonare invalid.", safe="")
            return RedirectResponse(url=f"/?newsletter_err={q}", status_code=303)
        email = parse_unsubscribe_token(str(t).strip())
        if not email:
            q = quote("Link de dezabonare expirat sau invalid.", safe="")
            return RedirectResponse(url=f"/?newsletter_err={q}", status_code=303)
        remove_subscriber(email)
        return RedirectResponse(url="/?newsletter_unsub=1", status_code=303)

    @app.post("/newsletter/subscribe", include_in_schema=False)
    async def newsletter_subscribe(request: Request):
        form = await request.form()
        referer = request.headers.get("referer") or "/"
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "json" in request.headers.get("accept", "").lower()
        
        loc = getattr(request.state, "locale", None) or resolve_locale(request)
        success_msg = get_translation(loc, "newsletter.success") or "Mulțumim pentru abonare! Te rugăm să verifici și folderul Spam pentru e-mailurile viitoare."
        already_msg = get_translation(loc, "newsletter.already_subscribed") or "Această adresă de e-mail este deja abonată la newsletter."
        err_invalid = get_translation(loc, "newsletter.error") or "Adresă de e-mail invalidă."

        if (form.get("company") or "").strip():
            if is_ajax:
                return JSONResponse({"ok": True, "msg": success_msg, "is_new": True})
            return RedirectResponse(url=f"{referer}?newsletter_ok=1", status_code=303)

        raw = form.get("email")
        if raw is None:
            raw = ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        email = _normalize_email(str(raw))
        if not email or not _EMAIL_RE.match(email):
            if is_ajax:
                return JSONResponse({"ok": False, "err": err_invalid}, status_code=400)
            q = quote(err_invalid, safe="")
            return RedirectResponse(url=f"{referer}?newsletter_err={q}", status_code=303)

        is_new = append_subscriber_if_new(email, locale=loc)
        sep = "&" if "?" in referer else "?"

        if is_new:
            publish("newsletter.subscribed", email=email, is_new=True)
            try_send_newsletter_subscribe_notice(email)
            if is_ajax:
                return JSONResponse({"ok": True, "msg": success_msg, "is_new": True})
            return RedirectResponse(url=f"{referer}{sep}newsletter_ok=1", status_code=303)
        else:
            if is_ajax:
                return JSONResponse({"ok": True, "msg": already_msg, "is_new": False, "is_already": True})
            return RedirectResponse(url=f"{referer}{sep}newsletter_already=1", status_code=303)

    def on_blog_post_published(
        slug: str,
        title: str,
        excerpt: str,
        post_url: str,
        hero_image_abs: str | None = None,
        translations: dict[str, dict[str, str]] | None = None,
        **kwargs: object,
    ) -> None:
        opt = get_plugin_setting(plugin_id, "email_subscribers_on_publish").strip().lower()
        if opt in ("0", "false", "no", "off"):
            logger.info(
                "newsletter: skip broadcast pentru %r — „Notifică abonații la articol nou” e dezactivat în setări.",
                slug,
            )
            return
        subscribers = list_subscribers_detailed()
        if not subscribers:
            logger.info(
                "newsletter: skip broadcast pentru %r — nu există abonați.",
                slug,
            )
            return

        trans_map = translations or {}
        site_label = get_site_display_name()
        tpl = _jinja_env().get_template("newsletter_new_post.html")
        deliveries: list[tuple[str, str, str, str | None]] = []

        # Deliver custom localized email to each subscriber
        for sub in subscribers:
            em = sub["email"]
            sub_loc = sub.get("locale", "ro")
            
            # Lookup translation for subscriber's locale
            sub_trans = trans_map.get(sub_loc) or trans_map.get("ro") or {}
            sub_title = (sub_trans.get("title") or title or slug).strip()
            sub_excerpt = (sub_trans.get("excerpt") or excerpt or "").strip()

            tok = make_unsubscribe_token(em)
            unsub = public_unsubscribe_url(tok)
            html = tpl.render(
                site_label=site_label,
                post_title=sub_title,
                post_url=post_url,
                hero_abs=hero_image_abs or "",
                excerpt=sub_excerpt,
                unsub_url=unsub,
            )
            text_plain = sub_title + "\n\n" + sub_excerpt + "\n\nCitește: " + post_url + "\n\n—\nDezabonare: " + unsub + "\n"
            deliveries.append((em, text_plain, html, unsub))

        default_title = (title or slug).strip()
        main_subject = f"Articol nou: {default_title}"
        n = send_newsletter_post_to_subscribers(subject=main_subject, deliveries=deliveries)
        logger.info(
            "newsletter: după publicare %r — încercat broadcast către %s abonați; trimise cu succes: %s.",
            slug,
            len(subscribers),
            n,
        )

    subscribe("blog.post_published", on_blog_post_published)


    def render_newsletter_widget(post: object, request: Request) -> str:
        loc = getattr(request.state, "locale", None) or resolve_locale(request)
        from app.core.i18n import get_plugin_translation
        
        txt_title = get_plugin_translation("newsletter", loc, "subscribe_title", "📧 Abonare Newsletter")
        txt_desc = get_plugin_translation("newsletter", loc, "subscribe_desc", "Abonează-te pentru a primi ultimele articole direct pe e-mail.")
        txt_placeholder = get_plugin_translation("newsletter", loc, "email_placeholder", "Introdu adresa ta de e-mail...")
        txt_btn = get_plugin_translation("newsletter", loc, "subscribe_btn", "Abonează-te")

        html = [
            '<section id="newsletter-widget" class="mt-5 pt-2">',
            '  <div class="card border p-4 shadow-sm rounded-3">',
            '    <div class="row align-items-center">',
            '      <div class="col-md-6 mb-3 mb-md-0">',
            f'        <h4 class="fw-bold mb-1">{txt_title}</h4>',
            f'        <p class="text-secondary small mb-0">{txt_desc}</p>',
            '      </div>',
            '      <div class="col-md-6">',
            '        <form id="newsletter-form" onsubmit="submitNewsletter(event)">',
            '          <div class="input-group">',
            f'            <input type="email" id="newsletter-email" class="form-control" placeholder="{txt_placeholder}" required />',
            f'            <button type="submit" id="newsletter-btn" class="btn btn-primary fw-semibold px-4">{txt_btn}</button>',
            '          </div>',
            '          <div id="newsletter-status" class="small mt-2"></div>',
            '        </form>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</section>',
            '''
            <script>
            async function submitNewsletter(e) {
                e.preventDefault();
                const emailInput = document.getElementById('newsletter-email');
                const btn = document.getElementById('newsletter-btn');
                const status = document.getElementById('newsletter-status');

                const email = (emailInput.value || '').trim();
                if (!email) return;

                btn.disabled = true;
                status.innerHTML = '<span class="text-muted"><span class="spinner-border spinner-border-sm me-1"></span> Se trimite...</span>';

                const formData = new FormData();
                formData.append('email', email);

                try {
                    const res = await fetch('/newsletter/subscribe', {
                        method: 'POST',
                        body: formData,
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.ok) {
                        emailInput.value = '';
                        status.innerHTML = '<span class="text-success fw-semibold">✅ ' + (data.msg || 'Abonat cu succes!') + '</span>';
                    } else {
                        status.innerHTML = '<span class="text-danger fw-semibold">❌ ' + (data.err || 'Eroare la abonare') + '</span>';
                        btn.disabled = false;
                    }
                } catch(err) {
                    status.innerHTML = '<span class="text-danger fw-semibold">❌ Eroare de rețea.</span>';
                    btn.disabled = false;
                }
            }
            </script>
            '''
        ]
        return "\n".join(html)

    # register_post_article_footer(render_newsletter_widget) -- Newsletter is embedded in Footer Col 1
