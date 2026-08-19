# 🔌 Guide: How to Create a Custom Plugin for VlahX Core 2.0

This guide explains step-by-step how to design, develop, package, and install a custom plugin for **VlahX Core 2.0**.

---

## 📁 1. Plugin Directory Architecture

Every plugin in **VlahX Core 2.0** must be **100% self-contained** inside its own directory in `plugins/<plugin_id>/`. Nothing should spill over into core `templates/` or `app/` folders.

```text
plugins/<plugin_id>/
├── plugin.json               # Required plugin manifest & metadata
├── plugin.py                 # Main entry point (register(app) function)
├── db.py                     # SQLite database tables & CRUD logic (optional)
├── locales/                  # Multi-language translations (optional)
│   ├── ro.json               # Romanian translations
│   └── en.json               # English translations
├── templates/                # Embedded Jinja2 HTML templates (optional)
│   ├── admin/                # Admin Panel pages (e.g. templates/admin/<plugin_id>.html)
│   └── <feature>/            # Public frontend pages (e.g. templates/shop/index.html)
└── assets/                   # Static CSS/JS files (optional)
    └── script.js
```

---

## 📜 2. Plugin Manifest (`plugin.json`)

Create a `plugin.json` file inside `plugins/<plugin_id>/`:

```json
{
  "id": "my_custom_plugin",
  "name": "My Custom Plugin",
  "description": "Adds awesome custom features to the blog.",
  "version": "1.0.0",
  "author": "Your Name",
  "permissions": [
    "routes",
    "database",
    "template_hooks",
    "admin_nav",
    "admin_top_bar"
  ],
  "settings": {
    "enable_feature_x": {
      "type": "checkbox",
      "label": "Enable Feature X",
      "description": "Toggles Feature X on or off",
      "default": true,
      "required": false
    },
    "custom_api_key": {
      "type": "text",
      "label": "API Key",
      "description": "Enter your third-party API Key",
      "default": "",
      "required": false
    }
  }
}
```

### Manifest Fields:
- **`id`**: Unique lowercase identifier matching folder name (e.g. `newsletter`, `minishop`, `comments`).
- **`name`**: Human-readable name shown in Admin Plugin Manager (`/admin/plugins`).
- **`description`**: Brief summary of what the plugin does.
- **`version`**: Semantic version string (e.g. `1.0.0`).
- **`permissions`**: List of features requested by the plugin:
  - `"routes"`: Registers custom FastAPI HTTP GET/POST endpoints.
  - `"database"`: Initializes SQLite database tables.
  - `"template_hooks"`: Injects HTML into article footers, header metas, or navbar links.
  - `"admin_nav"`: Adds link to the main Admin Sub-Navbar.
  - `"admin_top_bar"`: Adds button to the Admin Top Bar.
- **`settings`**: Configurable settings editable from `/admin/plugin-settings?plugin=<id>`.

---

## 🚀 3. Plugin Entry Point (`plugin.py`)

The `plugin.py` file is loaded dynamically when the application starts. It MUST contain a `register(app: FastAPI)` function.

```python
from __future__ import annotations
import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.templates import build_templates, render_template
from app.core.plugin_manager import get_plugin_setting, is_plugin_enabled
from app.core.i18n import get_plugin_translation, resolve_locale
from app.core.events import subscribe

logger = logging.getLogger(__name__)

def register(app: FastAPI, plugin_id: str = "my_custom_plugin") -> None:
    # 1. Initialize database tables
    # from plugins.my_custom_plugin.db import init_db
    # init_db()

    # 2. Sync locale files to DB
    # sync_translations()

    templates = build_templates("templates")

    # 3. Public Frontend Route
    @app.get("/my-plugin-page", response_class=HTMLResponse)
    async def my_page(request: Request):
        if not is_plugin_enabled("my_custom_plugin"):
            return JSONResponse({"error": "Plugin is disabled"}, status_code=403)
        
        locale = resolve_locale(request)
        t_plugin = lambda key, def_val="": get_plugin_translation("my_custom_plugin", locale, key, def_val)

        return render_template(
            templates,
            request=request,
            name="my_custom_plugin/index.html",
            context={
                "title": t_plugin("title", "My Plugin Page"),
                "t_plugin": t_plugin,
            }
        )

    # 4. Template Hooks (Frontend Navbar link)
    def render_my_navbar_link(request: Request) -> str:
        loc = resolve_locale(request)
        label = get_plugin_translation("my_custom_plugin", loc, "nav_link", "⚡ My Feature")
        return f'<li class="nav-item"><a class="nav-link py-1 px-3 rounded-pill fw-semibold" href="/my-plugin-page">{label}</a></li>'

    # 5. Admin Navigation Hooks
    def render_my_admin_nav(request: Request) -> str:
        return '<li class="nav-item"><a class="nav-link fw-semibold px-3 rounded-2" href="/admin/my-plugin">⚡ My Plugin</a></li>'

    def render_my_admin_top_bar(request: Request) -> str:
        return '<a class="btn btn-sm btn-outline-primary fw-semibold me-2" href="/admin/my-plugin">⚡ My Plugin Admin</a>'

    from app.core.template_hooks import register_admin_nav, register_admin_top_bar, register_navbar_link
    register_admin_nav(render_my_admin_nav)
    register_admin_top_bar(render_my_admin_top_bar)
    register_navbar_link(render_my_navbar_link)

    # 6. Event Subscriptions (Optional)
    def on_blog_post_published(event_name: str, payload: dict[str, Any]) -> None:
        post_slug = payload.get("slug")
        logger.info("New blog post published: %s", post_slug)

    subscribe("blog.post_published", on_blog_post_published)
```

