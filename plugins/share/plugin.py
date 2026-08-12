from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import post_public_path
from app.core.template_hooks import register_post_article_footer
from app.utils.open_graph import public_site_origin

_ASSET_DIR = Path(__file__).resolve().parent


def _share_url(post: Any, request: Request) -> str:
    base = public_site_origin(request).rstrip("/")
    slug = getattr(post, "slug", "")
    if hasattr(post, "product_type") or hasattr(post, "price"):
        return f"{base}/shop/product/{slug}"
    try:
        path = post_public_path(slug)
        if path.startswith("/"):
            return f"{base}{path}"
        return f"{base}/{path}"
    except Exception:
        return f"{base}/{slug}"


def register(app: FastAPI) -> None:
    app.mount(
        "/static/plugin-assets/share",
        StaticFiles(directory=str(_ASSET_DIR)),
        name="share_plugin_static",
    )

    def _article_footer_share(post: Any, request: Request) -> str:
        try:
            share_url = _share_url(post, request)
            title = getattr(post, "title", "") or ""
            title_e = escape(title)
            url_e = escape(share_url)
            return f'''<h5 class="card-title mb-4 d-flex align-items-center">
          <svg class="me-2" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/>
          </svg>
          Distribuie
        </h5>
        <p class="text-secondary mb-4">Împărtășește cu prietenii tăi!</p>
        <textarea id="share-url-field" class="share-offscreen" readonly tabindex="-1" aria-hidden="true">{url_e}</textarea>
        <textarea id="share-title-field" class="share-offscreen" readonly tabindex="-1" aria-hidden="true">{title_e}</textarea>
        <div class="share-actions d-flex flex-wrap gap-2">
          <button type="button" class="btn btn-outline-primary share-btn d-flex align-items-center gap-2" id="share-native">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/>
            </svg>
            Distribuie
          </button>
          <a class="btn btn-outline-success share-btn d-flex align-items-center gap-2" id="share-wa" target="_blank" rel="noopener noreferrer" href="#">WhatsApp</a>
          <a class="btn btn-outline-primary share-btn d-flex align-items-center gap-2" id="share-fb" target="_blank" rel="noopener noreferrer" href="#">Facebook</a>
          <a class="btn btn-outline-info share-btn d-flex align-items-center gap-2" id="share-x" target="_blank" rel="noopener noreferrer" href="#">X</a>
          <a class="btn btn-outline-secondary share-btn d-flex align-items-center gap-2" id="share-mail" href="#">Email</a>
          <button type="button" class="btn btn-outline-secondary share-btn d-flex align-items-center gap-2" id="share-copy">Copiază link</button>
        </div>
        <p class="share-toast muted d-none mt-3 p-2 rounded" id="share-toast"></p>
        <script src="/static/plugin-assets/share/share.js"></script>'''
        except Exception:
            return ""

    register_post_article_footer(_article_footer_share, order=10)
