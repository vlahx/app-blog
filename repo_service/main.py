from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
import pathlib
import json
import hmac
import hashlib
import base64
import time
import os
import zipfile
import io

app = FastAPI(title="VlahX Official Repository Microservice", version="1.0.0")

BASE_DIR = pathlib.Path(__file__).parent.resolve()
CATALOG_PATH = BASE_DIR / "catalog.json"
STORAGE_DIR = BASE_DIR / "storage"

# Shared secret key for SSO verification (defaults to standard session secret)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip() or "change-me-to-a-long-random-string"


def verify_sso_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, sig = parts[0], parts[1]
        
        expected_sig = hmac.new(SESSION_SECRET.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
            
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded.encode('utf-8'))
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return None
            
        role = str(payload.get("role", "")).lower()
        if "developer" not in role:
            return None

        return payload
    except Exception:
        return None


def get_current_dev_user(request: Request) -> dict | None:
    session_cookie = request.cookies.get("vlahx_repo_session")
    if not session_cookie:
        return None
    try:
        parts = session_cookie.split(".")
        if len(parts) != 2:
            return None
        b64_payload, sig = parts[0], parts[1]
        expected_sig = hmac.new(SESSION_SECRET.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded.encode('utf-8'))
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None


@app.get("/auth/sso")
def sso_login(token: str, response: Response):
    user_data = verify_sso_token(token)
    if not user_data:
        raise HTTPException(status_code=400, detail="Jetonul SSO este nevalid sau a expirat. Te rugăm să te reautentifici pe vlahx.org.")
    
    user_data["logged_at"] = int(time.time())
    payload_bytes = json.dumps(user_data).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    sig = hmac.new(SESSION_SECRET.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    cookie_val = f"{b64_payload}.{sig}"
    
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie(key="vlahx_repo_session", value=cookie_val, max_age=86400, httponly=True, samesite="lax")
    return resp


@app.get("/auth/logout")
def sso_logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(key="vlahx_repo_session")
    return resp


@app.get("/")
def home(request: Request):
    dev_user = get_current_dev_user(request)
    
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

    user_bar_html = ""
    if dev_user:
        user_display_name = dev_user.get("first_name") or dev_user.get("username") or "Dezvoltator"
        user_bar_html = f"""
        <div class="d-flex flex-column align-items-center align-items-md-end gap-2">
          <!-- Row 1: Identity & Logout -->
          <div class="d-flex align-items-center gap-2">
            <span class="badge text-white px-3 py-2 fs-6 rounded-pill" style="background-color: #6f42c1;">👤 {user_display_name}</span>
            <a href="/auth/logout" class="btn btn-sm btn-outline-danger rounded-pill px-3">Delogare</a>
          </div>
          <!-- Row 2: Action & Navigation Buttons -->
          <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
            <a href="https://vlahx.org/" class="btn btn-sm btn-outline-info rounded-pill px-3 py-2 fw-semibold">🌐 Înapoi la VlahX.org</a>
            <a href="/dashboard" class="btn btn-sm btn-success rounded-pill px-3 py-2 fw-semibold">🚀 Panou Publicare</a>
          </div>
        </div>
        """
    else:
        user_bar_html = """
        <div class="d-flex flex-column align-items-center align-items-md-end gap-2">
          <!-- Row 1: Main Platform Link -->
          <div>
            <a href="https://vlahx.org/" class="btn btn-sm btn-outline-info rounded-pill px-4 py-1 fw-semibold">🌐 Înapoi la VlahX.org</a>
          </div>
          <!-- Row 2: Login Action -->
          <div>
            <a href="https://vlahx.org/admin/login?target=repo" class="btn btn-primary rounded-pill px-4 py-2 fw-semibold">🔑 Autentificare Dezvoltator (vlahx.org)</a>
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
                {user_bar_html}
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


@app.get("/dashboard")
def dashboard(request: Request):
    dev_user = get_current_dev_user(request)
    if not dev_user:
        return RedirectResponse(url="https://vlahx.org/admin/login?target=repo", status_code=303)
        
    user_display_name = dev_user.get("first_name") or dev_user.get("username") or "Dezvoltator"
    user_email = dev_user.get("email", "Autentificat via SSO")
    
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="ro" data-bs-theme="dark">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Panou Dezvoltator - VlahX Repo Store</title>
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
          <style>
            body {{ background-color: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .card-glass {{ background: #161b22; border: 1px solid #30363d; border-radius: 1rem; }}
          </style>
        </head>
        <body class="py-5">
          <div class="container px-4" style="max-width: 900px;">
            
            <div class="d-flex align-items-center justify-content-between mb-4">
              <div>
                <a href="/" class="text-info text-decoration-none small">← Magazin Repo</a>
                <span class="text-secondary small ms-1 me-1">•</span>
                <a href="https://vlahx.org/" class="text-info text-decoration-none small">🌐 vlahx.org</a>
                <h2 class="fw-bold text-white mt-1 mb-0">👨‍💻 Panou Publicare Dezvoltator</h2>
              </div>
              <div class="d-flex flex-column align-items-end gap-2">
                <!-- Row 1: Identity & Logout -->
                <div class="d-flex align-items-center gap-2">
                  <span class="badge text-white px-3 py-2 fs-6 rounded-pill" style="background-color: #6f42c1;">👤 {user_display_name}</span>
                  <a href="/auth/logout" class="btn btn-sm btn-outline-danger rounded-pill px-3">Delogare</a>
                </div>
                <!-- Row 2: Platform Navigation Link -->
                <div>
                  <a href="https://vlahx.org/" class="btn btn-sm btn-outline-info rounded-pill px-3 py-1 fw-semibold">🌐 Înapoi la VlahX.org</a>
                </div>
              </div>
            </div>

            <!-- Developer Identity Card -->
            <div class="card-glass p-4 mb-4">
              <div class="d-flex align-items-center justify-content-between">
                <div>
                  <h5 class="fw-bold text-white mb-1">Sesiune SSO Activă & Autentificată</h5>
                  <p class="text-secondary small mb-0">Conectat prin <strong>vlahx.org</strong> • Status Rol: <span class="text-success fw-bold">DEVELOPER VERIFICAT ✓</span></p>
                </div>
                <span class="badge bg-success bg-opacity-25 text-success border border-success px-3 py-2">LIVE SSO SESSION</span>
              </div>
            </div>

            <!-- Upload Package Form -->
            <div class="card-glass p-4 mb-4">
              <h4 class="fw-bold text-white mb-3">📦 Publicare / Actualizare Pachet (.zip)</h4>
              <form action="/api/v1/publish" method="post" enctype="multipart/form-data">
                <div class="mb-3">
                  <label class="form-label text-secondary small fw-semibold">Tip Pachet</label>
                  <select name="package_type" class="form-select bg-dark text-white border-secondary rounded-3">
                    <option value="theme">🎨 Temă VlahX Core</option>
                    <option value="plugin">🔌 Plugin VlahX Core</option>
                  </select>
                </div>
                <div class="mb-3">
                  <label class="form-label text-secondary small fw-semibold">Fișier Arhivă (.zip)</label>
                  <input type="file" name="package_file" accept=".zip" class="form-control bg-dark text-white border-secondary rounded-3" required>
                  <div class="form-text text-secondary">Arhiva trebuie să conțină fișierul <code>theme.json</code> sau <code>plugin.py</code>.</div>
                </div>
                <button type="submit" class="btn btn-primary rounded-pill px-4 fw-semibold mt-2">🚀 Publică Pachetul în Repo Store</button>
              </form>
            </div>

          </div>
        </body>
        </html>
        """
    )