---

## 🎨 4. Template Encapsulation (`templates/`)

Plugins load HTML templates directly from `plugins/<plugin_id>/templates/`. 

### Admin Panel Page (`plugins/<plugin_id>/templates/admin/<plugin_id>.html`)
**CRITICAL**: Every Admin template MUST extend `"admin/admin_base.html"`:

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h2 class="h3 fw-bold mb-1">⚡ My Custom Plugin Admin</h2>
    <p class="text-secondary small mb-0">Manage options and view status.</p>
  </div>
</div>

<div class="card shadow-sm border-0 p-4">
  <h5>Welcome to My Plugin Admin Panel</h5>
</div>
{% endblock %}
```

### Public Frontend Page (`plugins/<plugin_id>/templates/<plugin_id>/index.html`)
Public frontend templates MUST extend `"base.html"` (which loads the active theme layout):

```html
{% extends "base.html" %}

{% block content %}
<div class="container py-5">
  <h1 class="fw-bold mb-3">{{ t_plugin('title', 'My Plugin Page') }}</h1>
  <p class="text-secondary">Plugin content goes here.</p>
</div>
{% endblock %}
```

---

## 🌐 5. Internationalization / Multi-language (`locales/`)

Plugins support full multi-language translations. Place JSON translation files inside `plugins/<plugin_id>/locales/`:

### Romanian (`plugins/<plugin_id>/locales/ro.json`):
```json
{
  "nav_link": "⚡ Opțiunea Mea",
  "title": "Pagina Mea Personalizată",
  "welcome_msg": "Bine ai venit pe pagina plugin-ului!"
}
```

### English (`plugins/<plugin_id>/locales/en.json`):
```json
{
  "nav_link": "⚡ My Feature",
  "title": "My Custom Page",
  "welcome_msg": "Welcome to the plugin page!"
}
```

### Retrieving Translations in Python:
```python
loc = resolve_locale(request)
text = get_plugin_translation("my_custom_plugin", loc, "welcome_msg", "Default text")
```

### Retrieving Translations in Jinja2:
```html
<p>{{ t_plugin('welcome_msg', 'Default text') }}</p>
```

---

## 🔗 6. Template Hooks Reference

The core application provides template hooks where plugins can inject HTML content dynamically:

| Registration Function | Hook Target / Location | Signature |
| :--- | :--- | :--- |
| `register_navbar_link(renderer)` | Public Navbar next to static pages | `renderer(request: Request) -> str` |
| `register_post_article_footer(renderer)` | Beneath articles/products | `renderer(post: Any, request: Request) -> str` |
| `register_post_header_meta(renderer)` | Article metadata bar | `renderer(post: Any, request: Request) -> str` |
| `register_admin_nav(renderer)` | Admin panel Sub-Navbar menu | `renderer(request: Request) -> str` |
| `register_admin_top_bar(renderer)` | Admin header top action buttons | `renderer(request: Request) -> str` |
| `register_footer_col1..col4(renderer)` | 4 Footer columns | `renderer(request: Request) -> str` |
| `register_footer_bottom(renderer)` | Footer bottom copyright line | `renderer(request: Request) -> str` |

---

## 📦 7. Packaging & Installation (ZIP Format)

To distribute or upload a plugin via the Admin Panel (`/admin/plugins` -> Upload Plugin ZIP):

### Archive Structure Requirement:
The `.zip` archive MUST contain the top-level plugin directory matching the `id` in `plugin.json`:

```text
my_custom_plugin.zip
 └── my_custom_plugin/
      ├── plugin.json
      ├── plugin.py
      ├── db.py (optional)
      ├── locales/ (optional)
      └── templates/ (optional)
