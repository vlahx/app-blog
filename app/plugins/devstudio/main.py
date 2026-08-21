from __future__ import annotations

import ast
import json
import logging
import os
import pathlib
import shutil
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import jinja2

from app.core.config import APP_DIR, get_active_theme
from app.core.templates import render_template
from app.utils.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/plugins/devstudio", tags=["devstudio"])
PLUGIN_DIR = pathlib.Path(__file__).parent.resolve()
TEMPLATES_DIR = PLUGIN_DIR / "templates"


def get_user_workspace(user: dict | None) -> pathlib.Path:
    user_id = str(user.get("id") or user.get("username") or "default_dev") if user else "default_dev"
    ws = APP_DIR / "storage" / "workspaces" / user_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _validate_code(rel_path: str, code: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    p_str = rel_path.lower()
    
    if p_str.endswith(".py"):
        try:
            ast.parse(code, filename=rel_path)
        except SyntaxError as e:
            errors.append({
                "line": e.lineno or 1,
                "col": e.offset or 1,
                "message": f"Python SyntaxError: {e.msg}"
            })
        except Exception as e:
            errors.append({"line": 1, "col": 1, "message": str(e)})

    elif p_str.endswith(".json"):
        try:
            json.loads(code)
        except json.JSONDecodeError as e:
            errors.append({
                "line": e.lineno,
                "col": e.colno,
                "message": f"JSON FormatError: {e.msg}"
            })
        except Exception as e:
            errors.append({"line": 1, "col": 1, "message": str(e)})

    elif p_str.endswith(".html") or p_str.endswith(".jinja") or p_str.endswith(".jinja2"):
        try:
            env = jinja2.Environment()
            env.parse(code)
        except jinja2.TemplateSyntaxError as e:
            errors.append({
                "line": e.lineno,
                "col": 1,
                "message": f"Jinja2 TemplateSyntaxError: {e.message}"
            })
        except Exception as e:
            errors.append({"line": 1, "col": 1, "message": str(e)})

    return errors


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def devstudio_dashboard(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Trebuie să fii autentificat pentru a accesa DevStudio.")
    
    templates = request.app.state.templates
    ws = get_user_workspace(user)
    
    installed_themes = []
    themes_dir = APP_DIR / "themes"
    if themes_dir.exists():
        for d in themes_dir.iterdir():
            if d.is_dir():
                installed_themes.append(d.name)
                
    installed_plugins = []
    plugins_dir = APP_DIR / "plugins"
    if plugins_dir.exists():
        for d in plugins_dir.iterdir():
            if d.is_dir() and d.name != "devstudio":
                installed_plugins.append(d.name)

    ctx = {
        "request": request,
        "title": "Cloud DevStudio & Web IDE",
        "user": user,
        "workspace_path": str(ws),
        "installed_themes": installed_themes,
        "installed_plugins": installed_plugins,
    }
    return render_template(templates, "editor.html", ctx, custom_dir=str(TEMPLATES_DIR))


@router.get("/tree")
async def get_workspace_tree(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)

    def _build_tree(dir_path: pathlib.Path) -> list[dict[str, Any]]:
        nodes = []
        for item in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name.startswith(".") or item.name in ["__pycache__", "venv"]:
                continue
            rel = str(item.relative_to(ws)).replace("\\", "/")
            if item.is_dir():
                nodes.append({
                    "name": item.name,
                    "type": "folder",
                    "path": rel,
                    "children": _build_tree(item)
                })
            else:
                nodes.append({
                    "name": item.name,
                    "type": "file",
                    "path": rel
                })
        return nodes

    return {"ok": True, "tree": _build_tree(ws)}


@router.get("/file")
async def get_file_content(path: str, request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    target = (ws / path).resolve()
    
    if not str(target).startswith(str(ws.resolve())):
        raise HTTPException(status_code=400, detail="Cale nevalidă în spațiul de lucru.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=440, detail="Fișierul nu există.")
        
    try:
        content = target.read_text(encoding="utf-8")
        return {"ok": True, "path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la citire fișier: {e}")


@router.post("/save")
async def save_file_content(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    
    data = await request.json()
    path = str(data.get("path") or "").strip()
    content = str(data.get("content") or "")
    
    if not path:
        raise HTTPException(status_code=400, detail="Calea fișierului este lipsă.")
        
    target = (ws / path).resolve()
    if not str(target).startswith(str(ws.resolve())):
        raise HTTPException(status_code=400, detail="Cale nevalidă.")
        
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    
    errors = _validate_code(path, content)
    return {"ok": True, "path": path, "errors": errors}


@router.post("/create-file")
async def create_file_or_folder(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    data = await request.json()
    
    path = str(data.get("path") or "").strip()
    item_type = str(data.get("type") or "file").strip()
    
    if not path:
        raise HTTPException(status_code=400, detail="Calea este lipsă.")
        
    target = (ws / path).resolve()
    if not str(target).startswith(str(ws.resolve())):
        raise HTTPException(status_code=400, detail="Cale nevalidă.")
        
    if item_type == "folder":
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("", encoding="utf-8")
            
    return {"ok": True, "path": path}


@router.post("/delete")
async def delete_item(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    data = await request.json()
    path = str(data.get("path") or "").strip()
    
    if not path:
        raise HTTPException(status_code=400, detail="Calea este lipsă.")
        
    target = (ws / path).resolve()
    if not str(target).startswith(str(ws.resolve())):
        raise HTTPException(status_code=400, detail="Cale nevalidă.")
        
    if target.is_dir():
        shutil.rmtree(target)
    elif target.is_file():
        target.unlink()
        
    return {"ok": True}


@router.post("/fork")
async def fork_package(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    data = await request.json()
    
    package_type = str(data.get("type") or "theme").strip()
    package_id = str(data.get("id") or "").strip()
    
    if not package_id:
        raise HTTPException(status_code=400, detail="ID pachet lipsă.")
        
    if package_type == "theme":
        src = APP_DIR / "themes" / package_id
    else:
        src = APP_DIR / "plugins" / package_id
        
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Pachetul '{package_id}' nu a fost găsit pe sistem.")
        
    dest = ws / f"{package_id}-fork"
    if dest.exists():
        shutil.rmtree(dest)
        
    shutil.copytree(src, dest)
    
    manifest_file = dest / ("theme.json" if package_type == "theme" else "plugin.json")
    if manifest_file.exists():
        try:
            m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            dev_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("username") or "Developer"
            m_data["author"] = f"{dev_name} (Fork)"
            m_data["version"] = "1.0.0-fork"
            manifest_file.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return {"ok": True, "fork_path": f"{package_id}-fork"}


@router.post("/upload-zip")
async def upload_workspace_zip(request: Request, file: UploadFile = File(...)):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Doar fișierele .zip sunt permise.")
        
    contents = await file.read()
    with zipfile.ZipFile(io.BytesIO(contents)) as zipf:
        zipf.extractall(ws)
        
    return {"ok": True, "message": f"Arhiva {file.filename} a fost dezarhivată cu succes în spațiul de lucru."}


@router.post("/package-and-publish")
async def package_and_publish(request: Request):
    user = getattr(request.state, "user", None)
    ws = get_user_workspace(user)
    data = await request.json()
    
    folder_name = str(data.get("folder") or "").strip()
    custom_name = str(data.get("name") or "").strip()
    custom_desc = str(data.get("description") or "").strip()
    
    if not folder_name:
        raise HTTPException(status_code=400, detail="Selectează un dosar din spațiul de lucru.")
        
    target_dir = (ws / folder_name).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Dosarul selectat nu există.")
        
    theme_manifest = target_dir / "theme.json"
    plugin_manifest = target_dir / "plugin.json"
    
    dev_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("username") or "Developer"
    
    if theme_manifest.exists():
        manifest_path = theme_manifest
        pkg_type = "theme"
    elif plugin_manifest.exists():
        manifest_path = plugin_manifest
        pkg_type = "plugin"
    else:
        manifest_path = theme_manifest
        pkg_type = "theme"
        
    manifest_data = {}
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    if custom_name:
        manifest_data["name"] = custom_name
    if custom_desc:
        manifest_data["description"] = custom_desc
        
    manifest_data["author"] = dev_name
    
    raw_v = manifest_data.get("version", "1.0.0")
    try:
        parts = raw_v.split(".")
        parts[-1] = str(int(parts[-1].split("-")[0]) + 1)
        new_v = ".".join(parts)
    except Exception:
        new_v = "1.0.1"
    manifest_data["version"] = new_v
    
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    zip_buffer = io.BytesIO()
    prefix_root = f"themes/{folder_name}" if pkg_type == "theme" else f"plugins/{folder_name}"
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_path, dirs, files in os.walk(target_dir):
            for f in files:
                full_f = pathlib.Path(root_path) / f
                rel_f = full_f.relative_to(target_dir)
                zip_arc = f"{prefix_root}/{rel_f}"
                zipf.write(full_f, zip_arc)
                
    zip_bytes = zip_buffer.getvalue()
    
    out_dir = APP_DIR / "storage" / ("themes" if pkg_type == "theme" else "plugins")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{folder_name}.zip"
    out_file.write_bytes(zip_bytes)
    
    dest_installed = APP_DIR / ("themes" if pkg_type == "theme" else "plugins") / folder_name
    if dest_installed.exists():
        shutil.rmtree(dest_installed)
    shutil.copytree(target_dir, dest_installed)

    return {
        "ok": True,
        "message": f"Pachetul '{manifest_data.get('name')}' v{new_v} a fost generat și activat cu succes!",
        "author": dev_name,
        "version": new_v,
        "zip_path": str(out_file)
    }
