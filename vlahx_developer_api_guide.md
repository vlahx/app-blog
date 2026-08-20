# Ghidul Dezvoltatorului VlahX Engine (v2.0 Core)
## Arhitectură, API-uri, Variabile, Regulament de Versionare & Sistem de Plugin-uri/Teme

Acest ghid oferă documentația tehnică completă a platformei **VlahX Engine 2.0 Core**. Orice dezvoltator poate folosi acest document pentru a înțelege structura aplicației și pentru a crea, publica și actualiza **plugin-uri** și **teme** personalizate în ecosistemul `repo.vlahx.org`.

---

## 1. Concepte de Bază & Filosofia VlahX Engine

* **Tehnologii Core**: Python (FastAPI), Jinja2 Templates, SQLite (`db/app.db`), Vanilla CSS/Bootstrap 5, JavaScript.
* **Single Source of Truth**: Toate setările globale ale aplicației sunt stocate în tabela SQLite `app_settings` (sub formă de cheie-valoare), eliminând fișierele temporare `.json`.
* **Arhitectură Modulară (Plugin-driven)**: Orice funcționalitate avansată (SEO, Notificări Telegram, Analytics, Magazin, Sitemap) este încapsulată într-un plugin decuplat.
* **Distribuție 1-Click din Repository**: Modulele și temele sunt distribuite securizat prin microserviciul containerizat `repo.vlahx.org`.

---

## 2. Regulamentul Oficial de Versionare (Semantic Versioning & Compatibility)

Pentru a asigura stabilitatea platformei VlahX pe mii de site-uri active, toate modulele și temele trebuie să respecte regulamentul de versionare **SemVer (`MAJOR.MINOR.PATCH`)**:

### A. Convenția Versiunilor (`vMAJOR.MINOR.PATCH`)
- **Versiunea de Start**: Toate plugin-urile și temele noi lansate pentru VlahX Core 2.0 pornesc de la versiunea baseline **`v2.0.0`**.
- **Versiuni `PATCH` (`v2.0.0` ➔ `v2.0.1`)**: Modificări minore, rezolvări de bug-uri, optimizări de performanță.
- **Versiuni `MINOR` (`v2.0.0` ➔ `v2.1.0`)**: Funcționalități noi adăugate, dar care păstrează **100% compatibilitatea înapoi** cu VlahX Core 2.x.
- **Versiuni `MAJOR` (`v2.x.x` ➔ `v3.0.0`)**: Schimbări majore de arhitectură ale engine-ului care necesită refactorizarea codului sursă.

### B. Manifestul `plugin.json` & `theme.json`
Orice modul trebuie să declare în fișierul de configurare versiunea sa și versiunea minimă de engine necesară:

```json
{
  "id": "my_custom_plugin",
  "name": "Plugin-ul Meu Personalizat",
  "version": "2.0.0",
  "min_engine_version": "2.0.0",
  "author": "Numele Tău / Developer VlahX",
  "description": "Descrierea modulului."
}
```

### C. Fluxul de Publicare & Update pe `repo.vlahx.org`
1. **Prima Publicare**: Modulul este încărcat în repo cu versiunea inițială **`v2.0.0`**.
2. **Actualizare / Re-salvare (Update Flow)**:
   - Când developerul urcă o arhivă nouă pentru un modul existent, portalul `repo.vlahx.org` detectează versiunea curentă.
   - Developerul este invitat să introducă **Changelog-ul / Notele Lansării** (descrierea scurtă a modificărilor).
   - Microserviciul incrementează versiunea (ex: `v2.0.1`), arhivează build-ul anterior (`my_custom_plugin-2.0.0.zip`) și actualizează `catalog.json`.
   - Toate site-urile VlahX active afișează automat insigna: **`🚀 Update Disponibil (v2.0.1)`** cu buton de **`⚡ 1-Click Update`**.

---

## 3. Constante & Ajutoare Globale (`app/core/config.py`)

Aceste funcții helper pot fi apelate din orice plugin sau ruter pentru a citi dinamic setările site-ului:

