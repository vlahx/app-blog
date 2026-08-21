# 🎨 Ghidul Tehnic de Creare Teme pentru VlahX Core 2.0
## (Zero Hardcoding & Full Template Architecture Guide)

Acest ghid oferă specificațiile tehnice complete, regulile de dezvoltare și exemplele de cod sursă de referință pentru crearea de **teme 100% dinamice și compatibile** pe platforma **VlahX Core 2.0**.

---

## 🌟 1. Filosofia "Zero Hardcoding" (Regula de Aur)

În VlahX Core 2.0, **NICIO TEMĂ NU TREBUIE SĂ CONȚINĂ TEXTE SAU STRUCTURI HARDCODATE**.

* **Nume Site & Tagline**: Folosește întotdeauna `{{ site_display_name() }}` și `{{ site_tagline() }}` (care suportă traducere și configurare din Admin).
* **Logo / Icon**: Folosește `{{ site_nav_icon_abs }}`. Dacă este setat, afișează `<img>`, altfel afișează un fallback SVG/icon.
* **Comutator de Limbi (Language Switcher)**: În navbar, se include întotdeauna formularul de selectare a limbii din `available_locales` (vezi exemplul din `navbar.html`).
* **Traduceri & Etichete UI**: Folosește cheile oficiale din dicționarul i18n (`ro.json`/`en.json`) precum:
  - `footer.navigation`, `footer.information`, `footer.quickNav`, `footer.adminPanel`, `footer.craftedBy`, `footer.myAccount`
  - `nav.home`, `ui.admin`, `ui.login`, `ui.logout`, `ui.profile`, `blog.author`, `blog.readMore`
  - Folosește `{{ t('cheie') }}` sau `{{ t_safe(translations, 'cheie', 'Fallback') }}`.
* **Credite Autor Temă**: În subsol (footer), folosește combinația:
  `© {{ year }} {{ site_display_name() }}. {{ t('footer.craftedBy') }} {{ theme_author }}.`
  (unde `theme_author` este extras automat din câmpul `author` definit în `theme.json`).

---

## 📁 2. Structura de Foldere & Fișiere a unei Teme

Orice temă VlahX Core 2.0 se creează în directorul `/themes/<theme_slug>/`:

```text
/themes/<theme_slug>/
├── theme.json               # Manifestul și metadatele temei (obligatoriu)
└── templates/               # Override-uri Jinja2 (opționale, dar recomandate)
    ├── base.html            # Layout-ul principal HTML (wrapper)
    ├── blog/
    │   ├── index.html       # Pagina principală / lista de articole
    │   └── post.html        # Pagina individuală a unui articol / pagini statice
    └── partials/
        ├── navbar.html      # Meniul de navigare superior
        └── footer.html      # Subsolul responsive cu 4 coloane
```

Fișierele de stil CSS specifice temei se plasează în `/static/themes/<theme_slug>/theme.css`.

---

## 📜 3. Manifestul Temei (`theme.json`)

Fișierul `theme.json` definește caracteristicile temei tale:

```json
{
  "name": "Elevate Premium",
  "author": "Serge VlahX",
  "version": "2.0.0",
  "min_engine_version": "2.0.0",
  "description": "A modern, sleek dark-mode glassmorphism theme for VlahX Core.",
  "supports_color_scheme_toggle": true
}
```

* **`name`**: Numele vizibil în Panoul de Admin (`/admin/themes`).
* **`author`**: Autorul / creatorul temei.
* **`version`**: Versiunea SemVer a temei (ex: `2.0.0`).
* **`min_engine_version`**: Versiunea minimă de VlahX Core compatibilă.
* **`supports_color_scheme_toggle`**: `true` dacă tema suportă comutare automată Light/Dark.

---

## 📊 4. Contractul de Date (Obiecte & Variabile disponibile în Șabloane)

### A. Obiectul `post` (în `blog/post.html` și `blog/index.html`)

Atributele disponibile pe obiectul `post`:

