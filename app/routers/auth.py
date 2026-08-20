from __future__ import annotations

from datetime import datetime, timezone
import os
import json
import urllib.request
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import events
from app.core.config import TELEGRAM_AUTH_URL, get_telegram_bot_username
from app.core.templates import render_template
from app.models.db_models import User
from app.utils.auth import login_required, get_current_user_from_request
from app.utils.db import get_db
from app.utils.telegram import verify_telegram_login
from app.utils.open_graph import public_site_origin

router = APIRouter(tags=["auth"])


def build_auth_router(templates: Jinja2Templates) -> APIRouter:
    @router.get("/admin/login", response_class=HTMLResponse)
    def login_page(request: Request):
        bot_username = get_telegram_bot_username()

        google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")

        return render_template(
            templates,
            request=request,
            name="admin/login.html",
            context={
                "bot_username": bot_username or "",
                "auth_url": TELEGRAM_AUTH_URL,
                "google_client_id": google_client_id,
            },
        )

    @router.get("/dev/login")
    async def dev_login(
        request: Request,
        user_id: int = 1,
        role: str = "admin",
        db: Session = Depends(get_db),
    ):
        """Quick developer session login & elevation route for local testing."""
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if user is None:
            user = User(
                provider="dev",
                oauth_id=f"dev_{user_id}",
                username="Developer Admin",
                first_name="Dev",
                last_name="Admin",
                email="dev@camionagiul.club",
                role=role,
                created_at=now,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if role:
                user.role = role
                db.commit()

        request.session["user_id"] = str(user.id)
        return RedirectResponse(url="/profile", status_code=303)

    @router.get("/admin/pending", response_class=HTMLResponse)
    def pending_page(request: Request):
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=303)

        return render_template(
            templates,
            request=request,
            name="admin/pending.html",
            context={"title": "Cont în Așteptare"},
        )

    @router.get("/admin/login/telegram")
    async def telegram_login(
        request: Request,
        db: Session = Depends(get_db),
    ):
        params = dict(request.query_params)

        if not verify_telegram_login(params):
            return HTMLResponse("Telegram login verification failed.", status_code=403)

        telegram_id = params.get("id")
        if not telegram_id:
            return HTMLResponse("Missing Telegram id.", status_code=400)

        provider = "telegram"
        stmt = select(User).where(User.provider == provider, User.oauth_id == str(telegram_id))
        result = db.execute(stmt)
        existing = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if existing is None:
            count_stmt = select(func.count()).select_from(User)
            user_count = db.execute(count_stmt).scalar() or 0
            initial_role = "admin" if user_count == 0 else "reader"

            existing = User(
                provider=provider,
                oauth_id=str(telegram_id),
                username=params.get("username"),
                first_name=params.get("first_name"),
                last_name=params.get("last_name"),
                image_url=params.get("photo_url"),
                role=initial_role,
                created_at=now,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
            events.publish(
                "user.registered",
                provider=provider,
                username=existing.username,
                first_name=existing.first_name,
                last_name=existing.last_name,
                email=existing.email,
            )
        else:
            existing.username = params.get("username") or existing.username
            existing.first_name = params.get("first_name") or existing.first_name
            existing.last_name = params.get("last_name") or existing.last_name
            existing.image_url = params.get("photo_url") or existing.image_url

        db.commit()
        db.refresh(existing)

        request.session["user_id"] = str(existing.id)

        next_url = (params.get("next") or request.session.get("auth_next") or "").strip()
        if "auth_next" in request.session:
            del request.session["auth_next"]

        if existing.role == "pending":
            existing.role = "reader"
            db.commit()

        if existing.role in ("reader", "user"):
            if next_url and next_url.startswith("/") and not next_url.startswith("/admin"):
                return RedirectResponse(url=next_url, status_code=303)
            return RedirectResponse(url="/profile", status_code=303)

        if next_url and next_url.startswith("/"):
            return RedirectResponse(url=next_url, status_code=303)

        return RedirectResponse(url="/admin", status_code=303)

    @router.get("/auth/google/login")
    async def google_login(request: Request):
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        if not client_id:
            return HTMLResponse("GOOGLE_CLIENT_ID nu este configurat în mediu (.env).", status_code=500)
        
        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/auth/google/callback"

        next_url = request.query_params.get("next", "/profile")
        request.session["auth_next"] = next_url

        google_auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            + urllib.parse.urlencode({
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "prompt": "select_account",
            })
        )
        return RedirectResponse(url=google_auth_url, status_code=303)

    @router.get("/auth/google/callback")
    async def google_callback(
        request: Request,
        db: Session = Depends(get_db),
    ):
        code = request.query_params.get("code")
        if not code:
            return HTMLResponse("Codul de autorizare Google lipsește.", status_code=400)

        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        base = public_site_origin(request).rstrip("/")
        redirect_uri = f"{base}/auth/google/callback"

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        try:
            req = urllib.request.Request(token_url, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req) as resp:
                tokens = json.loads(resp.read().decode("utf-8"))
            
            access_token = tokens.get("access_token")
            if not access_token:
                return HTMLResponse("Eroare la obținerea token-ului Google.", status_code=400)

            # Fetch user info
            userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
            u_req = urllib.request.Request(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(u_req) as u_resp:
                user_info = json.loads(u_resp.read().decode("utf-8"))

            google_sub = str(user_info.get("sub"))
            email = user_info.get("email")
            given_name = user_info.get("given_name") or user_info.get("name")
            family_name = user_info.get("family_name")
            picture = user_info.get("picture")

            provider = "google"
            stmt = select(User).where(User.provider == provider, User.oauth_id == google_sub)
            existing = db.execute(stmt).scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if existing is None:
                count_stmt = select(func.count()).select_from(User)
                user_count = db.execute(count_stmt).scalar() or 0
                initial_role = "admin" if user_count == 0 else "reader"

                existing = User(
                    provider=provider,
                    oauth_id=google_sub,
                    email=email,
                    first_name=given_name,
                    last_name=family_name,
                    image_url=picture,
                    role=initial_role,
                    created_at=now,
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
                events.publish(
                    "user.registered",
                    provider=provider,
                    first_name=existing.first_name,
                    last_name=existing.last_name,
                    email=existing.email,
                )
            else:
                existing.email = email or existing.email
                existing.first_name = given_name or existing.first_name
                existing.last_name = family_name or existing.last_name
                existing.image_url = picture or existing.image_url

            db.commit()
            db.refresh(existing)

            request.session["user_id"] = str(existing.id)

            next_url = request.session.get("auth_next", "/profile")
            if "auth_next" in request.session:
                del request.session["auth_next"]

            return RedirectResponse(url=next_url, status_code=303)

        except Exception as e:
            return HTMLResponse(f"Eroare autentificare Google: {e}", status_code=500)

    @router.get("/profile", response_class=HTMLResponse)
    async def user_profile_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login?next=/profile", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none() or user

        # Retrieve user's orders from minishop if minishop plugin exists
        orders = []
        try:
            from app.plugins.minishop.db import list_user_orders
            orders = list_user_orders(user_id=db_user.id, email=db_user.email)
        except Exception:
            pass

        return render_template(
            templates,
            request=request,
            name="user/profile.html",
            context={
                "title": "Profilul Meu — Club",
                "user": db_user,
                "orders": orders,
            },
        )

    @router.post("/profile/update")
    async def user_profile_update(
        request: Request,
        first_name: str = Form(...),
        last_name: str = Form(None),
        email: str = Form(None),
        phone: str = Form(None),
        image_url: str = Form(None),
        bio: str = Form(None),
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none()
        if not db_user:
            return RedirectResponse(url="/admin/login", status_code=303)

        if first_name:
            db_user.first_name = first_name.strip()
        db_user.last_name = last_name.strip() if last_name else None
        db_user.email = email.strip() if email else None
        db_user.phone = phone.strip() if phone else None
        db_user.image_url = image_url.strip() if image_url else None
        db_user.bio = bio.strip() if bio else None

        db.commit()
        return RedirectResponse(url="/profile?updated=1", status_code=303)

    @router.get("/user/{user_id}", response_class=HTMLResponse)
    async def public_user_profile(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db),
    ):
        stmt = select(User).where(User.id == user_id)
        pub_user = db.execute(stmt).scalar_one_or_none()
        if not pub_user:
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit.")

        return render_template(
            templates,
            request=request,
            name="user/public_profile.html",
            context={
                "title": f"Profil {pub_user.first_name or pub_user.username} — Club",
                "public_user": pub_user,
            },
        )

    @router.get("/auth/logout")
    @router.get("/admin/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)

    @router.post("/profile/request-role")
    async def user_request_role(
        request: Request,
        requested_role: str = Form(...),
        motivation: str = Form(""),
        db: Session = Depends(get_db),
    ):
        user = getattr(request.state, "current_user", None) or get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/admin/login", status_code=303)

        db_user = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none() or user

        roles_map = {
            "developer": "👨‍💻 Programator / Dezvoltator (VlahX Developer)",
            "seller": "🛍️ Vânzător (Magazin / Piață)",
            "author": "✍️ Autor / Scriitor Articole",
            "editor": "📝 Editor Conținut",
        }
        role_label = roles_map.get(requested_role, requested_role)
        user_name = f"{db_user.first_name or db_user.username or 'Utilizator'} {db_user.last_name or ''}".strip()

        if requested_role == "developer":
            db_user.dev_status = "pending"
            db_user.dev_notes = motivation.strip()
            db_user.dev_requested_at = datetime.now(timezone.utc)
            db.commit()

        msg = (
            f"🔔 *SOLICITARE ROL NOU PE SITE!*\n\n"
            f"👤 *Utilizator:* {user_name} (`ID: #{db_user.id}`)\n"
            f"📧 *Email:* {db_user.email or 'Nespecificat'}\n"
            f"📱 *Telefon:* {db_user.phone or 'Nespecificat'}\n"
            f"🎯 *Rol Solicitat:* {role_label}\n"
            f"💬 *Motivare:* {motivation.strip() or 'Fără mesaj suplimentar'}\n\n"
            f"⚡ *Aprobă în Admin:* {public_site_origin(request)}/admin/users"
        )

        try:
            from app.utils.telegram_notify import send_telegram_message
            sent_ok = send_telegram_message(msg)
            if not sent_ok:
                logger.warning("user_request_role: Telegram notification returned False")
        except Exception as e:
            logger.warning(f"user_request_role: Exception sending Telegram notification: {e}")

        return RedirectResponse(url="/profile?requested=1", status_code=303)

    return router