| Funcție Helper | Returnează | Descriere & Utilitate |
| :--- | :--- | :--- |
| `VLAH_CORE_VERSION` | `str` | Versiunea curentă a engine-ului Core (ex: `"2.0.0"`). |
| `get_site_display_name(locale=None)` | `str` | Numele oficial al site-ului (cu suport pentru traducere per limbă). |
| `get_site_tagline(locale=None)` | `str` | Sloganul / subtitlul site-ului. |
| `get_public_site_url()` | `str` | URL-ul public configurat al site-ului. |
| `public_site_origin(request)` | `str` | Originea absolută (ex: `https://vlahx.org`), detectând automat HTTPS din reverse-proxy (`X-Forwarded-Proto`). |
| `get_homepage_mode()` | `str` | Regimul primei pagini (`blog` = feed articole, `page:<slug>` = pagină statică, `shop` = magazin). |
| `get_active_theme()` | `str` | Numele temei active (ex: `"minimal"`). |
| `get_flat_post_urls()` | `bool` | `True` dacă URL-urile articolelor sunt la `/{slug}` sau `False` dacă sunt la `/blog/{slug}`. |
| `get_site_favicon_path()` | `str` | Calea către favicon-ul site-ului. |
| `get_site_brand_image_path()` | `str` | Calea către imaginea / logo-ul principal al brandului. |
| `get_site_nav_icon_path()` | `str` | Calea către iconița din navbar (dacă există). |
| `get_og_card_image_path()` | `str` | Calea către imaginea implicită pentru cardurile OpenGraph / rețele sociale. |
| `get_telegram_bot_token()` | `str` | Token-ul botului Telegram citit din SQLite/plugin. |
| `get_telegram_notify_chat_id()` | `str` | Chat ID-ul pentru notificări Telegram citit din SQLite/plugin. |
| `get_telegram_bot_username()` | `str` | Numele de utilizator al botului Telegram (fără `@`). |

---

## 4. Structura Bazei de Date (ORM Models — `app/models/db_models.py`)

VlahX folosește SQLAlchemy ORM peste baza de date SQLite (`db/app.db`).

### A. Tabela `AppSetting` (Setări Globale Site)
* `key` (`String`, Primary Key): Numele setării (ex: `SITE_DISPLAY_NAME`, `HOMEPAGE_MODE`, `STATIC_NAV_LINKS`).
* `value` (`Text`): Valoarea salvată (text sau JSON serializat).

### B. Tabela `PluginSetting` (Setări Per-Plugin)
* `id` (`Integer`, Primary Key): ID unic.
* `plugin_id` (`String`): ID-ul plugin-ului (ex: `"telegram_notify"`, `"google_seo"`).
* `key` (`String`): Numele setării per plugin (ex: `"bot_token"`, `"service_account_json"`).
* `value` (`Text`): Valoarea setării.

### C. Tabela `Post` (Articole & Pagini Statice)
* `id` (`Integer`, Primary Key)
* `slug` (`String`, Unique): Calea URL a articolului (ex: `despre-mine`, `prima-postare`).
* `title` (`String`): Titlul articolului sau al paginii.
* `excerpt` (`Text`): Rezumatul articolului.
* `content_html` (`Text`): Conținutul HTML al articolului.
* `category` (`String`): Categoria (dacă este `"pages"`, `"pagini"` sau `"static"`, este tratată ca pagină statică).
* `draft` (`Boolean`): `True` dacă este ciornă/neactiv.
* `created_at` / `updated_at` (`DateTime`)

### D. Tabela `User` (Utilizatori & Roluri)
* `id` (`Integer`, Primary Key)
* `username` (`String`)
* `first_name` / `last_name` (`String`)
* `role` (`String`): Rolurile utilizatorului (`admin`, `editor`, `seller`, `author`, `reader`, `developer`, `pending`).
* `dev_status` (`String`): Statutul cererii de developer (`pending`, `approved`, `rejected`).
* `dev_notes` (`Text`): Descrierea experienței furnizată de utilizator.
* `provider` (`String`): Metoda de autentificare (`dev`, `telegram`, `google`).

---

## 5. Sistemul de Cârlige (Hooks) & Evenimente (`app/core/`)

VlahX Engine oferă dezvoltatorilor două mecanicisme puternice pentru extinderea aplicației:

### A. Cârlige de Șablon / UI (Template Hooks — `app/core/template_hooks.py`)

