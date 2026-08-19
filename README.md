# ⚡ VlahX Engine (v2.0 Core) — Modular Web Platform

[![VlahX Engine](https://img.shields.io/badge/VlahX_Engine-v2.0_Core-6f42c1?style=for-the-badge&logo=python&logoColor=white)](https://vlahx.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

**VlahX Engine** este o platformă web modulară, ultra-rapidă și extrem de flexibilă, construită cu **Python (FastAPI)**, **SQLAlchemy**, **Jinja2** și **Bootstrap 5**. Este concepută pentru a construi și extinde aplicații web moderne, bloguri, magazine online și portaluri de comunitate prin intermediul unui sistem decuplat de **plugin-uri** și **teme**.

🌐 **Site Oficial & Comunitate**: [https://vlahx.org/](https://vlahx.org/)

---

## 🌟 Caracteristici Principale (Key Features)

- ⚡ **Core De-a Dreptul Rapid**: Alimentat de Python 3.11+, FastAPI, Uvicorn și SQLite / SQLAlchemy.
- 🗄️ **Single Source of Truth**: Toate setările aplicației sunt salvate direct în baza de date SQLite (`db/app.db`), oferind dinamism complet fără fișiere temporare de configurare.
- 🔀 **Root Router Dinamic (Homepage Mode)**: Setează prima pagină pe Feed Blog (`/`), Pagină Statică (ex: `home`) sau Magazin Online (`minishop`).
- 🧩 **Sistem Modular de Plugin-uri**:
  - Plugin-uri oficiale disponibile: **Google SEO & Indexing API**, **Analytics & Surse de Trafic (Referrers)**, **Notificări Telegram**, **Sitemap XML**, **Robots.txt**, **Comentarii Widget**, **Newsletter**, **Social Share** și **MiniShop**.
- 🎨 **Multi-Theme Engine**:
  - Teme dinamice decuplate (`themes/minimal`).
  - Suport nativ pentru Dark Mode & Light Mode.
- ⚡ **Manager de Navigare Navbar**:
  - Control complet pe linkuri interne (`/blog`, `/shop`) și URL-uri externe cu suport `target="_blank"` și securitate `rel="noopener noreferrer"`.
- 🔐 **Autentificare & Securitate**:
  - Suport pentru Google OAuth 2.0 și Telegram Login Widget.
  - Rezoluție dinamică a domeniului și protecție automată HTTPS (`X-Forwarded-Proto`).
- 🌐 **Sistem Multilingv (RO / EN)**:
  - Comutare dinamică a limbii site-ului și suport pentru pagini/articole traduse.

---

## 📘 Invitație pentru Dezvoltatori & Comunitate

Rețeaua **VlahX** este construită pe principiile open-source și pe puterea comunității! 

Orice dezvoltator este invitat să creeze plugin-uri noi, teme personalizate și să contribuie la extinderea ecosistemului.

* 📖 **Ghidul Oficial al Dezvoltatorului**: Consultă [vlahx_developer_api_guide.md](vlahx_developer_api_guide.md) pentru lista completă a funcțiilor helper, cârligelor de șablon (hooks), sistemului de evenimente Pub-Sub, rutelor API și To-Do Roadmap.
* 🏬 **VlahX Ecosystem 1-Click Repository**: Descoperă pachetele oficiale și alătură-te comunității de creatori pe [https://vlahx.org/](https://vlahx.org/).

---

## 🚀 Ghid Rapid de Instalare

### 1. Clonare & Mediu Virtual

```bash
git clone git@github.com:vlahx/vlahx-engine.git
cd vlahx-engine

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Rulare Locală (Development)

```bash
python main.py
```
Sau cu Uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Deschide `http://localhost:8000` în browser.

---

## 🐳 Rulare cu Docker

Pornire container cu Docker Compose:
```bash
docker compose up -d --build
```

---

## 📜 Licență

Distribuit sub licența **Apache License 2.0**. Vezi fișierul `LICENSE` pentru detalii.

© 2026 **[VlahX Engine Community](https://vlahx.org/)** — Construiește și extinde aplicații web cu pluginuri și teme.