| Atribut ORM | Tip Date | Descriere |
| :--- | :--- | :--- |
| `post.title` | `str` | Titlul articolului sau paginii. |
| `post.slug` | `str` | Slug-ul URL (ex: `despre-noi`, `prima-postare`). |
| `post.excerpt` | `str` | Textul scurt / rezumatul articolului. |
| `post.content_html` | `str` | Conținutul HTML complet al articolului. |
| `post.category` | `str \| None` | Numele categoriei (ex: `"Noutăți"`). Dacă nu există sau este `None`, nu se afișează insigna. |
| `post.hero_image_url` | `str \| None` | Calea URL a imaginii principale de fundal/banner (ex: `/static/uploads/users/1/blog/hero.jpg`). |
| `post.image_url` | `str \| None` | Imaginea miniatură (thumbnail). |
| `post.images_url_json` | `str \| None` | Array JSON cu imagini secundare pentru galerie. |
| `post.meta_keywords` | `str \| None` | Cuvinte cheie SEO pentru tag-ul `<meta name="keywords">`. |
| `post.author_name` | `str \| None` | Numele complet al autorului (ex: `"Serge VlahX"`). |
| `post.author_id` | `int \| None` | ID-ul unic al autorului în baza de date. |
| `post.published_at` | `datetime` | Data publicării în format local (ex: `post.published_at.strftime("%d %B %Y")`). |
| `post.published_at_utc` | `datetime` | Data publicării în format UTC pentru tag-uri OpenGraph / SEO ISO. |
| `post.draft` | `bool` | `True` dacă articolul este în stare de ciornă (Draft). |

---

### B. Variabile & Helper-e Globale în Contextul Jinja2

Disponibile automat în toate fișierele `.html`:

| Variabilă / Helper | Tip | Descriere |
| :--- | :--- | :--- |
| `user` | `User \| None` | Obiectul utilizatorului autentificat (sau `None` dacă este vizitator). |
| `has_role(*roles)` | `func` | Helper securizat pentru verificare roluri: `{% if has_role('admin', 'editor', 'author', 'developer', 'seller') %}`. |
| `available_locales` | `list[dict]` | Limbi active pe site (`[{'code': 'ro', 'name': 'Română'}, {'code': 'en', 'name': 'English'}]`). |
| `current_locale` | `str` | Codul limbii curente (ex: `'ro'`). |
| `fixed_nav_posts` | `list[dict]` | Pagini statice fixate în meniu (`[{'label': 'Despre', 'href': '/despre'}]`). |
| `site_nav_icon_abs` | `str \| None` | URL-ul absolut pentru iconița/logo-ul brandului. |
| `post_header_meta_html` | `str` | HTML injectat automat de plugin-uri pentru articole (Tag-uri SEO, Vizualizări Analytics, Timp citire). |
| `post_article_footer_html` | `str` | HTML injectat automat sub articole (Modul de Comentarii, Formular Newsletter). |

---

## 🧩 5. Lista Completă a Cârligelor de Plugin (`plugin_area_*`)

Pentru ca toate plugin-urile existente (Comentarii, Magazin, Forum, SEO, Analytics, Newsletter) să funcționeze pe tema ta, **TREBUIE să păstrezi aceste cârlige în șabloane**:

```html
<!-- În <head> -->
{{ plugin_area_head | safe }}

<!-- În Navbar <ul class="navbar-nav"> -->
{{ plugin_area_navbar_links | safe }}

<!-- În User Dropdown Menu <ul> -->
{{ plugin_area_user_dropdown | safe }}

<!-- În Main Body / Homepage -->
{{ plugin_area_main_content | safe }}

<!-- În Antetul Articolului (post.html) -->
{{ post_header_meta_html | safe }}
{{ plugin_area_article_header | safe }}

<!-- Sub Conținutul Articolului (post.html) -->
{{ plugin_area_article_footer | safe }}
{{ post_article_footer_html | safe }}

<!-- În Footer (Coloanele 1-4 și Bottom) -->
{{ plugin_area_footer_col1 | safe }}
{{ plugin_area_footer_col2 | safe }}
{{ plugin_area_footer_col3 | safe }}
{{ plugin_area_footer_col4 | safe }}
{{ plugin_area_footer_bottom | safe }}

<!-- În Profil Utilizator (profile.html) -->
{{ plugin_area_profile_tabs | safe }}
{{ plugin_area_profile_content | safe }}
```

---

## 📐 6. Șabloane de Referință (Exemple Complete de Cod)

### A. `templates/base.html` (Wrapper Principal)