```

### Installing:
1. Go to **Admin Panel** ➔ **Extensii & Plugin-uri** (`/admin/plugins`).
2. Click **Upload Plugin ZIP**.
3. Select your `<plugin_id>.zip` file and click **Instalează Plugin**.
4. Enable the plugin using the toggle switch!

---

## 🔄 8. Frontend Custom Content Types & Analytics Integration Scheme

When developing a custom frontend plugin that introduces new viewable items (e.g. **Shop Products**, **Portfolio Items**, **Real Estate Listings**, **Forum Topics**, etc.), your plugin needs to communicate with **Analytics** (as well as Comments, Share, and Reaction plugins) — **regardless of whether Analytics is installed before or after your plugin**.

### How to Integrate Custom Items with Analytics Tracking:

#### 1. Route Controller (`plugin.py`):
Create an object wrapper exposing `.slug` (and optionally `.content_html` or `.title`), then invoke `render_post_header_metas` and `render_post_article_footers`:

```python
from app.core.template_hooks import render_post_article_footers, render_post_header_metas


class ItemObject:

    def __init__(self, item_dict: dict):
        for k, v in item_dict.items():
            setattr(self, k, v)


@app.get("/my-plugin/item/{slug}")
async def item_detail(request: Request, slug: str):
    item = get_item_by_slug(slug)
    item_obj = ItemObject(item)

    # Evaluates all registered header meta hooks (Analytics view badge, read time, JS beacon ping)
    post_header_meta_html = render_post_header_metas(item_obj, request)
    post_article_footer_html = render_post_article_footers(item_obj, request)

    return render_template(
        templates,
        request=request,
        name="my_plugin/detail.html",
        context={
            "item": item,
            "post_header_meta_html": post_header_meta_html,
            "post_article_footer_html": post_article_footer_html,
        },
    )
```

#### 2. Item Detail Template (`templates/my_plugin/detail.html`):
Render `post_header_meta_html` inside your detail page header badge wrapper:

```html
<div class="d-flex flex-wrap gap-2 mb-3 align-items-center">
  {% if post_header_meta_html %}
    {{ post_header_meta_html|safe }}
  {% endif %}
