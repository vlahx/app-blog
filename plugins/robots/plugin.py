from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from app.core.config import PROJECT_ROOT


def register(app: FastAPI) -> None:
    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt():
        path = PROJECT_ROOT / "robots.txt"
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
            except Exception:
                pass
        
        fallback = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\n\nSitemap: https://camionagiul.club/sitemap.xml\n"
        return PlainTextResponse(fallback, media_type="text/plain; charset=utf-8")
