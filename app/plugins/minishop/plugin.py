from __future__ import annotations
from app.core.events import publish
from app.core.template_hooks import render_post_article_footers, render_post_header_metas
from app.utils.open_graph import public_site_origin

import logging
import os
import json
from pathlib import Path

from fastapi import FastAPI, Request, Form, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.core.config import PROJECT_ROOT
from app.core.templates import build_templates, render_template
from app.utils.auth import get_current_user_from_request, role_required, user_has_role
from app.utils.auth import user_has_role

def user_can_manage_shop(user: Any) -> bool:
    return user_has_role(user, "admin", "editor", "seller")

from app.core.plugin_manager import get_plugin_setting, set_plugin_setting, is_plugin_enabled
from app.core.i18n import get_plugin_translation, resolve_locale
from typing import Any

def _get_user_role(user: Any) -> str | None:
    if not user:
        return None
    if isinstance(user, dict):
        return user.get("role")
    return getattr(user, "role", None)

def _get_user_id(user: Any) -> int | None:
    if not user:
        return None
    if isinstance(user, dict):
        return user.get("id")
    return getattr(user, "id", None)

def _get_user_name(user: Any, default: str = "Anonim") -> str:
    if not user:
        return default
    if isinstance(user, dict):
        return user.get("display_name") or user.get("first_name") or user.get("username") or default
    name_parts = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
    full_name = " ".join([p for p in name_parts if p]).strip()
    return full_name if full_name else (getattr(user, "username", None) or default)


from app.plugins.minishop.db import (
    init_minishop_db,
    list_shop_categories,
    save_shop_category,
    delete_shop_category,
    list_shop_products,
    get_shop_product,
    save_shop_product,
    delete_shop_product,
    create_shop_order,
    get_shop_order,
    list_shop_orders,
    update_order_status,
    add_shop_review,
    list_product_reviews,
    get_product_rating_summary,
)

logger = logging.getLogger(__name__)



def sync_minishop_translations() -> None:
    # Scaneaza toate limbile din site (get_available_locales) si creeaza/sincronizeaza fisierele din locales/ si cheile din DB.
    try:
        from app.core.translation_db import get_available_locales, set_translation_entry, DEFAULT_TRANSLATION_CATALOG
        from app.core.i18n import get_plugin_translation
        
        locales = get_available_locales()
        p_locales_dir = PROJECT_ROOT / "plugins" / "minishop" / "locales"
        p_locales_dir.mkdir(parents=True, exist_ok=True)
        
        ro_file = p_locales_dir / "ro.json"
        en_file = p_locales_dir / "en.json"
        
        for loc in locales:
            code_str = loc["code"].strip().lower()
            target_file = p_locales_dir / f"{code_str}.json"
            
            # Daca fisierul pentru aceasta limba nu exista pe disc, il cream automat din ro.json/en.json
            if not target_file.exists():
                src = ro_file if ro_file.exists() else en_file
                if src.exists():
                    with open(src, "r", encoding="utf-8") as sf, open(target_file, "w", encoding="utf-8") as df:
                        df.write(sf.read())
                        
            if target_file.exists():
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        tdata = json.load(f)
                    for k, v in tdata.items():
                        db_key = f"plugins.minishop.{k}"
                        set_translation_entry(code_str, db_key, v)
                        DEFAULT_TRANSLATION_CATALOG[db_key] = v
                except Exception as ex:
                    logger.warning(f"Failed to sync minishop i18n for {code_str}: {ex}")
    except Exception as e:
        logger.warning(f"sync_minishop_translations error: {e}")


