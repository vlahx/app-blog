from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import (
    is_static_page_slug,
    ROOT_SLUG_BLOCKLIST,
    get_flat_post_urls,
    get_site_display_name,
    get_site_tagline,
    post_public_path,
)
from app.core.template_hooks import render_post_article_footers, render_post_header_metas
from app.core.templates import render_template
from app.core.posts_db import get_post, list_categories, list_posts, post_preview_image_src
from app.utils.db import get_db
from app.utils.open_graph import (
    og_image_meta_for_url,
    public_site_origin,
    resolve_og_image_url,
    truncate_og_description,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>", re.S)


def _plain_text(s: str) -> str:
    return _HTML_TAG_RE.sub("", s or "").strip()


def _og_description_for_post(post, locale: str | None = None) -> str:
    """Descriere pentru og:description — Facebook/X ignoră meta gol; evită doar titlul dacă există text."""
    ex = _plain_text(post.excerpt)
    if ex:
        base = truncate_og_description(ex)
    else:
        body = _plain_text(post.content_html)
        if body:
            base = truncate_og_description(body)
        else:
            base = truncate_og_description(post.title)
    if len(base) < 96:
        brand = get_site_display_name(locale)
        suffix = f" — {brand}: jurnal de drum, comunitate, episoade noi."
        if brand not in base:
            base = truncate_og_description(f"{base}{suffix}")
    return base


def serve_blog_post(
    request: Request,
    templates: Jinja2Templates,
    db: Session,
    slug: str,
) -> HTMLResponse:
    """
    Pagină articol sau 404. Respectă ROOT_SLUG_BLOCKLIST (fără query DB).
    """
    if slug in ROOT_SLUG_BLOCKLIST:
        post = None
    else:
        locale = getattr(request.state, "locale", None)
        post = get_post(db, slug, locale=locale)
    if not post:
        base = public_site_origin(request)
        return render_template(
            templates,
            request=request,
            name="blog/404.html",
            context={
                "slug": slug,
                "title": "Nu există",
                "seo_title": "Nu există articolul",
                "seo_description": truncate_og_description(
                    "Pagina cerută nu există pe blog."
                ),
                "meta_description": truncate_og_description(
                    "Pagina cerută nu există pe blog."
                ),
                "seo_canonical": f"{base}{request.url.path}",
                "seo_type": "website",
            },
            status_code=404,
        )
    base = public_site_origin(request)
    preview_src = post_preview_image_src(post)
    seo_image, seo_image_is_card = resolve_og_image_url(base, preview_src)
    path = post_public_path(post.slug)
    canonical_url = f"{base}{path}"
    locale = getattr(request.state, "locale", None)
    og_desc = _og_description_for_post(post, locale)
    og_img_meta = og_image_meta_for_url(base, seo_image, is_card=seo_image_is_card)
    return render_template(
        templates,
        request=request,
        name="blog/post.html",
        context={
            "post": post,
            "title": post.title,
            "meta_description": og_desc,
            "seo_title": post.title,
            "seo_description": og_desc,
            "seo_canonical": canonical_url,
            "seo_type": "article",
            "seo_image": seo_image,
            "seo_image_is_card": seo_image_is_card,
            "seo_image_alt": post.title,
            "share_url": canonical_url,
            "post_article_footer_html": render_post_article_footers(post, request),
            "post_header_meta_html": render_post_header_metas(post, request),
            **og_img_meta,
        },
    )


def build_blog_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["blog"])

    def _render_blog_index(request: Request, db, current_category: str | None = None, current_author: str | None = None):
        base = public_site_origin(request)
        locale = getattr(request.state, "locale", None)
        posts = list_posts(db, category=current_category, author=current_author, locale=locale)
        categories = list_categories(db)
        from app.core.posts_db import list_authors_with_posts
        authors = list_authors_with_posts(db)
        seo_image, seo_image_is_card = resolve_og_image_url(base, None)
        seo_image_alt = get_site_display_name(locale)
        og_img_meta = og_image_meta_for_url(base, seo_image, is_card=seo_image_is_card)
        canonical = f"{base}/"
        locale = getattr(request.state, "locale", None)
        tagline = get_site_tagline(locale)
        idx_desc = truncate_og_description(tagline) if tagline else ""
        return render_template(
            templates,
            request=request,
            name="blog/index.html",
            context={
                "posts": posts,
                "categories": categories,
                "current_category": current_category,
                "current_author": current_author,
                "authors": authors,
                "title": get_site_display_name(locale),
                "seo_title": get_site_display_name(locale),
                "seo_description": idx_desc,
                "meta_description": idx_desc,
                "seo_canonical": canonical,
                "seo_type": "website",
                "seo_image": seo_image,
                "seo_image_is_card": seo_image_is_card,
                "seo_image_alt": seo_image_alt,
                **og_img_meta,
            },
        )

    @router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def blog_home(request: Request, db=Depends(get_db)):
        from app.core.config import get_homepage_mode
        hp_mode = get_homepage_mode()

        if hp_mode.startswith("page:"):
            target_slug = hp_mode.split(":", 1)[1].strip()
            if target_slug:
                post = get_post(db, target_slug)
                if post:
                    return serve_blog_post(request, templates, db, target_slug)

        if hp_mode == "shop":
            from app.core.templates import is_plugin_active
            if is_plugin_active("minishop"):
                return RedirectResponse(url="/shop", status_code=302)

        category = request.query_params.get("category", "").strip() or None
        author = request.query_params.get("author", "").strip() or None
        return _render_blog_index(request, db, current_category=category, current_author=author)

    @router.api_route("/blog", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def blog_index_feed(request: Request, db=Depends(get_db)):
        category = request.query_params.get("category", "").strip() or None
        author = request.query_params.get("author", "").strip() or None
        return _render_blog_index(request, db, current_category=category, current_author=author)

    @router.api_route("/blog/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def blog_index_feed_trailing_slash(request: Request, db=Depends(get_db)):
        category = request.query_params.get("category", "").strip() or None
        author = request.query_params.get("author", "").strip() or None
        return _render_blog_index(request, db, current_category=category, current_author=author)

    @router.api_route("/blog/{slug}", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def blog_post(request: Request, slug: str, db=Depends(get_db)):
        locale = getattr(request.state, "locale", None)
        post = get_post(db, slug, locale=locale)
        if not post:
            return serve_blog_post(request, templates, db, slug)
        if get_flat_post_urls() or is_static_page_slug(slug):
            return RedirectResponse(url=post_public_path(slug), status_code=301)
        return serve_blog_post(request, templates, db, slug)

    @router.post("/lang", response_class=RedirectResponse)
    async def switch_language(request: Request):
        form = await request.form()
        target_locale = str(form.get("locale") or "ro").strip().lower()
        next_url = str(form.get("next") or "/").strip()
        if not next_url.startswith("/") or next_url.startswith("//") or "\\" in next_url:
            next_url = "/"
        response = RedirectResponse(url=next_url, status_code=303)
        from app.core.i18n import set_locale_cookie
        set_locale_cookie(response, target_locale)
        return response

    return router