```html
<!DOCTYPE html>
<html lang="{{ lang|default('ro') }}" data-bs-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}{{ seo_title or title or site_display_name() }}{% endblock %}</title>
  
  <!-- Primary Meta Tags & SEO -->
  <meta name="description" content="{{ seo_description or meta_description or site_tagline() }}">
  {% if meta_keywords %}<meta name="keywords" content="{{ meta_keywords|e }}">{% endif %}
  <link rel="canonical" href="{{ seo_canonical or request.url }}">
  <meta name="theme-color" content="#10b981">
  
  <!-- Open Graph / Facebook & Social Share -->
  <meta property="og:type" content="{{ seo_type or 'website' }}">
  <meta property="og:url" content="{{ seo_canonical or share_url or request.url }}">
  <meta property="og:title" content="{{ seo_title or title or site_display_name() }}">
  <meta property="og:description" content="{{ seo_description or meta_description or site_tagline() }}">
  {% if seo_image %}<meta property="og:image" content="{{ seo_image }}">{% endif %}
  {% if seo_image_alt %}<meta property="og:image:alt" content="{{ seo_image_alt }}">{% endif %}
  {% if site_nav_icon_abs %}<meta property="og:logo" content="{{ site_nav_icon_abs }}">{% endif %}

  <!-- Twitter Cards -->
  <meta name="twitter:card" content="{% if seo_image_is_card %}summary_large_image{% else %}summary{% endif %}">
  <meta name="twitter:url" content="{{ seo_canonical or share_url or request.url }}">
  <meta name="twitter:title" content="{{ seo_title or title or site_display_name() }}">
  <meta name="twitter:description" content="{{ seo_description or meta_description or site_tagline() }}">
  {% if seo_image %}<meta name="twitter:image" content="{{ seo_image }}">{% endif %}

  <!-- Favicon & Icons -->
  {% if site_nav_icon_abs %}
    <link rel="icon" href="{{ site_nav_icon_abs }}">
    <link rel="apple-touch-icon" href="{{ site_nav_icon_abs }}">
  {% endif %}

  <!-- Bootstrap 5 CSS & Iconițe -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  
  <!-- Plugin Head Hook -->
  {% if plugin_area_head %}
    {{ plugin_area_head | safe }}
  {% endif %}
  
  {% block head_extra %}{% endblock %}
</head>
<body class="bg-body text-body d-flex flex-column min-vh-100 theme-{{ active_theme|default('minimal') }}">

  <!-- Top Navbar Partial -->
  {% include "partials/navbar.html" ignore missing %}

  <!-- Main Body Content -->
  <main class="flex-grow-1">
    {% block content %}{% endblock %}
  </main>

  <!-- Footer Partial -->
  {% include "partials/footer.html" ignore missing %}

  <!-- Bootstrap 5 JS Bundle -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  {% block scripts_extra %}{% endblock %}
</body>
</html>
```

---

### B. `templates/partials/navbar.html` (Meniu Navigare)

