from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
import pathlib
import json

app = FastAPI(title="VlahX Official Repository Microservice", version="1.0.0")

BASE_DIR = pathlib.Path(__file__).parent.resolve()
CATALOG_PATH = BASE_DIR / "catalog.json"
STORAGE_DIR = BASE_DIR / "storage"


@app.get("/")
def home():
    catalog_data = {"plugins": [], "themes": []}
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)
        except Exception:
            pass

    plugins_html = ""
    for p in catalog_data.get("plugins", []):
        icon = p.get("icon", "🔌")
        name = p.get("name", p.get("id"))
        version = p.get("version", "1.0.0")
        min_ver = p.get("min_engine_version", "2.0.0")
        desc = p.get("description", "")
        author = p.get("author", "Official")
        dl_url = f"/download/plugins/{p.get('id')}.zip"
        
        plugins_html += f"""
        <div class="col-md-6 col-lg-4 mb-4">
          <div class="card h-100 bg-dark text-white border-secondary shadow-sm rounded-4">
            <div class="card-body p-4 d-flex flex-column">
              <div class="d-flex align-items-center justify-content-between mb-3">
                <span class="fs-1">{icon}</span>
                <span class="badge bg-primary rounded-pill px-3 py-2">v{version}</span>
              </div>
              <h5 class="card-title fw-bold text-white mb-1">{name}</h5>
              <p class="text-secondary small mb-3">by {author} • <span class="text-info">v{min_ver}+</span></p>
              <p class="card-text text-light small flex-grow-1" style="opacity: 0.85;">{desc}</p>
              <div class="pt-3 border-top border-secondary mt-auto d-flex align-items-center justify-content-between">
                <span class="badge bg-success bg-opacity-25 text-success border border-success">✓ Verified</span>
                <a href="{dl_url}" class="btn btn-sm btn-outline-primary rounded-pill px-3">⬇️ Download ZIP</a>
              </div>
            </div>
          </div>
        </div>
        """

    themes_html = ""
    for t in catalog_data.get("themes", []):
        name = t.get("name", t.get("id"))
        version = t.get("version", "1.0.0")
        min_ver = t.get("min_engine_version", "2.0.0")
        desc = t.get("description", "")
        author = t.get("author", "Official")
        dl_url = f"/download/themes/{t.get('id')}.zip"
        
        themes_html += f"""
        <div class="col-md-6 col-lg-4 mb-4">
          <div class="card h-100 bg-dark text-white border-secondary shadow-sm rounded-4">
            <div class="card-body p-4 d-flex flex-column">
              <div class="d-flex align-items-center justify-content-between mb-3">
                <span class="fs-1">🎨</span>
                <span class="badge bg-warning text-dark rounded-pill px-3 py-2">v{version}</span>
              </div>
              <h5 class="card-title fw-bold text-white mb-1">{name}</h5>
              <p class="text-secondary small mb-3">by {author} • <span class="text-info">v{min_ver}+</span></p>
              <p class="card-text text-light small flex-grow-1" style="opacity: 0.85;">{desc}</p>
              <div class="pt-3 border-top border-secondary mt-auto d-flex align-items-center justify-content-between">
                <span class="badge bg-info bg-opacity-25 text-info border border-info">Theme</span>
                <a href="{dl_url}" class="btn btn-sm btn-outline-warning rounded-pill px-3">⬇️ Download ZIP</a>
              </div>
            </div>
          </div>
        </div>
        """

    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="en" data-bs-theme="dark">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>VlahX Official Repository Store</title>
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
          <style>
            body {{ background-color: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .hero-card {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 1.5rem; }}
            .badge-pulse {{ animation: pulse 2s infinite; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} 100% {{ opacity: 1; }} }}
          </style>
        </head>
        <body class="py-5">
          <div class="container px-4">
            
            <!-- Header Banner -->
            <div class="hero-card p-4 p-md-5 mb-5 shadow-lg text-center text-md-start d-md-flex align-items-center justify-content-between">
              <div>
                <span class="badge bg-success bg-opacity-25 text-success border border-success mb-2 px-3 py-2 badge-pulse">● REPOSITORY SERVICE ACTIVE</span>
                <h1 class="display-5 fw-extrabold text-white mb-2">🏪 VlahX Official Package Store</h1>
                <p class="text-secondary lead mb-0" style="max-width: 650px;">Standalone microservice serving official plugins, themes, and versioned catalog REST API for VlahX Core 2.0.</p>
              </div>
              <div class="mt-4 mt-md-0">
                <a href="/api/v1/catalog.json" target="_blank" class="btn btn-outline-info rounded-pill px-4 py-2 fw-semibold">📡 API Catalog JSON</a>
              </div>
            </div>

            <!-- Official Plugins Section -->
            <div class="d-flex align-items-center justify-content-between mb-4">
              <h3 class="fw-bold text-white mb-0">🔌 Official Plugins ({len(catalog_data.get("plugins", []))})</h3>
            </div>
            <div class="row">
              {plugins_html}
            </div>

            <!-- Official Themes Section -->
            <div class="d-flex align-items-center justify-content-between mt-5 mb-4">
              <h3 class="fw-bold text-white mb-0">🎨 Official Themes ({len(catalog_data.get("themes", []))})</h3>
            </div>
            <div class="row">
              {themes_html}
            </div>

            <!-- Footer -->
            <div class="text-center text-secondary border-top border-secondary pt-4 mt-5 small">
              © 2026 VlahX Engine Microservice (vlahx-repo) • Served dynamically via Port 8088 / repo.vlahx.org
            </div>

          </div>
        </body>
        </html>
        """
    )


@app.get("/api/v1/catalog.json")
def get_catalog():
    if not CATALOG_PATH.exists():
        raise HTTPException(status_code=404, detail="Catalog file missing")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)


@app.get("/download/plugins/{plugin_id}.zip")
def download_plugin(plugin_id: str):
    file_path = STORAGE_DIR / "plugins" / f"{plugin_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Plugin archive {plugin_id}.zip not found")
    return FileResponse(file_path, filename=f"{plugin_id}.zip", media_type="application/zip")


@app.get("/download/themes/{theme_id}.zip")
def download_theme(theme_id: str):
    file_path = STORAGE_DIR / "themes" / f"{theme_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Theme archive {theme_id}.zip not found")
    return FileResponse(file_path, filename=f"{theme_id}.zip", media_type="application/zip")


@app.get("/health")
def health():
    return {"status": "ok", "service": "vlahx-repo"}
