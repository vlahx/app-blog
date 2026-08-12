# ⚡ FastAPI Modular Blog & Shop Engine

A modern, lightweight, high-performance web platform built with **FastAPI**, **SQLAlchemy**, **Jinja2**, and **Bootstrap 5**. Designed with a modular plugin architecture, multi-theme engine, integrated MiniShop for digital & physical products, user profiles, and social OAuth authentication.

---

## 🌟 Key Features

- ⚡ **High Performance Core**: Powered by Python 3.11+, FastAPI, Uvicorn, and SQLite / SQLAlchemy.
- 🛍️ **MiniShop Subsystem**:
  - Support for **Physical** (apparel, equipment) and **Virtual/Digital** products (ZIP, PDF, APK, Ebook).
  - Automated secure digital file downloads post-purchase.
  - Stripe Payment Gateway integration (Live Card & Test mode support).
  - Preserved line-break descriptions (`white-space: pre-line`) for clean product copy.
- 👤 **User Profiles & Social OAuth**:
  - Personal User Dashboard (`/profile`) with profile editing and order history tracking.
  - Google OAuth 2.0 & Telegram Widget authentication.
  - Role Upgrade Request system sending instant Telegram notifications to site admins.
- 🧩 **Modular Plugin Architecture**:
  - Plug-and-play plugin system (`plugins/`).
  - Included plugins: **Analytics** (tracking posts + shop products), **Comments Widget**, **Sitemap**, **Robots.txt**, **Social Share**, **Newsletter**, **Telegram Notify**.
- 🎨 **Multi-Theme Engine**:
  - Dynamic theme support (`themes/default`, `themes/minimal`).
  - Native Dark Mode & Light Mode UI switching.
- 🖼️ **Media Manager & SEO**:
  - Integrated Pillow image processing & 500x500 square crop preset.
  - Automatic OpenGraph & Twitter Card meta tag generator for posts and products.

---

## 🌐 Live Demo / Example Implementation

A live production instance running this engine can be viewed at:  
👉 **[https://camionagiul.club](https://camionagiul.club)**

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Environment

```bash
git clone https://github.com/<your-username>/app-blog.git
cd app-blog

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Copy the example environment configuration:
```bash
cp .env.example .env
```

Edit `.env` with your settings (e.g., `SECRET_KEY`, `PUBLIC_SITE_URL`, Telegram / Google credentials).

### 3. Run Locally

```bash
python main.py
```
Or with Uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` in your browser.

---

## 🐳 Docker Deployment

Run with Docker Compose:
```bash
docker compose up -d --build
```

---

## 📜 License

Distributed under the **Apache License 2.0**. See `LICENSE` for details.
