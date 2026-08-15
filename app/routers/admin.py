from __future__ import annotations

import logging
import pathlib
import shutil
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.db_models import Post as PostModel, User, Category

from app.core.config import (
    APP_DIR,
    ADMIN_ENABLE_CONTAINER_RESTART,
    PROJECT_ROOT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
    TELEGRAM_NOTIFY_CHAT_ID,
    get_active_theme,
    get_flat_post_urls,
    get_nav_fixed_post_label_setting,
    get_nav_fixed_post_links,
    get_nav_fixed_post_slug_setting,
    get_og_card_image_path,
    get_post_image_crop_og,
    get_post_image_max_edge,
    get_post_image_output_height,
    get_post_image_output_width,
    get_public_site_url,
    get_site_brand_image_path,
    get_site_display_name,
    get_site_favicon_path,
    get_site_nav_icon_path,
    get_site_tagline,
)
from app.core.posts_db import (
    create_category,
    delete_category_by_id,
    delete_post,
    get_post,
    list_categories,
    list_posts,
    save_post,
    slugify,
)
from app.core.site_settings import read_settings, write_settings
from app.utils.db import SessionLocal
from app.models.db_models import AppSetting
from app.core.plugin_db_settings import (
    get_plugin_setting,
    has_plugin_setting,
    set_plugin_settings,
)
from app.core.plugin_package import (
    extract_plugin_zip,
    list_installed_plugins,
    safe_plugin_id,
)
from app.core.process_restart import sigterm_self_after_delay
from app.core.site_uploads import unlink_site_upload_file
from app.core.templates import render_template
from app.core.themes import list_installed_themes, set_active_theme
from app.core.i18n import (
    DEFAULT_LOCALE,
    get_available_locales,
)
from app.utils.auth import login_required, role_required
from app.utils.db import get_db
from app.utils.post_image import process_post_upload

logger = logging.getLogger(__name__)

_IMAGE_SETTING_KEYS = frozenset(
    {
        "SITE_FAVICON_PATH",
        "SITE_BRAND_IMAGE_PATH",
        "OG_CARD_IMAGE_PATH",
        "SITE_NAV_ICON_PATH",
    }
)
_SITE_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg"})

_THEME_SLUG_OK = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_THEME_SLUG_RESERVED = frozenset({"default", "static", "themes", "core"})


