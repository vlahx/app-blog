## Plugin-uri

### Structură

- Director **în runtime** (pe server / volum): `plugins/<id>/`
- Cod: `plugins/<id>/plugin.py` cu funcția **`register(app: FastAPI) -> None`**
- Opțional: `plugins/<id>/plugin.json` (metadate în Admin)

Sursele oficiale pentru pluginurile „stock” (robots, sitemap) stau în repo sub **`packaging/plugins/<id>/`** — nu sunt încărcate automat; le instalezi prin zip (vezi mai jos).

### Încărcare

La pornire, `app/core/plugins.py` parcurge `plugins/*/plugin.py` și apelează `register(app)` pentru fiecare modul valid.

Erorile dintr-un plugin sunt logate; restul aplicației pornește.

### Cârlige în șablon (sub articol)

`app/core/template_hooks.py`: `register_post_article_footer(fn, order=…)` — fragmente HTML concatenate în cardul de sub conținutul articolului (`post_article_footer_html` în `blog/post.html`). `order` mic = mai sus în card. Ex.: plugin **`share`** (order 10) + **`newsletter`** (order 20) pentru același card ca înainte.

### Arhive pentru Admin

Din rădăcina proiectului:

```bash
python3 scripts/build_plugin_zips.py
```

Rezultat: `dist/plugins/*.zip` (ex. `robots`, `sitemap`, `share`, `newsletter`, `telegram_notify`) — le urci în **Admin → Plugin-uri**, apoi **restart** container.

### Instalare din Admin

- **Admin → Plugin-uri**: upload `.zip` sau ștergere folder plugin.
- Zip acceptat:
  - `plugins/<id>/plugin.py` (+ `plugin.json` opțional), sau
  - un singur folder la rădăcină: `<id>/plugin.py`
- După **upload** sau **ștergere**: **repornește** containerul / procesul — rutele se înregistrează doar la startup.
- Opțional: în `.env` setezi `ADMIN_ENABLE_CONTAINER_RESTART=true` (și `restart: unless-stopped` în compose); în **Admin → Plugin-uri** apare butonul care oprește procesul ca Docker să repornească containerul.

### Exemplu: share

Partajare articol sub conținut; servește `share.js` la `/static/plugin-assets/share/share.js`. Stilurile rămân în `static/site.css` (`.share-toast`, `.share-offscreen`). Surse: `packaging/plugins/share/`.

### Exemplu: robots

Înregistrează `GET /robots.txt` (fișier `robots.txt` din rădăcina proiectului sau fallback text). Surse: `packaging/plugins/robots/`.

### Exemplu: sitemap

Servește `GET /sitemap.xml`: pagina principală + toate postările **publicate** (nu draft), cu URL-uri din `post_public_path`. Baza URL: `PUBLIC_SITE_URL` din `.env` dacă e setat, altfel hostul din request. Surse: `packaging/plugins/sitemap/`.

### Newsletter + Telegram

- **`newsletter`**: `GET /newsletter`, `POST /newsletter/subscribe`; abonați în `plugins/newsletter/subscribers.jsonl`; **`newsletter.subscribed`** (notificare admin la abonare). **`blog.post_published`** (emis din nucleu la publicare sau draft→publicat): e-mail către abonați dacă e bifat **Notifică abonații la articol nou**. SMTP: **Admin → Newsletter** (STARTTLS, cert self-signed, etc.) sau `.env` (`NEWSLETTER_*`).
- **`telegram_notify`**: se abonează la acel eveniment și trimite un mesaj pe Telegram dacă botul și chat ID-ul sunt configurate — din **Admin → Plugin-uri** (salvat în `app_settings`) sau din **`.env`** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_NOTIFY_CHAT_ID`, `TELEGRAM_BOT_USERNAME` pentru login). Tokenul din baza de date are prioritate față de `.env`.
- Nucleul expune **`app/core/events.py`** (`subscribe` / `publish`) ca alte pluginuri sau cod viitor să emită evenimente fără dependență de ordinea de încărcare a zip-urilor.

### Următorii pași posibili

- index sitemap / împărțire la multe URL-uri
- listare plugin-uri în admin (citire `plugin.json`)
- enable/disable per plugin în `site_settings.json`