@app.post("/api/v1/publish")
async def publish_package(request: Request):
    dev_user = get_current_dev_user(request)
    if not dev_user:
        raise HTTPException(status_code=401, detail="Trebuie să fii autentificat ca dezvoltator pentru a publica pachete.")
        
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Formularul trebuie să fie multipart/form-data.")
        
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Corp solicitare gol.")
        
    try:
        boundary = content_type.split("boundary=")[-1].encode('utf-8')
        parts = body.split(b"--" + boundary)
    except Exception:
        raise HTTPException(status_code=400, detail="Eroare la procesarea corpului multipart.")
        
    package_type = "theme"
    package_file_bytes = b""
    package_filename = "package.zip"
    
    for part in parts:
        if b'name="package_type"' in part:
            val = part.split(b"\r\n\r\n")[-1].rstrip(b"\r\n--\r\n").rstrip(b"\r\n").decode('utf-8').strip()
            if val in ("theme", "plugin"):
                package_type = val
        elif b'name="package_file"' in part:
            header_and_data = part.split(b"\r\n\r\n", 1)
            if len(header_and_data) == 2:
                hdr, data = header_and_data
                package_file_bytes = data.rstrip(b"\r\n--\r\n").rstrip(b"\r\n")
                if b'filename="' in hdr:
                    fn = hdr.split(b'filename="')[1].split(b'"')[0].decode('utf-8')
                    if fn:
                        package_filename = fn

    if not package_file_bytes or len(package_file_bytes) < 10:
        raise HTTPException(status_code=400, detail="Arhiva încărcată este goală sau nevalidă.")
        
    try:
        z = zipfile.ZipFile(io.BytesIO(package_file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fișierul nu este o arhivă ZIP validă: {e}")
        
    metadata = {}
    
    if package_type == "theme":
        json_file = None
        for filename in z.namelist():
            if filename.endswith("theme.json"):
                json_file = filename
                break
        if not json_file:
            raise HTTPException(status_code=400, detail="Arhiva temei nu conține fișierul obligatoriu theme.json")
            
        try:
            theme_meta_bytes = z.read(json_file)
            metadata = json.loads(theme_meta_bytes.decode('utf-8'))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Fișierul theme.json nu este un JSON valid: {e}")
            
        raw_id = str(metadata.get("id") or metadata.get("slug") or package_filename.replace(".zip", "")).strip().lower()
        raw_id = raw_id.replace("theme-", "").replace("-theme", "")
        import re
        pkg_id = re.sub(r"[-_]v?\d+.*$", "", raw_id).strip()
        if not pkg_id:
            pkg_id = "theme"

        metadata["id"] = pkg_id
        metadata["name"] = metadata.get("name", pkg_id.title())
        metadata["version"] = metadata.get("version", "1.0.0")
        metadata["author"] = metadata.get("author", dev_user.get("username", "Gemini AI"))
        metadata["description"] = metadata.get("description", "Temă VlahX Core")
        metadata["min_engine_version"] = metadata.get("min_engine_version", "2.0.0")
        metadata["download_url"] = f"/download/themes/{pkg_id}.zip"
        
        target_zip = STORAGE_DIR / "themes" / f"{pkg_id}.zip"
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        with open(target_zip, "wb") as f:
            f.write(package_file_bytes)
            
        catalog_data = {"plugins": [], "themes": []}
        if CATALOG_PATH.exists():
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)
        
        # Remove any existing entries for this theme ID or old version variants
        themes = [t for t in catalog_data.get("themes", []) if re.sub(r"[-_]v?\d+\.\d+(\.\d+)?.*$", "", str(t.get("id", "")).replace("-theme", "").strip().lower()) != pkg_id]
        themes.append(metadata)
        catalog_data["themes"] = themes
        
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="ro" data-bs-theme="dark">
        <head>
          <meta charset="UTF-8">
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        </head>
        <body class="p-5 bg-dark text-white text-center">
          <div class="card bg-secondary bg-opacity-10 border-success p-5 mx-auto rounded-4 shadow" style="max-width: 600px;">
            <h1 class="text-success display-4 mb-3">✅ Succes!</h1>
            <h3 class="fw-bold text-white">Tema "{metadata['name']}" v{metadata['version']} a fost publicată!</h3>
            <p class="text-secondary mt-2">Pachetul este acum disponibil live în Repo Store și gata pentru instalare 1-Click.</p>
            <div class="mt-4">
              <a href="/dashboard" class="btn btn-outline-light rounded-pill px-4">← Înapoi la Panou</a>
              <a href="/" class="btn btn-primary rounded-pill px-4 ms-2">🏪 Deschide Magazinul</a>
            </div>
          </div>
        </body>
        </html>
        """)
        
    elif package_type == "plugin":
        import re
        raw_id = package_filename.replace(".zip", "")
        pkg_id = re.sub(r"[-_]v?\d+\.\d+(\.\d+)?.*$", "", str(raw_id).strip().lower())
        if pkg_id.endswith("-plugin"):
            pkg_id = pkg_id[:-7]
        if not pkg_id:
            pkg_id = "plugin"

        target_zip = STORAGE_DIR / "plugins" / f"{pkg_id}.zip"
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        with open(target_zip, "wb") as f:
            f.write(package_file_bytes)
            
        metadata = {
            "id": pkg_id,
            "name": pkg_id.replace("_", " ").title(),
            "version": "1.0.0",
            "author": dev_user.get("username", "Official"),
            "description": f"Plugin oficial {pkg_id}",
            "min_engine_version": "2.0.0",
            "download_url": f"/download/plugins/{pkg_id}.zip"
        }
        
        catalog_data = {"plugins": [], "themes": []}
        if CATALOG_PATH.exists():
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)
                
        plugins = [p for p in catalog_data.get("plugins", []) if re.sub(r"[-_]v?\d+\.\d+(\.\d+)?.*$", "", str(p.get("id", "")).replace("-plugin", "").strip().lower()) != pkg_id]
        plugins.append(metadata)
        catalog_data["plugins"] = plugins
        
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="ro" data-bs-theme="dark">
        <head>
          <meta charset="UTF-8">
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        </head>
        <body class="p-5 bg-dark text-white text-center">
          <div class="card bg-secondary bg-opacity-10 border-success p-5 mx-auto rounded-4 shadow" style="max-width: 600px;">
            <h1 class="text-success display-4 mb-3">✅ Succes!</h1>
            <h3 class="fw-bold text-white">Plugin-ul "{metadata['name']}" a fost publicat!</h3>
            <p class="text-secondary mt-2">Pachetul este acum disponibil live în Repo Store.</p>
            <div class="mt-4">
              <a href="/dashboard" class="btn btn-outline-light rounded-pill px-4">← Înapoi la Panou</a>
              <a href="/" class="btn btn-primary rounded-pill px-4 ms-2">🏪 Deschide Magazinul</a>
            </div>
          </div>
        </body>
        </html>
        """)


@app.get("/api/v1/catalog.json")
def get_catalog():
    if not CATALOG_PATH.exists():
        raise HTTPException(status_code=404, detail="Catalog file missing")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)


@app.get("/download/plugins/{plugin_id}.zip")
@app.get("/storage/plugins/{plugin_id}.zip")
def download_plugin(plugin_id: str):
    file_path = STORAGE_DIR / "plugins" / f"{plugin_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Plugin archive {plugin_id}.zip not found")
    return FileResponse(file_path, filename=f"{plugin_id}.zip", media_type="application/zip")


@app.get("/download/themes/{theme_id}.zip")
@app.get("/storage/themes/{theme_id}.zip")
def download_theme(theme_id: str):
    file_path = STORAGE_DIR / "themes" / f"{theme_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Theme archive {theme_id}.zip not found")
    return FileResponse(file_path, filename=f"{theme_id}.zip", media_type="application/zip")


@app.get("/health")
def health():
    return {"status": "ok", "service": "vlahx-repo"}
