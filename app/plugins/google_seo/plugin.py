from __future__ import annotations
import json
import logging
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_DIR, get_public_site_url, post_public_path, get_site_display_name
from app.core.i18n import resolve_locale
from app.utils.db import SessionLocal
from app.core.template_hooks import (
    register_admin_nav,
    register_admin_top_bar,
    register_post_header_meta,
)
from app.models.db_models import PluginSetting as PluginSettingModel

logger = logging.getLogger("google_seo_plugin")

SETTINGS_KEY_CREDENTIALS = "service_account_json"
SETTINGS_KEY_AUTO_INDEX = "auto_indexing_enabled"

def get_plugin_setting(db: Session, key: str, default: str = "") -> str:
    stmt = select(PluginSettingModel).where(
        (PluginSettingModel.plugin_id == "google_seo") & (PluginSettingModel.key == key)
    )
    row = db.execute(stmt).scalars().first()
    return row.value if row else default

def set_plugin_setting(db: Session, key: str, value: str) -> None:
    stmt = select(PluginSettingModel).where(
        (PluginSettingModel.plugin_id == "google_seo") & (PluginSettingModel.key == key)
    )
    row = db.execute(stmt).scalars().first()
    now = datetime.now(timezone.utc)
    if row:
        row.value = value
        row.updated_at = now
    else:
        row = PluginSettingModel(
            plugin_id="google_seo",
            key=key,
            value=value,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    db.commit()

def publish_url_to_google(url: str, notification_type: str = "URL_UPDATED", credentials_json: str = "") -> dict[str, Any]:
    if not credentials_json:
        with SessionLocal() as db:
            credentials_json = get_plugin_setting(db, SETTINGS_KEY_CREDENTIALS)

    if not credentials_json.strip():
        return {"success": False, "error": "Cheia Google Service Account JSON lipsește."}

    try:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            import sys
            import subprocess
            logger.info("Auto-installing missing google-api-python-client dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "google-api-python-client", "google-auth"])
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

        info = json.loads(credentials_json)
        scopes = ["https://www.googleapis.com/auth/indexing"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        service = build("indexing", "v3", credentials=creds)

        body = {
            "url": url,
            "type": notification_type
        }
        response = service.urlNotifications().publish(body=body).execute()
        return {"success": True, "response": response}
    except Exception as e:
        err_msg = str(e)
        if "SERVICE_DISABLED" in err_msg or "indexing.googleapis.com" in err_msg:
            proj_id = ""
            if "project=" in err_msg:
                try:
                    proj_id = err_msg.split("project=")[1].split()[0].rstrip(".").rstrip('"').rstrip("'")
                except Exception:
                    pass
            act_url = f"https://console.developers.google.com/apis/api/indexing.googleapis.com/overview?project={proj_id}" if proj_id else "https://console.developers.google.com/apis/api/indexing.googleapis.com/overview"
            err_msg = f"Web Search Indexing API nu este activată în Google Cloud Console pentru proiectul tău! Accesează linkul următor pentru a o activa cu 1-click: {act_url}"
        logger.error(f"Google Indexing API error: {e}")
        return {"success": False, "error": err_msg}


def register(app: FastAPI, plugin_id: str = "google_seo") -> None:
    plugin_templates_dir = Path(__file__).resolve().parent / "templates"
    templates = Jinja2Templates(directory=str(plugin_templates_dir))

    @app.get("/admin/plugins/google_seo", response_class=HTMLResponse)
    async def google_seo_admin_page(request: Request):
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=303)

        with SessionLocal() as db:
            creds_json = get_plugin_setting(db, SETTINGS_KEY_CREDENTIALS)
            auto_idx = get_plugin_setting(db, SETTINGS_KEY_AUTO_INDEX, "1")

        is_configured = False
        sa_email = ""
        if creds_json.strip():
            try:
                info = json.loads(creds_json)
                sa_email = info.get("client_email", "")
                is_configured = bool(sa_email)
            except Exception:
                is_configured = False

        from app.core.templates import render_template
        return render_template(
            templates,
            request=request,
            name="admin/google_seo.html",
            context={
                "title": "Google SEO & Indexing API",
                "is_configured": is_configured,
                "sa_email": sa_email,
                "creds_json": creds_json,
                "auto_idx": auto_idx == "1",
                "site_url": get_public_site_url() or str(request.base_url).rstrip("/"),
            }
        )

    @app.post("/admin/plugins/google_seo/save")
    async def google_seo_save_settings(
        request: Request,
        credentials_json: str = Form(""),
        auto_indexing: str = Form("off")
    ):
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=303)

        with SessionLocal() as db:
            set_plugin_setting(db, SETTINGS_KEY_CREDENTIALS, credentials_json.strip())
            set_plugin_setting(db, SETTINGS_KEY_AUTO_INDEX, "1" if auto_indexing in ("on", "1", "true") else "0")

        return RedirectResponse(url="/admin/plugins/google_seo?saved=1", status_code=303)

    @app.post("/admin/plugins/google_seo/index-now")
    async def google_seo_index_now(
        request: Request,
        target_url: str = Form("")
    ):
        user_id = request.session.get("user_id")
        if not user_id:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

        url = target_url.strip()
        if not url:
            return JSONResponse({"success": False, "error": "URL missing"}, status_code=400)

        res = publish_url_to_google(url, "URL_UPDATED")
        return JSONResponse(res)

    def _admin_nav_google_seo(_request: Request) -> str:
        return '<a href="/admin/plugins/google_seo" class="nav-link text-white fw-semibold d-flex align-items-center gap-2 px-3 py-2 rounded"><span>🚀</span><span>Google SEO</span></a>'

    def _admin_top_bar_google_seo(_request: Request) -> str:
        return '<a href="/admin/plugins/google_seo" class="btn btn-sm btn-outline-success fw-bold rounded-pill px-3 shadow-sm d-inline-flex align-items-center gap-1"><span>🚀</span><span>Google SEO</span></a>'

    register_admin_nav(_admin_nav_google_seo, order=25)
    register_admin_top_bar(_admin_top_bar_google_seo, order=25)

    def _header_meta_seo(_post: object, _request: Request) -> str:
        slug = getattr(_post, "slug", "")
        title = getattr(_post, "title", "") or slug
        excerpt = getattr(_post, "excerpt", "") or ""
        keywords = getattr(_post, "meta_keywords", "") or ""
        hero_img = getattr(_post, "hero_image_url", "") or getattr(_post, "image_url", "") or ""
        author = getattr(_post, "author_name", "") or "Admin"
        pub_at = getattr(_post, "published_at", None)

        base_url = get_public_site_url() or str(_request.base_url).rstrip("/")
        full_url = f"{base_url}{post_public_path(slug)}"
        site_name = get_site_display_name() or "Camionagiul.club"

        tags = []
        if keywords.strip():
            tags.append(f'<meta name="keywords" content="{escape(keywords.strip())}" />')

        pub_iso = pub_at.isoformat() if pub_at else datetime.now(timezone.utc).isoformat()
        
        schema_data = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": full_url
            },
            "headline": title,
            "description": excerpt,
            "url": full_url,
            "datePublished": pub_iso,
            "dateModified": pub_iso,
            "author": {
                "@type": "Person",
                "name": author
            },
            "publisher": {
                "@type": "Organization",
                "name": site_name
            }
        }
        if keywords.strip():
            schema_data["keywords"] = keywords.strip()
        if hero_img:
            if hero_img.startswith(("http://", "https://")):
                schema_data["image"] = hero_img
            else:
                pth = hero_img if hero_img.startswith("/") else f"/{hero_img}"
                schema_data["image"] = f"{base_url}{pth}"

        tags.append(f'<script type="application/ld+json">{json.dumps(schema_data, ensure_ascii=False)}</script>')
        return "\n".join(tags)

    register_post_header_meta(_header_meta_seo, order=5)

    try:
        from app.core import events
        def _on_post_published(**kwargs):
            url = kwargs.get("post_url") or kwargs.get("url")
            if not url:
                slug = kwargs.get("slug")
                if slug:
                    base = get_public_site_url()
                    url = f"{base}{post_public_path(slug)}" if base else post_public_path(slug)

            if url:
                with SessionLocal() as db:
                    auto_idx = get_plugin_setting(db, SETTINGS_KEY_AUTO_INDEX, "1")
                if auto_idx == "1":
                    print(f"⚡ [Google SEO Plugin] Auto-submitting URL to Google Indexing API: {url}", flush=True)
                    res = publish_url_to_google(url, "URL_UPDATED")
                    print(f"✅ [Google SEO Plugin] Result for {url}: {res}", flush=True)

        events.subscribe("blog.post_published", _on_post_published)
    except Exception as ex:
        logger.warning(f"Could not subscribe to post_published event: {ex}")
