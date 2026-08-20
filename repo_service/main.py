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
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head>
          <title>repo.vlahx.org</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #0d1117; color: #c9d1d9; line-height: 1.6; }
            h1 { color: #58a6ff; }
            code { background: #161b22; padding: 2px 6px; border-radius: 4px; color: #79c0ff; }
            a { color: #58a6ff; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; max-width: 600px; margin-top: 20px; }
          </style>
        </head>
        <body>
          <h1>🏪 VlahX Official Repository Microservice (`repo.vlahx.org`)</h1>
          <div class="card">
            <p><strong>Status:</strong> <code style="color:#3fb950;">ONLINE 🟢</code> (Port 8080)</p>
            <p><strong>Service:</strong> <code>vlahx-repo</code> Container</p>
            <p><strong>REST API Catalog:</strong> <a href="/api/v1/catalog.json">/api/v1/catalog.json</a></p>
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