```html
<header class="navbar navbar-expand-lg border-bottom sticky-top bg-body-tertiary">
  <div class="container-fluid px-4 py-2">
    
    <!-- Brand Logo & Name -->
    <a class="navbar-brand fw-bold d-flex align-items-center gap-2" href="/">
      {% if site_nav_icon_abs %}
        <img src="{{ site_nav_icon_abs|e }}" width="28" height="28" alt="" style="object-fit:contain" />
      {% else %}
        <span class="fs-4">⚡</span>
      {% endif %}
      <span>{{ site_display_name() }}</span>
    </a>

    <!-- Mobile Toggle Button -->
    <button class="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
      <span class="navbar-toggler-icon"></span>
    </button>

    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav ms-auto align-items-lg-center gap-2">
        
        <!-- Fixed Header Navigation Links -->
        {% if fixed_nav_posts %}
          {% for nav_p in fixed_nav_posts %}
          <li class="nav-item">
            <a class="nav-link py-1 px-3 border rounded-pill bg-body-tertiary" href="{{ nav_p.href or nav_p.url }}">
              {{ nav_p.fixed_label or nav_p.label }}
            </a>
          </li>
          {% endfor %}
        {% endif %}

        <!-- Plugin Area for Navbar Links -->
        {% if plugin_area_navbar_links %}
          {{ plugin_area_navbar_links | safe }}
        {% endif %}

        <!-- User Authentication & Dropdown -->
        {% if user %}
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle d-flex align-items-center gap-2 py-1 px-3 border rounded-pill" href="#" data-bs-toggle="dropdown">
            {% if user.image_url %}
              <img src="{{ user.image_url }}" alt="" class="rounded-circle" width="24" height="24">
            {% else %}
              <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold" style="width:24px; height:24px; font-size:0.75rem;">
                {{ (user.first_name or user.username or 'U')[0]|upper }}
              </div>
            {% endif %}
            <span class="fw-semibold small">{{ user.first_name or user.username }}</span>
          </a>
          <ul class="dropdown-menu dropdown-menu-end shadow border-0 rounded-3 mt-1">
            <li><a class="dropdown-item" href="/profile">👤 {{ t('ui.profile') if t else 'Profilul meu' }}</a></li>
            {% if plugin_area_user_dropdown %}
              {{ plugin_area_user_dropdown | safe }}
            {% endif %}
            {% if has_role('admin', 'editor', 'author', 'seller', 'developer') %}
              <li><hr class="dropdown-divider"></li>
              <li><a class="dropdown-item fw-semibold text-primary" href="/admin">⚡ {{ t('ui.admin') if t else 'Panou Admin' }}</a></li>
              <li><a class="dropdown-item" href="/admin/new">✍️ {{ t('ui.new_post') if t else 'Articol Nou' }}</a></li>
            {% endif %}
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item text-danger" href="/auth/logout">🚪 {{ t('ui.logout') if t else 'Deconectare' }}</a></li>
          </ul>
        </li>
        {% else %}
        <li class="nav-item">
          <a class="btn btn-sm btn-primary rounded-pill px-3 fw-semibold" href="/admin/login">
            🔑 {{ t('ui.login') if t else 'Autentificare' }}
          </a>
        </li>
        {% endif %}

      </ul>
    </div>
  </div>
</header>
```

---

### C. `templates/partials/footer.html` (Subsol 4 Coloane)

```html
<footer class="border-top py-5 bg-body-tertiary mt-auto">
  <div class="container px-4">
    <div class="row g-4">
      
      <!-- Col 1: Brand & Description -->
      <div class="col-lg-3 col-md-6">
        <h5 class="fw-bold mb-3">{{ site_display_name() }}</h5>
        <p class="text-secondary small mb-3">{{ site_tagline() }}</p>
        {% if plugin_area_footer_col1 %}
          {{ plugin_area_footer_col1 | safe }}
        {% endif %}
      </div>

      <!-- Col 2: Navigation & Quick Links -->
      <div class="col-lg-3 col-md-6">
        <h5 class="fw-bold mb-3">{{ t('footer.navigation') if t else 'Navigare' }}</h5>
        <ul class="list-unstyled small d-flex flex-column gap-2">
          <li><a href="/" class="text-decoration-none text-secondary">🏠 {{ t('nav.home') if t else 'Acasă' }}</a></li>
        </ul>
        {% if plugin_area_footer_col2 %}
          {{ plugin_area_footer_col2 | safe }}
        {% endif %}
      </div>

      <!-- Col 3: User Management -->
      <div class="col-lg-3 col-md-6">
        <h5 class="fw-bold mb-3">{{ t('footer.management') if t else 'Cont & Admin' }}</h5>
        <ul class="list-unstyled small d-flex flex-column gap-2">
          {% if user %}
            <li><a href="/profile" class="text-decoration-none text-secondary">👤 {{ t('footer.myAccount') if t else 'Contul Meu' }}</a></li>
            {% if has_role('admin', 'editor', 'author', 'seller', 'developer') %}
              <li><a href="/admin" class="text-decoration-none text-secondary">⚡ {{ t('footer.adminPanel') if t else 'Panou Admin' }}</a></li>
            {% endif %}
          {% else %}
            <li><a href="/admin/login" class="text-decoration-none text-secondary">🔑 {{ t('ui.login') if t else 'Autentificare' }}</a></li>
          {% endif %}
        </ul>
        {% if plugin_area_footer_col3 %}
          {{ plugin_area_footer_col3 | safe }}
        {% endif %}
      </div>

      <!-- Col 4: Legal & Badges -->
      <div class="col-lg-3 col-md-6">
        <h5 class="fw-bold mb-3">{{ t('footer.information') if t else 'Informații' }}</h5>
        {% if plugin_area_footer_col4 %}
          {{ plugin_area_footer_col4 | safe }}
        {% endif %}
      </div>

    </div>

    <!-- Footer Bottom Bar -->
    <div class="border-top mt-4 pt-4 d-flex flex-wrap justify-content-between align-items-center small text-secondary">
      <div>
        © {{ year }} {{ site_display_name() }}. {{ t('footer.craftedBy') if t else 'Creat cu ❤️ de' }} {{ theme_author }}.
      </div>
      {% if plugin_area_footer_bottom %}
        <div>{{ plugin_area_footer_bottom | safe }}</div>
      {% endif %}
    </div>
  </div>
</footer>
```

