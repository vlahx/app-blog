from __future__ import annotations

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import FastAPI, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.core.config import post_public_path
from app.models.db_models import Post
from app.utils.db import SessionLocal
from app.utils.open_graph import public_site_origin
from app.core.plugin_manager import is_plugin_enabled


def _lastmod_utc(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _url_entry(loc: str, lastmod: str, priority: str = "0.8") -> str:
    loc_e = escape(loc)
    lines = ["  <url>", f"    <loc>{loc_e}</loc>"]
    if lastmod:
        lines.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
    lines.append(f"    <priority>{priority}</priority>")
    lines.append("  </url>")
    return "\n".join(lines)


def register(app: FastAPI) -> None:
    @app.get("/sitemap.xml", include_in_schema=False)
    @app.get("/sitemap.xml/", include_in_schema=False)
    @app.get("/sitemap", include_in_schema=False)
    async def sitemap_xml(request: Request):
        origin = public_site_origin(request).rstrip("/")
        entries: list[str] = []

        home_mod = ""
        with SessionLocal() as db:
            latest = db.execute(
                select(Post.updated_at)
                .where(Post.draft.is_(False))
                .order_by(Post.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest is not None:
                home_mod = _lastmod_utc(latest)

        # 1. Homepage
        entries.append(_url_entry(f"{origin}/", home_mod, priority="1.0"))

        # 2. Magazin (Dacă modulul Minishop este activat)
        if is_plugin_enabled("minishop"):
            entries.append(_url_entry(f"{origin}/shop", home_mod, priority="0.9"))
            try:
                from plugins.minishop.db import list_shop_products
                products = list_shop_products(active_only=True)
                for p in products:
                    prod_loc = f"{origin}/shop/product/{p['slug']}"
                    p_date = p.get("created_at")
                    p_lastmod = _lastmod_utc(p_date) if isinstance(p_date, datetime) else ""
                    entries.append(_url_entry(prod_loc, p_lastmod, priority="0.8"))
            except Exception as ex:
                pass

        # 3. Articole Blog
        with SessionLocal() as db:
            posts = db.execute(
                select(Post)
                .where(Post.draft.is_(False))
                .order_by(Post.updated_at.desc())
            ).scalars().all()

        for p in posts:
            path = post_public_path(p.slug)
            loc = f"{origin}{path}" if path.startswith("/") else f"{origin}/{path}"
            entries.append(_url_entry(loc, _lastmod_utc(p.updated_at), priority="0.8"))

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(entries)
            + "\n</urlset>"
        )
        return Response(
            content=body.strip(),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