Plugin-urile pot injecta HTML/cod direct în interfața administrativă sau în front-end:

```python
from app.core.template_hooks import (
    register_admin_nav,
    register_admin_top_bar,
    register_post_header_meta,
    register_footer_col,
    register_footer_bottom,
    register_user_dropdown,
)

# 1. Adăugare buton în meniul din stânga Admin
def _nav_link(request):
    return '<a href="/admin/plugins/my_plugin" class="nav-link text-white"><span>🚀</span> My Plugin</a>'

register_admin_nav(_nav_link, order=20)

# 2. Injectare tag-uri Meta SEO în <head> pentru articole
def _head_seo(post, request):
    return '<meta name="custom-seo" content="active" />'

register_post_header_meta(_head_seo, order=10)
```

### B. Sistemul de Evenimente (Pub-Sub — `app/core/events.py`)

Reacționează automat la acțiunile din sistem:

```python
from app.core import events

def _on_post_published(**kwargs):
    post_url = kwargs.get("post_url")
    # Cod executat când un articol nou este publicat (ex: trimitere notificare)

events.subscribe("blog.post_published", _on_post_published)
```

Evenimente disponibile:
* `blog.post_published`: Se declanșează la publicarea unui articol nou.
* `user.registered`: Se declanșează la înregistrarea unui utilizator nou.
* `order.created`: Se declanșează la plasarea unei comenzi pe magazin (Minishop).
* `comment.added`: Se declanșează la adăugarea unui comentariu.

---

## 6. Ghid Pas-cu-Pas: Cum Creezi un Plugin VlahX de la Zero

Un plugin VlahX se creează în folderul `app/plugins/<id_plugin>/` și conține minimum două fișiere:

### Pasul 1: Creează `plugin.json` (Manifestul Plugin-ului)
```json
{
  "id": "my_custom_plugin",
  "name": "Plugin-ul Meu Personalizat",
  "description": "Descrierea funcționalităților plugin-ului.",
  "version": "2.0.0",
  "min_engine_version": "2.0.0",
  "author": "Numele Tău",
  "permissions": ["events"],
  "settings": {
    "api_key": {
      "type": "password",
      "label": "Cheie API",
      "description": "Introdu cheia ta API",
      "default": "",
      "required": true
    },
    "enable_feature": {
      "type": "checkbox",
      "label": "Activează Funcționalitatea",
      "default": true
    }
  }
}
```

### Pasul 2: Creează `plugin.py` (Logica & Rutele Plugin-ului)
```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.core.plugin_manager import get_plugin_setting, set_plugin_setting

def register(app: FastAPI, plugin_id: str = "my_custom_plugin") -> None:
    
    @app.get("/admin/plugins/my_custom_plugin", response_class=HTMLResponse)
    async def admin_my_plugin_page(request: Request):
        api_key = get_plugin_setting(plugin_id, "api_key", default="")
        return f"<h1>Plugin-ul Meu</h1><p>Cheie API salvată: {api_key}</p>"
```

---

## 7. Ghid Pas-cu-Pas: Cum Creezi o Temă VlahX de la Zero

O temă VlahX se creează în folderul `app/themes/<slug_temă>/` și conține un manifest `theme.json` și șabloanele Jinja2:

### Pasul 1: Creează `theme.json`
```json
{
  "name": "Numele Temei Tale",
  "slug": "custom-theme-slug",
  "author": "Numele Tău",
  "version": "2.0.0",
  "min_engine_version": "2.0.0",
  "description": "O temă modernă și accesibilă."
}
```

### Pasul 2: Șabloane Jinja2 Necesare
- `templates/base.html`: Structura principală HTML (inclusiv `<head>`, navbar și footer).
- `templates/blog/index.html`: Feed-ul principal de articole.
- `templates/blog/post.html`: Vizualizarea articolului individual.
- `templates/blog/404.html`: Pagina de eroare 404.

---

> [!TIP]
> **Recomandare pentru dezvoltatori**: Pentru a dezvolta un plugin nou, folosiți `get_plugin_setting(plugin_id, key)` și `set_plugin_setting(plugin_id, key, value)` oferite de `app.core.plugin_manager`. Toate setările vor fi salvate automat în SQLite și vor fi ușor de configurat din Admin Panel!
