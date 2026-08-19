# 🎨 Guide: How to Create a Custom Theme for VlahX Core 2.0

This guide explains step-by-step how to design, build, package, and install a custom theme for **VlahX Core 2.0**.

---

## 📁 1. Theme Directory Architecture

Every theme in VlahX Core 2.0 lives in two clean locations:

```text
/themes/<theme_slug>/
├── theme.json               # Required theme manifest & metadata
└── templates/               # Custom Jinja2 template overrides (optional)
    ├── base.html            # Main site wrapper
    ├── blog/                # Article list and post view overrides
    └── partials/
        ├── navbar.html      # Top navigation header
        └── footer.html      # 4-column responsive footer

/static/themes/<theme_slug>/
└── theme.css                # Custom CSS stylesheet for your theme
```

---

## 📜 2. Theme Manifest (`theme.json`)

Create a `theme.json` file inside `/themes/<theme_slug>/`:

```json
{
  "name": "Dark Mode",
  "author": "Your Name",
  "version": "1.0.0",
  "supports_color_scheme_toggle": true
}
```

- **`name`**: Display name shown in Admin panel (`/admin/themes`).
- **`author`**: Theme creator.
- **`version`**: Theme semantic version (e.g. `1.0.0`).
- **`supports_color_scheme_toggle`**: Set `true` if your CSS supports automatic light/dark mode switching.

---

## 🎨 3. Styling Your Theme (`theme.css`)

Create a `theme.css` inside `/static/themes/<theme_slug>/theme.css`.

When your theme is active, the app automatically adds the CSS class `.theme-<theme_slug>` to the `<body>` element and links your `theme.css` in the `<head>`.

### Example Dark Mode CSS (`/static/themes/dark/theme.css`):

```css
:root {
  --bs-body-bg: #0f1117;
  --bs-body-color: #e2e8f0;
  --bs-border-color: #2a2f42;
}

body.theme-dark {
  background-color: #0f1117 !important;
  color: #e2e8f0 !important;
  font-family: 'Inter', sans-serif;
}

.theme-dark .navbar {
  background-color: rgba(15, 17, 23, 0.85) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #2a2f42 !important;
}

.theme-dark .card,
.theme-dark .card-modern {
  background-color: #161922 !important;
  border: 1px solid #2a2f42 !important;
  color: #e2e8f0 !important;
}

.theme-dark a {
  color: #818cf8;
}
```

---

## 🧩 4. Preserving `plugin_area` Hooks (Crucial Rule)

To ensure all installed plugins (e.g. Comments, Newsletter, Shop, Forum) continue working seamlessly on your custom theme, **your template overrides MUST include the standard `plugin_area` slot hooks**:

### Key `plugin_area` Slots:

| Slot Hook Name | Location in Template | Usage |
| :--- | :--- | :--- |
| `plugin_area_head` | In `<head>` before `</head>` | Analytics, custom fonts, meta tags |
| `plugin_area_navbar_links` | In Navbar `<ul class="navbar-nav">` | Dynamic top menu items |
| `plugin_area_user_dropdown` | In User Dropdown Menu | Dynamic profile dropdown actions |
| `plugin_area_main_content` | Inside `<main>` body | Homepage or section takeover |
| `plugin_area_article_header` | Above post content | Author bio, share buttons |
| `plugin_area_article_footer` | Below post content | Comments widget, Newsletter box |
| `plugin_area_footer_col1` | Footer Column 1 | Newsletter widget, brand badges, social links |
| `plugin_area_footer_col2` | Footer Column 2 | Dynamic quick links (Shop categories, Sitemap) |
| `plugin_area_footer_col3` | Footer Column 3 | User management links (Orders, Account) |
| `plugin_area_footer_col4` | Footer Column 4 | System info & Legal badges (GDPR, ANPC) |
| `plugin_area_footer_bottom` | Footer Copyright Bar | Legal terms, cookie consent policy link |
| `plugin_area_profile_tabs` | In Profile Nav Pills | Dynamic user profile tabs |
| `plugin_area_profile_content` | In Profile Tab Content | Profile tab panel views |

---

## 📦 5. Packaging & Installing via Admin Panel

To distribute your theme or install it on production:

1. Create a `.zip` archive containing your theme structure:
   ```bash
   zip -r dark-theme.zip themes/dark static/themes/dark
   ```
2. Go to **Admin Panel** ➡️ **Themes** (`http://127.0.0.1:8000/admin/themes`).
3. Upload `dark-theme.zip` under **Upload Theme**.
4. Click **Activate** next to your uploaded theme!

---

## 🛡️ 6. Admin Panel Isolation Guarantee

Changing your theme **will NEVER break or alter the Admin Panel (`/admin/*`)**. The Admin dashboard uses an isolated management layout in `templates/admin/` to ensure full stability regardless of custom frontend themes.
