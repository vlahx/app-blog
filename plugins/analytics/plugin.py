from __future__ import annotations

import logging
import re
from html import escape

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.i18n import get_translation, resolve_locale
from app.core.template_hooks import register_post_header_meta
from app.core.templates import build_templates
from app.routers.admin import login_required
from app.utils.db import get_db

from plugins.analytics.db import get_all_analytics, get_article_analytics, record_ping

logger = logging.getLogger(__name__)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.S)


def _strip_tags(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def register(app: FastAPI, plugin_id: str = "analytics") -> None:
    @app.post("/api/analytics/ping", include_in_schema=False)
    async def analytics_ping(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"ok": False}, status_code=400)

        slug = str(data.get("slug") or "").strip()
        seconds = int(data.get("seconds") or 0)
        is_new_view = bool(data.get("is_new_view"))

        seconds = max(0, min(30, seconds))

        if slug:
            record_ping(slug, seconds=seconds, is_new_view=is_new_view)

        return JSONResponse({"ok": True})

    @app.get("/admin/analytics", response_class=HTMLResponse)
    @login_required
    async def admin_analytics(request: Request, db: Session = Depends(get_db)):
        from app.core.config import PROJECT_ROOT
        from app.core.posts_db import list_posts
        from app.core.templates import render_template

        posts = list_posts(db, include_drafts=True)
        stats = get_all_analytics()
        stats_by_slug = {s["slug"]: s for s in stats}

        items = []
        total_views = 0
        total_seconds_all = 0

        for p in posts:
            s = stats_by_slug.get(p.slug, {"views": 0, "total_seconds": 0, "avg_seconds": 0})
            v = s["views"]
            tot_sec = s["total_seconds"]
            avg_sec = s["avg_seconds"]

            total_views += v
            total_seconds_all += tot_sec

            words = len(_strip_tags(p.content_html).split())
            est_min = max(1, round(words / 200))

            items.append({
                "title": p.title,
                "slug": p.slug,
                "type": "post",
                "url": f"/blog/{p.slug}",
                "edit_url": f"/admin/edit/{p.slug}",
                "draft": p.draft,
                "views": v,
                "total_seconds": tot_sec,
                "avg_seconds": avg_sec,
                "est_min": est_min,
                "info": f"/{p.slug} • {words} cuvinte",
            })

        # Include Shop Products if minishop plugin is active
        try:
            from app.core.plugin_manager import is_plugin_enabled
            if is_plugin_enabled("minishop"):
                from plugins.minishop.db import list_shop_products
                products = list_shop_products(active_only=False)
                for prod in products:
                    pslug = prod.get("slug") or ""
                    if not pslug:
                        continue
                    s = stats_by_slug.get(pslug, {"views": 0, "total_seconds": 0, "avg_seconds": 0})
                    v = s["views"]
                    tot_sec = s["total_seconds"]
                    avg_sec = s["avg_seconds"]

                    total_views += v
                    total_seconds_all += tot_sec

                    price = prod.get("price", 0.0)
                    curr = prod.get("currency", "RON")

                    items.append({
                        "title": prod.get("title") or pslug,
                        "slug": pslug,
                        "type": "product",
                        "url": f"/shop/product/{pslug}",
                        "edit_url": "/admin/minishop",
                        "draft": not bool(prod.get("is_active")),
                        "views": v,
                        "total_seconds": tot_sec,
                        "avg_seconds": avg_sec,
                        "est_min": 1,
                        "info": f"/{pslug} • {price:.2f} {curr}",
                    })
        except Exception as e:
            logger.warning(f"Error loading shop products in analytics: {e}")

        items.sort(key=lambda x: x["views"], reverse=True)

        rows_html = ""
        for item in items:
            avg_m = item["avg_seconds"] // 60
            avg_s = item["avg_seconds"] % 60
            avg_str = f"{avg_m}m {avg_s}s" if avg_m > 0 else f"{avg_s}s"

            tot_m = item["total_seconds"] // 60
            tot_s = item["total_seconds"] % 60
            tot_str = f"{tot_m}m {tot_s}s" if tot_m > 0 else f"{tot_s}s"

            if item["type"] == "product":
                type_badge = '<span class="badge bg-success me-2">📦 Produs</span>'
                status_badge = '<span class="badge bg-secondary ms-2">Inactiv</span>' if item["draft"] else ""
            else:
                type_badge = '<span class="badge bg-primary me-2">📝 Blog</span>'
                status_badge = '<span class="badge bg-warning text-dark ms-2">Draft</span>' if item["draft"] else ""

            rows_html += f'''
          <tr>
            <td>
              {type_badge}
              <a href="{item['url']}" target="_blank" class="fw-bold text-decoration-none text-body">{escape(item['title'])}</a>
              {status_badge}
              <div class="small text-secondary">{item['info']}</div>
            </td>
            <td class="text-center"><span class="badge bg-primary fs-6">{item['views']}</span></td>
            <td class="text-center fw-semibold">{avg_str}</td>
            <td class="text-center text-secondary">{tot_str}</td>
            <td class="text-center"><span class="badge bg-secondary">{item['est_min']} min</span></td>
            <td class="text-end">
              <a href="{item['edit_url']}" class="btn btn-sm btn-outline-primary">Editează</a>
            </td>
          </tr>'''

        tot_min_str = f"{round(total_seconds_all / 60, 1)} min"

        html_content = f'''{{% extends "base.html" %}}
{{% block content %}}
<div class="container-fluid px-4 py-4">
  <div class="d-flex justify-content-between align-items-center mb-4">
    <div>
      <h1 class="h3 fw-bold mb-1">📊 Analiză & Statistici Vizualizări</h1>
      <p class="text-secondary mb-0">Contorizare în timp real pentru articole, audiență și timpul de lectură.</p>
    </div>
    <a href="/admin" class="btn btn-outline-secondary">← Înapoi în Admin</a>
  </div>

  <div class="row g-3 mb-4">
    <div class="col-md-4">
      <div class="card shadow-sm border-0 bg-primary bg-opacity-10 h-100">
        <div class="card-body p-4 text-center">
          <div class="display-6 fw-bold text-primary">{total_views}</div>
          <div class="text-secondary small fw-semibold mt-1">Total Vizualizări Articole</div>
        </div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card shadow-sm border-0 bg-success bg-opacity-10 h-100">
        <div class="card-body p-4 text-center">
          <div class="display-6 fw-bold text-success">{tot_min_str}</div>
          <div class="text-secondary small fw-semibold mt-1">Timp Total Lectură Cititori</div>
        </div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card shadow-sm border-0 bg-info bg-opacity-10 h-100">
        <div class="card-body p-4 text-center">
          <div class="display-6 fw-bold text-info">{len(posts)}</div>
          <div class="text-secondary small fw-semibold mt-1">Total Articole Monitorizate</div>
        </div>
      </div>
    </div>
  </div>

  <div class="card shadow-sm border-0">
    <div class="card-header bg-body-tertiary fw-bold py-3">
      🏆 Clasament Articole după Vizualizări & Lectură
    </div>
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Articol</th>
            <th class="text-center">Vizualizări</th>
            <th class="text-center">Timp Mediu / Cititor</th>
            <th class="text-center">Timp Total Lectură</th>
            <th class="text-center">Est. Lectură</th>
            <th class="text-end">Acțiuni</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>
</div>
{{% endblock %}}'''

        tpl_path = PROJECT_ROOT / "templates" / "admin" / "analytics.html"
        tpl_path.parent.mkdir(parents=True, exist_ok=True)
        tpl_path.write_text(html_content, encoding="utf-8")

        templates = build_templates()
        return render_template(templates, request=request, name="admin/analytics.html", context={"title": "Analytics"}, status_code=200)

    def _header_meta_analytics(_post: object, _request: Request) -> str:
        slug = getattr(_post, "slug", "")
        if not slug:
            return ""

        loc = getattr(_request.state, "locale", None) or resolve_locale(_request)

        content_html = getattr(_post, "content_html", "") or ""
        words = len(_strip_tags(content_html).split())
        est_min = max(1, round(words / 200))

        stats = get_article_analytics(slug)
        views = stats["views"]

        views_label = get_translation(loc, "analytics.views") or "vizualizări"
        read_label = get_translation(loc, "analytics.read_time") or "min citire"

        return f'''<span class="badge bg-secondary bg-opacity-75 d-inline-flex align-items-center gap-1" title="Număr vizualizări"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>{views} {views_label}</span> <span class="badge bg-secondary bg-opacity-75 d-inline-flex align-items-center gap-1" title="Timp estimat de lectură"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>{est_min} {read_label}</span><script>(function(){{const slug="{slug}";const sessionKey="viewed_"+slug;const isNewView=!sessionStorage.getItem(sessionKey);if(isNewView){{sessionStorage.setItem(sessionKey,"1");}}function ping(seconds,isNew){{try{{navigator.sendBeacon("/api/analytics/ping",JSON.stringify({{slug:slug,seconds:seconds,is_new_view:isNew}}));}}catch(e){{fetch("/api/analytics/ping",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{slug:slug,seconds:seconds,is_new_view:isNew}})}});}}}}ping(0,isNewView);let activeSeconds=0;setInterval(function(){{if(!document.hidden){{activeSeconds+=15;ping(15,false);}}}},15000);}})();</script>'''

    register_post_header_meta(_header_meta_analytics, order=10)