def build_admin_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["admin"])

    @router.get("/admin", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_home(request: Request, db: Session = Depends(get_db)):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if user and user.role == "author":
            from app.models.db_models import Post
            from sqlalchemy import select
            stmt = select(Post).where(Post.author_id == user.id).order_by(Post.created_at.desc())
            posts = db.execute(stmt).scalars().all()
        else:
            posts = list_posts(db, include_drafts=True)
        categories = list_categories(db)
        return render_template(
            templates,
            request=request,
            name="admin/index.html",
            context={"posts": posts, "categories": categories, "title": "Admin Dashboard"},
        )

    @router.get("/admin/users", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_users(request: Request, msg: str | None = None, err: str | None = None, db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select
        users = db.execute(select(User).order_by(User.id.asc())).scalars().all()
        return render_template(
            templates,
            request=request,
            name="admin/users.html",
            context={"users": users, "msg": msg, "err": err, "title": "Utilizatori & Roluri"},
        )

    @router.post("/admin/users/{user_id}/role")
    @role_required("admin")
    async def admin_user_change_role(request: Request, user_id: int, role: str = Form(...), db: Session = Depends(get_db)):
        from app.models.db_models import User
        from sqlalchemy import select, func
        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)
        
        current_uid = getattr(request.state, "user_id", None)
        if current_uid and current_uid == user_id and role != "admin":
            admin_count = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar() or 0
            if admin_count <= 1:
                return RedirectResponse(url="/admin/users?err=Nu+îți+poți+revoca+singur+rolul+de+Admin!", status_code=303)
        
        form = await request.form()
        roles_selected = form.getlist("roles")
        if not roles_selected and form.get("role"):
            roles_selected = [form.get("role")]
            
        valid_roles = ("admin", "editor", "seller", "author", "reader", "pending")
        clean_roles = [r.strip().lower() for r in roles_selected if r.strip().lower() in valid_roles]
        if not clean_roles:
            clean_roles = ["reader"]
            
        final_role_str = ",".join(list(dict.fromkeys(clean_roles)))
        target_user.role = final_role_str
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Roluri+actualizate+cu+succes!", status_code=303)

    @router.post("/admin/users/{user_id}/delete")
    @role_required("admin")
    async def admin_user_delete(request: Request, user_id: int, db: Session = Depends(get_db)):
        from app.models.db_models import User, Post
        from sqlalchemy import select, func

        target_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not target_user:
            return RedirectResponse(url="/admin/users?err=Utilizatorul+nu+a+fost+găsit", status_code=303)

        current_uid = getattr(request.state, "user_id", None)
        if current_uid and current_uid == user_id:
            return RedirectResponse(url="/admin/users?err=Nu+îți+poți+șterge+propriul+cont!", status_code=303)

        if target_user.role == "admin":
            admin_count = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar() or 0
            if admin_count <= 1:
                return RedirectResponse(url="/admin/users?err=Nu+poți+șterge+singurul+Admin+din+sistem!", status_code=303)

        posts = db.execute(select(Post).where(Post.author_id == user_id)).scalars().all()
        for p in posts:
            p.author_id = None

        db.delete(target_user)
        db.commit()

        return RedirectResponse(url="/admin/users?msg=Utilizatorul+a+fost+șters+cu+succes!", status_code=303)

    def _editor_document_base(request: Request) -> str:
        base = get_public_site_url()
        if base:
            return f"{base.rstrip('/')}/"
        u = str(request.base_url).rstrip("/")
        return f"{u}/"

    @router.get("/admin/new", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_new(request: Request, db: Session = Depends(get_db)):
        categories = list_categories(db)
        locales = get_available_locales()
        return render_template(
            templates,
            request=request,
            name="admin/editor.html",
            context={
                "title": "Post nou",
                "post": None,
                "categories": categories,
                "locales": locales,
                "post_translations": {},
                "editor_document_base": _editor_document_base(request),
                "editor_nav_fixed": False,
                "editor_nav_fixed_label": "",
            },
        )

    @router.get("/admin/edit/{slug}", response_class=HTMLResponse)
    @role_required("admin", "editor", "author")
    async def admin_edit(request: Request, slug: str, db: Session = Depends(get_db)):
        post = get_post(db, slug)
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if post and user and user.role == "author" and getattr(post, "author_id", None) != user.id:
            return RedirectResponse(url="/admin?error=access_denied", status_code=302)
        if not post:
            return RedirectResponse(url="/admin/new", status_code=302)
        categories = list_categories(db)
        locales = get_available_locales()
        post_trans = {}
        with SessionLocal() as db_sess:
            stmt = select(PostModel).where(PostModel.slug == slug)
            row = db_sess.execute(stmt).scalars().first()
            if row:
                from app.core.posts_db import get_post_translations
                post_trans = get_post_translations(db_sess, row.id)
        cur_nav_links = [item.get("slug", "") for item in get_nav_fixed_post_links(locale=getattr(request.state, "locale", None))]
        editor_nav_fixed = post.slug in cur_nav_links
        editor_nav_fixed_label = ""
        for item in get_nav_fixed_post_links(locale=getattr(request.state, "locale", None)):
            if item.get("slug") == post.slug:
                editor_nav_fixed_label = item.get("label", "")
                break
        return render_template(
            templates,
            request=request,
            name="admin/editor.html",
            context={
                "title": f"Editează: {post.title}",
                "post": post,
                "categories": categories,
                "locales": locales,
                "post_translations": post_trans,
                "editor_document_base": _editor_document_base(request),
                "editor_nav_fixed": editor_nav_fixed,
                "editor_nav_fixed_label": editor_nav_fixed_label,
            },
        )

    @router.post("/admin/save")
    @role_required("admin", "editor", "author")
    async def admin_save(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        def _chk(key: str) -> bool:
            v = form.get(key)
            if v is None:
                return False
            if isinstance(v, str):
                return v.lower() in ("1", "true", "on", "yes")
            return bool(v)

        title = _txt("title")
        slug_in = _txt("slug")
        excerpt = _txt("excerpt")
        category = _txt("category")
        hero_image_url = _txt("hero_image_url")
        content_html = _txt("content_html")
        draft = _chk("draft")
        published_at_raw = _txt("published_at")
        editing_original_slug = _txt("editing_original_slug")
        nav_fixed = _chk("nav_fixed")
        nav_fixed_label = _txt("nav_fixed_label") or None

        locales = get_available_locales()
        translations_to_save = {}
        for loc in locales:
            code_loc = loc["code"]
            t_title = _txt(f"title_{code_loc}") or title
            t_excerpt = _txt(f"excerpt_{code_loc}") or excerpt
            t_content = _txt(f"content_html_{code_loc}") or content_html
            if t_title or t_content or t_excerpt:
                translations_to_save[code_loc] = {
                    "title": t_title,
                    "excerpt": t_excerpt,
                    "content_html": t_content,
                }

        primary_title = title
        if not primary_title and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_title = translations_to_save[first_code]["title"]

        primary_excerpt = excerpt
        if not primary_excerpt and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_excerpt = translations_to_save[first_code]["excerpt"]

        primary_content = content_html
        if not primary_content and translations_to_save:
            first_code = list(translations_to_save.keys())[0]
            primary_content = translations_to_save[first_code]["content_html"]

        slug_final = slugify(slug_in or primary_title)
        dt = None
        if published_at_raw:
            try:
                dt = datetime.fromisoformat(published_at_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                dt = None

        post = save_post(
            db,
            author_id=request.state.user_id,
            slug=slug_final,
            title=primary_title or "Post",
            excerpt=primary_excerpt,
            category=category or None,
            hero_image_url=hero_image_url or None,
            content_html=primary_content,
            draft=draft,
            published_at=dt,
        )

        if translations_to_save:
            from sqlalchemy import select
            from app.models.db_models import Post as PostModel
            from app.core.posts_db import save_post_translations
            row = db.execute(select(PostModel).where(PostModel.slug == post.slug)).scalars().first()
            if row:
                save_post_translations(db, row.id, translations_to_save)

        cur_links = read_settings().get("STATIC_NAV_LINKS") or []
        if not isinstance(cur_links, list):
            cur_links = []
        cleaned_links = []
        for item in cur_links:
            if isinstance(item, dict):
                slug = str(item.get("slug") or item.get("value") or "").strip()
                if slug:
                    cleaned_links.append({
                        "slug": slug,
                        "label": str(item.get("label") or item.get("fixed_label") or slug).strip(),
                        "fixed_label": str(item.get("fixed_label") or item.get("label") or slug).strip(),
                    })

        if nav_fixed:
            # Label-ul static este derivat din titlul postării în limba activă; câmpul vechi este doar fallback legacy.
            derived_label = post.title or slug_final
            new_item = {"slug": post.slug, "label": derived_label, "fixed_label": derived_label}
            filtered = [item for item in cleaned_links if str(item.get("slug") or "").strip() != post.slug]
            filtered.append(new_item)
            write_settings({"STATIC_NAV_LINKS": filtered})
        else:
            if editing_original_slug:
                filtered = [
                    item for item in cleaned_links
                    if str(item.get("slug") or "").strip() not in {editing_original_slug, post.slug}
                ]
                if filtered:
                    write_settings({"STATIC_NAV_LINKS": filtered})
                else:
                    write_settings({"STATIC_NAV_LINKS": []})

        from app.core.config import invalidate_nav_fixed_post_links_cache
        invalidate_nav_fixed_post_links_cache()



        return RedirectResponse(url="/admin?msg=Postare+salvată+cu+succes!", status_code=303)

    @router.get("/admin/categories", response_class=HTMLResponse)
    @router.get("/admin/categories/", response_class=HTMLResponse)
    @role_required("admin", "editor")
    async def admin_categories(request: Request, db: Session = Depends(get_db)):
        categories = list_categories(db)
        return render_template(
            templates,
            request=request,
            name="admin/categories.html",
            context={"title": "Categorii", "categories": categories},
        )

    @router.post("/admin/categories/save")
    @role_required("admin", "editor")
    async def admin_save_category(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        name = _txt("name")
        parent_ref = _txt("parent_id") or _txt("parent")
        if name:
            try:
                create_category(db, name=name, parent_slug=parent_ref or None)
            except ValueError:
                pass
        return RedirectResponse(url="/admin/categories", status_code=303)

    @router.post("/admin/categories/delete")
    @role_required("admin", "editor")
    async def admin_delete_category(request: Request, db: Session = Depends(get_db)):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        raw = _txt("category_id")
        if raw.isdigit():
            delete_category_by_id(db, int(raw))
        return RedirectResponse(url="/admin/categories", status_code=303)

    @router.get("/admin/settings", response_class=HTMLResponse)
    @router.get("/admin/settings/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_settings_page(request: Request):
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        active_locales = [loc for loc in get_available_locales() if loc.get("enabled")]
        with SessionLocal() as db:
            app_settings = {row.key: row.value for row in db.query(AppSetting).all() if row and row.key}
        localized_site_names = {
            loc["code"]: (app_settings.get(f"SITE_DISPLAY_NAME_{loc['code']}") or "").strip()
            for loc in active_locales
        }
        localized_site_taglines = {
            loc["code"]: (app_settings.get(f"SITE_TAGLINE_{loc['code']}") or "").strip()
            for loc in active_locales
        }
        return render_template(
            templates,
            request=request,
            name="admin/settings.html",
            context={
                "title": "Setări site",
                "settings_site_name": get_site_display_name(),
                "settings_site_tagline": get_site_tagline(),
                "active_locales": active_locales,
                "localized_site_names": localized_site_names,
                "localized_site_taglines": localized_site_taglines,
                "env_public_url": get_public_site_url(),
                "site_favicon_path": get_site_favicon_path(),
                "site_brand_image_path": get_site_brand_image_path(),
                "site_nav_icon_path": get_site_nav_icon_path(),
                "og_card_image_path": get_og_card_image_path(),
                "post_image_crop_og": get_post_image_crop_og(),
                "post_image_max_edge": get_post_image_max_edge(),
                "post_image_output_width": get_post_image_output_width(),
                "post_image_output_height": get_post_image_output_height(),
                "flat_post_urls": get_flat_post_urls(),
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
            },
        )

    @router.get("/admin/translations", response_class=HTMLResponse)
    @router.get("/admin/translations/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_translations_page(request: Request):
        from app.core.i18n import (
            DEFAULT_LOCALE,
            get_available_locales,
            list_translation_catalog,
        )
        locales = get_available_locales()
        preferred_locale = next((loc["code"] for loc in locales if loc.get("code") and loc["code"] != DEFAULT_LOCALE), None)
        selected_locale = (request.query_params.get("locale") or "").strip() or preferred_locale or (
            next((loc["code"] for loc in locales if loc.get("is_default")), None) or (locales[0]["code"] if locales else DEFAULT_LOCALE)
        )
        translation_items = list_translation_catalog(selected_locale) if selected_locale else []

        grouped_sections: dict[str, list[dict[str, Any]]] = {}
        def get_section_title(key: str) -> str:
            parts = key.split(".")
            if len(parts) >= 2 and parts[0] == "admin":
                sub = parts[1]
                if sub in ("dashboard", "nav"):
                    return "⚡ Admin Dashboard & Navigation"
                elif sub in ("users", "roles"):
                    return "👥 Admin Users & Roles"
                elif sub == "settings":
                    return "⚙️ Admin Site Settings"
                elif sub == "translations":
                    return "🌐 Admin Translations"
                elif sub == "themes":
                    return "🎨 Admin Themes"
                elif sub == "plugins":
                    return "🔌 Admin Plugins"
                elif sub == "categories":
                    return "📁 Admin Categories"
                elif sub == "editor":
                    return "📝 Admin Post Editor"
                elif sub in ("status", "actions", "confirm", "common"):
                    return "🛠️ Admin Common & Actions"
                else:
                    return f"⚙️ Admin {sub.capitalize()}"
            elif parts[0] == "footer":
                return "🦶 Footer Section"
            elif parts[0] == "home":
                return "🏠 Home Page & Blog"
            elif parts[0] == "ui":
                return "💻 UI & User Interface"
            elif parts[0] == "newsletter":
                return "📧 Newsletter"
            else:
                return f"📌 {parts[0].capitalize()}"

        for item in translation_items:
            sec = get_section_title(item.get("key", ""))
            if sec not in grouped_sections:
                grouped_sections[sec] = []
            grouped_sections[sec].append(item)

        return render_template(
            templates,
            request=request,
            name="admin/translations.html",
            context={
                "title": "Traduceri",
                "locales": locales,
                "selected_locale": selected_locale,
                "translation_items": translation_items,
                "grouped_sections": grouped_sections,
                "default_locale": DEFAULT_LOCALE,
            },
        )

    @router.post("/admin/translations/set-default")
    @role_required("admin")
    async def admin_set_default_locale(request: Request, locale_code: str = Form(...)):
        from app.core.i18n import set_default_locale
        set_default_locale(locale_code)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}&msg=Limba+implicită+a+fost+schimbată!", status_code=303)

    @router.post("/admin/translations/add-locale")
    @role_required("admin")
    async def admin_add_locale(request: Request):
        from app.core.i18n import add_locale
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        locale_code = _txt("locale_code").strip().lower()
        locale_name = _txt("locale_name") or locale_code.upper()
        if locale_code:
            add_locale(locale_code, locale_name)
        return RedirectResponse(url="/admin/translations?locale=" + locale_code, status_code=303)

    @router.post("/admin/translations/delete-locale")
    @role_required("admin")
    async def admin_delete_locale(request: Request):
        from app.core.i18n import delete_locale
        form = await request.form()
        locale_code = str(form.get("locale_code") or "").strip().lower()
        if locale_code:
            delete_locale(locale_code)
        return RedirectResponse(url="/admin/translations", status_code=303)

    @router.post("/admin/translations/save")
    @role_required("admin")
    async def admin_save_translation(request: Request):
        from app.core.i18n import save_translation_values
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        locale_code = _txt("locale_code").strip().lower()
        values: dict[str, str] = {}
        for name in form.keys():
            if name.startswith("translation_value__"):
                key = name[len("translation_value__") :].strip()
                if key:
                    values[key] = _txt(name)
        if locale_code and not values:
            key = _txt("translation_key")
            value = _txt("translation_value")
            if key:
                values[key] = value
        if locale_code and values:
            save_translation_values(locale_code, values)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}", status_code=303)

    @router.get("/admin/translations/delete")
    @role_required("admin")
    async def admin_delete_translation(request: Request):
        from app.core.i18n import delete_translation_entry
        locale_code = (request.query_params.get("locale") or "").strip()
        key = (request.query_params.get("key") or "").strip()
        if locale_code and key:
            delete_translation_entry(locale_code, key)
        return RedirectResponse(url=f"/admin/translations?locale={locale_code}", status_code=303)

    @router.get("/admin/themes", response_class=HTMLResponse)
    @router.get("/admin/themes/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_page(request: Request):
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": "",
            },
        )

    def _safe_theme_slug(raw: str) -> str | None:
        s = (raw or "").strip().lower()
        if not s or s in _THEME_SLUG_RESERVED:
            return None
        if any(ch not in _THEME_SLUG_OK for ch in s):
            return None
        return s

    def _zip_members(zipf: ZipFile) -> list[str]:
        return [n for n in zipf.namelist() if n and not n.endswith("/")]

    def _extract_theme_zip(data: bytes, *, overwrite: bool) -> tuple[str, str]:
        """
        Instalează o temă din zip. Returnează (slug, message).
        Așteaptă o structură de forma:
        - themes/<slug>/... (obligatoriu, cel puțin theme.json sau templates/)
        - static/themes/<slug>/... (opțional, ex. theme.css)
        """
        with tempfile.TemporaryDirectory(prefix="theme-upload-") as tmp:
            zpath = pathlib.Path(tmp) / "theme.zip"
            zpath.write_bytes(data)
            with ZipFile(zpath) as zipf:
                members = _zip_members(zipf)
                # Detect slug + layout variants.
                # Accepted zips:
                # 1) themes/<slug>/... + optional static/themes/<slug>/...
                # 2) <slug>/... (one theme folder at zip root)
                slug = None
                mode: str = "themes_root"  # or "slug_root"

                # Prefer explicit manifest path: themes/<slug>/theme.json
                if not slug:
                    for n in members:
                        if n.startswith("themes/") and n.endswith("/theme.json"):
                            parts = n.split("/", 3)
                            if len(parts) >= 3 and parts[1]:
                                cand = _safe_theme_slug(parts[1])
                                if cand:
                                    slug = cand
                                    mode = "themes_root"
                                    break

                # Fallback: any themes/<slug>/... path
                if not slug:
                    for n in members:
                        if n.startswith("themes/"):
                            parts = n.split("/", 2)
                            if len(parts) >= 2 and parts[1]:
                                cand = _safe_theme_slug(parts[1])
                                if cand:
                                    slug = cand
                                    mode = "themes_root"
                                    break

                if not slug:
                    # Try detect a theme folder at zip root: <slug>/theme.json or <slug>/templates/...
                    # Ignore common noise folders created by archivers.
                    ignore = {"__macosx", ".ds_store"}
                    top_levels = set()
                    for n in members:
                        if "/" in n:
                            top = n.split("/", 1)[0].strip()
                            if top and top.lower() not in ignore:
                                top_levels.add(top)

                    candidates = []
                    for top in sorted(top_levels):
                        cand = _safe_theme_slug(top)
                        if not cand:
                            continue
                        has_templates = any(
                            m.startswith(f"{top}/templates/") for m in members
                        )
                        has_manifest = any(m == f"{top}/theme.json" for m in members)
                        if has_templates or has_manifest:
                            candidates.append(cand)

                    if len(candidates) == 1:
                        slug = candidates[0]
                        mode = "slug_root"
                    elif len(candidates) > 1:
                        raise ValueError(
                            "Zip invalid: găsesc mai multe teme la rădăcină. "
                            f"Alege un singur folder temă: {', '.join(candidates[:8])}"
                        )

                if not slug:
                    if "theme.json" in members:
                        try:
                            tj_data = json.loads(zipf.read("theme.json").decode("utf-8"))
                            cand = _safe_theme_slug(tj_data.get("slug") or "")
                            if cand:
                                slug = cand
                                mode = "flat_root"
                        except Exception:
                            pass

                if not slug:
                    sample = ", ".join(members[:8]) if members else "(gol)"
                    raise ValueError(
                        "Zip invalid: aștept `themes/<slug>/...` sau `<slug>/...` (un singur folder la rădăcină cu numele temei). "
                        f"Exemple intrări: {sample}"
                    )

                # Secure extraction (prevent zip slip)
                extract_root = pathlib.Path(tmp) / "extract"
                extract_root.mkdir(parents=True, exist_ok=True)
                for n in members:
                    if ".." in n or n.startswith("/") or n.startswith("\\"):
                        raise ValueError("Zip invalid (path traversal).")
                    # Only allow themes/ and static/themes/
                    if mode == "themes_root":
                        # Normal:
                        # - themes/<slug>/...
                        # - static/themes/<slug>/...
                        if n.startswith(f"themes/{slug}/") or n.startswith(
                            f"static/themes/{slug}/"
                        ):
                            dest = extract_root / n
                        else:
                            continue
                    elif mode == "flat_root":
                        if n == "theme.json":
                            dest = extract_root / "themes" / slug / "theme.json"
                        elif n.startswith("templates/"):
                            dest = extract_root / "themes" / slug / n
                        elif n == "theme.css":
                            dest = extract_root / "static" / "themes" / slug / "theme.css"
                        elif n.startswith("static/"):
                            dest = extract_root / "static" / "themes" / slug / n[len("static/"):]
                        else:
                            continue
                    else:
                        # slug_root: accept a single theme folder:
                        # - <slug>/theme.json              -> themes/<slug>/theme.json
                        # - <slug>/templates/...           -> themes/<slug>/templates/...
                        # - <slug>/theme.css               -> static/themes/<slug>/theme.css
                        # - <slug>/static/themes/<slug>/.. -> static/themes/<slug>/...
                        if n.startswith(f"{slug}/"):
                            rel = n[len(slug) + 1 :]
                            if rel == "theme.json":
                                dest = extract_root / "themes" / slug / "theme.json"
                            elif rel.startswith("templates/"):
                                dest = extract_root / "themes" / slug / rel
                            elif rel == "theme.css":
                                dest = (
                                    extract_root
                                    / "static"
                                    / "themes"
                                    / slug
                                    / "theme.css"
                                )
                            elif rel.startswith(f"static/themes/{slug}/"):
                                dest = extract_root / rel
                            else:
                                continue
                        else:
                            continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zipf.open(n) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)

            theme_src = extract_root / "themes" / slug
            if not theme_src.is_dir():
                raise ValueError("Lipsește directorul `themes/<slug>/` din zip.")

            # Validate: must contain theme.json OR templates/
            def _is_theme_root(p: pathlib.Path) -> bool:
                return (p / "theme.json").is_file() or (p / "templates").is_dir()

            # Handle common nesting mistakes:
            # - themes/<slug>/<slug>/...
            # - themes/<slug>/themes/<slug>/...
            if not _is_theme_root(theme_src):
                nested1 = theme_src / slug
                nested2 = theme_src / "themes" / slug
                if nested1.is_dir() and _is_theme_root(nested1):
                    theme_src = nested1
                elif nested2.is_dir() and _is_theme_root(nested2):
                    theme_src = nested2
                else:
                    # If there's exactly one directory, try it (best effort).
                    subdirs = [p for p in theme_src.iterdir() if p.is_dir()]
                    if len(subdirs) == 1 and _is_theme_root(subdirs[0]):
                        theme_src = subdirs[0]

            has_manifest = (theme_src / "theme.json").is_file()
            has_templates = (theme_src / "templates").is_dir()
            if not (has_manifest or has_templates):
                # Try to help debugging by listing entries.
                entries = []
                try:
                    entries = sorted([p.name for p in theme_src.iterdir()])[:12]
                except Exception:
                    entries = []
                hint = f"Conținut găsit în themes/{slug}/: {', '.join(entries) if entries else '(nimic)'}"
                raise ValueError(
                    "Tema trebuie să conțină `themes/<slug>/theme.json` și/sau `themes/<slug>/templates/`. "
                    + hint
                )

            theme_dest = APP_DIR / "themes" / slug
            static_src = extract_root / "static" / "themes" / slug
            static_dest = APP_DIR / "static" / "themes" / slug

            if theme_dest.exists() or static_dest.exists():
                if not overwrite:
                    raise ValueError("Tema există deja. Bifează „Suprascrie” ca să o reinstalezi.")
                if theme_dest.is_dir():
                    shutil.rmtree(theme_dest)
                if static_dest.is_dir():
                    shutil.rmtree(static_dest)

            theme_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(theme_src, theme_dest)
            if static_src.is_dir():
                static_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(static_src, static_dest)

            return slug, f"Tema `{slug}` a fost instalată."

    @router.post("/admin/themes/upload", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_upload(
        request: Request,
        file: UploadFile = File(...),
        overwrite: str | None = Form(default=None),
    ):
        raw = await file.read()
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        if not raw:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Fișier gol.",
                    "message": "",
                },
                status_code=400,
            )
        try:
            slug, msg = _extract_theme_zip(raw, overwrite=overwrite == "1")
            themes = list_installed_themes()
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "",
                    "message": msg,
                },
            )
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": f"Eroare: {str(e)}",
                    "message": "",
                },
                status_code=400,
            )

    @router.post("/admin/themes/activate", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_activate(request: Request, slug: str = Form(...)):
        s = _safe_theme_slug(slug)
        cur_theme = get_active_theme()
        if s and s != cur_theme:
            set_active_theme(s)
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": f"Tema '{slug}' a fost activată cu succes!",
            },
        )

    @router.post("/admin/themes/delete", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_themes_delete(request: Request, slug: str = Form(...)):
        s = _safe_theme_slug(slug)
        themes = list_installed_themes()
        cur_theme = get_active_theme()
        if not s:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Slug invalid.",
                    "message": "",
                },
                status_code=400,
            )

        if s == cur_theme:
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": "Nu poți șterge tema activă în folosință!",
                    "message": "",
                },
                status_code=400,
            )

        theme_dir = APP_DIR / "themes" / s
        static_dir = APP_DIR / "static" / "themes" / s
        try:
            if theme_dir.is_dir():
                shutil.rmtree(theme_dir)
            if static_dir.is_dir():
                shutil.rmtree(static_dir)
        except Exception as e:
            themes = list_installed_themes()
            return render_template(
                templates,
                request=request,
                name="admin/themes.html",
                context={
                    "title": "Teme",
                    "installed_themes": themes,
                    "active_theme_slug": cur_theme,
                    "error": f"Eroare la ștergere: {str(e)}",
                    "message": "",
                },
                status_code=500,
            )

        # Dacă tema ștearsă era activă, revenim la default în setări.
        if cur_theme == s:
            write_settings({"ACTIVE_THEME": None})
            cur_theme = get_active_theme()

        themes = list_installed_themes()
        return render_template(
            templates,
            request=request,
            name="admin/themes.html",
            context={
                "title": "Teme",
                "installed_themes": themes,
                "active_theme_slug": cur_theme,
                "error": "",
                "message": f"Tema `{s}` a fost ștearsă.",
            },
        )

    def _plugins_page_ctx(
        installed_plugins,
        *,
        error: str = "",
        message: str = "",
    ) -> dict:
        # Obținem plugin-urile din baza de date cu status și setări
        from app.core.plugin_manager import get_installed_plugins, get_plugin_settings
        db_plugins = {p.id: p for p in get_installed_plugins()}
        
        return {
            "title": "Plugin-uri",
            "installed_plugins": installed_plugins,
            "db_plugins": db_plugins,
            "error": error,
            "message": message,
            "container_restart_enabled": ADMIN_ENABLE_CONTAINER_RESTART,
        }

    
    @router.get("/admin/plugins", response_class=HTMLResponse)
    @router.get("/admin/plugins/", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_page(request: Request):
        plugins = list_installed_plugins()
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(plugins),
        )

    @router.post("/admin/plugins/upload", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_upload(
        request: Request,
        file: UploadFile = File(...),
        overwrite: str | None = Form(default=None),
    ):
        raw = await file.read()
        if not raw:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="Fișier gol.",
                ),
                status_code=400,
            )
        try:
            _pid, msg = extract_plugin_zip(raw, overwrite=overwrite == "1")
            plugins = list_installed_plugins()
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(plugins, message=msg),
            )
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error=f"Eroare: {str(e)}",
                ),
                status_code=400,
            )

    @router.post("/admin/plugins/delete", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_plugins_delete(request: Request, slug: str = Form(...)):
        s = safe_plugin_id(slug)
        if not s:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="ID plugin invalid.",
                ),
                status_code=400,
            )
        dest = APP_DIR / "plugins" / s
        try:
            if dest.is_dir():
                shutil.rmtree(dest)
            # Ștergem și din baza de date (inclusiv setările)
            from app.core.plugin_manager import unregister_plugin_from_db
            unregister_plugin_from_db(s)
        except Exception as e:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error=f"Eroare la ștergere: {str(e)}",
                ),
                status_code=500,
            )
        plugins = list_installed_plugins()
        extra = (
            f"Plugin `{s}` și toate setările sale au fost șterse. Apoi „Repornește containerul” sau restart manual."
            if ADMIN_ENABLE_CONTAINER_RESTART
            else f"Plugin `{s}` și toate setările sale au fost șterse. Repornește aplicația ca schimbarea să fie completă."
        )
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(plugins, message=extra),
        )

    @router.post("/admin/app/restart", response_class=HTMLResponse)
    @role_required("admin")
    async def admin_app_restart(
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        if not ADMIN_ENABLE_CONTAINER_RESTART:
            return render_template(
                templates,
                request=request,
                name="admin/plugins.html",
                context=_plugins_page_ctx(
                    list_installed_plugins(),
                    error="Restart din Admin nu e activat. Setează ADMIN_ENABLE_CONTAINER_RESTART=true în .env și repornește manual containerul o dată ca să ia variabila.",
                ),
                status_code=403,
            )
        background_tasks.add_task(sigterm_self_after_delay, 0.35)
        return render_template(
            templates,
            request=request,
            name="admin/plugins.html",
            context=_plugins_page_ctx(
                list_installed_plugins(),
                message="Se trimite oprirea procesului; cu Docker (restart: unless-stopped) containerul ar trebui să revină în câteva secunde. Reîncarcă apoi această pagină.",
            ),
        )

    @router.post("/admin/settings/save")
    @role_required("admin")
    async def admin_save_settings(request: Request):
        form = await request.form()

        def _txt(key: str) -> str:
            v = form.get(key)
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v).decode("utf-8", errors="replace").strip()
            return ""

        def _opt_int(key: str) -> int | None:
            s = _txt(key)
            if not s:
                return None
            try:
                n = int(s)
                return n if n > 0 else None
            except ValueError:
                return None

        def _save_app_setting(key: str, value: str | None) -> None:
            with SessionLocal() as db:
                row = db.get(AppSetting, key)
                if value is None or str(value).strip() == "":
                    if row is not None:
                        db.delete(row)
                else:
                    if row is None:
                        db.add(AppSetting(key=key, value=str(value).strip()))
                    else:
                        row.value = str(value).strip()
                db.commit()

        _save_app_setting("SITE_DISPLAY_NAME", _txt("site_display_name") or None)
        _save_app_setting("SITE_TAGLINE", _txt("site_tagline") or None)

        for loc in get_available_locales():
            code = loc.get("code")
            if code:
                _save_app_setting(f"SITE_DISPLAY_NAME_{code}", _txt(f"site_display_name_{code}") or None)
                _save_app_setting(f"SITE_TAGLINE_{code}", _txt(f"site_tagline_{code}") or None)

        write_settings(
            {
                "FLAT_POST_URLS": _txt("flat_post_urls") == "1",
                "ACTIVE_THEME": _txt("active_theme") or None,
                "POST_IMAGE_MAX_EDGE": _opt_int("post_image_max_edge"),
                "POST_IMAGE_OUTPUT_WIDTH": _opt_int("post_image_output_width"),
                "POST_IMAGE_OUTPUT_HEIGHT": _opt_int("post_image_output_height"),
                "POST_IMAGE_CROP_OG": _txt("post_image_crop_og") == "1",
            }
        )
        return RedirectResponse(url="/admin/settings", status_code=303)

    @router.post("/admin/settings/upload-image")
    @role_required("admin")
    async def admin_settings_upload_image(
        request: Request,
        setting_key: str = Form(...),
        file: UploadFile = File(...),
    ):
        if setting_key not in _IMAGE_SETTING_KEYS:
            return RedirectResponse(url="/admin/settings", status_code=303)
        raw = await file.read()
        if not raw:
            return RedirectResponse(url="/admin/settings", status_code=303)
        orig = (file.filename or "upload").strip()
        ext = pathlib.Path(orig).suffix.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in _SITE_IMAGE_EXTS:
            return RedirectResponse(url="/admin/settings", status_code=303)
        dest_dir = pathlib.Path("static/images/site_uploads")
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid4().hex}{ext}"
        dest = dest_dir / name
        dest.write_bytes(raw)
        rel = f"/static/images/site_uploads/{name}"
        prev = read_settings().get(setting_key)
        write_settings({setting_key: rel})
        if isinstance(prev, str) and prev.strip() and prev.strip() != rel:
            unlink_site_upload_file(prev.strip())
        return RedirectResponse(url="/admin/settings", status_code=303)

    @router.post("/admin/settings/clear-image")
    @router.post("/admin/settings/clear-image/")
    @role_required("admin")
    async def admin_settings_clear_image(request: Request):
        form = await request.form()
        raw = form.get("setting_key")
        if raw is None:
            logger.warning("clear-image: missing setting_key")
            return RedirectResponse(url="/admin/settings", status_code=303)
        setting_key = (
            raw.decode("utf-8", errors="replace").strip()
            if isinstance(raw, (bytes, bytearray))
            else str(raw).strip()
        )
        if setting_key not in _IMAGE_SETTING_KEYS:
            logger.warning("clear-image: invalid setting_key=%r", setting_key)
            return RedirectResponse(url="/admin/settings", status_code=303)
        stored = read_settings().get(setting_key)
        if isinstance(stored, str) and stored.strip():
            unlink_site_upload_file(stored.strip())
        write_settings({setting_key: None})
        logger.info("clear-image: cleared %s", setting_key)
        return RedirectResponse(url="/admin/settings", status_code=303)

    @router.post("/admin/upload-image")
    @role_required("admin", "editor", "author")
    async def admin_upload_image(request: Request, file: UploadFile = File(...)):
        try:
            base = pathlib.Path("static/images/post_images")
            base.mkdir(parents=True, exist_ok=True)

            original = (file.filename or "upload").strip()
            ext = pathlib.Path(original).suffix.lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            allowed = {".png", ".jpg", ".jpeg", ".gif"}
            if ext not in allowed:
                return JSONResponse(
                    {"error": "Acceptăm doar JPEG, PNG sau GIF animat (fără WebP)."},
                    status_code=415,
                )

            data = await file.read()
            data, out_ext = process_post_upload(data, ext)
            name = f"{uuid4().hex}{out_ext}"
            dest = base / name
            dest.write_bytes(data)

            return JSONResponse({"location": f"/static/images/post_images/{name}"})
        except Exception as e:
            logger.exception("Error uploading image")
            return JSONResponse(
                {"error": f"Eroare la upload: {str(e)}"},
                status_code=500,
            )

    @router.get("/admin/post/{slug}/delete")
    @role_required("admin")
    async def delete_my_post(
        request: Request, slug: str, db: Session = Depends(get_db)
    ):
        success = delete_post(db, slug)
        if success:
            cur_links = read_settings().get("STATIC_NAV_LINKS") or []
            if isinstance(cur_links, list):
                filtered = [
                    item for item in cur_links
                    if isinstance(item, dict) and str(item.get("slug") or "").strip() != slug
                ]
                if filtered:
                    write_settings({"STATIC_NAV_LINKS": filtered})
                else:
                    write_settings({"STATIC_NAV_LINKS": []})
            else:
                write_settings({"STATIC_NAV_LINKS": []})
            return RedirectResponse(url="/admin", status_code=303)
        return JSONResponse(
            {"error": "Nu am putut șterge postarea!"},
            status_code=404,
        )

    return router