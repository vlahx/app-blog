# Ghidul Dezvoltatorului VlahX Engine (v2.0 Core)
## Arhitectură, API-uri, Variabile & Sistem de Plugin-uri

Acest ghid oferă documentația tehnică completă a platformei **VlahX Core 2.0**. Orice dezvoltator poate folosi acest document pentru a înțelege structura aplicației și pentru a crea **plugin-uri** și **teme** personalizate.

---

## 1. Concepte de Baza & Filosofia VlahX Core 2.0

* **Tehnologii Core**: Python (FastAPI), Jinja2 Templates, SQLite (`db/app.db`), Vanilla CSS/Bootstrap 5, JavaScript.
* **Single Source of Truth**: Toate setările globale ale aplicației sunt stocate în tabela SQLite `app_settings` (sub formă de cheie-valoare), eliminând fișierele temporare `.json`.
* **Arhitectură Modulară (Plugin-driven)**: Orice funcționalitate avansată (SEO, Notificări Telegram, Analytics, Magazin, Sitemap) este încapsulată într-un plugin decuplat.

---

## 2. Constante & Ajutoare Globale (`app/core/config.py`)

Aceste funcții helper pot fi apelate din orice plugin sau ruter pentru a citi dinamic setările site-ului:

| Funcție Helper | Returnează | Descriere & Utilitate |
| :--- | :--- | :--- |
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

## 3. Structura Bazei de Date (ORM Models — `app/models/db_models.py`)

VlahX Core 2.0 folosește SQLAlchemy ORM peste baza de date SQLite (`db/app.db`).

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
* `excerpt` (`Text`): Rezumatul / introducerea articolului.
* `content_html` (`Text`): Conținutul HTML al articolului.
* `category` (`String`): Categoria articolului (ex: `"Noutăți"`).
* `hero_image_url` (`String`): Imaginea banner principală (Hero image URL).
* `image_url` (`String`): Imaginea miniatură (thumbnail).
* `images_url_json` (`Text`): JSON array cu imagini suplimentare pentru galerie.
* `meta_keywords` (`String`): Cuvinte cheie SEO.
* `author_id` (`Integer`): ID-ul utilizatorului autor.
* `author_name` (`String`): Numele complet al autorului.
* `published_at` (`DateTime`): Data publicării locale.
* `published_at_utc` (`DateTime`): Data publicării în format UTC.
* `draft` (`Boolean`): `True` dacă este ciornă/neactiv.
* `created_at` / `updated_at` (`DateTime`)

### D. Tabela `User` (Utilizatori & Roluri)
* `id` (`Integer`, Primary Key)
* `username` (`String`)
* `first_name` / `last_name` (`String`)
* `role` (`String`): Rolurile utilizatorului (`admin`, `editor`, `seller`, `author`, `reader`, `developer`, `pending`).
* `provider` (`String`): Metoda de autentificare (`dev`, `telegram`, `google`).
* `oauth_id` (`String`): ID-ul unic transmis de furnizorul OAuth.

---

## 4. Sistemul de Carlige (Hooks) & Evenimente (`app/core/`)

VlahX Core 2.0 oferă dezvoltatorilor două mecanicisme puternice pentru extinderea aplicației:

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

## 5. Ghid Pas-cu-Pas: Cum Creezi un Plugin VlahX de la Zero

Un plugin VlahX se creează în folderul `app/plugins/<id_plugin>/` și conține minimum două fișiere:

### Pasul 1: Creează `plugin.json` (Manifestul Plugin-ului)
```json
{
  "id": "my_custom_plugin",
  "name": "Plugin-ul Meu Personalizat",
  "description": "Descrierea funcționalităților plugin-ului.",
  "version": "1.0.0",
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

## 6. Lista Rutelor API ale Aplicației Core

### A. Rute Publice (Front-End)
* `GET /` — **Root Router Dinamic**: Randează automat Feed-ul de Blog, Pagina Statică setată în Admin, sau Magazinul Online (`minishop`).
* `GET /blog` — Feed-ul de articole ale blogului (când prima pagină este setată pe o pagină statică).
* `GET /blog/{slug}` (sau `GET /{slug}`) — Vizualizare articol individual.
* `POST /lang` — Schimbare dinamică de limbă (`locale` + `next`).

### B. Rute de Autentificare (`/auth`)
* `GET /admin/login` — Interfața de alegere a metodei de autentificare (Telegram / Google).
* `GET /admin/login/telegram` — Callback-ul verificat pentru Telegram Login Widget.
* `GET /dev/login` — Autentificare rapidă pentru dezvoltare și instalare inițială.
* `GET /auth/logout` — Deconectare utilizator și distrugere sesiune.

### C. Rute de Administrare (`/admin`)
* `GET /admin` — Panou de control și statistici generale.
* `GET /admin/settings` & `POST /admin/settings/save` — Gestionare setări site (nume, slogan, prima pagină, meniu navbar personalizat, imagnie brand/favicon).
* `GET /admin/users` & `POST /admin/users/{user_id}/role` — Gestionare utilizatori și roluri.
* `GET /admin/themes` & `POST /admin/themes/activate` — Gestionare teme instalate.
* `GET /admin/plugins` & `POST /admin/plugins/toggle` — Activare/dezactivare plugin-uri.

---

## 7. Roadmap & To-Do Ecosystem (Repository API & Developer Portal)

> [!NOTE]
> - [ ] **Subdomeniu & Microserviciu dedicat `repo.vlahx.org`**:
>   - Container Docker izolat (Microserviciu fără frontend HTML) dedicat 100% API-urilor JSON.
>   - Endpoint-uri: `GET /v1/plugins`, `GET /v1/themes`, `GET /v1/check-updates`, `POST /v1/submit`.
> - [ ] **Flux de Comunitate stil Linux (AUR / Apt)**:
>   - *Testing / Beta*: Pachete trimise de comunitate în curs de verificare.
>   - *Verified / Stable*: Pachete verificate și validate pentru producție.
> - [ ] **Instalare 1-Click din Admin Panel**:
>   - Tab-ul *Magazin & Comunitate (1-Click)* în `/admin/plugins` și `/admin/themes` din VlahX Core 2.0.
>   - Descărcare automată pachet zip, verificare SHA256, dezarhivare și activare pe loc.
> - [ ] **Rolul `developer` și Developer Portal**:
>   - Frontend-ul web `repo.vlahx.org` este rezervat ca **Developer Portal** pentru utilizatorii cu rolul `developer` (pentru trimitere pachete, vizualizare statistici și chei API).
>   - Acces extins pe **Forumul Tehnic VlahX**.

---

> [!TIP]
> **Recomandare pentru dezvoltatori**: Pentru a dezvolta un plugin nou, folosiți `get_plugin_setting(plugin_id, key)` și `set_plugin_setting(plugin_id, key, value)` oferite de `app.core.plugin_manager`. Toate setările vor fi salvate automat în SQLite și vor fi ușor de configurat din Admin Panel!
