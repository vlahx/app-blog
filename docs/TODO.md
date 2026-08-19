# 📌 Future Roadmap & TODO List — VlahX Core 2.0

Lista de funcționalități și îmbunătățiri planificate pentru ciclurile viitoare de dezvoltare.

---

## 🔮 Planuri de Viitor (Future To-Do)

### 1. 🏬 VlahX Ecosystem 1-Click Repository API (`repo.vlahx.org`) & Community Marketplace
- **Subdomeniu & Microserviciu dedicat `repo.vlahx.org`**:
  - Container Docker izolat (Microserviciu fără frontend HTML) dedicat 100% API-urilor JSON REST (`GET /v1/plugins`, `GET /v1/themes`, `GET /v1/check-updates`, `POST /v1/submit`).
- **Flux de Comunitate stil Linux (AUR / Apt)**:
  - *Testing / Beta*: Pachete trimise de comunitate în curs de verificare.
  - *Verified / Stable*: Pachete verificate și validate pentru producție.
- **Instalare 1-Click din Admin Panel**:
  - Tab-ul *Magazin & Comunitate (1-Click)* în `/admin/plugins` și `/admin/themes` din VlahX Core 2.0.
  - Descărcare automată pachet zip, verificare SHA256, dezarhivare și activare pe loc.
- **Rolul `developer` și Developer Portal**:
  - Frontend-ul web `repo.vlahx.org` este rezervat ca **Developer Portal** pentru utilizatorii cu rolul `developer` (pentru trimitere pachete, vizualizare statistici și chei API).
  - Acces extins pe **Forumul Tehnic VlahX**.

### 2. 🌐 Traducerea Integrală a Panoului de Admin (Full Admin i18n)
- Extinderea acoperirii complete de traducere `RO` / `EN` pentru toate formularele, modalele, antetele de tabel și mesajele de stare rămase în Panoul de Admin.

### 3. 🎨 Sistem de Teme Separate pentru Admin Panel
- Arhitectură dedicată de teme pentru Panoul de Admin (`/admin`), permițând teme personalizabile pentru panoul administrativ (ex: Dark Mode Admin, Compact Admin, Glassmorphism Admin) total independente de tema activă a site-ului public.

---

*Plan stabilit: 19 August 2026*