---

### D. `templates/blog/post.html` (Pagina de Articol cu Imagine Banner Hero)

```html
{% extends "base.html" %}

{% block title %}{{ post.title }} — {{ site_display_name() }}{% endblock %}

{% block head_extra %}
  {% if post.published_at_utc %}
    <meta property="article:published_time" content="{{ post.published_at_utc.strftime('%Y-%m-%dT%H:%M:%SZ')|e }}" />
  {% endif %}
{% endblock %}

{% block content %}
<div class="container px-3 px-md-4 py-4 py-md-5">
  <article class="row justify-content-center">
    <div class="col-lg-9 col-xl-8">
      
      <!-- Back Link -->
      <nav class="mb-3">
        <a href="/" class="text-decoration-none text-secondary">← {{ t('home.postPage.backToBlog') if t else 'Înapoi la articole' }}</a>
      </nav>

      <!-- Category & Metadata Header Bar -->
      <div class="mb-3 d-flex flex-wrap align-items-center gap-2">
        {% if post.category and post.category.lower() not in ['none', 'null', 'uncategorized', ''] %}
          <span class="badge text-bg-primary rounded-pill px-3 py-2 fs-6">{{ post.category }}</span>
        {% endif %}
        {% if post.author_name %}
          <span class="text-secondary small fw-semibold">✍️ {{ t('blog.author') if t else 'Autor' }}: {{ post.author_name }}</span>
        {% endif %}
        {% if post.published_at %}
          <span class="text-secondary small">• 📅 {{ post.published_at.strftime("%d.%m.%Y") }}</span>
        {% endif %}
        {% if post_header_meta_html %}
          {{ post_header_meta_html | safe }}
        {% endif %}
        {% if post.draft %}
          <span class="badge text-bg-warning">Draft</span>
        {% endif %}
      </div>

      <!-- Article Title -->
      <h1 class="display-4 fw-bold mb-4">{{ post.title }}</h1>

      <!-- Hero Banner Image (if available) -->
      {% if post.hero_image_url %}
      <div class="mb-4 overflow-hidden rounded-4 shadow">
        <img src="{{ post.hero_image_url }}" alt="{{ post.title }}" class="w-100 object-fit-cover" style="max-height: 450px;">
      </div>
      {% endif %}

      <!-- Plugin Area Header -->
      {% if plugin_area_article_header %}
      <div class="mb-4">
        {{ plugin_area_article_header | safe }}
      </div>
      {% endif %}

      <!-- Article Excerpt -->
      {% if post.excerpt %}
      <div class="lead text-secondary mb-4 fst-italic">
        {{ post.excerpt }}
      </div>
      {% endif %}

      <!-- Main Article HTML Body -->
      <div class="article-body lh-lg fs-5 mb-5">
        {{ post.content_html | safe }}
      </div>

      <!-- Plugin Area Article Footer (Comments & Newsletter) -->
      {% if plugin_area_article_footer %}
      <div class="my-4">
        {{ plugin_area_article_footer | safe }}
      </div>
      {% endif %}
      {% if post_article_footer_html %}
      <div class="my-4">
        {{ post_article_footer_html | safe }}
      </div>
      {% endif %}

    </div>
  </article>
</div>
{% endblock %}
```

---

## 📦 7. Împachetarea & Instalarea Temei în Admin Panel

1. Arhivează structura temei tale într-un fișier `.zip`:
   ```bash
   zip -r theme-elevate.zip themes/elevate static/themes/elevate
   ```
2. Mergi în **Panoul de Admin** ➡️ **Teme** (`/admin/themes`).
3. Încarcă `theme-elevate.zip` la secțiunea **Încarcă Temă**.
4. Apasă **Activează** în dreptul temei încărcate!