</div>
```

#### 3. Item Catalog Cards Template (`templates/my_plugin/index.html`):
Pass `render_post_article_footers(item_obj, request)` on each card item to render view counters dynamically:

```html
{% if item.article_footer_html %}
  {{ item.article_footer_html|safe }}
{% endif %}
```

---

## 🧰 9. Platform Reference: Detailed Descriptions & Code Usage

### 🐍 Backend Python Functions & Constants (`app/` Core Ecosystem)

| Variable / Function | Type / Signature | Description & Code Function | Usage Example |
| :--- | :--- | :--- | :--- |
| **`APP_DIR`** | `pathlib.Path` | Calea absolută către directorul `/app/app`. Folosită pentru construirea de căi sigure către resursele interne ale aplicației. | `db_path = APP_DIR / "plugins" / "my_plugin" / "data.db"` |
| **`PROJECT_ROOT`** | `pathlib.Path` | Calea absolută către rădăcina spațiului de lucru al proiectului. | `log_path = PROJECT_ROOT / "logs" / "plugin.log"` |
| **`build_templates(subfolder)`** | `(str) -> Jinja2Templates` | Construiește loader-ul Jinja2 cu sistemul `ChoiceLoader`, căutând șabloanele în ordine: Tema Activă ➔ Tema Minimal (Fallback) ➔ Directorul Plugin-ului ➔ Nucleul `/app/templates`. | `templates = build_templates("templates")` |
| **`render_template(...)`** | `(templates, request, name, context, status=200)` | Randează un șablon HTML și injectează automat toate variabilele globale de context ale platformei (`t`, `t_plugin`, `locale`, `site_display_name`, `plugin_area_*`, etc.). | `return render_template(templates, request=request, name="my_plugin/index.html", context={"title": "Demo"})` |
| **`is_plugin_enabled(id)`** | `(str) -> bool` | Interogează baza de date SQLite pentru a verifica dacă un plugin specific este activat din Panoul de Admin. | `if is_plugin_enabled("minishop"): ...` |
| **`get_plugin_setting(...)`** | `(plugin_id, key, default=None)` | Extrage o valoare de configurare salvată pentru un plugin din tabelul `plugin_settings` în baza de date. | `currency = get_plugin_setting("minishop", "currency", "RON")` |
| **`set_plugin_setting(...)`** | `(plugin_id, key, value)` | Salvează sau actualizează o valoare de configurare pentru plugin în baza de date. | `set_plugin_setting("my_plugin", "api_key", "secret123")` |
| **`resolve_locale(request)`** | `(Request) -> str` | Detectează limba activă pentru cererea HTTP curentă (din cookie, query string `?lang=ro`, header-ul browser-ului sau limba implicită a site-ului). | `loc = resolve_locale(request)` *(returnează `"ro"` sau `"en"`)* |
| **`get_plugin_translation(...)`** | `(plugin_id, locale, key, default)` | Caută cheia de traducere în fișierul JSON al plugin-ului (`locales/<locale>.json`). Dacă nu o găsește, returnează valoarea implicită. | `text = get_plugin_translation("analytics", "ro", "views", "vizualizări")` |
| **`subscribe(event, callback)`** | `(str, Callable)` | Înregistrează o funcție ascultător (listener) pentru un eveniment din sistem. | `subscribe("blog.post_published", send_telegram_notification)` |
| **`dispatch(event, payload)`** | `(str, dict)` | Emite un eveniment în mod asincron către toți ascultătorii înregistrați în platformă. | `dispatch("shop.order_created", {"order_id": 105, "total": 150.0})` |

---

### 🎨 Jinja2 Template Context Reference (Disponibile direct în fișierele `.html`)

| Variable / Function | Return Type | Description & Code Function | HTML Jinja2 Example |
| :--- | :--- | :--- | :--- |
| **`t(key, default="")`** | `str` | Traduce o etichetă din dicționarul principal al nucleului platformei (core translations) în limba vizitatorului. | `{{ t('blog.read_more', 'Citește mai mult') }}` |
| **`t_plugin(plugin_id, key, default)`** | `str` | Traduce o etichetă din fișierele de limba (`locales/*.json`) ale plugin-ului specific. | `{{ t_plugin('analytics', 'views', 'vizualizări') }}` |
| **`locale`** | `str` | Codul limbii curente active pentru cererea curentă (ex: `"ro"`, `"en"`). | `<html lang="{{ locale }}">` |
| **`is_plugin_active(plugin_id)`** | `bool` | Helper în șablon pentru a verifica dacă un plugin este instalat și activat. | `{% if is_plugin_active('comments') %}{% include "comments/box.html" %}{% endif %}` |
| **`get_plugin_setting(...)`** | `Any` | Citește o setare din baza de date direct în HTML. | `{{ get_plugin_setting('minishop', 'currency', 'RON') }}` |
| **`active_theme_info()`** | `dict` | Returnează un dicționar cu metadatele temei curente active (`name`, `version`, `author`). | `Tema: {{ active_theme_info().name }}` |
| **`site_display_name()`** | `str` | Numele oficial configurat al blogului/site-ului. | `<h1>{{ site_display_name() }}</h1>` |
| **`site_tagline()`** | `str` | Sloganul/descrierea scurtă configurată a site-ului. | `<p class="lead">{{ site_tagline() }}</p>` |
| **`site_nav_icon_abs`** | `str` | Calea URL absolută către sigla/iconița configurată a site-ului. | `<img src="{{ site_nav_icon_abs }}" alt="Logo">` |
| **`now()`** | `datetime` | Obiect Python `datetime` cu timpul curent UTC. | `© {{ now().strftime("%Y") }}` |
| **`request`** | `Request` | Obiectul FastAPI `Request` al paginii curente HTTP. | `Cale: {{ request.url.path }}` |

---

### 🔗 Variabile de Injecție HTML în Șabloane (Arii de Plugin-uri)

| Template Variable | Injected Content Description | Injected Location |
| :--- | :--- | :--- |
| **`{{ plugin_area_admin_nav \| safe }}`** | Randează elementele `<li>` adăugate de plugin-uri în meniul Sub-Navbar din Admin. | `app/templates/admin/admin_base.html` |
| **`{{ plugin_area_admin_top_bar \| safe }}`** | Randează butoanele de acțiune rapidă în bara dreaptă a Sub-Navbar-ului din Admin. | `app/templates/admin/admin_base.html` |
| **`{{ plugin_area_navbar_links \| safe }}`** | Randează link-urile adăugate de plugin-uri în Navbar-ul public din antetul site-ului. | `app/templates/partials/navbar.html` |
| **`{{ plugin_area_footer_col1 \| safe }}` .. `col4`** | Randează widget-urile adăugate de plugin-uri în cele 4 coloane responsive din subsolul site-ului. | `app/templates/partials/footer.html` |
| **`{{ plugin_area_footer_bottom \| safe }}`** | Randează HTML suplimentar sub linia de copyright din subsolul site-ului. | `app/templates/partials/footer.html` |

---

## 🎉 Summary Checklist for Plugin Developers

- [x] Folder name matches `id` in `plugin.json` (`plugins/<id>/`).
- [x] `plugin.json` contains valid metadata and permissions array.
- [x] `plugin.py` exports `register(app: FastAPI)` function.
- [x] Admin templates extend `"admin/admin_base.html"`.
- [x] Public templates extend `"base.html"`.
- [x] Custom content detail pages render `post_header_meta_html` for Analytics compatibility.
- [x] Translation strings use `resolve_locale(request)` and `get_plugin_translation(...)`.
- [x] ZIP archive contains top-level `<id>/` directory.
