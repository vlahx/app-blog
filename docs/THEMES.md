## Teme (Themes)

Acest proiect separă **core-ul** (schelet stabil + SEO) de **temă** (layout/UI + stiluri).

### Principii
- **Core-ul** rămâne stabil: SEO/OG/canonical, structura generală a paginii și sloturile (blocks).
- **Tema** decide layout-ul vizual (navbar/footer etc.) și poate suprascrie template-uri specifice (post, index, 404).
- **Fallback garantat**: dacă tema activă nu are template-urile necesare, aplicația cade pe tema `default`.

### Structura directoarelor

#### 1) Template-uri (Jinja)
Template-urile unei teme stau în:

- `themes/<theme_slug>/templates/`

Tema `default` (layout-ul de bază) este în:

- `themes/default/templates/`

Core-ul (scheletul stabil) este în:

- `templates/core/shell.html`

Toate paginile existente folosesc:

- `{% extends "base.html" %}`

Iar `base.html` este oferit de tema curentă (sau fallback pe `themes/default`).

#### 2) Assets (CSS/JS/imagini)
În momentul de față, stilul unei teme este încărcat din:

- `static/themes/<theme_slug>/theme.css`

În `themes/default/templates/partials/head.html` există logica:

- dacă tema activă nu e `default`, include automat `/static/themes/<theme_slug>/theme.css`.

### theme.json (manifest)
Fiecare temă poate avea:

- `themes/<theme_slug>/theme.json`

Exemplu:

```json
{
  "name": "Minimal",
  "author": "Camionagiul",
  "version": "0.1.0",
  "supports_color_scheme_toggle": false
}
```

Chei folosite:
- **name**: nume afișat (footer + Admin → Setări).
- **author**: autor (footer + Admin → Setări).
- **version**: informativ.
- **supports_color_scheme_toggle**:
  - `true`: apare butonul de comutare light/dark în navbar
  - `false`: butonul e ascuns (teme care nu au paletă completă pentru ambele moduri)

### Instalare temă

#### Variantă A: „CSS-only theme” (cel mai simplu)
Tema schimbă doar stilurile, păstrând layout-ul `default`.

1) Creezi:
- `themes/<slug>/theme.json`
2) Creezi:
- `static/themes/<slug>/theme.css`
3) (opțional) creezi și `themes/<slug>/templates/` gol — pentru organizare
4) În Admin → Setări, alegi tema `<slug>`.

Rezultat:
- **Layout**: din `default` (fallback).
- **Skin**: din `static/themes/<slug>/theme.css`.

#### Variantă B: „Full theme” (templates + CSS)
1) Creezi:
- `themes/<slug>/templates/base.html` (de obicei extinde `templates/core/shell.html`)
2) (opțional) suprascrii pagini:
- `themes/<slug>/templates/blog/post.html`
- `themes/<slug>/templates/blog/index.html`
- `themes/<slug>/templates/blog/404.html`
3) Creezi:
- `static/themes/<slug>/theme.css`
4) Alegi tema din Admin.

### Override de pagini (exemple)

#### Override pentru post:
- default: `templates/blog/post.html`
- theme: `themes/<slug>/templates/blog/post.html`

#### Override pentru index:
- default: `templates/blog/index.html`
- theme: `themes/<slug>/templates/blog/index.html`

### Contract (sloturi/blocuri)
Core-ul definește în `templates/core/shell.html`:
- `head_assets`
- `head_extra`
- `navbar`
- `content`
- `footer`
- `scripts`
- `scripts_extra`

Tema `default` oferă `base.html` și partialele de bază.

### Despre „tema într-un singur director”
În prezent, o temă este împărțită în două zone:
- `themes/<slug>/...` (manifest + templates)
- `static/themes/<slug>/theme.css` (assets servite public)

Dacă vrei ca un autor extern să livreze tema „într-un singur folder”, recomandarea practică este să livreze un pachet care conține ambele rădăcini (ex. zip cu folderele `themes/` și `static/`), iar la instalare se copiază în proiect în locurile corespunzătoare.

Dacă vrei să schimbăm arhitectura ca asset-urile unei teme să fie servite direct din `themes/<slug>/assets/` (fără `static/themes`), trebuie un mic mecanism suplimentar de static mounting/routing — îl putem face, dar e un pas separat.