def register(app: FastAPI, plugin_id: str = "minishop") -> None:
    init_minishop_db()
    sync_minishop_translations()
    templates = build_templates("templates")

    # --- PUBLIC FRONTEND ROUTES ---

    @app.get("/shop", response_class=HTMLResponse)
    async def shop_index(request: Request, category: str = Query(None)):
        if not is_plugin_enabled("minishop"):
            return RedirectResponse(url="/?error=plugin_disabled")
        
        categories = list_shop_categories()
        products = list_shop_products(category_slug=category, active_only=True)
        currency = get_plugin_setting("minishop", "currency", "RON")
        
        locale = resolve_locale(request)
        t_shop = lambda key, def_val="": get_plugin_translation("minishop", locale, key, def_val)

        class ProductObject:
            def __init__(self, s: str):
                self.slug = s

        for p in products:
            pslug = p.get("slug") or ""
            if pslug:
                p["article_footer_html"] = render_post_article_footers(ProductObject(pslug), request)
            s_desc = (p.get("short_description") or "").strip()
            if not s_desc:
                import re
                d_html = p.get("description_html") or ""
                clean_txt = re.sub(r'<[^>]+>', '', d_html).strip()
                s_desc = (clean_txt[:160] + "...") if len(clean_txt) > 160 else clean_txt
            p["short_description_display"] = s_desc or "Descoperă detaliile acestui produs exclusiv din magazinul nostru."

        ctx = {
            "title": f"{t_shop('title', 'Magazin Online')} — {t_shop('subtitle', 'Camionagiul Club')}",
            "categories": categories,
            "products": products,
            "current_category": category,
            "currency": currency,
            "t_shop": t_shop,
            "locale": locale,
        }
        return render_template(templates, request=request, name="shop/index.html", context=ctx)

    @app.get("/shop/product/{slug}", response_class=HTMLResponse)
    async def shop_product_detail(request: Request, slug: str):
        if not is_plugin_enabled("minishop"):
            return RedirectResponse(url="/?error=plugin_disabled")
        
        product = get_shop_product(slug)
        if not product or not product.get("is_active"):
            raise HTTPException(status_code=404, detail="Produsul nu a fost găsit.")
        
        reviews = list_product_reviews(product["id"], approved_only=True)
        rating_summary = get_product_rating_summary(product["id"])
        currency = get_plugin_setting("minishop", "currency", "RON")
        stripe_pub_key = get_plugin_setting("minishop", "stripe_publishable_key", "")
        
        feat_img = product.get("featured_image") or ""
        if feat_img and not feat_img.startswith("http"):
            base_url = public_site_origin(request)
            feat_img = base_url.rstrip("/") + ("" if feat_img.startswith("/") else "/") + feat_img

        canon_url = public_site_origin(request).rstrip("/") + f"/shop/product/{slug}"

        raw_desc = (product.get("short_description") or "").strip()
        if not raw_desc:
            import re
            desc_html = product.get("description_html") or ""
            raw_desc = re.sub(r'<[^>]+>', '', desc_html).strip()[:300]
        if not raw_desc:
            raw_desc = product.get("title") or ""

        prod_title = product.get("title") or ""

        # Object wrapper to integrate with template_hooks (Share, Comments, Newsletter)
        class ProductObject:
            def __init__(self, d: dict):
                for k, v in d.items():
                    setattr(self, k, v)

        prod_obj = ProductObject(product)
        post_article_footer_html = render_post_article_footers(prod_obj, request)
        post_header_meta_html = render_post_header_metas(prod_obj, request)

        locale = resolve_locale(request)
        t_shop = lambda key, def_val="": get_plugin_translation("minishop", locale, key, def_val)

        ctx = {
            "title": f"{prod_title} — {t_shop('title', 'Magazin')}",
            "seo_title": prod_title,
            "seo_description": raw_desc,
            "meta_description": raw_desc,
            "seo_image": feat_img,
            "seo_canonical": canon_url,
            "og_image_width": 1200,
            "og_image_height": 630,
            "seo_type": "product",
            "product": product,
            "reviews": reviews,
            "rating_summary": rating_summary,
            "currency": currency,
            "stripe_pub_key": stripe_pub_key,
            "post_article_footer_html": post_article_footer_html,
            "post_header_meta_html": post_header_meta_html,
            "t_shop": t_shop,
            "locale": locale,
        }
        return render_template(templates, request=request, name="shop/product.html", context=ctx)

    @app.post("/shop/product/{slug}/review")
    async def shop_submit_review(
        request: Request,
        slug: str,
        rating: int = Form(...),
        comment: str = Form(...),
        user_name: str = Form(None)
    ):
        if not is_plugin_enabled("minishop"):
            return JSONResponse({"ok": False, "err": "Modul dezactivat"}, status_code=400)
        
        product = get_shop_product(slug)
        if not product:
            return JSONResponse({"ok": False, "err": "Produs negăsit"}, status_code=404)
        
        user = get_current_user_from_request(request)
        u_id = _get_user_id(user)
        u_name = _get_user_name(user, user_name or "Anonim")
        u_avatar = user.get("avatar") if user else None
        
        if rating < 1 or rating > 5:
            return JSONResponse({"ok": False, "err": "Rating nevalid (1-5)"}, status_code=400)
        if not comment or len(comment.strip()) < 3:
            return JSONResponse({"ok": False, "err": "Comentariul este prea scurt"}, status_code=400)
        
        add_shop_review(product["id"], u_id, u_name, u_avatar, rating, comment.strip())
        publish("shop.review_added", product_title=product["title"], rating=rating, user_name=u_name)
        return JSONResponse({"ok": True, "msg": "Recenzia ta a fost înregistrată cu succes!"})

    @app.post("/shop/checkout")
    async def shop_checkout(
        request: Request,
        product_id: int = Form(...),
        quantity: int = Form(1),
        customer_name: str = Form(...),
        customer_email: str = Form(...),
        customer_phone: str = Form(None),
        shipping_address: str = Form(None),
        payment_method: str = Form("ramburs")
    ):
        if not is_plugin_enabled("minishop"):
            return JSONResponse({"ok": False, "err": "Modul dezactivat"}, status_code=400)
        
        product = get_shop_product(product_id)
        if not product or not product.get("is_active"):
            return JSONResponse({"ok": False, "err": "Produs indisponibil"}, status_code=404)
        
        user = get_current_user_from_request(request)
        u_id = _get_user_id(user)
        
        total = float(product["price"]) * int(quantity)
        currency = get_plugin_setting("minishop", "currency", "RON")
        
        # Generare Comandă
        order_data = {
            "user_id": u_id,
            "customer_name": customer_name.strip(),
            "customer_email": customer_email.strip(),
            "customer_phone": customer_phone.strip() if customer_phone else None,
            "shipping_address": shipping_address.strip() if shipping_address else None,
            "total_amount": total,
            "currency": currency,
            "payment_method": payment_method,
            "payment_status": "paid" if product["product_type"] == "digital" and payment_method == "stripe" else "pending",
            "fulfillment_status": "completed" if product["product_type"] == "digital" else "processing",
        }
        items = [{
            "product_id": product["id"],
            "product_title": product["title"],
            "quantity": quantity,
            "unit_price": product["price"],
        }]
        
        order = create_shop_order(order_data, items)
        publish(
            "shop.order_created",
            order_number=order["order_number"],
            customer_name=customer_name.strip(),
            customer_email=customer_email.strip(),
            total_amount=total,
            currency=currency,
            payment_method=payment_method,
        )
        
        # Notificare Telegram dacă e bifat în setări
        if get_plugin_setting("minishop", "notify_telegram", "true").lower() == "true":
            try:
                from app.plugins.telegram_notify.plugin import send_admin_telegram_notice
                msg = f"🛒 **Comandă nouă #{order['order_number']}**\n👤 Client: {customer_name}\n📧 Email: {customer_email}\n📦 Produs: {product['title']} (x{quantity})\n💰 Total: {total} {currency}\n💳 Plată: {payment_method.upper()}"
                send_admin_telegram_notice(msg)
            except Exception as e:
                logger.warning(f"Telegram order notify failed: {e}")
        
        # Daca plata e cu Stripe
        if payment_method == "stripe":
            stripe_secret = get_plugin_setting("minishop", "stripe_secret_key", "")
            if stripe_secret:
                try:
                    import stripe
                    stripe.api_key = stripe_secret
                    order_token = order.get("download_token") or order.get("order_number")
                    session = stripe.checkout.Session.create(
                                                line_items=[{
                            "price_data": {
                                "currency": currency.lower(),
                                "product_data": {"name": product["title"]},
                                "unit_amount": int(float(product["price"]) * 100),
                            },
                            "quantity": quantity,
                        }],
                        mode="payment",
                        customer_email=customer_email,
                        client_reference_id=order_token,
                        metadata={"order_token": order_token, "order_number": order["order_number"]},
                        success_url=str(request.base_url).rstrip("/") + f"/shop/checkout/success?order={order['order_number']}&token={order_token}&st_paid=1",
                        cancel_url=str(request.base_url).rstrip("/") + f"/shop/product/{product['slug']}?cancelled=1",
                    )
                    update_order_status(order["id"], payment_status="pending")
                    return JSONResponse({"ok": True, "redirect_url": session.url})
                except Exception as ex:
                    logger.error(f"Stripe Session creation error: {ex}")
                    err_msg = str(ex)
                    if "at least Lei2.00" in err_msg or "amount" in err_msg:
                        err_msg = "Prețul minim pentru plata online cu cardul Stripe este 2.00 RON."
                    return JSONResponse({"ok": False, "err": f"Eroare Stripe: {err_msg}"}, status_code=400)
        
        # Plată Ramburs sau Stripe fallback
        return JSONResponse({"ok": True, "redirect_url": f"/shop/checkout/success?order={order['order_number']}"})

    @app.get("/shop/checkout/success", response_class=HTMLResponse)
    async def shop_checkout_success(request: Request, order: str = Query(...), token: str = Query(None), st_paid: str = Query(None)):
        if not is_plugin_enabled("minishop"):
            return RedirectResponse(url="/")

        order_obj = get_shop_order(token or order)
        if not order_obj:
            raise HTTPException(status_code=404, detail="Comanda nu a fost găsită.")

        if (st_paid == "1" or order_obj.get("payment_method") == "stripe") and order_obj.get("payment_status") != "paid":
            update_order_status(order_obj["id"], payment_status="paid", fulfillment_status="completed")
            order_obj["payment_status"] = "paid"
            order_obj["fulfillment_status"] = "completed"
        
        currency = get_plugin_setting("minishop", "currency", "RON")
        
        # Verificare daca comanda conține vreun produs digital
        has_digital = False
        digital_file_name = None
        for item in order_obj.get("items", []):
            prod = get_shop_product(item["product_id"]) if item.get("product_id") else None
            if prod and prod.get("product_type") == "digital":
                has_digital = True
                digital_file_name = prod.get("title")
                break
        
        ctx = {
            "title": f"Confirmare Comandă #{order_obj['order_number']}",
            "order": order_obj,
            "currency": currency,
            "has_digital": has_digital,
            "digital_file_name": digital_file_name,
        }
        return render_template(templates, request=request, name="shop/success.html", context=ctx)

    @app.get("/shop/download/{token}")
    async def shop_download_file(request: Request, token: str):
        if not is_plugin_enabled("minishop"):
            return RedirectResponse(url="/")

        order_obj = get_shop_order(token)
        if not order_obj:
            raise HTTPException(status_code=404, detail="Comanda sau token-ul de descărcare nu a fost găsit.")

        digital_file_url = None
        for item in order_obj.get("items", []):
            prod = get_shop_product(item["product_id"]) if item.get("product_id") else None
            if prod and prod.get("product_type") == "digital" and prod.get("digital_file_url"):
                digital_file_url = prod["digital_file_url"]
                break

        if not digital_file_url:
            raise HTTPException(status_code=404, detail="Această comandă nu conține un fișier digital descărcabil.")

        if digital_file_url.startswith("http://") or digital_file_url.startswith("https://"):
            return RedirectResponse(url=digital_file_url)

        rel_p = digital_file_url.lstrip("/")
        local_file = PROJECT_ROOT / rel_p

        if not local_file.is_file():
            logger.error(f"Digital file missing on disk: {local_file}")
            raise HTTPException(status_code=404, detail="Fișierul digital nu a fost găsit pe disc. Contactează administratorul.")

        return FileResponse(
            path=local_file,
            filename=local_file.name,
            media_type="application/octet-stream"
        )
    
    @app.post("/shop/stripe/webhook", include_in_schema=False)
    async def shop_stripe_webhook(request: Request):
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature") or request.headers.get("Stripe-Signature")
        webhook_secret = get_plugin_setting("minishop", "stripe_webhook_secret", "")
        stripe_secret = get_plugin_setting("minishop", "stripe_secret_key", "")

        if not webhook_secret or not stripe_secret:
            logger.warning("Stripe webhook received but stripe_webhook_secret or stripe_secret_key not configured")
            return JSONResponse({"status": "ignored_not_configured"})

        try:
            import stripe
            stripe.api_key = stripe_secret
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError as e:
            logger.error(f"Invalid payload for Stripe webhook: {e}")
            return JSONResponse({"error": "Invalid payload"}, status_code=400)
        except Exception as e:
            logger.error(f"Invalid signature / Stripe webhook error: {e}")
            return JSONResponse({"error": "Invalid signature"}, status_code=400)

        event_type = getattr(event, "type", None) or (event.get("type") if hasattr(event, "get") else "")
        if event_type in ("checkout.session.completed", "payment_intent.succeeded"):
            data_obj = getattr(event, "data", None)
            session_obj = getattr(data_obj, "object", None) if data_obj else None
            metadata = getattr(session_obj, "metadata", {}) or {}
            order_token = (metadata.get("order_token") if hasattr(metadata, "get") else None) or getattr(session_obj, "client_reference_id", None)

            if order_token:
                order = get_shop_order(order_token)
                if order:
                    update_order_status(order["id"], payment_status="paid", fulfillment_status="completed")
                    logger.info(f"Stripe Webhook successfully marked order #{order['order_number']} as PAID!")

                    notify_tg = get_plugin_setting("minishop", "notify_telegram", "false")
                    if notify_tg in ("true", "1", "yes"):
                        try:
                            from app.routers.admin import send_telegram_alert
                            msg = f"💳 *PLATĂ STRIPE CONFIRMATĂ VIA WEBHOOK!*\n\nComandă: #{order['order_number']}\nClient: {order['customer_name']}\nSuma: {order['total_amount']} {order['currency']}\nStatus: Plătit ✅"
                            send_telegram_alert(msg)
                        except Exception as ex:
                            logger.warning(f"Error sending TG alert for paid order: {ex}")

        return JSONResponse({"status": "success"})

    async def shop_download_file(request: Request, token: str):
        if not is_plugin_enabled("minishop"):
            raise HTTPException(status_code=403, detail="Modul dezactivat")
        
        order_obj = get_shop_order(token)
        if not order_obj:
            raise HTTPException(status_code=404, detail="Link nevalid sau expirat.")
        
        # Gasire produs digital din comanda
        digital_url = None
        prod_title = "file"
        for item in order_obj.get("items", []):
            prod = get_shop_product(item["product_id"]) if item.get("product_id") else None
            if prod and prod.get("product_type") == "digital" and prod.get("digital_file_url"):
                digital_url = prod["digital_file_url"]
                prod_title = prod["title"]
                break
        
        if not digital_url:
            raise HTTPException(status_code=404, detail="Nu există niciun fișier digital atașat acestei comenzi.")
        
        # Daca e cale locala
        clean_path = digital_url.strip()
        if clean_path.startswith("/"):
            file_path = PROJECT_ROOT / clean_path.lstrip("/")
        else:
            file_path = PROJECT_ROOT / clean_path
            
        if file_path.exists() and file_path.is_file():
            return FileResponse(path=str(file_path), filename=file_path.name)
        elif digital_url.startswith("http://") or digital_url.startswith("https://"):
            return RedirectResponse(url=digital_url)
        else:
            raise HTTPException(status_code=404, detail="Fișierul nu a fost găsit pe server.")

    # --- ADMIN ROUTES (`/admin/minishop`) ---

    @app.get("/admin/minishop", response_class=HTMLResponse)
    async def admin_minishop_dashboard(request: Request):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return RedirectResponse(url="/admin/login")
        
        categories = list_shop_categories()
        products = list_shop_products(active_only=False)
        orders = list_shop_orders()
        currency = get_plugin_setting("minishop", "currency", "RON")
        stripe_pub = get_plugin_setting("minishop", "stripe_publishable_key", "")
        stripe_sec = get_plugin_setting("minishop", "stripe_secret_key", "")
        notify_tg = get_plugin_setting("minishop", "notify_telegram", "true")
        
        ctx = {
            "title": "Administrare Magazin — Minishop",
            "categories": categories,
            "products": products,
            "orders": orders,
            "currency": currency,
            "stripe_pub": stripe_pub,
            "stripe_sec": stripe_sec,
            "stripe_whsec": get_plugin_setting("minishop", "stripe_webhook_secret", ""),
            "notify_tg": notify_tg,
        }
        return render_template(templates, request=request, name="admin/minishop.html", context=ctx)

    @app.post("/admin/minishop/product/save")
    async def admin_save_product(request: Request):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        form = await request.form()
        
        prod_id = form.get("id")
        prod_id = int(prod_id) if prod_id and str(prod_id).isdigit() else None
        
        category_id = form.get("category_id")
        category_id = int(category_id) if category_id and str(category_id).isdigit() else None
        
        title = (form.get("title") or "").strip()
        slug = (form.get("slug") or "").strip()
        if not slug and title:
            from re import sub
            slug = sub(r'[-\s]+', '-', sub(r'[^\w\s-]', '', title.lower())).strip()
            
        short_description = (form.get("short_description") or "").strip()
        description_html = (form.get("description_html") or "").strip()
        
        try:
            price = float(form.get("price", 0.0))
        except ValueError:
            price = 0.0
            
        currency = (form.get("currency") or "RON").strip()
        product_type = (form.get("product_type") or "physical").strip()
        digital_file_url = (form.get("digital_file_url") or "").strip() or None
        
        try:
            stock_quantity = int(form.get("stock_quantity", 100))
        except ValueError:
            stock_quantity = 100
            
        video_url = (form.get("video_url") or "").strip() or None
        is_active_val = form.get("is_active")
        is_active = True if is_active_val is None else (is_active_val in ("1", "true", "on"))
        
        # Load existing product if editing
        existing_prod = get_shop_product(prod_id) if prod_id else None
        existing_featured = existing_prod.get("featured_image") if existing_prod else None
        existing_gallery = existing_prod.get("gallery_images", []) if existing_prod else []
        
        # Dedicated Directory for Product Uploads: static/uploads/shop/{slug}/
        import shutil, time
        safe_slug = slug or f"prod-{int(time.time())}"
        upload_dir = PROJECT_ROOT / "static" / "uploads" / "shop" / safe_slug
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        newly_uploaded = []
        upload_files = form.getlist("upload_images")
        ts = int(time.time())
        for idx, uf in enumerate(upload_files):
            if hasattr(uf, "filename") and uf.filename:
                clean_filename = f"{ts}_{idx}_{uf.filename.replace(' ', '_')}"
                dest_path = upload_dir / clean_filename
                with dest_path.open("wb") as buffer:
                    shutil.copyfileobj(uf.file, buffer)
                rel_url = f"/static/uploads/shop/{safe_slug}/{clean_filename}"
                newly_uploaded.append(rel_url)
                
        # Imagini trimise din formular ca "existing_images" (cele nebifate ca sters)
        form_existing = form.getlist("existing_images")
        if not form_existing and existing_prod:
            # Daca nu au fost trimise prin JS, le pastram pe cele vechi din DB
            if existing_featured:
                form_existing.append(existing_featured)
            form_existing.extend(existing_gallery)
            
        manual_gallery = form.get("gallery_images") or ""
        if manual_gallery:
            for line in manual_gallery.splitlines():
                clean_url = line.strip()
                if clean_url and clean_url not in form_existing:
                    form_existing.append(clean_url)
                    
        # Combina toate imaginile fără duplicate
        all_product_images = list(dict.fromkeys(form_existing + newly_uploaded))
        
        chosen_default = (form.get("default_image") or "").strip()
        default_new_idx = form.get("default_new_index")
        if default_new_idx is not None and str(default_new_idx).isdigit():
            idx = int(default_new_idx)
            if 0 <= idx < len(newly_uploaded):
                chosen_default = newly_uploaded[idx]
                
        featured_image_url = (form.get("featured_image") or "").strip()
        
        if chosen_default and chosen_default in all_product_images:
            final_featured = chosen_default
        elif featured_image_url and featured_image_url in all_product_images:
            final_featured = featured_image_url
        elif featured_image_url:
            final_featured = featured_image_url
            all_product_images.insert(0, final_featured)
        elif all_product_images:
            final_featured = all_product_images[0]
        else:
            final_featured = None
            
        final_gallery = [img for img in all_product_images if img != final_featured]
        
        p_data = {
            "id": prod_id,
            "category_id": category_id,
            "title": title,
            "slug": slug,
            "short_description": short_description,
            "description_html": description_html,
            "price": price,
            "currency": currency,
            "product_type": product_type,
            "digital_file_url": digital_file_url,
            "stock_quantity": stock_quantity,
            "is_active": is_active,
            "featured_image": final_featured,
            "gallery_images": final_gallery,
            "video_url": video_url,
        }
        pid = save_shop_product(p_data)
        return RedirectResponse(url="/admin/minishop?saved=1", status_code=303)

    @app.post("/admin/minishop/product/image/delete")
    async def admin_delete_product_image(request: Request, product_id: int = Form(...), image_url: str = Form(...)):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        from app.plugins.minishop.db import remove_product_image
        updated_prod = remove_product_image(product_id, image_url)
        return JSONResponse({"ok": True, "product": updated_prod})

    @app.post("/admin/minishop/product/image/set-cover")
    async def admin_set_product_cover(request: Request, product_id: int = Form(...), image_url: str = Form(...)):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        from app.plugins.minishop.db import set_product_cover_image
        updated_prod = set_product_cover_image(product_id, image_url)
        return JSONResponse({"ok": True, "product": updated_prod})

    @app.post("/admin/minishop/product/delete")
    async def admin_delete_product(request: Request, id: int = Form(...)):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        delete_shop_product(id)
        return RedirectResponse(url="/admin/minishop?deleted=1", status_code=303)

    @app.post("/admin/minishop/category/save")
    async def admin_save_category(
        request: Request,
        id: int = Form(None),
        name: str = Form(...),
        slug: str = Form(...),
        description: str = Form(""),
        icon: str = Form("📦")
    ):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        save_shop_category(name.strip(), slug.strip(), description.strip(), icon.strip(), cat_id=id)
        return RedirectResponse(url="/admin/minishop?cat_saved=1", status_code=303)

    @app.post("/admin/minishop/category/delete")
    async def admin_delete_category(request: Request, id: int = Form(...)):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        delete_shop_category(id)
        return RedirectResponse(url="/admin/minishop?cat_deleted=1", status_code=303)

    @app.post("/admin/minishop/order/status")
    async def admin_update_order_status(
        request: Request,
        order_id: int = Form(...),
        payment_status: str = Form(None),
        fulfillment_status: str = Form(None)
    ):
        user = get_current_user_from_request(request)
        if not user or not user_can_manage_shop(user):
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        update_order_status(order_id, payment_status, fulfillment_status)
        return RedirectResponse(url="/admin/minishop?order_updated=1", status_code=303)

    @app.post("/admin/minishop/settings/save")
    async def admin_save_settings(
        request: Request,
        currency: str = Form("RON"),
        stripe_publishable_key: str = Form(""),
        stripe_secret_key: str = Form(""),
        notify_telegram: bool = Form(False)
    ):
        user = get_current_user_from_request(request)
        if not user or _get_user_role(user) not in ["admin"]:
            return JSONResponse({"ok": False, "err": "Acces interzis"}, status_code=403)
        
        set_plugin_setting("minishop", "currency", currency.strip())
        set_plugin_setting("minishop", "stripe_publishable_key", stripe_publishable_key.strip())
        set_plugin_setting("minishop", "stripe_secret_key", stripe_secret_key.strip())
        set_plugin_setting("minishop", "notify_telegram", "true" if notify_telegram else "false")
        
        return RedirectResponse(url="/admin/minishop?settings_saved=1", status_code=303)

    def render_minishop_admin_nav(request: Request) -> str:
        return '<li class="nav-item"><a class="nav-link fw-semibold px-3 rounded-2" href="/admin/minishop">🛒 Minishop</a></li>'

    def render_minishop_admin_top_bar(request: Request) -> str:
        return '<a class="btn btn-sm btn-outline-primary fw-semibold me-2" href="/admin/minishop">🛒 Administrare Minishop</a>'

    def render_minishop_navbar_link(request: Request) -> str:
        loc = resolve_locale(request)
        label = get_plugin_translation("minishop", loc, "nav_link", "🛒 Shop")
        return f'<li class="nav-item"><a class="nav-link py-1 px-3 rounded-pill fw-semibold" href="/shop">{label}</a></li>'

    from app.core.template_hooks import register_admin_nav, register_admin_top_bar, register_navbar_link
    register_admin_nav(render_minishop_admin_nav)
    register_admin_top_bar(render_minishop_admin_top_bar)
    register_navbar_link(render_minishop_navbar_link)